export type TaskStatus = 'TODO' | 'IN_PROGRESS' | 'PAUSED' | 'BLOCKED' | 'DONE'

export type TaskRepeatRule = 'NONE' | 'DAILY' | 'WEEKDAYS' | 'WEEKLY' | 'MONTHLY'

export type TaskNodeType = 'PROJECT' | 'MODULE' | 'TASK'

export type TaskBudgetMode = 'ROLLUP' | 'FIXED_CAP'

export type TaskPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'

export type BudgetLevel =
  | 'NOT_SET'
  | 'NORMAL'
  | 'NEAR_LIMIT'
  | 'EXHAUSTED'
  | 'SEVERE'

export interface Task {
  id: string
  owner_id: string
  parent_id: string | null
  node_type: TaskNodeType
  title: string
  priority: TaskPriority
  due_date: string | null
  dependency_ids: string[]
  status: TaskStatus
  estimated_seconds: number
  budget_mode: TaskBudgetMode
  fixed_budget_seconds: number | null
  default_estimated_seconds: number | null
  default_repeat_rule: TaskRepeatRule | null
  default_daily_reminder_time: string | null
  repeat_rule: TaskRepeatRule
  daily_reminder_time: string | null
  repeat_end_date: string | null
  sort_order: number
  completed_at: string | null
  created_at: string
  updated_at: string
  direct_actual_seconds: number
  actual_seconds: number
  planned_seconds: number
  children_estimated_seconds: number
  is_leaf: boolean
  task_count: number
  completed_task_count: number
  progress_ratio: number | null
  budget_usage_ratio: number | null
  budget_level: BudgetLevel
}

export interface TaskCreatePayload {
  id?: string
  title: string
  parent_id: string | null
  node_type: TaskNodeType
  priority?: TaskPriority
  due_date?: string | null
  dependency_ids?: string[]
  estimated_seconds: number
  budget_mode?: TaskBudgetMode
  fixed_budget_seconds?: number | null
  default_estimated_seconds?: number | null
  default_repeat_rule?: TaskRepeatRule | null
  default_daily_reminder_time?: string | null
  repeat_rule: TaskRepeatRule
  daily_reminder_time: string | null
  repeat_end_date?: string | null
}

export interface TaskUpdatePayload {
  title?: string
  parent_id?: string | null
  priority?: TaskPriority
  due_date?: string | null
  dependency_ids?: string[]
  estimated_seconds?: number
  budget_mode?: TaskBudgetMode
  fixed_budget_seconds?: number | null
  default_estimated_seconds?: number | null
  default_repeat_rule?: TaskRepeatRule | null
  default_daily_reminder_time?: string | null
  status?: TaskStatus
  repeat_rule?: TaskRepeatRule
  daily_reminder_time?: string | null
  repeat_end_date?: string | null
}

export interface TaskNode extends Task {
  children: TaskNode[]
}

export interface TaskBulkApplyPayload {
  overwrite: boolean
  apply_estimated_seconds?: boolean
  apply_repeat_rule?: boolean
  apply_daily_reminder_time?: boolean
}

export interface TaskBulkApplyResponse {
  affected_count: number
  skipped_count: number
  tasks: Task[]
}
