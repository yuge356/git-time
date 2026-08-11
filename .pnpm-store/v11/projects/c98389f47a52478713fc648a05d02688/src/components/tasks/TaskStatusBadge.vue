<template>
  <span :class="['status-badge', `status-badge--${status.toLowerCase()}`]">
    <span class="status-badge__icon" aria-hidden="true">{{ icons[status] }}</span>
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
  BLOCKED: '阻塞',
  DONE: '已完成',
}

const icons: Record<TaskStatus, string> = {
  TODO: '○',
  IN_PROGRESS: '◐',
  PAUSED: 'Ⅱ',
  BLOCKED: '!',
  DONE: '✓',
}
</script>
