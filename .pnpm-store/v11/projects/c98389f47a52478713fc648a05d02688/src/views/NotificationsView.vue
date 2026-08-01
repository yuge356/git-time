<template>
  <AppShell>
    <main class="notifications-page">
      <section class="page-heading">
        <p class="eyebrow">通知中心</p>
        <h1>伙伴与计划动态</h1>
        <p>邀请、分享、鼓励和计划项完成动态都会保存在这里。</p>
      </section>

      <FormMessage :message="errorMessage" />

      <section class="notification-card">
        <p v-if="notifications.items.length === 0" class="empty-state">暂无通知。</p>
        <ol v-else class="notification-list">
          <li
            v-for="item in notifications.items"
            :key="item.id"
            :class="{ unread: item.read_at === null }"
          >
            <span class="notification-dot" />
            <button type="button" @click="markRead(item)">
              <strong>{{ notificationTitle(item.notification_type) }}</strong>
              <span>{{ notificationBody(item) }}</span>
              <time>{{ displayTime(item.created_at) }}</time>
            </button>
          </li>
        </ol>
      </section>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import type { Notification, NotificationType } from '@/types/sharing'
import { getApiErrorMessage } from '@/utils/api-error'

const auth = useAuthStore()
const notifications = useNotificationStore()
const errorMessage = ref('')

onMounted(async () => {
  const ownerId = auth.user?.profile.id
  if (!ownerId) return
  try {
    await notifications.initialize(ownerId)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
})

const titles: Record<NotificationType, string> = {
  PARTNER_INVITE: '新的伙伴邀请',
  PARTNER_ACCEPTED: '伙伴邀请已接受',
  PLAN_SHARED: '伙伴分享了计划',
  ENCOURAGEMENT: '收到伙伴鼓励',
  TASK_COMPLETED: '伙伴完成了计划项',
}

const encouragements: Record<string, string> = {
  KEEP_GOING: '继续加油',
  GREAT_JOB: '做得很棒',
  WELL_DONE: '完成得好',
  YOU_CAN_DO_IT: '你可以的',
}

function notificationTitle(type: NotificationType): string {
  return titles[type]
}

function notificationBody(item: Notification): string {
  if (item.notification_type === 'TASK_COMPLETED') {
    return `已完成“${item.payload.item_title ?? '计划项'}”`
  }
  if (item.notification_type === 'ENCOURAGEMENT') {
    return encouragements[item.payload.encouragement_type ?? ''] ?? '伙伴为你加油'
  }
  if (item.notification_type === 'PLAN_SHARED') return '打开计划分享页查看进度'
  if (item.notification_type === 'PARTNER_INVITE') return '前往学习伙伴页处理邀请'
  return '你们现在可以互相分享每日计划'
}

function displayTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function markRead(item: Notification): Promise<void> {
  if (item.read_at !== null) return
  try {
    await notifications.markRead(item.id)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}
</script>
