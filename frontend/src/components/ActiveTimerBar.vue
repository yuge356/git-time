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
      <time>{{ formatTimer(timer.totalSeconds) }}</time>
      <span v-if="timer.targetNotice" class="active-timer-bar__notice">
        {{ timer.targetNotice }}
      </span>
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
        title="停止计时并保留已记录的时长，稍后可以继续"
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
import { projectPrefixedTaskTitle } from '@/utils/task-title'
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
  const task = tasks.items.find((candidate) => candidate.id === snapshot.task_id)
  return task ? projectPrefixedTaskTitle(task, tasks.items) : '进行中的任务'
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

/**
 * Stop the session and keep the measured time without closing the task, the
 * same as 结束计时 on the Today page. Completion is always an explicit act.
 */
async function finishTimer(): Promise<void> {
  const item = activePlanItem.value
  const actualSeconds = item ? timer.totalSeconds : 0
  await runTimerAction(async () => {
    await timer.finish(false)
    if (item) await daily.applyEndedTimer(item.id, actualSeconds)
  })
}
</script>
