import type { Notification } from '@/types/sharing'
import { http } from './http'
import { supabase } from './supabase'

export const notificationService = {
  async list(): Promise<Notification[]> {
    const { data } = await http.get<Notification[]>('/notifications')
    return data
  },

  async unreadCount(): Promise<number> {
    const { data } = await http.get<{ count: number }>('/notifications/unread-count')
    return data.count
  },

  async markRead(notificationId: string): Promise<Notification> {
    const { data } = await http.patch<Notification>(
      `/notifications/${notificationId}/read`,
    )
    return data
  },

  async socketUrl(): Promise<string | null> {
    const { data, error } = await supabase.auth.getSession()
    if (error) throw error
    const token = data.session?.access_token
    if (!token) return null
    const base = new URL(
      http.defaults.baseURL ?? '/api/v1',
      window.location.origin,
    )
    base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
    base.pathname = `${base.pathname.replace(/\/$/, '')}/ws/notifications`
    base.search = new URLSearchParams({ token }).toString()
    return base.toString()
  },
}
