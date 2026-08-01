export type SyncEntityType = 'task' | 'daily_plan' | 'daily_plan_item'
export type SyncAction = 'create' | 'update' | 'delete'

export interface SyncOperation {
  id: string
  owner_id: string
  entity_type: SyncEntityType
  entity_id: string
  action: SyncAction
  payload: Record<string, unknown>
  created_at: string
  retry_count: number
  last_error: string | null
}
