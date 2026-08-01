import axios from 'axios'

import { localDb, pendingSyncCount } from '@/db/local'
import { http } from '@/services/http'
import type { DailyPlan, DailyPlanItem } from '@/types/daily-plan'
import type { SyncOperation } from '@/types/offline'
import type { Task } from '@/types/task'

export function isNetworkError(error: unknown): boolean {
  return axios.isAxiosError(error) && !error.response
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
  await localDb.cachedDailyPlans.put(recalculatePlan({ ...plan, items }))
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
    await localDb.cachedDailyPlans.put(serverPlan)
    return
  }
  await localDb.cachedDailyPlans.delete(localPlanId)
  await localDb.cachedDailyPlans.put(serverPlan)
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
      await localDb.cachedTasks.put(data)
    } else if (operation.action === 'update') {
      const { data } = await http.patch<Task>(
        `/tasks/${operation.entity_id}`,
        operation.payload,
      )
      await localDb.cachedTasks.put(data)
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
    const { data } = await http.post<DailyPlanItem>(
      `/daily-plans/${dailyPlanId}/items`,
      body,
    )
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
      await replayOperation(operation)
      await localDb.syncOperations.delete(operation.id)
    } catch (error) {
      if (isNetworkError(error)) break
      await localDb.syncOperations.update(operation.id, {
        retry_count: operation.retry_count + 1,
        last_error: '服务器拒绝了该离线操作',
      })
      throw error
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
