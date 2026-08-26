import { http } from './http'
import type {
  AnalyticsDashboard,
  AnalyticsSummary,
  HourlyFocusDistribution,
  TaskDailyResponse,
} from '@/types/analytics'

const dashboardCache = new Map<string, AnalyticsDashboard>()

export const analyticsService = {
  peekDashboard(key: string): AnalyticsDashboard | null {
    return dashboardCache.get(key) ?? null
  },
  storeDashboard(key: string, data: AnalyticsDashboard): void {
    dashboardCache.set(key, data)
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
  async dashboard(dateFrom: string, dateTo: string, today: string): Promise<AnalyticsDashboard> {
    const { data } = await http.get<AnalyticsDashboard>('/analytics/dashboard', {
      params: { date_from: dateFrom, date_to: dateTo, today },
    })
    return data
  },
}
