<template>
  <AppShell>
    <main class="profile-page">
      <section v-if="auth.showPageIntros" class="page-heading">
        <p class="eyebrow">账户设置</p>
        <h1>个人资料</h1>
        <p>这些信息用于标识你的账户；是否允许伙伴搜索由你控制。</p>
      </section>

      <section v-if="auth.user" class="profile-card">
        <div class="profile-summary">
          <div class="avatar" aria-hidden="true">
            {{ initials }}
          </div>
          <div>
            <strong>{{ auth.user.profile.display_name }}</strong>
            <span>@{{ auth.user.profile.username }}</span>
            <small>{{ accountIdentifier }}</small>
          </div>
        </div>

        <form class="form-stack" @submit.prevent="save">
          <div class="field-grid">
            <label class="field">
              <span>用户名</span>
              <input
                v-model.trim="form.username"
                type="text"
                minlength="3"
                maxlength="30"
                pattern="[A-Za-z0-9_]+"
                required
              />
            </label>

            <label class="field">
              <span>显示名称</span>
              <input v-model.trim="form.display_name" type="text" maxlength="80" required />
            </label>
          </div>

          <label class="field">
            <span>头像 URL</span>
            <input v-model.trim="form.avatar_url" type="url" maxlength="2048" placeholder="https://" />
          </label>

          <label class="field">
            <span>个人简介</span>
            <textarea v-model.trim="form.bio" maxlength="300" rows="4" />
            <small>{{ form.bio.length }}/300</small>
          </label>

          <label class="field">
            <span>时区</span>
            <input v-model.trim="form.timezone" type="text" maxlength="64" required />
            <small>使用 IANA 时区，例如 Asia/Shanghai</small>
          </label>

          <label class="toggle-row">
            <input v-model="form.is_searchable" type="checkbox" />
            <span>
              <strong>允许其他用户搜索我</strong>
              <small>关闭后，用户名不会出现在伙伴搜索结果中。</small>
            </span>
          </label>

          <FormMessage :message="errorMessage" />
          <FormMessage :message="successMessage" type="success" />

          <div class="form-actions">
            <button class="button button--primary" type="submit" :disabled="saving">
              {{ saving ? '保存中…' : '保存资料' }}
            </button>
          </div>
        </form>
      </section>

      <p v-else class="loading-state">正在加载资料…</p>

      <section class="profile-card notification-card" aria-labelledby="profile-notifications">
        <header class="notification-card__header">
          <div>
            <h2 id="profile-notifications">
              通知
              <HintIcon text="伙伴邀请、计划分享、鼓励和伙伴完成计划项的动态都会出现在这里；点击一条即可标记为已读。" />
            </h2>
            <p>
              {{ notifications.unreadCount > 0 ? `${notifications.unreadCount} 条未读` : '全部已读' }}
            </p>
          </div>
          <button
            class="button button--quiet button--small"
            type="button"
            :disabled="refreshingNotifications"
            @click="refreshNotifications"
          >
            {{ refreshingNotifications ? '刷新中…' : '刷新' }}
          </button>
        </header>

        <FormMessage :message="notificationError" />

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
import { computed, onMounted, reactive, ref } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import HintIcon from '@/components/HintIcon.vue'
import { profileService } from '@/services/profile'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import type { Notification, NotificationType } from '@/types/sharing'
import { getApiErrorMessage } from '@/utils/api-error'

const auth = useAuthStore()
const notifications = useNotificationStore()
const saving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const profile = auth.user?.profile

const form = reactive({
  username: profile?.username ?? '',
  display_name: profile?.display_name ?? '',
  avatar_url: profile?.avatar_url ?? '',
  bio: profile?.bio ?? '',
  timezone: profile?.timezone ?? 'Asia/Shanghai',
  is_searchable: profile?.is_searchable ?? true,
})

const initials = computed(() => {
  const name = auth.user?.profile.display_name.trim()
  return name ? name.slice(0, 2).toUpperCase() : 'DF'
})

const accountIdentifier = computed(() => auth.user?.phone ?? auth.user?.email ?? '')

/* ---- 通知中心：不再单独占一个页面，作为个人资料的一部分展示 ---- */

const notificationError = ref('')
const refreshingNotifications = ref(false)

onMounted(() => {
  const ownerId = auth.user?.profile.id
  if (!ownerId || notifications.initialized) return
  void notifications.initialize(ownerId).catch((error) => {
    notificationError.value = getApiErrorMessage(error)
  })
})

const notificationTitles: Record<NotificationType, string> = {
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
  return notificationTitles[type]
}

function notificationBody(item: Notification): string {
  if (item.notification_type === 'TASK_COMPLETED') {
    return `已完成“${item.payload.item_title ?? '计划项'}”`
  }
  if (item.notification_type === 'ENCOURAGEMENT') {
    return encouragements[item.payload.encouragement_type ?? ''] ?? '伙伴为你加油'
  }
  if (item.notification_type === 'PLAN_SHARED') return '打开伙伴协作页查看进度'
  if (item.notification_type === 'PARTNER_INVITE') return '前往伙伴协作页处理邀请'
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
  notificationError.value = ''
  try {
    await notifications.markRead(item.id)
  } catch (error) {
    notificationError.value = getApiErrorMessage(error)
  }
}

async function refreshNotifications(): Promise<void> {
  const ownerId = auth.user?.profile.id
  if (!ownerId) return
  refreshingNotifications.value = true
  notificationError.value = ''
  try {
    if (notifications.initialized) await notifications.refresh()
    else await notifications.initialize(ownerId)
  } catch (error) {
    notificationError.value = getApiErrorMessage(error)
  } finally {
    refreshingNotifications.value = false
  }
}

async function save(): Promise<void> {
  if (!auth.user) return
  saving.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const updated = await profileService.updateCurrent({
      username: form.username,
      display_name: form.display_name,
      avatar_url: form.avatar_url || null,
      bio: form.bio || null,
      timezone: form.timezone,
      is_searchable: form.is_searchable,
    })
    auth.user.profile = updated
    successMessage.value = '个人资料已保存。'
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    saving.value = false
  }
}

</script>
