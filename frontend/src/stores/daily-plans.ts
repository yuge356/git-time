import axios from 'axios'
import { defineStore } from 'pinia'

import {
  enqueueSyncOperation,
  localDb,
  pendingSyncCount,
  readCachedDailyPlan,
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
  listenerBound: boolean
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
    listenerBound: false,
  }),

  actions: {
    async initialize(ownerId: string, planDate?: string): Promise<void> {
      this.ownerId = ownerId
      if (!this.listenerBound) {
        window.addEventListener('online', () => {
          this.online = true
          void this.load(this.selectedDate)
        })
        window.addEventListener('offline', () => {
          this.online = false
        })
        this.listenerBound = true
      }
      await this.load(planDate)
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
      await localDb.cachedDailyPlans.put(plan)
      await enqueueSyncOperation(this.ownerId, 'daily_plan', plan.id, 'create', {
        id: plan.id,
        plan_date: plan.plan_date,
      })
      return plan
    },

    async load(planDate?: string): Promise<void> {
      if (!this.ownerId) throw new Error('Daily plan store is not initialized')
      const targetDate = planDate ?? this.selectedDate
      this.loading = true
      this.selectedDate = targetDate
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
            this.plan = await this.mergeServerPlan(serverPlan)
            try {
              const populated = await dailyPlanService.autoPopulate(this.plan.id)
              if (populated.items.length > this.plan.items.length) {
                this.plan = populated
                await localDb.cachedDailyPlans.put(this.plan)
              }
            } catch { /* auto-populate is best-effort */ }
            this.checkIn = await dailyPlanService.checkIn(targetDate)
            return
          } catch (error) {
            if (!isNetworkError(error)) throw error
            this.online = false
          }
        }

        this.plan = (await readCachedDailyPlan(this.ownerId, targetDate)) ?? null
        if (!this.plan) this.plan = await this.createLocalPlan()
        this.pendingCount = await pendingSyncCount(this.ownerId)
        this.failedCount = await getFailedSyncCount(this.ownerId)
        await this.buildLocalCheckIn()
      } finally {
        this.loading = false
      }
    },

    /**
     * Merge the server plan with optimistic items still waiting in the sync
     * queue so unsynced additions/updates/deletes never vanish from the UI.
     */
    async mergeServerPlan(serverPlan: DailyPlan): Promise<DailyPlan> {
      if (!this.ownerId) return serverPlan
      const pendingOps = (
        await getPendingOperations(this.ownerId, 'daily_plan_item')
      ).filter((op) => op.payload.daily_plan_id === serverPlan.id)
      const cachedPlan = await readCachedDailyPlan(this.ownerId, serverPlan.plan_date)
      let merged = serverPlan
      if (pendingOps.length > 0 && cachedPlan && cachedPlan.id === serverPlan.id) {
        const pendingIds = new Set(pendingOps.map((op) => op.entity_id))
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
        const optimisticCreates = cachedPlan.items.filter(
          (item) => pendingIds.has(item.id) && !serverIds.has(item.id),
        )
        merged = recalculatePlan({ ...serverPlan, items: [...items, ...optimisticCreates] })
      }
      await localDb.cachedDailyPlans.put(merged)
      return merged
    },

    async refresh(): Promise<void> {
      await this.load(this.selectedDate)
    },

    async flushAndRefresh(): Promise<void> {
      if (!this.ownerId) return
      this.pendingCount = await pendingSyncCount(this.ownerId)
      if (navigator.onLine) {
        try {
          this.pendingCount = await syncPendingChanges(this.ownerId)
        } catch (error) {
          if (!isNetworkError(error)) throw error
          this.online = false
        }
      }
      await this.load(this.selectedDate)
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
        title: payload.title ?? '长期任务',
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
        await localDb.cachedDailyPlans.put(this.plan)
        await enqueueSyncOperation(this.ownerId, 'daily_plan_item', id, 'create', {
          ...payload,
          id,
          daily_plan_id: this.plan.id,
        })
        await this.buildLocalCheckIn()
        await this.flushAndRefresh()
      } finally {
        this.saving = false
      }
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
        await localDb.cachedDailyPlans.put(this.plan)
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
        await localDb.cachedDailyPlans.put(this.plan)
        await enqueueSyncOperation(this.ownerId, 'daily_plan_item', itemId, 'delete', {
          daily_plan_id: this.plan.id,
        })
        await this.buildLocalCheckIn()
        await this.flushAndRefresh()
      } finally {
        this.saving = false
      }
    },
  },
})
