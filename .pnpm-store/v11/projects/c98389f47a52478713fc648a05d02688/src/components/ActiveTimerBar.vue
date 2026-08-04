<template>
  <aside v-if="timer.active" class="active-timer-bar" aria-label="正在进行的计时">
    <RouterLink class="active-timer-bar__main" to="/today" title="返回今日任务">
      <span
        :class="[
          'active-timer-bar__state',
          { 'active-timer-bar__state--paused': timer.active.snapshot.status === 'PAUSED' },
        ]"
      >
        {{ timer.active.snapshot.status === 'RUNNING' ? '计时中' : '已暂停' }}
      </span>
      <strong>{{ activeTitle }}</strong>
      <time>{{ formatTimer(timer.displaySeconds) }}</time>
    </RouterLink>

    <div class="active-timer-bar__actions">
      <button
        v-if="timer.active.snapshot.status === 'RUNNING'"
        class="button button--quiet button--small"
        type="button"
        :disabled="timer.busy"
        @click="runTimerAction(() => timer.pause())"
      >
        暂停
      </button>
      <button
        v-else
        class="button button--primary button--small"
        type="button"
        :disabled="timer.busy"
        @click="runTimerAction(() => timer.resume())"
      >
        继续
      </button>
      <button
        class="button button--finish button--small"
        type="button"
        :disabled="timer.busy"
        @click="finishTimer"
      >
        结束
      </button>
    </div>

    <span v-if="errorMessage || timer.syncError" class="active-timer-bar__error">
      {{ errorMessage || timer.syncError }}
    </span>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useDailyPlanStore } from '@/stores/daily-plans'
import { useTaskStore } from '@/stores/tasks'
import { useTimerStore } from '@/stores/timer'
import { getApiErrorMessage } from '@/utils/api-error'
import { formatTimer } from '@/utils/timer'

const auth = useAuthStore()
const daily = useDailyPlanStore()
const tasks = useTaskStore()
const timer = useTimerStore()
const errorMessage = ref('')

const activePlanItem = computed(() =>
  daily.plan?.items.find((item) => item.id === timer.active?.snapshot.daily_plan_item_id),
)

const activeTitle = computed(() => {
  const snapshot = timer.active?.snapshot
  if (!snapshot) return '进行中的任务'
  const planItem = activePlanItem.value
  if (planItem) return planItem.title
  return tasks.items.find((task) => task.id === snapshot.task_id)?.title ?? '进行中的任务'
})

onMounted(async () => {
  const ownerId = auth.user?.profile.id
  if (!ownerId) return
  try {
    await timer.initialize(ownerId)
    if (timer.active?.snapshot.task_id && tasks.ownerId !== ownerId) {
      await tasks.initialize(ownerId)
    }
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
})

async function runTimerAction(action: () => Promise<void>): Promise<void> {
  errorMessage.value = ''
  try {
    await action()
    daily.setActiveItem(timer.active?.snapshot.daily_plan_item_id ?? null)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}

async function finishTimer(): Promise<void> {
  const item = activePlanItem.value
  const liveSeconds = timer.active?.snapshot.status === 'RUNNING'
    ? Math.max(0, timer.displaySeconds - timer.active.snapshot.duration_seconds)
    : 0
  const actualSeconds = item ? item.actual_seconds + liveSeconds : 0
  await runTimerAction(async () => {
    await timer.finish()
    if (item) await daily.applyFinishedTimer(item.id, actualSeconds)
  })
}
</script>
