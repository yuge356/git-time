<template>
  <main class="auth-layout">
    <section class="auth-intro" aria-labelledby="product-title">
      <AppLogo />
      <div class="auth-intro__content">
        <p class="eyebrow">TIME BUDGET LEARNING TRACKER</p>
        <h1 id="product-title">把时间花在整个学习目标上。</h1>
        <p>
          用预算、实际投入和进度偏差判断学习节奏，避免在单个章节投入过多时间。
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
</script>

