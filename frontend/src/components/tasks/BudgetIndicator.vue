<template>
  <div class="budget-indicator">
    <div class="budget-indicator__labels">
      <span>预算 {{ formatDuration(estimatedSeconds) }}</span>
      <span v-if="estimatedSeconds > 0">
        已用 {{ actualSeconds > 0 ? formatDuration(actualSeconds) : '0 分钟' }}
      </span>
      <span v-if="estimatedSeconds > 0" class="budget-remaining">
        {{ remainingLabel }}
      </span>
    </div>
    <div
      v-if="estimatedSeconds > 0"
      class="budget-track"
      role="progressbar"
      :aria-valuenow="percentage"
      aria-valuemin="0"
      aria-valuemax="150"
      :aria-label="budgetText"
    >
      <span
        :class="['budget-track__fill', `budget-track__fill--${level.toLowerCase()}`]"
        :style="{ width: `${Math.min(percentage, 100)}%` }"
      />
    </div>
    <small v-if="actualSeconds > estimatedSeconds && estimatedSeconds > 0" class="budget-warning">
      ⚠ 已超时 {{ formatDuration(actualSeconds - estimatedSeconds) }}
    </small>
    <small v-else-if="level !== 'NORMAL' && level !== 'NOT_SET'" class="budget-warning">
      {{ levelLabels[level] }}
    </small>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { BudgetLevel } from '@/types/task'
import { formatDuration } from '@/utils/time'

const props = defineProps<{
  estimatedSeconds: number
  actualSeconds: number
  level: BudgetLevel
}>()

const percentage = computed(() => {
  if (props.estimatedSeconds <= 0) return 0
  return Math.round((props.actualSeconds / props.estimatedSeconds) * 100)
})

const remainingLabel = computed(() => {
  const remaining = props.estimatedSeconds - props.actualSeconds
  if (remaining > 0) return `剩余 ${formatDuration(remaining)}`
  if (remaining === 0) return '已达到预算'
  return `超出 ${formatDuration(Math.abs(remaining))}`
})

const budgetText = computed(() => `预算已使用 ${percentage.value}%`)

const levelLabels: Record<BudgetLevel, string> = {
  NOT_SET: '',
  NORMAL: '',
  NEAR_LIMIT: '已接近预算上限',
  EXHAUSTED: '已达到预算上限',
  SEVERE: '已严重超出预算',
}
</script>
