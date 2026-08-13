<template>
  <main :class="['auth-layout', { 'auth-layout--minimal': variant === 'login' }]">
    <section class="auth-intro" aria-labelledby="product-title">
      <AppLogo />

      <div v-if="variant === 'login'" class="auth-line-art" aria-hidden="true">
        <svg viewBox="0 0 760 720" role="presentation">
          <defs>
            <linearGradient id="auth-orbit-gradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#aa97ff" />
              <stop offset="1" stop-color="#5b3df5" />
            </linearGradient>
          </defs>
          <path class="auth-line-art__grid" d="M54 118H706M54 260H706M54 402H706M54 544H706" />
          <path class="auth-line-art__grid" d="M150 64V630M310 64V630M470 64V630M630 64V630" />
          <circle class="auth-line-art__orbit" cx="470" cy="304" r="190" />
          <circle class="auth-line-art__orbit auth-line-art__orbit--inner" cx="470" cy="304" r="112" />
          <path
            class="auth-line-art__accent"
            d="M281 323A190 190 0 0 1 600 163"
          />
          <path
            class="auth-line-art__curve"
            d="M56 516C168 440 220 502 312 426C392 360 446 415 518 346C574 292 628 306 706 238"
          />
          <path class="auth-line-art__hand" d="M470 304L470 205M470 304L552 352" />
          <circle class="auth-line-art__point" cx="470" cy="304" r="8" />
          <circle class="auth-line-art__point auth-line-art__point--small" cx="312" cy="426" r="5" />
          <circle class="auth-line-art__point auth-line-art__point--small" cx="600" cy="163" r="5" />
        </svg>
        <div class="auth-line-note auth-line-note--time">
          <span>08:30</span>
          <small>FOCUS WINDOW</small>
        </div>
        <div class="auth-line-note auth-line-note--progress">
          <span>72%</span>
          <small>WEEKLY RHYTHM</small>
        </div>
        <span class="auth-line-index">01&nbsp;&nbsp;—&nbsp;&nbsp;24</span>
      </div>

      <div class="auth-intro__content">
        <template v-if="variant === 'login'">
          <p class="eyebrow">TIME, INTENTIONALLY</p>
          <h1 id="product-title">让时间，成为目标的证据。</h1>
          <p>规划投入，记录专注，在每一次回顾中看见真正重要的进展。</p>
        </template>
        <template v-else>
          <p class="eyebrow">TIME BUDGET PROJECT TRACKER</p>
          <h1 id="product-title">把时间花在真正重要的目标上。</h1>
          <p>
            用预算、实际投入和进度偏差管理项目与个人任务，让每一段时间都有清晰去向。
          </p>
        </template>
      </div>
    </section>

    <section class="auth-panel">
      <div v-if="variant === 'login'" class="auth-panel__edition" aria-hidden="true">
        <span>TIME BUDGET</span>
        <i></i>
        <span>2026</span>
      </div>
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
}>(), {
  variant: 'default',
})
</script>
