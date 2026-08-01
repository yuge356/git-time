import type { PublicProfile } from '@/types/partnership'
import type { TaskStatus } from '@/types/task'

export type EncouragementType =
  | 'KEEP_GOING'
  | 'GREAT_JOB'
  | 'WELL_DONE'
  | 'YOU_CAN_DO_IT'

export type NotificationType =
  | 'PARTNER_INVITE'
  | 'PARTNER_ACCEPTED'
  | 'PLAN_SHARED'
  | 'ENCOURAGEMENT'
  | 'TASK_COMPLETED'

export interface SentPlanShare {
  id: string
  daily_plan_id: string
  plan_date: string
  partner: PublicProfile
  share_duration: boolean
  created_at: string
}

export interface SharedPlanItem {
  id: string
  title: string
  status: TaskStatus
  estimated_seconds: number | null
  actual_seconds: number | null
}

export interface ReceivedSharedPlan {
  share_id: string
  daily_plan_id: string
  plan_date: string
  owner: PublicProfile
  share_duration: boolean
  total_items: number
  completed_items: number
  items: SharedPlanItem[]
  created_at: string
}

export interface Notification {
  id: string
  user_id: string
  actor_id: string | null
  notification_type: NotificationType
  payload: Record<string, string>
  read_at: string | null
  created_at: string
}
