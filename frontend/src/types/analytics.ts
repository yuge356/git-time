export interface TaskTimeSlice {
  task_id: string | null
  title: string
  seconds: number
  percentage: number
}

export interface DailyTrendPoint {
  date: string
  seconds: number
  completed_items: number
}

export interface BudgetComparison {
  task_id: string
  title: string
  estimated_seconds: number
  actual_seconds: number
  deviation_seconds: number
  usage_ratio: number | null
}

export interface AnalyticsSummary {
  date_from: string
  date_to: string
  total_learning_seconds: number
  completed_session_count: number
  completed_task_count: number
  total_task_count: number
  task_distribution: TaskTimeSlice[]
  daily_trend: DailyTrendPoint[]
  budget_comparison: BudgetComparison[]
}
