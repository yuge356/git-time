import { http } from './http'
import type {
  AnalyticsDashboard,
  AnalyticsSummary,
  HourlyFocusDistribution,
  TaskDailyResponse,
  TodayOverview,
} from '@/types/analytics'

const dashboardCache = new Map<string, AnalyticsDashboard>()
// Persist dashboards so a full page reload still renders the analytics view
// instantly and refreshes in the background; keys are pruned oldest-first.
const DASHBOARD_LS_PREFIX = 'dayflow:dashboard-cache:'
const DASHBOARD_LS_LIMIT = 8

function persistDashboard(key: string, data: AnalyticsDashboard): void {
  try {
    localStorage.setItem(DASHBOARD_LS_PREFIX + key, JSON.stringify(data))
    const keys = Object.keys(localStorage)
      .filter((name) => name.startsWith(DASHBOARD_LS_PREFIX))
      .sort()
    while (keys.length > DASHBOARD_LS_LIMIT) {
      localStorage.removeItem(keys.shift()!)
    }
  } catch {
    /* storage unavailable or full */
  }
}

export const analyticsService = {
  peekDashboard(key: string): AnalyticsDashboard | null {
    const cached = dashboardCache.get(key)
    if (cached) return cached
    try {
      const raw = localStorage.getItem(DASHBOARD_LS_PREFIX + key)
      if (!raw) return null
      const parsed = JSON.parse(raw) as AnalyticsDashboard
      dashboardCache.set(key, parsed)
      return parsed
    } catch {
      return null
    }
  },
  storeDashboard(key: string, data: AnalyticsDashboard): void {
    dashboardCache.set(key, data)
    persistDashboard(key, data)
  },
  async summary(dateFrom: string, dateTo: string): Promise<AnalyticsSummary> {
    const { data } = await http.get<AnalyticsSummary>('/analytics/summary', {
      params: {
        date_from: dateFrom,
        date_to: dateTo,
      },
    })
    return data
  },
  async hourlyFocus(day: string): Promise<HourlyFocusDistribution> {
    const { data } = await http.get<HourlyFocusDistribution>('/analytics/hourly-focus', {
      params: { day },
    })
    return data
  },
  async taskDaily(dateFrom: string, dateTo: string): Promise<TaskDailyResponse> {
    const { data } = await http.get<TaskDailyResponse>('/analytics/task-daily', {
      params: {
        date_from: dateFrom,
        date_to: dateTo,
      },
    })
    return data
  },
  /**
   * Load the Today page's calendar, hourly focus and Gantt data at once.
   * Three separate requests used to compete for the backend's very small
   * database pool and regularly failed, leaving the page's charts empty.
   */
  async todayOverview(params: {
    calendarFrom: string
    calendarTo: string
    focusDay: string
    ganttFrom: string
    ganttTo: string
  }): Promise<TodayOverview> {
    const { data } = await http.get<TodayOverview>('/analytics/today-overview', {
      params: {
        calendar_from: params.calendarFrom,
        calendar_to: params.calendarTo,
        focus_day: params.focusDay,
        gantt_from: params.ganttFrom,
        gantt_to: params.ganttTo,
      },
    })
    return data
  },
  async dashboard(dateFrom: string, dateTo: string, today: string): Promise<AnalyticsDashboard> {
    const { data } = await http.get<AnalyticsDashboard>('/analytics/dashboard', {
      params: { date_from: dateFrom, date_to: dateTo, today },
    })
    return data
  },
}
