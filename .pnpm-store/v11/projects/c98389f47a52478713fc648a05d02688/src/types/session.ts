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
