import axios from 'axios'

import {
  localDb,
  pendingSyncCount,
  saveCachedDailyPlan,
  saveCachedTask,
} from '@/db/local'
import { http } from '@/services/http'
import type { DailyPlan, DailyPlanItem } from '@/types/daily-plan'
import type { SyncOperation } from '@/types/offline'
import type { Task } from '@/types/task'

export function isNetworkError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false
  if (!error.response) return true
  // Bare 500s are excluded on purpose: the server answered, so the request
  // reached application logic. Treating app-level rejections as outages made
  // every retry flap the "saved locally" banner while quarantining nothing.
  return [408, 425, 429, 502, 503, 504].includes(error.response.status)
}

function isNonExecutableTaskConflict(error: unknown): boolean {
  if (!axios.isAxiosError<{ detail?: string }>(error)) return false
  return (
    error.response?.status === 409
    && error.response.data?.detail === 'Only executable tasks can be timed or added to a daily plan'
  )
}

async function replaceCachedDailyItem(item: DailyPlanItem): Promise<void> {
  const plans = await localDb.cachedDailyPlans
    .where('owner_id')
    .equals(item.owner_id)
    .toArray()
  const plan = plans.find((candidate) =>
    candidate.items.some((existing) => existing.id === item.id),
  )
  if (!plan) return
  const items = plan.items.map((existing) => (existing.id === item.id ? item : existing))
  await saveCachedDailyPlan(recalculatePlan({ ...plan, items }))
}

function recalculatePlan(plan: DailyPlan): DailyPlan {
  const totalItems = plan.items.length
  const completedItems = plan.items.filter((item) => item.status === 'DONE').length
  return {
    ...plan,
    total_items: totalItems,
    completed_items: completedItems,
    completion_rate: totalItems ? completedItems / totalItems : 0,
    actual_seconds: plan.items.reduce((sum, item) => sum + item.actual_seconds, 0),
  }
}

async function remapDailyPlan(
  ownerId: string,
  localPlanId: string,
  serverPlan: DailyPlan,
): Promise<void> {
  if (localPlanId === serverPlan.id) {
    await saveCachedDailyPlan(serverPlan)
    return
  }
  const localPlan = await localDb.cachedDailyPlans.get(localPlanId)
  const remappedItems = (localPlan?.items ?? []).map((item) => ({
    ...item,
    daily_plan_id: serverPlan.id,
  }))
  const remappedPlan = recalculatePlan({
    ...serverPlan,
    items: remappedItems.length > 0 ? remappedItems : serverPlan.items,
  })
  await localDb.cachedDailyPlans.delete(localPlanId)
  await saveCachedDailyPlan(remappedPlan)
  const operations = await localDb.syncOperations.where('owner_id').equals(ownerId).toArray()
  for (const operation of operations) {
    if (
      operation.entity_type === 'daily_plan_item' &&
      operation.payload.daily_plan_id === localPlanId
    ) {
      await localDb.syncOperations.update(operation.id, {
        payload: {
          ...operation.payload,
          daily_plan_id: serverPlan.id,
        },
      })
    }
  }
}

async function replayOperation(operation: SyncOperation): Promise<void> {
  if (operation.entity_type === 'task') {
    if (operation.action === 'create') {
      const { data } = await http.post<Task>('/tasks', operation.payload)
      await saveCachedTask(data)
    } else if (operation.action === 'update') {
      const { data } = await http.patch<Task>(
        `/tasks/${operation.entity_id}`,
        operation.payload,
      )
      await saveCachedTask(data)
    } else {
      await http.delete(`/tasks/${operation.entity_id}`)
      await localDb.cachedTasks.delete(operation.entity_id)
    }
    return
  }

  if (operation.entity_type === 'daily_plan') {
    if (operation.action !== 'create') return
    const { data } = await http.post<DailyPlan>('/daily-plans', operation.payload)
    await remapDailyPlan(operation.owner_id, operation.entity_id, data)
    return
  }

  const dailyPlanId = String(operation.payload.daily_plan_id)
  if (operation.action === 'create') {
    const body = { ...operation.payload }
    delete body.daily_plan_id
    let data: DailyPlanItem
    try {
      const response = await http.post<DailyPlanItem>(
        `/daily-plans/${dailyPlanId}/items`,
        body,
      )
      data = response.data
    } catch (error) {
      // Structured task trees turned legacy top-level tasks into containers.
      // Keep their daily snapshots usable by replaying them as ad-hoc items.
      if (!isNonExecutableTaskConflict(error) || body.task_id == null) throw error
      const response = await http.post<DailyPlanItem>(
        `/daily-plans/${dailyPlanId}/items`,
        { ...body, task_id: null },
      )
      data = response.data
    }
    await replaceCachedDailyItem(data)
  } else if (operation.action === 'update') {
    const body = { ...operation.payload }
    delete body.daily_plan_id
    const { data } = await http.patch<DailyPlanItem>(
      `/daily-plan-items/${operation.entity_id}`,
      body,
    )
    await replaceCachedDailyItem(data)
  } else {
    await http.delete(`/daily-plan-items/${operation.entity_id}`)
  }
}

export async function getPendingOperations(
  ownerId: string,
  entityType?: SyncOperation['entity_type'],
): Promise<SyncOperation[]> {
  const operations = await localDb.syncOperations
    .where('owner_id')
    .equals(ownerId)
    .toArray()
  return entityType
    ? operations.filter((operation) => operation.entity_type === entityType)
    : operations
}

export async function getFailedSyncCount(ownerId: string): Promise<number> {
  const operations = await getPendingOperations(ownerId)
  return operations.filter((operation) => operation.retry_count > 0).length
}

const activeSyncs = new Map<string, Promise<number>>()

async function runPendingSync(ownerId: string): Promise<number> {
  if (!navigator.onLine) return pendingSyncCount(ownerId)
  const operations = await localDb.syncOperations.where('owner_id').equals(ownerId).toArray()
  operations.sort(
    (left, right) =>
      left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id),
  )
  for (const operation of operations) {
    try {
      // Plan creation can remap the payloads of item operations that were
      // already included in this batch. Reload each operation so the next
      // request always uses the newest server plan id.
      const current = await localDb.syncOperations.get(operation.id)
      if (!current) continue
      await replayOperation(current)
      await localDb.syncOperations.delete(current.id)
    } catch (error) {
      // A gateway/server outage means the request never reached stable
      // application logic. Keep the operation untouched and let callers mark
      // the app offline so focus/visibility retries can replay it later.
      if (isNetworkError(error)) throw error
      await localDb.syncOperations.update(operation.id, {
        retry_count: operation.retry_count + 1,
        last_error: axios.isAxiosError<{ detail?: string }>(error)
          ? (error.response?.data?.detail ?? '服务器拒绝了该离线操作')
          : '服务器拒绝了该离线操作',
      })
      // Quarantine a rejected operation and keep syncing independent work
      // behind it. One stale legacy record must not block new timer sessions.
      continue
    }
  }
  return pendingSyncCount(ownerId)
}

export async function syncPendingChanges(ownerId: string): Promise<number> {
  const active = activeSyncs.get(ownerId)
  if (active) return active
  const sync = runPendingSync(ownerId)
  activeSyncs.set(ownerId, sync)
  try {
    return await sync
  } finally {
    if (activeSyncs.get(ownerId) === sync) activeSyncs.delete(ownerId)
  }
}
