<template>
  <span :class="['status-badge', `status-badge--${status.toLowerCase()}`]">
    {{ labels[status] }}
  </span>
</template>

<script setup lang="ts">
import type { TaskStatus } from '@/types/task'

defineProps<{
  status: TaskStatus
}>()

const labels: Record<TaskStatus, string> = {
  TODO: '待开始',
  IN_PROGRESS: '进行中',
  PAUSED: '已暂停',
  DONE: '已完成',
}
</script>

