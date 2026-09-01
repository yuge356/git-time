import type { TaskStatus } from '@/types/task'

export interface DailyPlanItem {
  id: string
  daily_plan_id: string
  owner_id: string
  task_id: string | null
  title: string
  status: TaskStatus
  estimated_seconds: number
  actual_seconds: number
  sort_order: number
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface DailyPlan {
  id: string
  owner_id: string
  plan_date: string
  items: DailyPlanItem[]
  total_items: number
  completed_items: number
  completion_rate: number
  actual_seconds: number
  created_at: string
  updated_at: string
}

export interface DailyPlanItemCreate {
  id?: string
  task_id: string | null
  title?: string
  estimated_seconds?: number
}

export interface DailyPlanItemUpdate {
  title?: string
  status?: TaskStatus
  estimated_seconds?: number
  sort_order?: number
}

export interface CheckIn {
  plan_date: string
  learning_seconds: number
  completed_items: number
  total_items: number
  streak_days: number
}

/** One request's worth of "open today": the plan plus its check-in. */
export interface DailyPlanOpenResult {
  plan: DailyPlan
  check_in: CheckIn
}
