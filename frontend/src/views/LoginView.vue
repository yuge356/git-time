<template>
  <AuthLayout variant="login" :auth-mode="mode" @switch-mode="switchMode">
    <header class="form-header">
      <h2>{{ mode === 'login' ? '登录' : '注册' }}</h2>
      <p>
        {{ mode === 'login' ? '欢迎回到 DayFlow' : '创建你的 DayFlow 账号' }}
      </p>
    </header>

    <form v-if="mode === 'login'" class="form-stack auth-login-form" @submit.prevent="submitLogin">
      <label class="auth-login-field">
        <span class="sr-only">邮箱或手机号</span>
        <span class="auth-login-input">
          <input
            v-model.trim="loginForm.identifier"
            type="text"
            autocomplete="username"
            required
            placeholder="邮箱或手机号（+86…）"
          />
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7 8a7 7 0 0 0-14 0" />
          </svg>
        </span>
      </label>

      <label class="auth-login-field">
        <span class="sr-only">密码</span>
        <span class="auth-login-input">
          <input
            v-model="loginForm.password"
            type="password"
            autocomplete="current-password"
            required
            placeholder="密码"
          />
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="5" y="10" width="14" height="10" rx="2" />
            <path d="M8 10V7a4 4 0 0 1 8 0v3" />
          </svg>
        </span>
      </label>

      <button class="auth-forgot" type="button" @click="showPasswordHelp">
        忘记密码？
      </button>

      <FormMessage :message="errorMessage" />
      <p v-if="helpMessage" class="auth-help-message" role="status">{{ helpMessage }}</p>

      <button class="button button--primary" type="submit" :disabled="auth.loading">
        {{ auth.loading ? '正在登录…' : '登录' }}
      </button>
    </form>

    <form v-else class="form-stack auth-login-form auth-register-form" @submit.prevent="submitRegister">
      <div class="auth-register-grid">
        <label class="auth-login-field">
          <span class="sr-only">用户名</span>
          <span class="auth-login-input">
            <input
              v-model.trim="registerForm.username"
              type="text"
              autocomplete="username"
              minlength="3"
              maxlength="30"
              pattern="[A-Za-z0-9_]+"
              required
              placeholder="用户名（字母、数字或下划线）"
            />
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7 8a7 7 0 0 0-14 0" />
            </svg>
          </span>
        </label>

        <label class="auth-login-field">
          <span class="sr-only">显示名称</span>
          <span class="auth-login-input">
            <input
              v-model.trim="registerForm.display_name"
              type="text"
              autocomplete="name"
              maxlength="80"
              required
              placeholder="显示名称"
            />
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 20h16M7 16l9-9 2 2-9 9-3 1 1-3Z" />
            </svg>
          </span>
        </label>
      </div>

      <label class="auth-login-field">
        <span class="sr-only">邮箱或手机号</span>
        <span class="auth-login-input">
          <input
            v-model.trim="registerForm.identifier"
            type="text"
            autocomplete="username"
            required
            placeholder="邮箱或手机号（+86…）"
          />
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <path d="m4 7 8 6 8-6" />
          </svg>
        </span>
      </label>

      <label class="auth-login-field">
        <span class="sr-only">密码</span>
        <span class="auth-login-input">
          <input
            v-model="registerForm.password"
            type="password"
            autocomplete="new-password"
            minlength="8"
            maxlength="128"
            required
            placeholder="密码（至少 8 个字符）"
          />
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="5" y="10" width="14" height="10" rx="2" />
            <path d="M8 10V7a4 4 0 0 1 8 0v3" />
          </svg>
        </span>
      </label>

      <FormMessage :message="errorMessage" />

      <button class="button button--primary" type="submit" :disabled="auth.loading">
        {{ auth.loading ? '正在创建…' : '创建账号' }}
      </button>
    </form>

    <p class="form-footer">
      {{ mode === 'login' ? '还没有账号？' : '已经有账号？' }}
      <button class="auth-mode-switch" type="button" @click="switchMode(mode === 'login' ? 'register' : 'login')">
        {{ mode === 'login' ? '注册' : '登录' }}
      </button>
    </p>
  </AuthLayout>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AuthLayout from '@/components/AuthLayout.vue'
import FormMessage from '@/components/FormMessage.vue'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/utils/api-error'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const mode = ref<'login' | 'register'>(route.query.mode === 'register' ? 'register' : 'login')
const errorMessage = ref('')
const helpMessage = ref('')
const loginForm = reactive({
  identifier: '',
  password: '',
})
const registerForm = reactive({
  identifier: '',
  username: '',
  display_name: '',
  password: '',
})

watch(
  () => route.query.mode,
  (nextMode) => {
    mode.value = nextMode === 'register' ? 'register' : 'login'
    errorMessage.value = ''
    helpMessage.value = ''
  },
)

function switchMode(nextMode: 'login' | 'register'): void {
  mode.value = nextMode
  errorMessage.value = ''
  helpMessage.value = ''
  const query = { ...route.query }
  if (nextMode === 'register') query.mode = 'register'
  else delete query.mode
  void router.replace({ name: 'login', query })
}

function showPasswordHelp(): void {
  helpMessage.value = 'MVP 阶段暂不提供密码找回，请妥善保存密码。'
}

async function submitLogin(): Promise<void> {
  errorMessage.value = ''
  helpMessage.value = ''
  try {
    await auth.login(loginForm)
    const redirect = requestedDestination()
    await router.replace(
      auth.requiresOnboarding
        ? { name: 'onboarding', query: redirect !== '/today' ? { redirect } : {} }
        : redirect,
    )
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}

async function submitRegister(): Promise<void> {
  errorMessage.value = ''
  helpMessage.value = ''
  try {
    await auth.register(registerForm)
    await router.replace({ name: 'onboarding' })
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}

function requestedDestination(): string {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')
    ? redirect
    : '/today'
}
</script>
