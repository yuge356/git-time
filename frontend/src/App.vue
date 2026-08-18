<template>
  <RouterView v-slot="{ Component, route }">
    <KeepAlive :include="['TasksView', 'TodayView']">
      <component :is="Component" :key="route.name" />
    </KeepAlive>
  </RouterView>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>
