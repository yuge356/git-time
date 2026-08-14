<template>
  <div class="app-page">
    <aside class="app-sidebar">
      <AppLogo />

      <nav class="app-nav" aria-label="主要导航">
        <RouterLink to="/today" title="今日任务">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 3v2m0 14v2m9-9h-2M5 12H3m14.95-6.95-1.41 1.41M7.46 16.54l-1.41 1.41m0-11.9 1.41 1.41m9.08 9.08 1.41 1.41M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"
            />
          </svg>
          <span>今日任务</span>
        </RouterLink>
        <RouterLink to="/tasks" title="项目">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15Zm0 15A2.5 2.5 0 0 1 6.5 18H20M8 7h8m-8 4h5"
            />
          </svg>
          <span>项目</span>
        </RouterLink>
        <RouterLink to="/analytics" title="时间统计">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 20V10m5.33 10V4M14.67 20v-8M20 20v-13" />
          </svg>
          <span>时间统计</span>
        </RouterLink>
        <RouterLink to="/partners" title="伙伴协作">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M16 19c0-2.2-1.8-4-4-4s-4 1.8-4 4m8 0h3c0-2.2-1.8-4-4-4m-9 4H3c0-2.2 1.8-4 4-4m5-1a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm6.5 0a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z"
            />
          </svg>
          <span>伙伴协作</span>
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

      <button
        class="app-logout"
        type="button"
        :title="logoutError || '退出登录'"
        :disabled="loggingOut || timer.busy"
        :aria-busy="loggingOut"
        @click="logout"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5m5 5H3" />
        </svg>
        <span>{{ logoutError || (loggingOut ? '正在暂停计时…' : '退出登录') }}</span>
      </button>
    </aside>

    <div class="app-content">
      <ActiveTimerBar v-if="route.name !== 'today'" />
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import { useTimerStore } from '@/stores/timer'
import ActiveTimerBar from './ActiveTimerBar.vue'
import AppLogo from './AppLogo.vue'

const auth = useAuthStore()
const notifications = useNotificationStore()
const timer = useTimerStore()
const route = useRoute()
const router = useRouter()
const loggingOut = ref(false)
const logoutError = ref('')

onMounted(() => {
  const ownerId = auth.user?.profile.id
  if (ownerId) {
    void notifications.initialize(ownerId).catch(() => {
      // The notification center can retry independently without blocking the page.
    })
  }
})

async function logout(): Promise<void> {
  if (loggingOut.value) return
  loggingOut.value = true
  logoutError.value = ''
  try {
    const ownerId = auth.user?.profile.id
    if (ownerId && (!timer.initialized || timer.ownerId !== ownerId)) {
      await timer.initialize(ownerId)
    }
    if (timer.active?.snapshot.status === 'RUNNING') {
      try {
        // Persist the elapsed time and leave the same session resumable. Time
        // spent while signed out must never be included in the task total.
        await timer.pause()
      } catch (error) {
        // pause() writes the PAUSED snapshot locally before server sync. A
        // queued local pause is sufficient for logout; only block when the
        // timer is still actually running.
        if (timer.active?.snapshot.status === 'RUNNING') throw error
      }
    }
    notifications.disconnect()
    await auth.logout()
    await router.replace('/login')
  } catch {
    logoutError.value = '计时暂停失败，请重试'
  } finally {
    loggingOut.value = false
  }
}
</script>
