<template>
  <main v-if="variant === 'login'" class="auth-login-page">
    <div class="auth-login-shell">
      <section class="auth-login-intro" aria-labelledby="login-welcome-title">
        <AppLogo />

        <div class="auth-login-welcome">
          <p class="eyebrow">
            {{ authMode === 'login' ? 'WELCOME TO DAYFLOW' : 'START WITH DAYFLOW' }}
          </p>
          <h1 id="login-welcome-title">
            {{ authMode === 'login' ? 'Hello, Welcome!' : 'Create with clarity.' }}
          </h1>
          <p>
            {{ authMode === 'login' ? "Don't have an account?" : 'Already have an account?' }}
          </p>
          <button
            class="auth-login-register"
            type="button"
            @click="emit('switch-mode', authMode === 'login' ? 'register' : 'login')"
          >
            {{ authMode === 'login' ? 'Register' : 'Login' }}
          </button>
        </div>

        <p class="auth-login-tagline">PLAN · FOCUS · FLOW</p>
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
