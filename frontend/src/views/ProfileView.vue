<template>
  <AppShell>
    <main class="profile-page">
      <section class="page-heading">
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
            <small>{{ auth.user.email }}</small>
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
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import { profileService } from '@/services/profile'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/utils/api-error'

const auth = useAuthStore()
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
  return name ? name.slice(0, 2).toUpperCase() : 'TB'
})

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
