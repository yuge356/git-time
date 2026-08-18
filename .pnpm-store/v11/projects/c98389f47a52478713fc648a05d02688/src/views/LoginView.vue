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

      <div class="auth-register-method" role="group" aria-label="注册方式">
        <button
          type="button"
          :class="{ 'is-active': registrationIdentifierKind === 'phone' }"
          @click="registrationIdentifierKind = 'phone'"
        >
          手机号注册
        </button>
        <button
          type="button"
          :class="{ 'is-active': registrationIdentifierKind === 'email' }"
          @click="registrationIdentifierKind = 'email'"
        >
          邮箱注册
        </button>
      </div>

      <div v-if="registrationIdentifierKind === 'phone'" class="auth-phone-field">
        <label class="auth-country-select">
          <span class="sr-only">国家或地区号</span>
          <select v-model="selectedCountryIso" required @change="countrySelectionTouched = true">
            <option
              v-for="country in countryDialCodes"
              :key="country.iso"
              :value="country.iso"
            >
              {{ country.name }} {{ country.dialCode }}
            </option>
            <option value="OTHER">其他国家/地区</option>
          </select>
        </label>
        <label v-if="selectedCountryIso === 'OTHER'" class="auth-custom-dial-code">
          <span class="sr-only">自定义国家区号</span>
          <input
            v-model.trim="customDialCode"
            type="text"
            inputmode="tel"
            required
            pattern="\+[1-9][0-9]{0,3}"
            placeholder="+00"
          />
        </label>
        <label class="auth-login-field auth-phone-number">
          <span class="sr-only">手机号</span>
          <span class="auth-login-input">
            <input
              v-model.trim="phoneNationalNumber"
              type="tel"
              inputmode="tel"
              autocomplete="tel-national"
              required
              pattern="[0-9\s-]{6,20}"
              placeholder="输入手机号"
            />
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M7 3h3l1.5 4-2 1.5a15 15 0 0 0 6 6l1.5-2L21 14v3c0 2-2 4-4 4A14 14 0 0 1 3 7c0-2 2-4 4-4Z" />
            </svg>
          </span>
        </label>
      </div>
      <p v-if="registrationIdentifierKind === 'phone'" class="auth-phone-hint">
        已根据访问 IP 预选区号，可手动更改。不发送短信验证码。
      </p>

      <label v-else class="auth-login-field">
        <span class="sr-only">邮箱</span>
        <span class="auth-login-input">
          <input
            v-model.trim="registerForm.identifier"
            type="email"
            autocomplete="email"
            required
            placeholder="邮箱"
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
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AuthLayout from '@/components/AuthLayout.vue'
import FormMessage from '@/components/FormMessage.vue'
import { authService } from '@/services/auth'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/utils/api-error'
import {
  countryDialCode,
  countryDialCodes,
  DEFAULT_COUNTRY_ISO,
} from '@/utils/country-codes'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const mode = ref<'login' | 'register'>(route.query.mode === 'register' ? 'register' : 'login')
const errorMessage = ref('')
const helpMessage = ref('')
const registrationIdentifierKind = ref<'phone' | 'email'>('phone')
const selectedCountryIso = ref(DEFAULT_COUNTRY_ISO)
const customDialCode = ref('')
const phoneNationalNumber = ref('')
const countrySelectionTouched = ref(false)
const countryDetectionStarted = ref(false)
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

const selectedDialCode = computed(() => {
  if (selectedCountryIso.value === 'OTHER') return customDialCode.value.trim()
  return countryDialCode(selectedCountryIso.value)?.dialCode ?? '+86'
})

watch(
  () => route.query.mode,
  (nextMode) => {
    mode.value = nextMode === 'register' ? 'register' : 'login'
    errorMessage.value = ''
    helpMessage.value = ''
  },
)

watch(
  mode,
  (nextMode) => {
    if (nextMode === 'register') void detectRegistrationCountry()
  },
  { immediate: true },
)

async function detectRegistrationCountry(): Promise<void> {
  if (countryDetectionStarted.value) return
  countryDetectionStarted.value = true
  try {
    const detectedIso = (await authService.registrationCountry()).toUpperCase()
    if (!countrySelectionTouched.value && countryDialCode(detectedIso)) {
      selectedCountryIso.value = detectedIso
    }
  } catch {
    selectedCountryIso.value = DEFAULT_COUNTRY_ISO
  }
}

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
    if (registrationIdentifierKind.value === 'phone') {
      const dialCode = selectedDialCode.value.replace(/[\s-]/g, '')
      const nationalNumber = phoneNationalNumber.value.replace(/[\s-]/g, '').replace(/^0+/, '')
      if (!/^\+[1-9]\d{0,3}$/.test(dialCode) || !/^\d{6,14}$/.test(nationalNumber)) {
        errorMessage.value = '请选择国家区号并输入正确的手机号。'
        return
      }
      registerForm.identifier = `${dialCode}${nationalNumber}`
    }
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
