<template>
  <main v-if="variant === 'login'" class="auth-login-page">
    <div class="auth-login-shell">
      <section class="auth-login-intro" aria-labelledby="login-welcome-title">
        <AppLogo />

        <div class="auth-login-welcome">
          <p class="eyebrow">
            {{ authMode === 'login' ? '欢迎使用 DAYFLOW' : '从 DAYFLOW 开始' }}
          </p>
          <h1 id="login-welcome-title">
            {{ authMode === 'login' ? '你好，欢迎回来' : '从清晰的计划开始' }}
          </h1>
          <p>
            {{ authMode === 'login' ? '还没有账号？' : '已经有账号？' }}
          </p>
          <button
            class="auth-login-register"
            type="button"
            @click="emit('switch-mode', authMode === 'login' ? 'register' : 'login')"
          >
            {{ authMode === 'login' ? '注册' : '登录' }}
          </button>
        </div>

        <p class="auth-login-tagline">计划 · 专注 · 流动</p>
      </section>

      <section class="auth-login-panel" aria-label="登录表单">
        <div class="auth-card">
          <slot />
        </div>
      </section>
    </div>
  </main>

  <main v-else class="auth-layout">
    <section class="auth-intro" aria-labelledby="product-title">
      <AppLogo />

      <div class="auth-intro__content">
        <p class="eyebrow">DAYFLOW PROJECT TRACKER</p>
        <h1 id="product-title">把时间花在真正重要的目标上。</h1>
        <p>
          用预算、实际投入和进度偏差管理项目与个人任务，让每一段时间都有清晰去向。
        </p>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
        <slot />
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import AppLogo from './AppLogo.vue'

withDefaults(defineProps<{
  variant?: 'default' | 'login'
  authMode?: 'login' | 'register'
}>(), {
  variant: 'default',
  authMode: 'login',
})

const emit = defineEmits<{
  'switch-mode': [mode: 'login' | 'register']
}>()
</script>
