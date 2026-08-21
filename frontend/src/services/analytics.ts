import { http } from './http'
import type {
  AnalyticsDashboard,
  AnalyticsSummary,
  HourlyFocusDistribution,
} from '@/types/analytics'

export const analyticsService = {
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
  async dashboard(dateFrom: string, dateTo: string, today: string): Promise<AnalyticsDashboard> {
    const { data } = await http.get<AnalyticsDashboard>('/analytics/dashboard', {
      params: { date_from: dateFrom, date_to: dateTo, today },
    })
    return data
  },
}
