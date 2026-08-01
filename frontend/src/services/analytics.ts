import { http } from './http'
import type { AnalyticsSummary } from '@/types/analytics'

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
}
