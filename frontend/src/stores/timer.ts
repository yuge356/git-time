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
import { isNetworkError, syncPendingChanges } from '@/services/offline-sync'
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
  retryTimerId: number | null
  onlineListenerBound: boolean
}

function nextTimestamp(previous: string | null = null): string {
  const previousTime = previous ? Date.parse(previous) : 0
  return new Date(Math.max(Date.now(), previousTime + 1)).toISOString()
}

function isMissingDailyPlanItemError(error: unknown): boolean {
  return (
    axios.isAxiosError<{ detail?: string }>(error) &&
    error.response?.status === 404 &&
    error.response.data?.detail === 'Daily plan item not found'
  )
}

async function upsertSessionWithReferenceRecovery(
  sessionId: string,
  snapshot: SessionSnapshot,
): Promise<SessionSnapshot> {
  try {
    await sessionService.upsert(sessionId, snapshot)
    return snapshot
  } catch (error) {
    if (
      !isMissingDailyPlanItemError(error) ||
      snapshot.task_id === null ||
      snapshot.daily_plan_item_id === null
    ) {
      throw error
    }

    // Daily items may disappear during an old offline queue replay. Preserve
    // the completed time against the still-owned task instead of losing it.
    const recovered = {
      ...snapshot,
      daily_plan_item_id: null,
      complete_daily_item: false,
    }
    await sessionService.upsert(sessionId, recovered)
    return recovered
  }
}

function finalizeOrphanedActiveSnapshot(
  sessionId: string,
  currentSessionId: string | null,
  snapshot: SessionSnapshot,
): SessionSnapshot {
  if (sessionId === currentSessionId || snapshot.status === 'COMPLETED') {
    return snapshot
  }

  // Only timerStates can represent the resumable timer. Older outbox entries
  // left RUNNING/PAUSED by previous navigation bugs would otherwise violate
  // the server's one-active-session invariant forever. Preserve their known
  // duration as closed history without completing today's item.
  return {
    ...snapshot,
    status: 'COMPLETED',
    ended_at: snapshot.client_updated_at,
    last_resumed_at: null,
    complete_daily_item: false,
  }
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
    retryTimerId: null,
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
        const retryPending = (): void => {
          if (!navigator.onLine) return
          this.online = true
          void this.syncPending()
            .then(() => this.refreshHistory())
            .catch(() => {
              // syncPending already stores a user-visible conflict message.
            })
        }
        window.addEventListener('online', () => {
          retryPending()
        })
        window.addEventListener('offline', () => {
          this.online = false
        })
        window.addEventListener('focus', retryPending)
        document.addEventListener('visibilitychange', () => {
          if (document.visibilityState === 'visible') retryPending()
        })
        this.retryTimerId = window.setInterval(() => {
          if (this.pendingCount > 0 && document.visibilityState === 'visible') {
            retryPending()
          }
        }, 15_000)
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
        if (isNetworkError(error)) {
          this.online = false
        } else {
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
      if (!navigator.onLine || this.syncing || !this.ownerId) {
        if (!navigator.onLine) this.online = false
        return
      }
      this.syncing = true
      this.syncError = ''
      this.online = true
      let connectionFailed = false
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
            const recoverableSnapshot = finalizeOrphanedActiveSnapshot(
              item.session_id,
              this.active?.session_id ?? null,
              item.snapshot,
            )
            const syncedSnapshot = await upsertSessionWithReferenceRecovery(
              item.session_id,
              recoverableSnapshot,
            )
            if (
              this.active?.session_id === item.session_id &&
              syncedSnapshot.daily_plan_item_id !== item.snapshot.daily_plan_item_id
            ) {
              this.active = { ...this.active, snapshot: syncedSnapshot }
              await saveActiveTimer(
                this.ownerId,
                item.session_id,
                syncedSnapshot,
                this.targetSeconds,
              )
            }
            await localDb.sessionOutbox.delete(item.session_id)
          } catch (error) {
            if (isNetworkError(error)) {
              this.online = false
              connectionFailed = true
              break
            }
            await localDb.sessionOutbox.update(item.session_id, {
              retry_count: item.retry_count + 1,
              last_error: '服务器拒绝了该计时状态。',
            })
            // Keep the rejected historical snapshot for inspection, but do
            // not prevent independent, newer sessions from reaching server.
            continue
          }
        }
        if (!connectionFailed) this.online = true
      } catch (error) {
        if (isNetworkError(error)) {
          this.online = false
          this.syncError = '计时已保存在本机，服务恢复后将自动同步。'
          return
        }
        throw error
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
      if (!navigator.onLine || !this.ownerId) {
        if (!navigator.onLine) this.online = false
        return
      }
      const queued = await localDb.sessionOutbox.get(sessionId)
      if (!queued) return
      try {
        const syncedSnapshot = await upsertSessionWithReferenceRecovery(
          sessionId,
          queued.snapshot,
        )
        if (
          this.active?.session_id === sessionId &&
          syncedSnapshot.daily_plan_item_id !== queued.snapshot.daily_plan_item_id
        ) {
          this.active = { ...this.active, snapshot: syncedSnapshot }
          await saveActiveTimer(
            this.ownerId,
            sessionId,
            syncedSnapshot,
            this.targetSeconds,
          )
        }
        await localDb.sessionOutbox.delete(sessionId)
        this.online = true
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
      if (this.active?.snapshot.status === 'RUNNING') {
        throw new Error('请先暂停当前计时，再切换到其他任务。')
      }
      if (this.active?.snapshot.status === 'PAUSED') {
        // Close the old local segment without waiting for the network. The
        // outbox replays it before the new RUNNING segment in timestamp order.
        await this.finish(false, false)
      }
      this.busy = true
      this.syncError = ''
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
          // Structural changes must be attempted before their session, but a
          // rejected or temporarily blocked sync must not cancel local timing.
          await this.syncPending()
          if (!this.online) {
            this.syncError = '计时已在本机开始，联网后将自动同步。'
          }
        } catch (error) {
          if (isNetworkError(error)) this.online = false
          this.syncError = isNetworkError(error)
            ? '计时已在本机开始，联网后将自动同步。'
            : '计时已开始，但新任务或计时记录暂未同步，请稍后重试。'
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

    async finish(
      completeDailyItem = true,
      syncImmediately = true,
    ): Promise<void> {
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
          complete_daily_item: completeDailyItem,
        }
        await this.persistSnapshot(sessionId, snapshot, false)
        this.targetSeconds = null
        if (syncImmediately) {
          await this.syncLatestOrKeepOffline(sessionId)
          await this.refreshHistory()
        }
        this.completedRevision += 1
      } finally {
        this.busy = false
      }
    },
  },
})
