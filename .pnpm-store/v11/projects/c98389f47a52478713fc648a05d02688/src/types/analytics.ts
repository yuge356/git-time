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

export interface HourlyFocusPoint {
  hour: number
  seconds: number
}

export interface HourlyFocusDistribution {
  date: string
  total_seconds: number
  hours: HourlyFocusPoint[]
}

export interface TaskDailyPoint {
  date: string
  seconds: number
}

export interface TaskDailySeries {
  task_id: string | null
  title: string
  total_seconds: number
  daily: TaskDailyPoint[]
}

export interface TaskDailyResponse {
  date_from: string
  date_to: string
  tasks: TaskDailySeries[]
}

export interface GanttChartRow {
  id: string
  title: string
  totalSeconds: number
  firstDate: string
  lastDate: string
  days: TaskDailyPoint[]
}

export interface BudgetComparison {
  task_id: string
  title: string
  estimated_seconds: number
  actual_seconds: number
  deviation_seconds: number
  usage_ratio: number | null
}

export interface ProjectTimeHistory {
  project_id: string
  title: string
  seconds: number
  session_count: number
  task_count: number
  last_tracked_at: string
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
  project_history: ProjectTimeHistory[]
}

export interface AnalyticsDashboard {
  range_summary: AnalyticsSummary
  today_summary: AnalyticsSummary
  today_check_in: import('@/types/daily-plan').CheckIn
}
