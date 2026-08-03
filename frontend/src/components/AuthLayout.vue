<template>
  <main class="auth-layout">
    <section class="auth-intro" aria-labelledby="product-title">
      <AppLogo />
      <div class="auth-intro__content">
        <p class="eyebrow">TIME BUDGET PROJECT TRACKER</p>
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
</script>
