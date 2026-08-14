import { defineStore } from 'pinia'

import { notificationService } from '@/services/notifications'
import type { Notification } from '@/types/sharing'

interface NotificationState {
  ownerId: string | null
  items: Notification[]
  unreadCount: number
  initialized: boolean
  socket: WebSocket | null
  reconnectTimer: number | null
  stopped: boolean
}

export const useNotificationStore = defineStore('notifications', {
  state: (): NotificationState => ({
    ownerId: null,
    items: [],
    unreadCount: 0,
    initialized: false,
    socket: null,
    reconnectTimer: null,
    stopped: false,
  }),

  actions: {
    async initialize(ownerId: string): Promise<void> {
      if (this.initialized && this.ownerId === ownerId) return
      this.disconnect()
      this.ownerId = ownerId
      this.stopped = false
      ;[this.items, this.unreadCount] = await Promise.all([
        notificationService.list(),
        notificationService.unreadCount(),
      ])
      this.initialized = true
      this.connect()
    },

    async connect(): Promise<void> {
      if (this.stopped || this.socket?.readyState === WebSocket.OPEN) return
      const url = await notificationService.socketUrl()
      if (!url) return
      const socket = new WebSocket(url)
      this.socket = socket
      socket.onmessage = (event) => {
        const notification = JSON.parse(event.data as string) as Notification
        if (!this.items.some((item) => item.id === notification.id)) {
          this.items.unshift(notification)
          if (notification.read_at === null) this.unreadCount += 1
        }
      }
      socket.onclose = () => {
        if (this.socket === socket) this.socket = null
        if (!this.stopped) {
          this.reconnectTimer = window.setTimeout(() => void this.connect(), 3_000)
        }
      }
    },

    async refresh(): Promise<void> {
      ;[this.items, this.unreadCount] = await Promise.all([
        notificationService.list(),
        notificationService.unreadCount(),
      ])
    },

    async markRead(notificationId: string): Promise<void> {
      const updated = await notificationService.markRead(notificationId)
      const index = this.items.findIndex((item) => item.id === notificationId)
      if (index >= 0) this.items[index] = updated
      this.unreadCount = Math.max(0, this.unreadCount - 1)
    },

    disconnect(): void {
      this.stopped = true
      if (this.reconnectTimer !== null) {
        window.clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }
      this.socket?.close()
      this.socket = null
      this.initialized = false
      this.ownerId = null
      this.items = []
      this.unreadCount = 0
    },
  },
})
