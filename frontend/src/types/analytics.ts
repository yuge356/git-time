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
  /** 所属项目（任务树根节点）；null 表示项目已被删除或未关联项目。 */
  projectId: string | null
  projectTitle: string
  status: import('./task').TaskStatus | null
  /** 0-1 之间的投入进度；无法计算时为 null（条形按已投入实色展示）。 */
  progressRatio: number | null
  /** 有学习记录的天数。 */
  activeDays: number
  /** 首次到最后一次学习的自然日跨度。 */
  spanDays: number
  /** 计划窗口（甘特图上可拖拽调整）；null 表示尚未排期。 */
  plannedStart: string | null
  plannedEnd: string | null
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

/** Every Today-page chart, returned through a single request. */
export interface TodayOverview {
  calendar_trend: DailyTrendPoint[]
  hourly_focus: HourlyFocusDistribution
  task_daily: TaskDailyResponse
}

export interface AnalyticsDashboard {
  range_summary: AnalyticsSummary
  today_summary: AnalyticsSummary
  today_check_in: import('@/types/daily-plan').CheckIn
}
