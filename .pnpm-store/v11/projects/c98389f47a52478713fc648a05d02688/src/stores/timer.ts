import axios from 'axios'
import { defineStore } from 'pinia'

import {
  clearActiveTimer,
  enqueueSessionSnapshot,
  getClientId,
  loadActiveTimer,
  localDb,
  saveActiveTimer,
} from '@/db/local'
import { sessionService } from '@/services/sessions'
import { syncPendingChanges } from '@/services/offline-sync'
import type {
  LocalTimerState,
  SessionSnapshot,
  StudySession,
} from '@/types/session'
import { snapshotDuration } from '@/utils/timer'

interface TimerState {
  ownerId: string | null
  active: LocalTimerState | null
  history: StudySession[]
  displaySeconds: number
  targetSeconds: number | null
  pendingCount: number
  initialized: boolean
  busy: boolean
  syncing: boolean
  online: boolean
  syncError: string
  completedRevision: number
  tickerId: number | null
  onlineListenerBound: boolean
}

function nextTimestamp(previous: string | null = null): string {
  const previousTime = previous ? Date.parse(previous) : 0
  return new Date(Math.max(Date.now(), previousTime + 1)).toISOString()
}

function isNetworkError(error: unknown): boolean {
  return axios.isAxiosError(error) && !error.response
}

export const useTimerStore = defineStore('timer', {
  state: (): TimerState => ({
    ownerId: null,
    active: null,
    history: [],
    displaySeconds: 0,
    targetSeconds: null,
    pendingCount: 0,
    initialized: false,
    busy: false,
    syncing: false,
    online: navigator.onLine,
    syncError: '',
    completedRevision: 0,
    tickerId: null,
    onlineListenerBound: false,
  }),

  actions: {
    startTicker(): void {
      if (this.tickerId !== null) return
      this.tickerId = window.setInterval(() => {
        if (this.active) {
          this.displaySeconds = snapshotDuration(this.active.snapshot)
        }
      }, 1_000)
    },

    async initialize(ownerId: string): Promise<void> {
      if (this.initialized && this.ownerId === ownerId) return
      this.ownerId = ownerId
      this.initialized = false
      this.active = (await loadActiveTimer(ownerId)) ?? null
      this.targetSeconds = this.active?.target_seconds ?? null
      this.history = []
      this.syncError = ''
      this.online = navigator.onLine
      this.displaySeconds = this.active ? snapshotDuration(this.active.snapshot) : 0
      this.startTicker()

      if (!this.onlineListenerBound) {
        window.addEventListener('online', () => {
          this.online = true
          void this.syncPending()
            .then(() => this.refreshHistory())
            .catch(() => {
              // syncPending already stores a user-visible conflict message.
            })
        })
        window.addEventListener('offline', () => {
          this.online = false
        })
        this.onlineListenerBound = true
      }

      try {
        await this.syncPending()
        if (!this.active && this.online) {
          const serverActive = await sessionService.active()
          if (serverActive) {
            this.active = {
              id: ownerId,
              owner_id: ownerId,
              session_id: serverActive.id,
              target_seconds: this.targetSeconds,
              snapshot: {
                task_id: serverActive.task_id,
                daily_plan_item_id: serverActive.daily_plan_item_id,
                client_id: serverActive.client_id,
                status: serverActive.status,
                started_at: serverActive.started_at,
                ended_at: serverActive.ended_at,
                duration_seconds: serverActive.duration_seconds,
                last_resumed_at: serverActive.last_resumed_at,
                client_updated_at: serverActive.client_updated_at,
              },
            }
            await saveActiveTimer(
              ownerId,
              this.active.session_id,
              this.active.snapshot,
              this.targetSeconds,
            )
            this.displaySeconds = snapshotDuration(this.active.snapshot)
          }
        }
        await this.refreshHistory()
      } catch (error) {
        if (!isNetworkError(error)) {
          this.syncError = '本地计时记录暂时无法与服务器同步。'
        }
      } finally {
        this.pendingCount = await localDb.sessionOutbox.where('owner_id').equals(ownerId).count()
        this.initialized = true
      }
    },

    async refreshHistory(): Promise<void> {
      if (!this.online) return
      this.history = await sessionService.list()
    },

    async syncPending(): Promise<void> {
      if (!this.online || this.syncing || !this.ownerId) return
      this.syncing = true
      this.syncError = ''
      try {
        // Offline-created tasks and plan items must reach the server before
        // their Session snapshots replay foreign-key references.
        await syncPendingChanges(this.ownerId)
        const pending = await localDb.sessionOutbox
          .where('owner_id')
          .equals(this.ownerId)
          .toArray()
        pending.sort((left, right) =>
          left.snapshot.client_updated_at.localeCompare(right.snapshot.client_updated_at),
        )
        for (const item of pending) {
          try {
            await sessionService.upsert(item.session_id, item.snapshot)
            await localDb.sessionOutbox.delete(item.session_id)
          } catch (error) {
            if (isNetworkError(error)) {
              this.online = false
              break
            }
            await localDb.sessionOutbox.update(item.session_id, {
              retry_count: item.retry_count + 1,
              last_error: '服务器拒绝了该计时状态。',
            })
            this.syncError = '存在需要处理的计时同步冲突。'
            throw error
          }
        }
      } finally {
        this.pendingCount = await localDb.sessionOutbox
          .where('owner_id')
          .equals(this.ownerId)
          .count()
        this.syncing = false
      }
    },

    async persistSnapshot(
      sessionId: string,
      snapshot: SessionSnapshot,
      keepActive: boolean,
    ): Promise<void> {
      if (!this.ownerId) throw new Error('Timer store is not initialized')
      if (keepActive) {
        await saveActiveTimer(
          this.ownerId,
          sessionId,
          snapshot,
          this.targetSeconds,
        )
        this.active = {
          id: this.ownerId,
          owner_id: this.ownerId,
          session_id: sessionId,
          target_seconds: this.targetSeconds,
          snapshot,
        }
        this.displaySeconds = snapshotDuration(snapshot)
      } else {
        await clearActiveTimer(this.ownerId)
        this.active = null
        this.displaySeconds = 0
      }
      await enqueueSessionSnapshot(this.ownerId, sessionId, snapshot)
      this.pendingCount = await localDb.sessionOutbox
        .where('owner_id')
        .equals(this.ownerId)
        .count()
    },

    async syncLatestOrKeepOffline(sessionId: string): Promise<void> {
      if (!this.online || !this.ownerId) return
      const queued = await localDb.sessionOutbox.get(sessionId)
      if (!queued) return
      try {
        await sessionService.upsert(sessionId, queued.snapshot)
        await localDb.sessionOutbox.delete(sessionId)
        this.pendingCount = await localDb.sessionOutbox
          .where('owner_id')
          .equals(this.ownerId)
          .count()
      } catch (error) {
        if (isNetworkError(error)) {
          this.online = false
          return
        }
        throw error
      }
    },

    async start(
      taskId: string | null,
      dailyPlanItemId: string | null = null,
      targetSeconds: number | null = null,
    ): Promise<void> {
      if (this.active) throw new Error('已有活动计时器')
      this.busy = true
      this.targetSeconds = targetSeconds && targetSeconds > 0 ? targetSeconds : null
      const sessionId = crypto.randomUUID()
      const now = nextTimestamp()
      const snapshot: SessionSnapshot = {
        task_id: taskId,
        daily_plan_item_id: dailyPlanItemId,
        client_id: await getClientId(),
        status: 'RUNNING',
        started_at: now,
        ended_at: null,
        duration_seconds: 0,
        last_resumed_at: now,
        client_updated_at: now,
      }

      try {
        await this.persistSnapshot(sessionId, snapshot, true)
        try {
          await this.syncLatestOrKeepOffline(sessionId)
        } catch (error) {
          if (!this.ownerId) throw error
          await clearActiveTimer(this.ownerId)
          await localDb.sessionOutbox.delete(sessionId)
          this.active = null
          this.displaySeconds = 0
          this.targetSeconds = null
          throw error
        }
      } finally {
        this.pendingCount = this.ownerId
          ? await localDb.sessionOutbox.where('owner_id').equals(this.ownerId).count()
          : 0
        this.busy = false
      }
    },

    async pause(): Promise<void> {
      if (!this.active || this.active.snapshot.status !== 'RUNNING') return
      this.busy = true
      try {
        const now = nextTimestamp(this.active.snapshot.client_updated_at)
        const snapshot: SessionSnapshot = {
          ...this.active.snapshot,
          status: 'PAUSED',
          duration_seconds: snapshotDuration(this.active.snapshot, new Date(now)),
          last_resumed_at: null,
          client_updated_at: now,
        }
        await this.persistSnapshot(this.active.session_id, snapshot, true)
        await this.syncLatestOrKeepOffline(this.active.session_id)
      } finally {
        this.busy = false
      }
    },

    async resume(): Promise<void> {
      if (!this.active || this.active.snapshot.status !== 'PAUSED') return
      this.busy = true
      try {
        const now = nextTimestamp(this.active.snapshot.client_updated_at)
        const snapshot: SessionSnapshot = {
          ...this.active.snapshot,
          status: 'RUNNING',
          last_resumed_at: now,
          client_updated_at: now,
        }
        await this.persistSnapshot(this.active.session_id, snapshot, true)
        await this.syncLatestOrKeepOffline(this.active.session_id)
      } finally {
        this.busy = false
      }
    },

    async finish(): Promise<void> {
      if (!this.active) return
      this.busy = true
      const sessionId = this.active.session_id
      try {
        const now = nextTimestamp(this.active.snapshot.client_updated_at)
        const snapshot: SessionSnapshot = {
          ...this.active.snapshot,
          status: 'COMPLETED',
          ended_at: now,
          duration_seconds: snapshotDuration(this.active.snapshot, new Date(now)),
          last_resumed_at: null,
          client_updated_at: now,
        }
        await this.persistSnapshot(sessionId, snapshot, false)
        this.targetSeconds = null
        await this.syncLatestOrKeepOffline(sessionId)
        await this.refreshHistory()
        this.completedRevision += 1
      } finally {
        this.busy = false
      }
    },
  },
})
