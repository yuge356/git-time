<template>
  <AppShell>
    <main class="today-page">
      <section class="page-heading today-heading">
        <div>
          <p class="eyebrow">今天</p>
          <h1>选一项，开始专注</h1>
          <p>{{ displayDate }}</p>
        </div>
        <label class="field today-date">
          <span>切换日期</span>
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

      <section class="today-checklist">
        <header class="today-checklist__header">
          <div>
            <h2>今日任务</h2>
            <p>点击任务即可选中；色块表示已使用的计划时间。</p>
          </div>
          <div class="today-summary" aria-label="今日学习概览">
            <span><strong>{{ formatDuration(displayLearningSeconds) }}</strong> 已学习</span>
            <span><strong>{{ daily.checkIn?.completed_items ?? 0 }}/{{ daily.checkIn?.total_items ?? 0 }}</strong> 已完成</span>
            <span><strong>{{ daily.checkIn?.streak_days ?? 0 }} 天</strong> 连续打卡</span>
          </div>
        </header>

        <p v-if="daily.loading" class="empty-state">正在读取计划…</p>
        <div v-else-if="daily.plan?.items.length === 0" class="today-empty">
          <strong>今天还没有任务</strong>
          <span>从学习任务中挑一项，或添加一个临时事项。</span>
        </div>

        <ol v-else class="daily-item-list">
          <li
            v-for="item in daily.plan?.items"
            :key="item.id"
            :class="{
              'daily-item--selected': selectedItemId === item.id,
              'daily-item--timing': isTiming(item),
              'daily-item--overrun': isOverrun(item),
              'daily-item--done': item.status === 'DONE',
            }"
            :style="progressStyle(item)"
          >
            <button
              class="daily-check"
              :class="{ 'daily-check--done': item.status === 'DONE' }"
              type="button"
              :aria-label="item.status === 'DONE' ? `将${item.title}标为未完成` : `完成${item.title}`"
              :disabled="daily.saving || isTiming(item)"
              @click="toggleDone(item)"
            >
              {{ item.status === 'DONE' ? '✓' : '' }}
            </button>

            <button
              class="daily-item-main"
              type="button"
              :aria-pressed="selectedItemId === item.id"
              :disabled="item.status === 'DONE'"
              @click="selectedItemId = item.id"
            >
              <strong :class="{ 'is-complete': item.status === 'DONE' }">{{ item.title }}</strong>
              <span>
                {{ item.status === 'DONE' ? '已完成' : statusLabel(item) }}
                <template v-if="item.estimated_seconds > 0">
                  · 计划 {{ formatDuration(item.estimated_seconds) }}
                </template>
              </span>
            </button>

            <div class="daily-item-usage">
              <strong>{{ isTiming(item) ? formatTimer(timer.displaySeconds) : formatDuration(displayActual(item)) }}</strong>
              <span v-if="isOverrun(item)" class="daily-overrun">⚠ 已超时 {{ formatDuration(overrunSeconds(item)) }}</span>
              <span v-else>{{ progressPercent(item) }}% 用时</span>
            </div>

            <div class="daily-item-actions">
              <template v-if="isTiming(item)">
                <button
                  v-if="timer.active?.snapshot.status === 'RUNNING'"
                  class="button button--quiet button--small"
                  type="button"
                  :disabled="timer.busy"
                  @click="pause"
                >
                  暂停
                </button>
                <button
                  v-else
                  class="button button--primary button--small"
                  type="button"
                  :disabled="timer.busy"
                  @click="resume"
                >
                  继续
                </button>
                <button class="button button--finish button--small" type="button" :disabled="timer.busy" @click="finish">
                  结束
                </button>
              </template>
              <button
                v-else
                class="button button--small"
                :class="selectedItemId === item.id ? 'button--primary' : 'button--quiet'"
                type="button"
                :disabled="timer.busy || Boolean(timer.active) || item.status === 'DONE'"
                @click="startItem(item)"
              >
                {{ timer.active ? '计时占用中' : '开始' }}
              </button>
              <button
                class="daily-remove"
                type="button"
                :aria-label="`从今日计划移除${item.title}`"
                :disabled="daily.saving || isTiming(item)"
                @click="removeItem(item)"
              >
                ×
              </button>
            </div>
          </li>
        </ol>

        <details class="quick-add">
          <summary>+ 添加今日任务</summary>
          <div class="quick-add__body">
            <div class="quick-add__tabs" role="group" aria-label="任务类型">
              <button type="button" :class="{ active: itemKind === 'task' }" @click="itemKind = 'task'">学习任务</button>
              <button type="button" :class="{ active: itemKind === 'adhoc' }" @click="itemKind = 'adhoc'">临时事项</button>
            </div>
            <form class="quick-add__form" @submit.prevent="addItem">
              <select v-if="itemKind === 'task'" v-model="planTaskId" class="quick-add__select" required aria-label="选择学习任务">
                <option value="">选择学习任务…</option>
                <option v-for="task in availableTasks" :key="task.id" :value="task.id">{{ task.title }}</option>
              </select>
              <input v-else v-model.trim="adHocTitle" class="quick-add__input" maxlength="200" placeholder="输入临时事项…" required aria-label="临时事项名称" />
              <label class="quick-add__duration">
                <input v-model.number="estimatedMinutes" type="number" min="0" max="5256000" class="quick-add__minutes" aria-label="计划分钟数" />
                <span>分钟</span>
              </label>
              <button class="button button--primary button--small" type="submit" :disabled="daily.saving || !canAdd">
                {{ daily.saving ? '添加中…' : '添加' }}
              </button>
            </form>
          </div>
        </details>
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
const adHocTitle = ref('')
const estimatedMinutes = ref(30)
const selectedItemId = ref('')
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
  tasks.items.filter((task) => task.is_leaf && !plannedTaskIds.value.has(task.id)),
)
const canAdd = computed(() =>
  itemKind.value === 'task' ? Boolean(planTaskId.value) : Boolean(adHocTitle.value),
)
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

// Selecting a task pre-fills the planned duration with the task's own
// estimated study time; the user can still adjust it afterwards.
watch(planTaskId, (taskId) => {
  const task = tasks.items.find((item) => item.id === taskId)
  if (task && task.estimated_seconds > 0) {
    estimatedMinutes.value = Math.max(1, Math.round(task.estimated_seconds / 60))
  }
})

watch(
  () => daily.plan?.items,
  (items) => {
    if (!items?.length) {
      selectedItemId.value = ''
      return
    }
    const activeId = timer.active?.snapshot.daily_plan_item_id
    if (activeId && items.some((item) => item.id === activeId)) {
      selectedItemId.value = activeId
      return
    }
    if (!items.some((item) => item.id === selectedItemId.value && item.status !== 'DONE')) {
      selectedItemId.value = items.find((item) => item.status !== 'DONE')?.id ?? items[0]!.id
    }
  },
  { immediate: true },
)

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

function isTiming(item: DailyPlanItem): boolean {
  return timer.active?.snapshot.daily_plan_item_id === item.id
}

function progressPercent(item: DailyPlanItem): number {
  if (item.estimated_seconds <= 0) return 0
  return Math.round((displayActual(item) / item.estimated_seconds) * 100)
}

function isOverrun(item: DailyPlanItem): boolean {
  return item.estimated_seconds > 0 && displayActual(item) > item.estimated_seconds
}

function overrunSeconds(item: DailyPlanItem): number {
  return Math.max(0, displayActual(item) - item.estimated_seconds)
}

function progressStyle(item: DailyPlanItem): Record<string, string> {
  return {
    '--task-progress': `${Math.min(100, progressPercent(item))}%`,
  }
}

function statusLabel(item: DailyPlanItem): string {
  if (isTiming(item)) {
    return timer.active?.snapshot.status === 'RUNNING' ? '正在专注' : '计时已暂停'
  }
  if (item.status === 'IN_PROGRESS') return '进行中'
  if (item.status === 'PAUSED') return '已暂停'
  return '待开始'
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

async function startItem(item: DailyPlanItem): Promise<void> {
  selectedItemId.value = item.id
  await runTimerAction(async () => {
    await timer.start(item.task_id, item.id)
    if (item.status !== 'IN_PROGRESS') {
      await daily.updateItem(item.id, { status: 'IN_PROGRESS' })
    }
  })
}

async function pause(): Promise<void> {
  await runTimerAction(() => timer.pause())
}

async function resume(): Promise<void> {
  await runTimerAction(() => timer.resume())
}

async function finish(): Promise<void> {
  await runTimerAction(() => timer.finish())
}

async function removeItem(item: DailyPlanItem): Promise<void> {
  await runAction(() => daily.removeItem(item.id))
}
</script>
