<template>
  <AuthLayout>
    <header class="form-header">
      <p class="eyebrow">欢迎回来</p>
      <h2>登录账户</h2>
      <p>继续管理你的项目与任务时间预算。</p>
    </header>

    <form class="form-stack" @submit.prevent="submit">
      <label class="field">
        <span>邮箱</span>
        <input
          v-model.trim="form.email"
          type="email"
          autocomplete="email"
          required
          placeholder="name@example.com"
        />
      </label>

      <label class="field">
        <span>密码</span>
        <input
          v-model="form.password"
          type="password"
          autocomplete="current-password"
          required
          placeholder="请输入密码"
        />
      </label>

      <FormMessage :message="errorMessage" />

      <button class="button button--primary" type="submit" :disabled="auth.loading">
        {{ auth.loading ? '登录中…' : '登录' }}
      </button>
    </form>

    <p class="form-footer">
      还没有账户？
      <RouterLink to="/register">创建账户</RouterLink>
    </p>
  </AuthLayout>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'

import AuthLayout from '@/components/AuthLayout.vue'
import FormMessage from '@/components/FormMessage.vue'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/utils/api-error'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const errorMessage = ref('')
const form = reactive({
  email: '',
  password: '',
})

async function submit(): Promise<void> {
  errorMessage.value = ''
  try {
    await auth.login(form)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/today'
    await router.replace(redirect)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}
</script>
