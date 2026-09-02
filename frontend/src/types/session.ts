export type SessionStatus = 'RUNNING' | 'PAUSED' | 'COMPLETED'

export interface SessionSnapshot {
  task_id: string | null
  daily_plan_item_id: string | null
  client_id: string
  status: SessionStatus
  started_at: string
  ended_at: string | null
  duration_seconds: number
  last_resumed_at: string | null
  client_updated_at: string
  complete_daily_item?: boolean
}

export interface StudySession extends SessionSnapshot {
  id: string
  owner_id: string
  created_at: string
  updated_at: string
}

export interface LocalTimerState {
  id: string
  owner_id: string
  session_id: string
  snapshot: SessionSnapshot
  target_seconds: number | null
  /**
   * Seconds the timed daily item had already accumulated when this session
   * started. The timer displays `base_seconds + session duration`, so ending
   * a task early and starting it again continues from where it stopped
   * instead of restarting at zero. `null` marks a session restored from the
   * server, whose baseline is adopted from the daily item on first render.
   */
  base_seconds: number | null
}

export interface SessionOutboxItem {
  session_id: string
  owner_id: string
  snapshot: SessionSnapshot
  retry_count: number
  last_error: string | null
}

export interface LocalMetadata {
  key: string
  value: string
}
