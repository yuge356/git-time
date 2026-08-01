import { http } from './http'
import type {
  EncouragementType,
  ReceivedSharedPlan,
  SentPlanShare,
} from '@/types/sharing'

export const sharingService = {
  async share(
    dailyPlanId: string,
    partnerId: string,
    shareDuration: boolean,
  ): Promise<SentPlanShare> {
    const { data } = await http.post<SentPlanShare>('/plan-shares', {
      daily_plan_id: dailyPlanId,
      partner_id: partnerId,
      share_duration: shareDuration,
    })
    return data
  },

  async sent(): Promise<SentPlanShare[]> {
    const { data } = await http.get<SentPlanShare[]>('/plan-shares/sent')
    return data
  },

  async received(): Promise<ReceivedSharedPlan[]> {
    const { data } = await http.get<ReceivedSharedPlan[]>('/shared-plans')
    return data
  },

  async revoke(shareId: string): Promise<void> {
    await http.delete(`/plan-shares/${shareId}`)
  },

  async encourage(
    shareId: string,
    encouragementType: EncouragementType,
  ): Promise<void> {
    await http.post(`/plan-shares/${shareId}/encouragements`, {
      encouragement_type: encouragementType,
    })
  },
}
