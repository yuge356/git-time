<template>
  <AppShell>
    <main class="today-page">
      <section class="page-heading today-heading">
        <div>
          <p class="eyebrow">每日计划</p>
          <h1>安排今天，专注当下</h1>
          <p>把长期任务或临时事项放进当天清单，计时同步累计到任务，完成后形成连续打卡。</p>
        </div>
        <label class="field today-date">
          <span>计划日期</span>
          <input v-model="selectedDate" type="date" @change="loadSelectedDate" />
        </label>
      </section>

      <FormMessage :message="errorMessage" />

      <div v-if="!daily.online || daily.pendingCount > 0" class="sync-banner">
        <strong>{{ daily.online ? '等待同步' : '当前离线' }}</strong>
        <span>{{ daily.pendingCount }} 条任务或计划变更已保存在本机。</span>
      </div>
      <div v-if="daily.failedCount > 0" class="sync-banner sync-banner--error">
        <strong>同步受阻</strong>
        <span>
          {{ daily.failedCount }} 条变更被服务器拒绝，仍保留在本机，请检查数据后重试。
        </span>
      </div>

      <section class="check-in-grid" aria-label="当日打卡概览">
        <article class="stat-card stat-card--purple">
          <span>学习时长</span>
          <strong>{{ formatDuration(displayLearningSeconds) }}</strong>
        </article>
        <article class="stat-card stat-card--pink">
          <span>完成进度</span>
          <strong>
            {{ daily.checkIn?.completed_items ?? 0 }}/{{ daily.checkIn?.total_items ?? 0 }}
          </strong>
        </article>
        <article class="stat-card stat-card--blue">
          <span>连续打卡</span>
          <strong>{{ daily.checkIn?.streak_days ?? 0 }} 天</strong>
        </article>
      </section>

      <section class="timer-workspace">
        <article class="timer-card">
          <template v-if="timer.active">
            <header class="timer-card__header">
              <div>
                <p class="eyebrow">
                  {{ timer.active.snapshot.status === 'RUNNING' ? '正在学习' : '计时已暂停' }}
                </p>
                <h2>{{ activeTask?.title ?? activePlanItem?.title ?? '学习任务' }}</h2>
              </div>
              <span
                :class="[
                  'timer-state',
                  { 'timer-state--paused': timer.active.snapshot.status === 'PAUSED' },
                ]"
              >
                {{ timer.active.snapshot.status === 'RUNNING' ? '计时中' : '已暂停' }}
              </span>
            </header>

            <div class="timer-display" aria-live="polite">
              {{ formatTimer(timer.displaySeconds) }}
            </div>

            <div class="timer-meta">
              <span>开始于 {{ formatDate(timer.active.snapshot.started_at) }}</span>
              <span v-if="activeTask && activeTask.estimated_seconds > 0">
                任务预算 {{ formatDuration(activeTask.estimated_seconds) }} · 已用
                {{ formatDuration(activeTaskUsed) }} · 剩余
                {{ formatDuration(activeTaskRemaining) }}
              </span>
              <span v-else-if="activePlanItem && activePlanItem.estimated_seconds > 0">
                计划 {{ formatDuration(activePlanItem.estimated_seconds) }} · 剩余
                {{ formatDuration(activeItemRemaining) }}
              </span>
            </div>

            <div class="timer-actions">
              <button
                v-if="timer.active.snapshot.status === 'RUNNING'"
                class="button button--quiet"
                type="button"
                :disabled="timer.busy"
                @click="pause"
              >
                暂停
              </button>
              <button
                v-else
                class="button button--primary"
                type="button"
                :disabled="timer.busy"
                @click="resume"
              >
                恢复
              </button>
              <button
                class="button button--finish"
                type="button"
                :disabled="timer.busy"
                @click="finish"
              >
                结束学习
              </button>
            </div>
          </template>

          <template v-else>
            <header class="timer-card__header">
              <div>
                <p class="eyebrow">开始学习</p>
                <h2>选择一个任务</h2>
              </div>
            </header>

            <label class="field timer-task-select">
              <span>计时任务</span>
              <select v-model="timerTaskId" :disabled="tasks.loading">
                <option value="">请选择任务</option>
                <option v-for="task in tasks.items" :key="task.id" :value="task.id">
                  {{ task.title }}
                </option>
              </select>
            </label>

            <div class="timer-empty-display" aria-hidden="true">00:00:00</div>

            <button
              class="button button--primary timer-start-button"
              type="button"
              :disabled="!timerTaskId || timer.busy"
              @click="startTimer"
            >
              {{ timer.busy ? '启动中…' : '开始学习' }}
            </button>
          </template>
        </article>

        <aside class="session-history">
          <header>
            <p class="eyebrow">SESSION 记录</p>
            <h2>最近学习</h2>
          </header>

          <p v-if="timer.history.length === 0" class="history-empty">
            完成一次学习后，记录会显示在这里。
          </p>

          <ol v-else class="history-list">
            <li v-for="session in timer.history" :key="session.id">
              <div>
                <strong>{{ taskTitle(session.task_id) }}</strong>
                <span>{{ formatDate(session.started_at) }}</span>
              </div>
              <time>{{ formatTimer(session.duration_seconds) }}</time>
            </li>
          </ol>
        </aside>
      </section>

      <section class="today-layout">
        <article class="today-card">
          <header class="today-card__header">
            <div>
              <p class="eyebrow">当日清单</p>
              <h2>{{ displayDate }}</h2>
            </div>
            <span class="completion-pill">{{ completionPercent }}%</span>
          </header>

          <p v-if="daily.loading" class="empty-state">正在读取计划…</p>
          <p v-else-if="daily.plan?.items.length === 0" class="empty-state">
            还没有计划项，从右侧添加一个长期任务或临时事项。
          </p>

          <ol v-else class="daily-item-list">
            <li
              v-for="item in daily.plan?.items"
              :key="item.id"
              :class="{ 'daily-item--timing': isTiming(item) }"
            >
              <button
                class="daily-check"
                :class="{ 'daily-check--done': item.status === 'DONE' }"
                type="button"
                :aria-label="item.status === 'DONE' ? '标记为待办' : '标记为完成'"
                :disabled="daily.saving"
                @click="toggleDone(item)"
              >
                {{ item.status === 'DONE' ? '✓' : '' }}
              </button>

              <div class="daily-item-main">
                <strong :class="{ 'is-complete': item.status === 'DONE' }">
                  {{ item.title }}
                </strong>
                <span>
                  计划 {{ formatDuration(item.estimated_seconds) }} · 已学习
                  {{ formatDuration(displayActual(item)) }}
                  <template v-if="remainingLabel(item)"> · {{ remainingLabel(item) }}</template>
                </span>
              </div>

              <select
                :value="item.status"
                class="daily-status"
                :disabled="daily.saving"
                :aria-label="`${item.title}状态`"
                @change="changeStatus(item, $event)"
              >
                <option value="TODO">待办</option>
                <option value="IN_PROGRESS">进行中</option>
                <option value="PAUSED">已暂停</option>
                <option value="DONE">已完成</option>
              </select>

              <button
                class="button button--primary button--small"
                type="button"
                :disabled="timer.busy || Boolean(timer.active) || item.status === 'DONE'"
                @click="startItem(item)"
              >
                {{ isTiming(item) ? '计时中' : '计时' }}
              </button>
              <button
                class="button button--quiet button--small"
                type="button"
                :disabled="daily.saving"
                @click="removeItem(item)"
              >
                删除
              </button>
            </li>
          </ol>
        </article>

        <aside class="today-card today-add-card">
          <header>
            <p class="eyebrow">添加计划项</p>
            <h2>今天准备做什么？</h2>
          </header>

          <div class="segmented-control" role="group" aria-label="计划项类型">
            <button
              type="button"
              :class="{ active: itemKind === 'task' }"
              @click="itemKind = 'task'"
            >
              长期任务
            </button>
            <button
              type="button"
              :class="{ active: itemKind === 'adhoc' }"
              @click="itemKind = 'adhoc'"
            >
              临时事项
            </button>
          </div>

          <form class="today-add-form" @submit.prevent="addItem">
            <label v-if="itemKind === 'task'" class="field">
              <span>选择任务</span>
              <select v-model="planTaskId" required>
                <option value="">请选择任务</option>
                <option v-for="task in availableTasks" :key="task.id" :value="task.id">
                  {{ task.title }}
                </option>
              </select>
            </label>

            <label v-else class="field">
              <span>事项名称</span>
              <input
                v-model.trim="adHocTitle"
                maxlength="200"
                placeholder="例如：阅读课程资料"
                required
              />
            </label>

            <label class="field">
              <span>计划用时（分钟）</span>
              <input v-model.number="estimatedMinutes" type="number" min="0" max="5256000" />
              <small v-if="itemKind === 'task' && planTaskHint">{{ planTaskHint }}</small>
            </label>

            <button
              class="button button--primary"
              type="submit"
              :disabled="daily.saving || !canAdd"
            >
              {{ daily.saving ? '添加中…' : '加入今日计划' }}
            </button>
          </form>
        </aside>
      </section>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import { useAuthStore } from '@/stores/auth'
import { useDailyPlanStore } from '@/stores/daily-plans'
import { useTaskStore } from '@/stores/tasks'
import { useTimerStore } from '@/stores/timer'
import type { DailyPlanItem } from '@/types/daily-plan'
import type { TaskStatus } from '@/types/task'
import { getApiErrorMessage } from '@/utils/api-error'
import { formatDuration } from '@/utils/time'
import { formatTimer } from '@/utils/timer'

const auth = useAuthStore()
const daily = useDailyPlanStore()
const tasks = useTaskStore()
const timer = useTimerStore()
const selectedDate = ref(daily.selectedDate)
const itemKind = ref<'task' | 'adhoc'>('task')
const planTaskId = ref('')
const timerTaskId = ref('')
const adHocTitle = ref('')
const estimatedMinutes = ref(30)
const errorMessage = ref('')
let dayRolloverTimer: number | null = null
let lastRealDate = ''

/**
 * The daily list resets every 24 hours: while the user is viewing "today",
 * crossing midnight automatically loads the new day's fresh plan. Users
 * browsing a historical date are left untouched.
 */
function startDayRolloverWatch(): void {
  if (dayRolloverTimer !== null) return
  lastRealDate = localDateString()
  dayRolloverTimer = window.setInterval(() => {
    const today = localDateString()
    if (today === lastRealDate) return
    const wasViewingToday = selectedDate.value === lastRealDate
    lastRealDate = today
    if (wasViewingToday) {
      selectedDate.value = today
      void runAction(() => daily.load(today))
    }
  }, 30_000)
}

const completionPercent = computed(() =>
  Math.round((daily.plan?.completion_rate ?? 0) * 100),
)
const displayDate = computed(() =>
  new Date(`${selectedDate.value}T00:00:00`).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }),
)
const plannedTaskIds = computed(
  () => new Set(daily.plan?.items.flatMap((item) => (item.task_id ? [item.task_id] : []))),
)
const availableTasks = computed(() =>
  tasks.items.filter((task) => !plannedTaskIds.value.has(task.id)),
)
const canAdd = computed(() =>
  itemKind.value === 'task' ? Boolean(planTaskId.value) : Boolean(adHocTitle.value),
)
const activeTask = computed(() =>
  tasks.items.find((task) => task.id === timer.active?.snapshot.task_id),
)
const activePlanItem = computed(() =>
  daily.plan?.items.find((item) => item.id === timer.active?.snapshot.daily_plan_item_id),
)
const planTaskHint = computed(() => {
  const task = tasks.items.find((item) => item.id === planTaskId.value)
  if (!task || task.estimated_seconds <= 0) return ''
  return `已按任务预计学习时间填入 ${formatDuration(task.estimated_seconds)}`
})

/**
 * Seconds accrued by the running timer since the last server-persisted
 * snapshot. Added on top of server-known values so learning time, budget
 * remaining and the daily list all tick live while timing — every timer
 * action re-syncs the base values from the server.
 */
const liveTimerExtra = computed(() => {
  if (!timer.active || timer.active.snapshot.status !== 'RUNNING') return 0
  return Math.max(0, timer.displaySeconds - timer.active.snapshot.duration_seconds)
})

const displayLearningSeconds = computed(
  () => (daily.checkIn?.learning_seconds ?? 0) + liveTimerExtra.value,
)

const activeTaskUsed = computed(() => {
  if (!activeTask.value) return 0
  return activeTask.value.actual_seconds + liveTimerExtra.value
})

const activeTaskRemaining = computed(() => {
  if (!activeTask.value) return 0
  return Math.max(0, activeTask.value.estimated_seconds - activeTaskUsed.value)
})

const activeItemRemaining = computed(() => {
  if (!activePlanItem.value) return 0
  return Math.max(
    0,
    activePlanItem.value.estimated_seconds -
      activePlanItem.value.actual_seconds -
      liveTimerExtra.value,
  )
})

// Selecting a task pre-fills the planned duration with the task's own
// estimated study time; the user can still adjust it afterwards.
watch(planTaskId, (taskId) => {
  const task = tasks.items.find((item) => item.id === taskId)
  if (task && task.estimated_seconds > 0) {
    estimatedMinutes.value = Math.max(1, Math.round(task.estimated_seconds / 60))
  }
})

function localDateString(date = new Date()): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

onMounted(async () => {
  startDayRolloverWatch()
  const ownerId = auth.user?.profile.id
  if (!ownerId) return
  await runAction(async () => {
    await Promise.all([
      tasks.initialize(ownerId),
      daily.initialize(ownerId),
      timer.initialize(ownerId),
    ])
  })
})

onBeforeUnmount(() => {
  if (dayRolloverTimer !== null) {
    window.clearInterval(dayRolloverTimer)
    dayRolloverTimer = null
  }
})

function liveExtra(item: DailyPlanItem): number {
  if (!isTiming(item)) return 0
  return liveTimerExtra.value
}

function displayActual(item: DailyPlanItem): number {
  return item.actual_seconds + liveExtra(item)
}

function remainingLabel(item: DailyPlanItem): string | null {
  if (item.estimated_seconds <= 0) return null
  const remaining = item.estimated_seconds - displayActual(item)
  return remaining > 0 ? `剩余 ${formatDuration(remaining)}` : '已用完计划用时'
}

function isTiming(item: DailyPlanItem): boolean {
  return timer.active?.snapshot.daily_plan_item_id === item.id
}

function taskTitle(taskId: string | null): string {
  return tasks.items.find((task) => task.id === taskId)?.title ?? '已删除任务'
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function runAction(action: () => Promise<void>): Promise<void> {
  errorMessage.value = ''
  try {
    await action()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}

/**
 * Timer sessions update task/plan actual seconds on the server — refresh
 * both stores after every timer action so budgets stay in sync.
 */
async function runTimerAction(action: () => Promise<void>): Promise<void> {
  await runAction(async () => {
    await action()
    await Promise.all([tasks.load(), daily.refresh()])
  })
}

async function loadSelectedDate(): Promise<void> {
  await runAction(() => daily.load(selectedDate.value))
}

async function addItem(): Promise<void> {
  await runAction(async () => {
    const selectedTask = tasks.items.find((task) => task.id === planTaskId.value)
    await daily.addItem({
      task_id: itemKind.value === 'task' ? planTaskId.value : null,
      ...(itemKind.value === 'adhoc'
        ? { title: adHocTitle.value }
        : selectedTask
          ? { title: selectedTask.title }
          : {}),
      estimated_seconds: Math.round(estimatedMinutes.value * 60),
    })
    planTaskId.value = ''
    adHocTitle.value = ''
  })
}

async function toggleDone(item: DailyPlanItem): Promise<void> {
  await runAction(() =>
    daily.updateItem(item.id, {
      status: item.status === 'DONE' ? 'TODO' : 'DONE',
    }),
  )
}

async function changeStatus(item: DailyPlanItem, event: Event): Promise<void> {
  const status = (event.target as HTMLSelectElement).value as TaskStatus
  await runAction(() => daily.updateItem(item.id, { status }))
}

async function startItem(item: DailyPlanItem): Promise<void> {
  await runTimerAction(async () => {
    await timer.start(item.task_id, item.id)
    if (item.status !== 'IN_PROGRESS') {
      await daily.updateItem(item.id, { status: 'IN_PROGRESS' })
    }
  })
}

async function startTimer(): Promise<void> {
  if (!timerTaskId.value) return
  await runTimerAction(() => timer.start(timerTaskId.value))
}

async function pause(): Promise<void> {
  await runTimerAction(() => timer.pause())
}

async function resume(): Promise<void> {
  await runTimerAction(() => timer.resume())
}

async function finish(): Promise<void> {
  await runTimerAction(() => timer.finish())
  timerTaskId.value = ''
}

async function removeItem(item: DailyPlanItem): Promise<void> {
  await runAction(() => daily.removeItem(item.id))
}
</script>
