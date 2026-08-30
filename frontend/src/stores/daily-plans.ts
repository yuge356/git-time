import axios from 'axios'
import { defineStore } from 'pinia'

import {
  enqueueSyncOperation,
  localDb,
  pendingSyncCount,
  readCachedDailyPlan,
  saveCachedDailyPlan,
} from '@/db/local'
import { dailyPlanService } from '@/services/daily-plans'
import {
  getFailedSyncCount,
  getPendingOperations,
  isNetworkError,
  syncPendingChanges,
} from '@/services/offline-sync'
import type {
  CheckIn,
  DailyPlan,
  DailyPlanItem,
  DailyPlanItemCreate,
  DailyPlanItemUpdate,
} from '@/types/daily-plan'
import type { Task } from '@/types/task'
import { useTaskStore } from '@/stores/tasks'
import { projectPrefixedTaskTitle } from '@/utils/task-title'

interface DailyPlanState {
  ownerId: string | null
  plan: DailyPlan | null
  checkIn: CheckIn | null
  selectedDate: string
  loading: boolean
  saving: boolean
  online: boolean
  pendingCount: number
  failedCount: number
  activeItemId: string | null
  listenerBound: boolean
  rolloverDate: string
  rolloverTimerId: number | null
}

function localDateString(date = new Date()): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
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
    updated_at: new Date().toISOString(),
  }
}

function parseLocalDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year!, month! - 1, day!))
}

function taskRepeatsOnDate(task: Task, targetDate: string): boolean {
  if (
    task.node_type !== 'TASK' ||
    task.status === 'DONE' ||
    task.repeat_rule === 'NONE'
  ) {
    return false
  }
  const startDate = localDateString(new Date(task.created_at))
  if (targetDate < startDate) return false
  if (task.repeat_end_date && targetDate > task.repeat_end_date) return false

  const target = parseLocalDate(targetDate)
  const start = parseLocalDate(startDate)
  if (task.repeat_rule === 'DAILY') return true
  if (task.repeat_rule === 'WEEKDAYS') {
    const weekday = target.getUTCDay()
    return weekday >= 1 && weekday <= 5
  }
  if (task.repeat_rule === 'WEEKLY') {
    return Math.floor((target.getTime() - start.getTime()) / 86_400_000) % 7 === 0
  }
  if (task.repeat_rule === 'MONTHLY') {
    const lastDay = new Date(
      Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0),
    ).getUTCDate()
    return target.getUTCDate() === Math.min(start.getUTCDate(), lastDay)
  }
  return false
}

export const useDailyPlanStore = defineStore('daily-plans', {
  state: (): DailyPlanState => ({
    ownerId: null,
    plan: null,
    checkIn: null,
    selectedDate: localDateString(),
    loading: false,
    saving: false,
    online: navigator.onLine,
    pendingCount: 0,
    failedCount: 0,
    activeItemId: null,
    listenerBound: false,
    rolloverDate: localDateString(),
    rolloverTimerId: null,
  }),

  actions: {
    async initialize(
      ownerId: string,
      planDate?: string,
      activeItemId: string | null = null,
    ): Promise<void> {
      this.ownerId = ownerId
      this.activeItemId = activeItemId
      if (!this.listenerBound) {
        const retryPending = (): void => {
          if (navigator.onLine && this.ownerId) {
            void this.refreshForCurrentDate().then((dateChanged) => {
              if (!dateChanged) return this.load(this.selectedDate, { silent: true })
            }).catch(() => {
              // The next focus, network restore, or scheduled retry will try again.
            })
          }
        }
        window.addEventListener('online', () => {
          this.online = true
          retryPending()
        })
        window.addEventListener('offline', () => {
          this.online = false
        })
        window.addEventListener('focus', retryPending)
        document.addEventListener('visibilitychange', () => {
          if (document.visibilityState === 'visible') retryPending()
        })
        this.rolloverDate = localDateString()
        this.rolloverTimerId = window.setInterval(() => {
          void this.refreshForCurrentDate().catch(() => {
            // Keeping the previous daily plan locally is safer than clearing it
            // when the network changes exactly at midnight.
          })
        }, 30_000)
        this.listenerBound = true
      }
      await this.load(planDate)
    },

    /**
     * Daily plans are date snapshots. Keep the refresh watcher in the store
     * rather than in TodayView so midnight works while the user is elsewhere.
     */
    async refreshForCurrentDate(): Promise<boolean> {
      const today = localDateString()
      if (today === this.rolloverDate) return false
      this.rolloverDate = today
      await this.load(today, { silent: true })
      return true
    },

    setActiveItem(activeItemId: string | null): void {
      this.activeItemId = activeItemId
    },

    async buildLocalCheckIn(): Promise<void> {
      if (!this.ownerId || !this.plan) return
      const plans = await localDb.cachedDailyPlans
        .where('owner_id')
        .equals(this.ownerId)
        .toArray()
      const completedDates = new Set(
        plans
          .filter((plan) => plan.completed_items > 0)
          .map((plan) => plan.plan_date),
      )
      let streak = 0
      const cursor = new Date(`${this.selectedDate}T00:00:00`)
      while (completedDates.has(localDateString(cursor))) {
        streak += 1
        cursor.setDate(cursor.getDate() - 1)
      }
      this.checkIn = {
        plan_date: this.selectedDate,
        learning_seconds: this.plan.actual_seconds,
        completed_items: this.plan.completed_items,
        total_items: this.plan.total_items,
        streak_days: streak,
      }
    },

    async createLocalPlan(): Promise<DailyPlan> {
      if (!this.ownerId) throw new Error('Daily plan store is not initialized')
      const now = new Date().toISOString()
      const plan: DailyPlan = {
        id: crypto.randomUUID(),
        owner_id: this.ownerId,
        plan_date: this.selectedDate,
        items: [],
        total_items: 0,
        completed_items: 0,
        completion_rate: 0,
        actual_seconds: 0,
        created_at: now,
        updated_at: now,
      }
      await saveCachedDailyPlan(plan)
      await enqueueSyncOperation(this.ownerId, 'daily_plan', plan.id, 'create', {
        id: plan.id,
        plan_date: plan.plan_date,
      })
      return plan
    },

    async load(
      planDate?: string,
      options: { silent?: boolean } = {},
    ): Promise<void> {
      if (!this.ownerId) throw new Error('Daily plan store is not initialized')
      const targetDate = planDate ?? this.selectedDate
      const isDateChange = this.plan?.plan_date !== targetDate
      if (!options.silent) this.loading = true
      this.selectedDate = targetDate
      if (isDateChange) {
        // A daily plan is a date-scoped snapshot. Never leave the previous
        // day's items visible while the new date is being loaded or created.
        // Recurring project tasks are added again by autoPopulate below with
        // a new daily-item id; ordinary and ad-hoc items stay on their day.
        this.plan = null
        this.checkIn = null
        this.activeItemId = null
      }
      this.online = navigator.onLine
      try {
        if (this.online) {
          try {
            this.pendingCount = await syncPendingChanges(this.ownerId)
            this.failedCount = await getFailedSyncCount(this.ownerId)
            // A plan whose create is still queued does not exist on the
            // server yet — fetching would 404 and spawn a duplicate plan.
            const pendingOps = await getPendingOperations(this.ownerId)
            const planCreatePending = pendingOps.some(
              (op) =>
                op.entity_type === 'daily_plan' &&
                op.action === 'create' &&
                op.payload.plan_date === targetDate,
            )
            if (planCreatePending) {
              this.plan =
                (await readCachedDailyPlan(this.ownerId, targetDate)) ??
                (await this.createLocalPlan())
              await this.autoPopulateLocalRecurringItems()
              await this.buildLocalCheckIn()
              return
            }
            let serverPlan: DailyPlan
            try {
              serverPlan = await dailyPlanService.readByDate(targetDate)
            } catch (error) {
              if (!axios.isAxiosError(error) || error.response?.status !== 404) throw error
              serverPlan = await dailyPlanService.create(targetDate)
            }
            serverPlan = await this.repairMissingServerItems(serverPlan)
            this.plan = await this.mergeServerPlan(serverPlan)
            try {
              const populated = await dailyPlanService.autoPopulate(this.plan.id)
              this.plan = await this.mergeServerPlan(populated)
            } catch (error) {
              if (!isNetworkError(error)) throw error
              this.online = false
            }
            this.checkIn = await dailyPlanService.checkIn(targetDate)
            return
          } catch {
            this.online = false
          }
        }

        this.plan = (await readCachedDailyPlan(this.ownerId, targetDate)) ?? null
        if (!this.plan) this.plan = await this.createLocalPlan()
        await this.autoPopulateLocalRecurringItems()
        this.pendingCount = await pendingSyncCount(this.ownerId)
        this.failedCount = await getFailedSyncCount(this.ownerId)
        await this.buildLocalCheckIn()
      } finally {
        if (!options.silent) this.loading = false
      }
    },

    async repairMissingServerItems(serverPlan: DailyPlan): Promise<DailyPlan> {
      if (!this.ownerId || !navigator.onLine) return serverPlan
      const cachedPlan = await readCachedDailyPlan(this.ownerId, serverPlan.plan_date)
      if (!cachedPlan) return serverPlan
      const pendingOps = await getPendingOperations(this.ownerId, 'daily_plan_item')
      const deletedIds = new Set(
        pendingOps.filter((op) => op.action === 'delete').map((op) => op.entity_id),
      )
      const serverIds = new Set(serverPlan.items.map((item) => item.id))
      const missingItems = cachedPlan.items.filter(
        (item) => !serverIds.has(item.id) && !deletedIds.has(item.id),
      )
      if (missingItems.length === 0) return serverPlan

      const repaired = [...serverPlan.items]
      for (const cachedItem of missingItems) {
        let savedItem: DailyPlanItem
        try {
          try {
            savedItem = await dailyPlanService.addItem(serverPlan.id, {
              id: cachedItem.id,
              task_id: cachedItem.task_id,
              title: cachedItem.title,
              estimated_seconds: cachedItem.estimated_seconds,
            })
          } catch (error) {
            // If the source project was deleted, the daily snapshot still
            // belongs to this day and is restored as an ad-hoc item. The same
            // applies to legacy roots that became project/module containers.
            if (
              !axios.isAxiosError(error) ||
              ![404, 409].includes(error.response?.status ?? 0) ||
              cachedItem.task_id === null
            ) {
              throw error
            }
            savedItem = await dailyPlanService.addItem(serverPlan.id, {
              id: cachedItem.id,
              task_id: null,
              title: cachedItem.title,
              estimated_seconds: cachedItem.estimated_seconds,
            })
          }
          if (
            savedItem.title !== cachedItem.title ||
            savedItem.status !== cachedItem.status ||
            savedItem.estimated_seconds !== cachedItem.estimated_seconds ||
            savedItem.sort_order !== cachedItem.sort_order
          ) {
            savedItem = await dailyPlanService.updateItem(savedItem.id, {
              title: cachedItem.title,
              status: cachedItem.status,
              estimated_seconds: cachedItem.estimated_seconds,
              sort_order: cachedItem.sort_order,
            })
          }
          repaired.push(savedItem)
          serverIds.add(savedItem.id)
        } catch (error) {
          if (!isNetworkError(error)) throw error
          this.online = false
          break
        }
      }
      return recalculatePlan({ ...serverPlan, items: repaired })
    },

    async autoPopulateLocalRecurringItems(): Promise<void> {
      if (!this.ownerId || !this.plan) return
      const taskNodes = await localDb.cachedTasks
        .where('owner_id')
        .equals(this.ownerId)
        .toArray()
      const existingTaskIds = new Set(
        this.plan.items.flatMap((item) => (item.task_id ? [item.task_id] : [])),
      )
      const dueTasks = taskNodes.filter(
        (task) =>
          !existingTaskIds.has(task.id) &&
          taskRepeatsOnDate(task, this.selectedDate),
      )
      if (dueTasks.length === 0) return

      const now = new Date().toISOString()
      const createdItems: DailyPlanItem[] = dueTasks.map((task, index) => ({
        id: crypto.randomUUID(),
        daily_plan_id: this.plan!.id,
        owner_id: this.ownerId!,
        task_id: task.id,
        title: projectPrefixedTaskTitle(task, taskNodes),
        status: 'TODO',
        estimated_seconds: task.estimated_seconds,
        actual_seconds: 0,
        sort_order: this.plan!.items.length + index,
        completed_at: null,
        created_at: now,
        updated_at: now,
      }))
      this.plan = recalculatePlan({
        ...this.plan,
        items: [...this.plan.items, ...createdItems],
      })
      await saveCachedDailyPlan(this.plan)
      for (const item of createdItems) {
        await enqueueSyncOperation(this.ownerId, 'daily_plan_item', item.id, 'create', {
          id: item.id,
          daily_plan_id: item.daily_plan_id,
          task_id: item.task_id,
          title: item.title,
          estimated_seconds: item.estimated_seconds,
        })
      }
    },

    /**
     * Treat cached daily items as durable snapshots. Server updates may
     * change them, but only an explicit local delete may remove them.
     */
    async mergeServerPlan(serverPlan: DailyPlan): Promise<DailyPlan> {
      if (!this.ownerId) return serverPlan
      const cachedPlan = await readCachedDailyPlan(this.ownerId, serverPlan.plan_date)
      const pendingOps = (
        await getPendingOperations(this.ownerId, 'daily_plan_item')
      ).filter(
        (op) =>
          op.payload.daily_plan_id === serverPlan.id ||
          op.payload.daily_plan_id === cachedPlan?.id,
      )
      let merged = serverPlan
      const pendingIds = new Set(pendingOps.map((op) => op.entity_id))
      if (cachedPlan) {
        const deletedIds = new Set(
          pendingOps.filter((op) => op.action === 'delete').map((op) => op.entity_id),
        )
        const cachedById = new Map(cachedPlan.items.map((item) => [item.id, item]))
        const serverIds = new Set(serverPlan.items.map((item) => item.id))
        const items = serverPlan.items
          .filter((item) => !deletedIds.has(item.id))
          .map((item) =>
            pendingIds.has(item.id) ? (cachedById.get(item.id) ?? item) : item,
          )
        const retainedLocalItems = cachedPlan.items
          .filter((item) => !serverIds.has(item.id) && !deletedIds.has(item.id))
          .map((item) => ({ ...item, daily_plan_id: serverPlan.id }))
        merged = recalculatePlan({ ...serverPlan, items: [...items, ...retainedLocalItems] })
      }
      await saveCachedDailyPlan(merged)
      if (cachedPlan && cachedPlan.id !== serverPlan.id) {
        // Drop the stale local-id record so future reads can only resolve to
        // the server-authoritative plan for this date.
        await localDb.cachedDailyPlans.delete(cachedPlan.id)
      }
      return merged
    },

    async refresh(options: { silent?: boolean } = {}): Promise<void> {
      await this.load(this.selectedDate, options)
    },

    async flushAndRefresh(): Promise<void> {
      if (!this.ownerId) return
      this.pendingCount = await pendingSyncCount(this.ownerId)
      if (navigator.onLine) {
        try {
          this.pendingCount = await syncPendingChanges(this.ownerId)
          this.online = true
        } catch (error) {
          if (!isNetworkError(error)) throw error
          this.online = false
        }
      }
      this.failedCount = await getFailedSyncCount(this.ownerId)
    },

    /**
     * Queue a create operation for the currently loaded local plan when the
     * server has not seen it yet. Plan creation is idempotent by date, and
     * the sync replay remaps queued item operations to the server plan id,
     * so this is safe even if the date already has a server-side plan.
     */
    async ensurePlanCreateQueued(): Promise<void> {
      if (!this.ownerId || !this.plan) return
      const planCreates = await getPendingOperations(this.ownerId, 'daily_plan')
      if (planCreates.some((op) => op.entity_id === this.plan?.id)) return
      await enqueueSyncOperation(this.ownerId, 'daily_plan', this.plan.id, 'create', {
        id: this.plan.id,
        plan_date: this.plan.plan_date,
      })
    },

    async addItem(payload: DailyPlanItemCreate): Promise<void> {
      if (!this.ownerId || !this.plan) throw new Error('Daily plan is not loaded')
      this.saving = true
      const now = new Date().toISOString()
      const id = payload.id ?? crypto.randomUUID()
      const item: DailyPlanItem = {
        id,
        daily_plan_id: this.plan.id,
        owner_id: this.ownerId,
        task_id: payload.task_id,
        title: payload.title ?? '项目任务',
        status: 'TODO',
        estimated_seconds: payload.estimated_seconds ?? 0,
        actual_seconds: 0,
        sort_order: this.plan.items.length,
        completed_at: null,
        created_at: now,
        updated_at: now,
      }
      try {
        this.plan = recalculatePlan({
          ...this.plan,
          items: [...this.plan.items, item],
        })
        await saveCachedDailyPlan(this.plan)
        await enqueueSyncOperation(this.ownerId, 'daily_plan_item', id, 'create', {
          ...payload,
          id,
          daily_plan_id: this.plan.id,
        })
        await this.buildLocalCheckIn()
        this.pendingCount = await pendingSyncCount(this.ownerId)
        // Adding a task is cache-first. The shared outbox serializes the
        // identical server write in the background, avoiding a visible wait
        // for both the item request and a second check-in request.
        void this.flushAndRefresh().catch(async () => {
          this.failedCount = await getFailedSyncCount(this.ownerId!)
        })
      } finally {
        this.saving = false
      }
    },

    async syncLinkedTaskEstimate(
      ownerId: string,
      taskId: string,
      estimatedSeconds: number,
    ): Promise<void> {
      const normalizedSeconds = Math.max(0, Math.round(estimatedSeconds))
      const today = localDateString()
      const plans = await localDb.cachedDailyPlans
        .where('owner_id')
        .equals(ownerId)
        .toArray()
      let loadedPlanChanged = false

      for (const plan of plans) {
        if (plan.plan_date < today) continue
        const linkedItems = plan.items.filter((item) => item.task_id === taskId)
        if (linkedItems.length === 0) continue
        const linkedIds = new Set(linkedItems.map((item) => item.id))
        const updatedPlan = recalculatePlan({
          ...plan,
          items: plan.items.map((item) =>
            linkedIds.has(item.id)
              ? {
                  ...item,
                  estimated_seconds: normalizedSeconds,
                  updated_at: new Date().toISOString(),
                }
              : item,
          ),
        })
        await saveCachedDailyPlan(updatedPlan)
        if (this.plan?.id === updatedPlan.id) {
          this.plan = updatedPlan
          loadedPlanChanged = true
        }
        for (const item of linkedItems) {
          await enqueueSyncOperation(ownerId, 'daily_plan_item', item.id, 'update', {
            daily_plan_id: plan.id,
            estimated_seconds: normalizedSeconds,
          })
        }
      }

      if (this.ownerId === ownerId) {
        this.pendingCount = await pendingSyncCount(ownerId)
        if (loadedPlanChanged) await this.buildLocalCheckIn()
      }
    },

    async applyFinishedTimer(itemId: string, actualSeconds: number): Promise<void> {
      if (!this.plan) return
      const existing = this.plan.items.find((item) => item.id === itemId)
      if (!existing) return
      const now = new Date().toISOString()
      const finished: DailyPlanItem = {
        ...existing,
        status: 'DONE',
        actual_seconds: Math.max(existing.actual_seconds, actualSeconds),
        completed_at: existing.completed_at ?? now,
        updated_at: now,
      }
      this.plan = recalculatePlan({
        ...this.plan,
        items: this.plan.items.map((item) => (item.id === itemId ? finished : item)),
      })
      this.pushTimerSecondsToTasks(existing, finished.actual_seconds)
      await saveCachedDailyPlan(this.plan)
      await this.buildLocalCheckIn()
    },

    async applyStoppedTimer(itemId: string, actualSeconds: number): Promise<void> {
      if (!this.plan) return
      const existing = this.plan.items.find((item) => item.id === itemId)
      if (!existing) return
      const updated: DailyPlanItem = {
        ...existing,
        actual_seconds: Math.max(existing.actual_seconds, actualSeconds),
        updated_at: new Date().toISOString(),
      }
      this.plan = recalculatePlan({
        ...this.plan,
        items: this.plan.items.map((item) => (item.id === itemId ? updated : item)),
      })
      this.pushTimerSecondsToTasks(existing, updated.actual_seconds)
      await saveCachedDailyPlan(this.plan)
      await this.buildLocalCheckIn()
    },

    /**
     * Keep the projects-page progress bars in step with the timer: the task
     * store only learns new actual seconds from server refreshes, so apply
     * the local delta right away (the session snapshot remains the source of
     * truth and is synced separately).
     */
    pushTimerSecondsToTasks(item: DailyPlanItem, newActualSeconds: number): void {
      const delta = Math.max(0, newActualSeconds - item.actual_seconds)
      if (delta <= 0 || !item.task_id) return
      useTaskStore().applyTimerSeconds(item.task_id, delta)
    },

    async updateItem(itemId: string, payload: DailyPlanItemUpdate): Promise<void> {
      if (!this.ownerId || !this.plan) throw new Error('Daily plan is not loaded')
      const existing = this.plan.items.find((item) => item.id === itemId)
      if (!existing) throw new Error('Daily plan item not found')
      this.saving = true
      const updated: DailyPlanItem = {
        ...existing,
        ...payload,
        completed_at:
          payload.status === 'DONE'
            ? new Date().toISOString()
            : payload.status
              ? null
              : existing.completed_at,
        updated_at: new Date().toISOString(),
      }
      try {
        this.plan = recalculatePlan({
          ...this.plan,
          items: this.plan.items.map((item) => (item.id === itemId ? updated : item)),
        })
        await saveCachedDailyPlan(this.plan)
        await enqueueSyncOperation(this.ownerId, 'daily_plan_item', itemId, 'update', {
          ...payload,
          daily_plan_id: this.plan.id,
        })
        await this.buildLocalCheckIn()
        await this.flushAndRefresh()
      } finally {
        this.saving = false
      }
    },

    async removeItem(itemId: string): Promise<void> {
      if (!this.ownerId || !this.plan) throw new Error('Daily plan is not loaded')
      this.saving = true
      try {
        this.plan = recalculatePlan({
          ...this.plan,
          items: this.plan.items.filter((item) => item.id !== itemId),
        })
        await saveCachedDailyPlan(this.plan)
        await enqueueSyncOperation(this.ownerId, 'daily_plan_item', itemId, 'delete', {
          daily_plan_id: this.plan.id,
        })
        await this.buildLocalCheckIn()
        await this.flushAndRefresh()
      } finally {
        this.saving = false
      }
    },

    /**
     * Import project tasks that are due today (by `due_date` or repeat rule)
     * but not yet present in today's daily plan. Safe to call repeatedly —
     * tasks already referenced by an existing plan item are skipped.
     */
    async syncProjectTasks(): Promise<void> {
      if (!this.plan || !this.ownerId) return
      const today = localDateString()
      if (this.selectedDate !== today) return

      const taskStore = useTaskStore()
      const existingTaskIds = new Set(
        this.plan.items.flatMap((item) => (item.task_id ? [item.task_id] : [])),
      )
      const parentIds = new Set(
        taskStore.items.flatMap((t) => (t.parent_id ? [t.parent_id] : [])),
      )
      const candidates = taskStore.items.filter(
        (task) =>
          task.node_type === 'TASK' &&
          task.status !== 'DONE' &&
          !existingTaskIds.has(task.id) &&
          !parentIds.has(task.id) &&
          (task.due_date === today || taskRepeatsOnDate(task, today)),
      )
      for (const task of candidates) {
        await this.addItem({
          task_id: task.id,
          title: projectPrefixedTaskTitle(task, taskStore.items),
          estimated_seconds: task.estimated_seconds,
        })
      }
    },
  },
})
