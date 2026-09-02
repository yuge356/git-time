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
  baseSeconds: number | null
  targetSeconds: number | null
  pendingCount: number
  initialized: boolean
  busy: boolean
  syncing: boolean
  online: boolean
  syncError: string
  completedRevision: number
  targetNotice: string
  notifiedSessionId: string | null
  tickerId: number | null
  retryTimerId: number | null
  onlineListenerBound: boolean
  observedLocalDate: string
  rolloverPausePending: boolean
}

interface PendingExitPause {
  owner_id: string
  session_id: string
  target_seconds: number | null
  base_seconds: number | null
  snapshot: SessionSnapshot
}

interface TimerHeartbeat {
  owner_id: string
  session_id: string
  observed_at: string
}

function exitPauseStorageKey(ownerId: string): string {
  return `time-budget:pending-exit-pause:${ownerId}`
}

function timerHeartbeatStorageKey(ownerId: string): string {
  return `time-budget:timer-heartbeat:${ownerId}`
}

function targetNoticeStorageKey(ownerId: string, sessionId: string): string {
  return `time-budget:target-notice:${ownerId}:${sessionId}`
}

function hasTargetNoticeMarker(ownerId: string, sessionId: string): boolean {
  try {
    return localStorage.getItem(targetNoticeStorageKey(ownerId, sessionId)) === '1'
  } catch {
    return false
  }
}

function writeTargetNoticeMarker(ownerId: string, sessionId: string): void {
  try {
    localStorage.setItem(targetNoticeStorageKey(ownerId, sessionId), '1')
  } catch {
    // The in-memory marker still prevents duplicate reminders this visit.
  }
}

function clearTargetNoticeMarker(ownerId: string, sessionId: string): void {
  try {
    localStorage.removeItem(targetNoticeStorageKey(ownerId, sessionId))
  } catch {
    // A stale marker is scoped to a completed session and is harmless.
  }
}

function requestSystemNotificationPermission(): void {
  if (!('Notification' in window) || Notification.permission !== 'default') return
  void Notification.requestPermission().catch(() => {
    // The in-app reminder remains available when browser permission is denied.
  })
}

function writeTimerHeartbeat(ownerId: string, sessionId: string): void {
  try {
    const heartbeat: TimerHeartbeat = {
      owner_id: ownerId,
      session_id: sessionId,
      observed_at: new Date().toISOString(),
    }
    localStorage.setItem(timerHeartbeatStorageKey(ownerId), JSON.stringify(heartbeat))
  } catch {
    // Lifecycle events still persist a complete pause snapshot. The heartbeat
    // is an additional crash-recovery guard for browsers that skip them.
  }
}

function readTimerHeartbeat(ownerId: string): TimerHeartbeat | null {
  try {
    const value = localStorage.getItem(timerHeartbeatStorageKey(ownerId))
    if (!value) return null
    const heartbeat = JSON.parse(value) as TimerHeartbeat
    if (
      heartbeat.owner_id !== ownerId ||
      typeof heartbeat.session_id !== 'string' ||
      !Number.isFinite(Date.parse(heartbeat.observed_at))
    ) {
      localStorage.removeItem(timerHeartbeatStorageKey(ownerId))
      return null
    }
    return heartbeat
  } catch {
    return null
  }
}

function clearTimerHeartbeat(ownerId: string): void {
  try {
    localStorage.removeItem(timerHeartbeatStorageKey(ownerId))
  } catch {
    // Nothing else is required when browser storage is unavailable.
  }
}

function readPendingExitPause(ownerId: string): PendingExitPause | null {
  const key = exitPauseStorageKey(ownerId)
  try {
    const value = localStorage.getItem(key)
    if (!value) return null
    const pending = JSON.parse(value) as PendingExitPause
    if (
      pending.owner_id !== ownerId ||
      typeof pending.session_id !== 'string' ||
      pending.snapshot?.status !== 'PAUSED'
    ) {
      clearPendingExitPause(ownerId)
      return null
    }
    return pending
  } catch {
    clearPendingExitPause(ownerId)
    return null
  }
}

function writePendingExitPause(ownerId: string, pending: PendingExitPause): void {
  try {
    localStorage.setItem(exitPauseStorageKey(ownerId), JSON.stringify(pending))
  } catch {
    // IndexedDB persistence and the keepalive request below remain available.
  }
}

function clearPendingExitPause(ownerId: string): void {
  try {
    localStorage.removeItem(exitPauseStorageKey(ownerId))
  } catch {
    // A stale marker is harmless and will be validated on the next load.
  }
}

async function restorePendingExitPause(ownerId: string): Promise<void> {
  const pending = readPendingExitPause(ownerId)
  if (!pending) return
  await saveActiveTimer(
    ownerId,
    pending.session_id,
    pending.snapshot,
    pending.target_seconds,
    pending.base_seconds ?? null,
  )
  await enqueueSessionSnapshot(ownerId, pending.session_id, pending.snapshot)
  clearPendingExitPause(ownerId)
}

function localDateString(date = new Date()): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function startOfLocalDate(dateText: string): Date {
  const [year, month, day] = dateText.split('-').map(Number)
  return new Date(year!, month! - 1, day!)
}

function nextTimestamp(previous: string | null = null, minimumTime = Date.now()): string {
  const previousTime = previous ? Date.parse(previous) : 0
  return new Date(Math.max(minimumTime, previousTime + 1)).toISOString()
}

async function recoverInterruptedRunningTimer(
  ownerId: string,
  timerState: LocalTimerState,
): Promise<LocalTimerState> {
  if (timerState.snapshot.status !== 'RUNNING') {
    clearTimerHeartbeat(ownerId)
    return timerState
  }

  const heartbeat = readTimerHeartbeat(ownerId)
  const previousUpdate = Date.parse(timerState.snapshot.client_updated_at)
  const observedAt = heartbeat?.session_id === timerState.session_id
    ? Date.parse(heartbeat.observed_at)
    : previousUpdate
  const pauseTime = new Date(
    Math.max(
      Number.isFinite(previousUpdate) ? previousUpdate + 1 : 0,
      Math.min(Date.now(), Number.isFinite(observedAt) ? observedAt : Date.now()),
    ),
  )
  const snapshot: SessionSnapshot = {
    ...timerState.snapshot,
    status: 'PAUSED',
    duration_seconds: snapshotDuration(timerState.snapshot, pauseTime),
    last_resumed_at: null,
    client_updated_at: pauseTime.toISOString(),
  }
  const recovered = { ...timerState, snapshot }

  // A previous page stopped without completing its unload handler. Convert
  // the last observed running state into a durable pause before syncing.
  await saveActiveTimer(
    ownerId,
    timerState.session_id,
    snapshot,
    timerState.target_seconds,
    timerState.base_seconds ?? null,
  )
  await enqueueSessionSnapshot(ownerId, timerState.session_id, snapshot)
  clearTimerHeartbeat(ownerId)
  return recovered
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
    baseSeconds: null,
    targetSeconds: null,
    pendingCount: 0,
    initialized: false,
    busy: false,
    syncing: false,
    online: navigator.onLine,
    syncError: '',
    completedRevision: 0,
    targetNotice: '',
    notifiedSessionId: null,
    tickerId: null,
    retryTimerId: null,
    onlineListenerBound: false,
    observedLocalDate: localDateString(),
    rolloverPausePending: false,
  }),

  getters: {
    /**
     * Seconds shown on the timer face: everything the timed daily item has
     * accumulated today, not just the current session. Ending a task early
     * and starting it again therefore continues from the point it stopped,
     * and the focus panel, the today list and the floating bar all read the
     * same number.
     */
    totalSeconds(state): number {
      return (state.baseSeconds ?? 0) + state.displaySeconds
    },
  },

  actions: {
    startTicker(): void {
      if (this.tickerId !== null) return
      this.tickerId = window.setInterval(() => {
        const currentDate = localDateString()
        if (currentDate !== this.observedLocalDate) {
          this.observedLocalDate = currentDate
          void this.pauseForDayRollover().catch(() => {
            this.syncError = '跨天计时已暂停在本机，服务恢复后将自动同步。'
          })
        }
        if (this.active) {
          this.displaySeconds = snapshotDuration(this.active.snapshot)
          this.maybeNotifyTargetReached()
          if (this.ownerId && this.active.snapshot.status === 'RUNNING') {
            writeTimerHeartbeat(this.ownerId, this.active.session_id)
          }
        }
      }, 1_000)
    },

    /**
     * Give a restored session the accumulated time of its daily item. A
     * session recovered from the server (or from a device whose local
     * database was cleared) has no stored baseline, so the item's own total
     * minus this session's contribution is the closest exact starting point.
     */
    async adoptBaseSeconds(itemActualSeconds: number): Promise<void> {
      if (!this.ownerId || !this.active || this.baseSeconds !== null) return
      const sessionSeconds = snapshotDuration(this.active.snapshot)
      const base = Math.max(0, Math.round(itemActualSeconds) - sessionSeconds)
      this.baseSeconds = base
      this.active = { ...this.active, base_seconds: base }
      await saveActiveTimer(
        this.ownerId,
        this.active.session_id,
        this.active.snapshot,
        this.targetSeconds,
        base,
      )
    },

    async initialize(ownerId: string): Promise<void> {
      if (this.initialized && this.ownerId === ownerId) return
      this.ownerId = ownerId
      this.initialized = false
      await restorePendingExitPause(ownerId)
      const storedTimer = await loadActiveTimer(ownerId)
      this.active = storedTimer
        ? await recoverInterruptedRunningTimer(ownerId, storedTimer)
        : null
      this.targetSeconds = this.active?.target_seconds ?? null
      this.baseSeconds = this.active ? (this.active.base_seconds ?? null) : null
      this.history = []
      this.syncError = ''
      this.online = navigator.onLine
      this.displaySeconds = this.active ? snapshotDuration(this.active.snapshot) : 0
      this.targetNotice = ''
      this.notifiedSessionId = null
      this.observedLocalDate = localDateString()
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
          // Hiding the document also happens when the user switches tabs or
          // applications. Keep the timer running in those cases; only a real
          // document unload (pagehide/beforeunload below) pauses it.
          if (document.visibilityState === 'visible') retryPending()
        })
        window.addEventListener('pagehide', () => {
          this.pauseForPageExit()
        })
        window.addEventListener('beforeunload', () => {
          this.pauseForPageExit()
        })
        this.retryTimerId = window.setInterval(() => {
          if (this.pendingCount > 0 && document.visibilityState === 'visible') {
            retryPending()
          }
        }, 15_000)
        this.onlineListenerBound = true
      }

      try {
        if (this.active) {
          // 本地已恢复显示：outbox 重放与历史刷新全部后台进行。
          void this.syncPending()
            .then(() => this.refreshHistory())
            .catch(() => {
              // syncPending already stores a user-visible conflict message.
            })
        } else if (this.online) {
          const localPending = await localDb.sessionOutbox
            .where('owner_id')
            .equals(ownerId)
            .count()
          this.pendingCount = localPending
          // With queued snapshots the replay must land first: restoring from
          // the server before it would resurrect an outdated RUNNING state.
          if (localPending > 0) {
            await this.syncPending()
          }
          if (!this.active && this.online) {
            const serverActive = await sessionService.active()
            if (serverActive) {
              this.active = {
                id: ownerId,
                owner_id: ownerId,
                session_id: serverActive.id,
                target_seconds: this.targetSeconds,
                // Adopted from the daily item once the Today page knows it.
                base_seconds: null,
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
                null,
              )
              this.displaySeconds = snapshotDuration(this.active.snapshot)
            }
          }
          // 历史列表不影响计时显示，放后台。
          void this.refreshHistory().catch(() => {})
        }
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

    maybeNotifyTargetReached(): void {
      if (
        !this.ownerId ||
        !this.active ||
        this.active.snapshot.status !== 'RUNNING' ||
        !this.targetSeconds ||
        this.totalSeconds < this.targetSeconds
      ) {
        return
      }
      const sessionId = this.active.session_id
      if (
        this.notifiedSessionId === sessionId ||
        hasTargetNoticeMarker(this.ownerId, sessionId)
      ) {
        this.notifiedSessionId = sessionId
        return
      }

      this.notifiedSessionId = sessionId
      this.targetNotice = '已到达计划用时，计时仍在继续；请按当前进度决定何时暂停或结束。'
      writeTargetNoticeMarker(this.ownerId, sessionId)
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('DayFlow 时间提醒', {
          body: this.targetNotice,
          tag: `dayflow-target-${sessionId}`,
        })
      }
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
                this.baseSeconds,
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
          this.baseSeconds,
        )
        this.active = {
          id: this.ownerId,
          owner_id: this.ownerId,
          session_id: sessionId,
          target_seconds: this.targetSeconds,
          base_seconds: this.baseSeconds,
          snapshot,
        }
        this.displaySeconds = snapshotDuration(snapshot)
      } else {
        await clearActiveTimer(this.ownerId)
        this.active = null
        this.displaySeconds = 0
        this.baseSeconds = null
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
            this.baseSeconds,
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

    async updateTargetForTask(taskId: string, targetSeconds: number): Promise<void> {
      if (!this.ownerId || !this.active || this.active.snapshot.task_id !== taskId) return
      const sessionId = this.active.session_id
      const normalizedTarget = targetSeconds > 0 ? Math.round(targetSeconds) : null
      clearTargetNoticeMarker(this.ownerId, sessionId)
      this.targetSeconds = normalizedTarget
      this.targetNotice = ''
      this.notifiedSessionId = null
      this.active = {
        ...this.active,
        target_seconds: normalizedTarget,
      }
      await saveActiveTimer(
        this.ownerId,
        sessionId,
        this.active.snapshot,
        normalizedTarget,
      )
      if (normalizedTarget) requestSystemNotificationPermission()
      this.maybeNotifyTargetReached()
    },

    /**
     * Begin a new session. `targetSeconds` is the item's whole planned time
     * and `baseSeconds` the time it has already accumulated today, so a task
     * that was ended early keeps counting from where it stopped.
     */
    async start(
      taskId: string | null,
      dailyPlanItemId: string | null = null,
      targetSeconds: number | null = null,
      baseSeconds = 0,
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
      this.baseSeconds = Math.max(0, Math.round(baseSeconds))
      const sessionId = crypto.randomUUID()
      this.targetNotice = ''
      this.notifiedSessionId = null
      if (this.targetSeconds) requestSystemNotificationPermission()
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
        if (this.ownerId) writeTimerHeartbeat(this.ownerId, sessionId)
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

    async pause(awaitSync = false): Promise<void> {
      await this.pauseAt(new Date(), awaitSync)
    },

    /**
     * Pause a running session at a precise boundary, including midnight.
     * The local PAUSED snapshot is persisted synchronously in the busy
     * window; the network sync runs in the background so the UI never waits
     * on a remote round trip (the outbox replays it if the sync fails).
     * Pass `awaitSync` where the server state must exist before continuing,
     * e.g. right before signing out.
     */
    async pauseAt(pauseTime: Date, awaitSync = false): Promise<void> {
      if (!this.active || this.active.snapshot.status !== 'RUNNING') return
      this.busy = true
      let synced = Promise.resolve()
      try {
        const now = nextTimestamp(
          this.active.snapshot.client_updated_at,
          pauseTime.getTime(),
        )
        const snapshot: SessionSnapshot = {
          ...this.active.snapshot,
          status: 'PAUSED',
          duration_seconds: snapshotDuration(this.active.snapshot, new Date(now)),
          last_resumed_at: null,
          client_updated_at: now,
        }
        await this.persistSnapshot(this.active.session_id, snapshot, true)
        if (this.ownerId) clearTimerHeartbeat(this.ownerId)
        synced = this.syncLatestOrKeepOffline(this.active.session_id)
        if (awaitSync) await synced
        else void synced.catch(() => {})
      } finally {
        this.busy = false
      }
    },

    /**
     * A running session must not silently carry into a fresh daily plan. This
     * runs from the global timer ticker, so switching routes does not affect
     * the midnight pause rule.
     */
    async pauseForDayRollover(): Promise<void> {
      if (this.rolloverPausePending || this.active?.snapshot.status !== 'RUNNING') return
      this.rolloverPausePending = true
      try {
        await this.pauseAt(startOfLocalDate(this.observedLocalDate))
      } finally {
        this.rolloverPausePending = false
      }
    },

    pauseForPageExit(): void {
      if (
        !this.ownerId ||
        !this.active ||
        this.active.snapshot.status !== 'RUNNING'
      ) {
        return
      }
      const ownerId = this.ownerId
      const sessionId = this.active.session_id
      const now = nextTimestamp(this.active.snapshot.client_updated_at)
      const snapshot: SessionSnapshot = {
        ...this.active.snapshot,
        status: 'PAUSED',
        duration_seconds: snapshotDuration(this.active.snapshot, new Date(now)),
        last_resumed_at: null,
        client_updated_at: now,
      }
      const pending: PendingExitPause = {
        owner_id: ownerId,
        session_id: sessionId,
        target_seconds: this.targetSeconds,
        base_seconds: this.baseSeconds,
        snapshot,
      }

      // localStorage is synchronous, so this recovery marker survives even
      // when the browser stops asynchronous IndexedDB work during unload.
      writePendingExitPause(ownerId, pending)
      clearTimerHeartbeat(ownerId)
      this.active = { ...this.active, snapshot }
      this.displaySeconds = snapshot.duration_seconds

      void this.persistSnapshot(sessionId, snapshot, true)
        .then(() => {
          clearPendingExitPause(ownerId)
        })
        .catch(() => {
          // The recovery marker remains for initialize() on the next visit.
        })
      sessionService.pauseOnPageExit(sessionId, snapshot)
    },

    async resume(): Promise<void> {
      if (!this.active || this.active.snapshot.status !== 'PAUSED') return
      this.busy = true
      if (this.targetSeconds) requestSystemNotificationPermission()
      try {
        const now = nextTimestamp(this.active.snapshot.client_updated_at)
        const snapshot: SessionSnapshot = {
          ...this.active.snapshot,
          status: 'RUNNING',
          last_resumed_at: now,
          client_updated_at: now,
        }
        await this.persistSnapshot(this.active.session_id, snapshot, true)
        if (this.ownerId) writeTimerHeartbeat(this.ownerId, this.active.session_id)
        // Sync in the background: the outbox already holds the snapshot, so
        // the RUNNING state must not wait on a remote round trip.
        void this.syncLatestOrKeepOffline(this.active.session_id).catch(() => {})
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
        // The local COMPLETED snapshot is the source of truth for the UI.
        // persistSnapshot also queues it in the outbox, so the network sync
        // below must never block the busy window: it runs in the background
        // and the offline sync replays it if it fails.
        await this.persistSnapshot(sessionId, snapshot, false)
        if (this.ownerId) clearTimerHeartbeat(this.ownerId)
        if (this.ownerId) clearTargetNoticeMarker(this.ownerId, sessionId)
        this.targetSeconds = null
        this.baseSeconds = null
        this.targetNotice = ''
        this.notifiedSessionId = null
        this.completedRevision += 1
      } finally {
        this.busy = false
      }
      if (syncImmediately) {
        void this.syncLatestOrKeepOffline(sessionId)
          .then(() => this.refreshHistory())
          .catch(() => {})
      }
    },
  },
})
