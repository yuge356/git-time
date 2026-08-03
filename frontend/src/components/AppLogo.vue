<template>
  <RouterLink class="brand" to="/" aria-label="时间预算追踪器首页">
    <span class="brand__mark" aria-hidden="true">TB</span>
    <span>
      <strong>时间预算</strong>
      <small>项目与任务追踪器</small>
    </span>
  </RouterLink>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>
