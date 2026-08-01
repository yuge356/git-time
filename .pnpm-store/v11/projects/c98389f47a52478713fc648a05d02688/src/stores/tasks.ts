import { defineStore } from 'pinia'

import {
  enqueueSyncOperation,
  localDb,
  pendingSyncCount,
} from '@/db/local'
import {
  getPendingOperations,
  isNetworkError,
  syncPendingChanges,
} from '@/services/offline-sync'
import { taskService } from '@/services/tasks'
import type {
  Task,
  TaskCreatePayload,
  TaskNode,
  TaskUpdatePayload,
} from '@/types/task'

interface TaskState {
  ownerId: string | null
  items: Task[]
  loading: boolean
  saving: boolean
  online: boolean
  pendingCount: number
  listenerBound: boolean
}

function compareTasks(left: Task, right: Task): number {
  if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order
  return left.created_at.localeCompare(right.created_at)
}

function updateWasApplied(task: Task, payload: TaskUpdatePayload): boolean {
  return Object.entries(payload).every(([key, value]) => {
    if (key === 'daily_reminder_time') {
      const current = task.daily_reminder_time?.slice(0, 5) ?? null
      const expected = typeof value === 'string' ? value.slice(0, 5) : value
      return current === expected
    }
    return task[key as keyof Task] === value
  })
}

export const useTaskStore = defineStore('tasks', {
  state: (): TaskState => ({
    ownerId: null,
    items: [],
    loading: false,
    saving: false,
    online: navigator.onLine,
    pendingCount: 0,
    listenerBound: false,
  }),

  getters: {
    tree(state): TaskNode[] {
      const nodes = new Map<string, TaskNode>()
      state.items.forEach((task) => nodes.set(task.id, { ...task, children: [] }))
      const roots: TaskNode[] = []
      nodes.forEach((node) => {
        const parent = node.parent_id ? nodes.get(node.parent_id) : undefined
        if (parent) parent.children.push(node)
        else roots.push(node)
      })
      const sortTree = (items: TaskNode[]): void => {
        items.sort(compareTasks)
        items.forEach((item) => sortTree(item.children))
      }
      sortTree(roots)
      return roots
    },
  },

  actions: {
    async initialize(ownerId: string): Promise<void> {
      this.ownerId = ownerId
      if (!this.listenerBound) {
        window.addEventListener('online', () => {
          this.online = true
          void this.load()
        })
        window.addEventListener('offline', () => {
          this.online = false
        })
        this.listenerBound = true
      }
      await this.load()
    },

    /**
     * Merge a fresh server list with local optimistic data.
     * Operations still sitting in the sync queue mean the server copy is
     * behind the local cache — never let it wipe unsynced local changes.
     */
    async mergeServerItems(serverItems: Task[]): Promise<Task[]> {
      if (!this.ownerId) return serverItems
      await localDb.cachedTasks.bulkPut(serverItems)
      const pendingOps = await getPendingOperations(this.ownerId, 'task')
      if (pendingOps.length === 0) {
        await this.dropStaleCache(serverItems, new Set())
        return serverItems
      }
      const pendingIds = new Set(pendingOps.map((op) => op.entity_id))
      const deletedIds = new Set(
        pendingOps.filter((op) => op.action === 'delete').map((op) => op.entity_id),
      )
      const cached = await localDb.cachedTasks
        .where('owner_id')
        .equals(this.ownerId)
        .toArray()
      const cachedById = new Map(cached.map((item) => [item.id, item]))
      const serverIds = new Set(serverItems.map((item) => item.id))
      const merged = serverItems
        .filter((item) => !deletedIds.has(item.id))
        .map((item) =>
          pendingIds.has(item.id) ? (cachedById.get(item.id) ?? item) : item,
        )
      const optimisticCreates = cached.filter(
        (item) => pendingIds.has(item.id) && !serverIds.has(item.id),
      )
      await this.dropStaleCache(serverItems, pendingIds)
      return [...merged, ...optimisticCreates]
    },

    async dropStaleCache(serverItems: Task[], keepIds: Set<string>): Promise<void> {
      if (!this.ownerId) return
      const currentIds = new Set(serverItems.map((item) => item.id))
      const cached = await localDb.cachedTasks
        .where('owner_id')
        .equals(this.ownerId)
        .toArray()
      const staleIds = cached
        .filter((item) => !currentIds.has(item.id) && !keepIds.has(item.id))
        .map((item) => item.id)
      if (staleIds.length > 0) {
        await localDb.cachedTasks.bulkDelete(staleIds)
      }
    },

    async load(): Promise<void> {
      if (!this.ownerId) throw new Error('Task store is not initialized')
      this.loading = true
      this.online = navigator.onLine
      try {
        if (this.online) {
          try {
            this.pendingCount = await syncPendingChanges(this.ownerId)
            const serverItems = await taskService.list()
            this.items = await this.mergeServerItems(serverItems)
            return
          } catch (error) {
            if (!isNetworkError(error)) throw error
            this.online = false
          }
        }
        this.items = await localDb.cachedTasks
          .where('owner_id')
          .equals(this.ownerId)
          .toArray()
        this.pendingCount = await pendingSyncCount(this.ownerId)
      } finally {
        this.loading = false
      }
    },

    async flush(): Promise<void> {
      if (!this.ownerId || !navigator.onLine) return
      try {
        this.pendingCount = await syncPendingChanges(this.ownerId)
        const serverItems = await taskService.list()
        this.items = await this.mergeServerItems(serverItems)
      } catch (error) {
        if (isNetworkError(error)) {
          this.online = false
          return
        }
        const serverItems = await taskService.list()
        this.items = await this.mergeServerItems(serverItems)
        throw error
      }
    },

    async reconcileTask(taskId: string): Promise<Task | null> {
      if (!navigator.onLine) return null
      try {
        const serverItems = await taskService.list()
        this.items = await this.mergeServerItems(serverItems)
        this.pendingCount = await pendingSyncCount(this.ownerId ?? '')
        return this.items.find((item) => item.id === taskId) ?? null
      } catch {
        return null
      }
    },

    async create(payload: TaskCreatePayload): Promise<Task> {
      if (!this.ownerId) throw new Error('Task store is not initialized')
      this.saving = true
      const now = new Date().toISOString()
      const id = payload.id ?? crypto.randomUUID()
      const siblings = this.items.filter((item) => item.parent_id === payload.parent_id)
      const task: Task = {
        id,
        owner_id: this.ownerId,
        parent_id: payload.parent_id,
        title: payload.title,
        status: 'TODO',
        estimated_seconds: payload.estimated_seconds,
        repeat_rule: payload.repeat_rule,
        daily_reminder_time: payload.daily_reminder_time,
        sort_order: siblings.length
          ? Math.max(...siblings.map((item) => item.sort_order)) + 1
          : 0,
        completed_at: null,
        created_at: now,
        updated_at: now,
        direct_actual_seconds: 0,
        actual_seconds: 0,
        budget_usage_ratio: payload.estimated_seconds > 0 ? 0 : null,
        budget_level: payload.estimated_seconds > 0 ? 'NORMAL' : 'NOT_SET',
      }
      try {
        this.items.push(task)
        await localDb.cachedTasks.put(task)
        await enqueueSyncOperation(this.ownerId, 'task', id, 'create', {
          ...payload,
          id,
        })
        this.pendingCount = await pendingSyncCount(this.ownerId)
        try {
          await this.flush()
        } catch (error) {
          const confirmed = await this.reconcileTask(id)
          if (!confirmed) throw error
          return confirmed
        }
        return this.items.find((item) => item.id === id) ?? task
      } finally {
        this.saving = false
      }
    },

    async update(taskId: string, payload: TaskUpdatePayload): Promise<Task> {
      if (!this.ownerId) throw new Error('Task store is not initialized')
      const existing = this.items.find((item) => item.id === taskId)
      if (!existing) throw new Error('Task not found')
      this.saving = true
      const updated: Task = {
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
        this.items = this.items.map((item) => (item.id === taskId ? updated : item))
        await localDb.cachedTasks.put(updated)
        await enqueueSyncOperation(this.ownerId, 'task', taskId, 'update', {
          ...payload,
        })
        this.pendingCount = await pendingSyncCount(this.ownerId)
        try {
          await this.flush()
        } catch (error) {
          const confirmed = await this.reconcileTask(taskId)
          if (!confirmed || !updateWasApplied(confirmed, payload)) throw error
          return confirmed
        }
        return this.items.find((item) => item.id === taskId) ?? updated
      } finally {
        this.saving = false
      }
    },

    async remove(taskId: string): Promise<void> {
      if (!this.ownerId) throw new Error('Task store is not initialized')
      this.saving = true
      try {
        const deletedIds = new Set<string>([taskId])
        let changed = true
        while (changed) {
          changed = false
          this.items.forEach((task) => {
            if (task.parent_id && deletedIds.has(task.parent_id) && !deletedIds.has(task.id)) {
              deletedIds.add(task.id)
              changed = true
            }
          })
        }
        this.items = this.items.filter((task) => !deletedIds.has(task.id))
        await localDb.cachedTasks.bulkDelete([...deletedIds])
        await enqueueSyncOperation(this.ownerId, 'task', taskId, 'delete', {})
        this.pendingCount = await pendingSyncCount(this.ownerId)
        await this.flush()
      } finally {
        this.saving = false
      }
    },
  },
})
