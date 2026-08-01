<template>
  <div class="app-page">
    <aside class="app-sidebar">
      <AppLogo />

      <nav class="app-nav" aria-label="主要导航">
        <RouterLink to="/today" title="今日计划">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 3v2m0 14v2m9-9h-2M5 12H3m14.95-6.95-1.41 1.41M7.46 16.54l-1.41 1.41m0-11.9 1.41 1.41m9.08 9.08 1.41 1.41M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"
            />
          </svg>
          <span>今日计划</span>
        </RouterLink>
        <RouterLink to="/tasks" title="学习任务">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15Zm0 15A2.5 2.5 0 0 1 6.5 18H20M8 7h8m-8 4h5"
            />
          </svg>
          <span>学习任务</span>
        </RouterLink>
        <RouterLink to="/analytics" title="学习统计">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 20V10m5.33 10V4M14.67 20v-8M20 20v-13" />
          </svg>
          <span>学习统计</span>
        </RouterLink>
        <RouterLink to="/partners" title="学习伙伴">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M16 19c0-2.2-1.8-4-4-4s-4 1.8-4 4m8 0h3c0-2.2-1.8-4-4-4m-9 4H3c0-2.2 1.8-4 4-4m5-1a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm6.5 0a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z"
            />
          </svg>
          <span>学习伙伴</span>
        </RouterLink>
        <RouterLink to="/sharing" title="计划分享">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M18 8a3 3 0 1 0-2.83-4H15a3 3 0 0 0 .17 1L8.9 8.35a3 3 0 1 0 0 3.3l6.25 3.35a3 3 0 1 0 .83-1.6L9.73 10.05a3 3 0 0 0 0-2.1l6.25-3.35A3 3 0 0 0 18 8Z"
            />
          </svg>
          <span>计划分享</span>
        </RouterLink>
        <RouterLink class="notification-link" to="/notifications" title="通知">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M18 9a6 6 0 1 0-12 0c0 6-2.5 7-2.5 7h17S18 15 18 9Zm-8.3 10a2.5 2.5 0 0 0 4.6 0"
            />
          </svg>
          <span>通知</span>
          <i v-if="notifications.unreadCount > 0">
            {{ notifications.unreadCount > 99 ? '99+' : notifications.unreadCount }}
          </i>
        </RouterLink>
        <RouterLink to="/profile" title="个人资料">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8c0-3.3 3.1-5 7-5s7 1.7 7 5"
            />
          </svg>
          <span>个人资料</span>
        </RouterLink>
      </nav>

      <button class="app-logout" type="button" title="退出登录" @click="logout">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5m5 5H3" />
        </svg>
        <span>退出登录</span>
      </button>
    </aside>

    <div class="app-content">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import AppLogo from './AppLogo.vue'

const auth = useAuthStore()
const notifications = useNotificationStore()
const router = useRouter()

onMounted(() => {
  const ownerId = auth.user?.profile.id
  if (ownerId) {
    void notifications.initialize(ownerId).catch(() => {
      // The notification center can retry independently without blocking the page.
    })
  }
})

async function logout(): Promise<void> {
  notifications.disconnect()
  auth.logout()
  await router.replace('/login')
}
</script>
