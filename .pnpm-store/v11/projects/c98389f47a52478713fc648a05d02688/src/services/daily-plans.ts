import { http } from './http'
import type {
  CheckIn,
  DailyPlan,
  DailyPlanItem,
  DailyPlanItemCreate,
  DailyPlanItemUpdate,
} from '@/types/daily-plan'

export const dailyPlanService = {
  async create(planDate: string, id?: string): Promise<DailyPlan> {
    const { data } = await http.post<DailyPlan>('/daily-plans', {
      plan_date: planDate,
      ...(id ? { id } : {}),
    })
    return data
  },

  async autoPopulate(planId: string): Promise<DailyPlan> {
    const { data } = await http.post<DailyPlan>(`/daily-plans/${planId}/auto-populate`)
    return data
  },

  async readByDate(planDate: string): Promise<DailyPlan> {
    const { data } = await http.get<DailyPlan>(`/daily-plans/by-date/${planDate}`)
    return data
  },

  async addItem(planId: string, payload: DailyPlanItemCreate): Promise<DailyPlanItem> {
    const { data } = await http.post<DailyPlanItem>(
      `/daily-plans/${planId}/items`,
      payload,
    )
    return data
  },

  async updateItem(
    itemId: string,
    payload: DailyPlanItemUpdate,
  ): Promise<DailyPlanItem> {
    const { data } = await http.patch<DailyPlanItem>(
      `/daily-plan-items/${itemId}`,
      payload,
    )
    return data
  },

  async removeItem(itemId: string): Promise<void> {
    await http.delete(`/daily-plan-items/${itemId}`)
  },

  async checkIn(planDate: string): Promise<CheckIn> {
    const { data } = await http.get<CheckIn>(`/check-ins/${planDate}`)
    return data
  },
}
