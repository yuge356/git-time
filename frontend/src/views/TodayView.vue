<template>
  <AppShell>
    <main class="today-page">
      <section v-if="auth.showPageIntros" class="page-heading today-heading">
        <div>
          <p class="eyebrow">今天</p>
          <h1>选一项，开始专注</h1>
          <p>{{ displayDate }}</p>
        </div>
      </section>

      <FormMessage :message="errorMessage || timer.syncError" />

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

      <div class="today-focus-grid">
        <section
          :class="[
            'focus-timer',
            { 'focus-timer--active': timer.active, 'focus-timer--paused': timer.active?.snapshot.status === 'PAUSED' },
          ]"
          aria-labelledby="focus-timer-title"
        >
          <header class="focus-timer__header">
            <div>
              <p class="eyebrow">专注计时</p>
              <h2 id="focus-timer-title">{{ timerTargetTitle }}</h2>
            </div>
            <span
              :class="[
                'timer-state',
                { 'timer-state--paused': timer.active?.snapshot.status === 'PAUSED' },
              ]"
            >
              {{ timerStateLabel }}
            </span>
          </header>

          <div class="focus-timer__body">
            <time class="focus-timer__display" aria-live="polite">
              {{ timer.active ? formatTimer(timer.displaySeconds) : '00:00:00' }}
            </time>
            <p v-if="timerTargetItem">
              已投入 {{ formatDuration(displayActual(timerTargetItem)) }}
              <template v-if="timerTargetItem.estimated_seconds > 0">
                · 计划 {{ formatDuration(timerTargetItem.estimated_seconds) }}
                · 剩余 {{ formatDuration(timerRemainingSeconds) }}
              </template>
            </p>
            <p v-else>从下方今日任务中选择一项，然后开始计时。</p>
          </div>

          <div class="focus-timer__actions">
            <template v-if="timer.active">
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
                继续
              </button>
              <button class="button button--finish" type="button" :disabled="timer.busy" @click="finish">
                结束计时
              </button>
            </template>
            <button
              v-else
              class="button button--primary"
              type="button"
              :disabled="!selectedTimerItem || timer.busy"
              @click="startSelectedItem"
            >
              {{ selectedTimerItem ? '开始计时' : '请先选择任务' }}
            </button>
          </div>
        </section>

        <section class="activity-calendar" aria-labelledby="activity-calendar-title">
          <header class="activity-calendar__header">
            <div>
              <p class="eyebrow">月度节奏</p>
              <h2 id="activity-calendar-title">计时日历</h2>
            </div>
            <div class="activity-calendar__month-control">
              <button type="button" aria-label="上一个月" @click="shiftCalendarMonth(-1)">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 7-5 5 5 5" /></svg>
              </button>
              <label>
                <span class="sr-only">选择年月</span>
                <input
                  v-model="calendarMonth"
                  type="month"
                  required
                  aria-label="选择计时日历年月"
                  @change="ensureCalendarMonth"
                />
              </label>
              <button type="button" aria-label="下一个月" @click="shiftCalendarMonth(1)">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 7 5 5-5 5" /></svg>
              </button>
            </div>
          </header>

          <div class="activity-calendar__summary">
            <strong>{{ formatCalendarDuration(calendarTotalSeconds) }}</strong>
            <span>{{ calendarActiveDays }} 个计时日</span>
          </div>

          <div class="activity-calendar__weekdays" aria-hidden="true">
            <span v-for="weekday in calendarWeekdays" :key="weekday">{{ weekday }}</span>
          </div>
          <div
            class="activity-calendar__grid"
            :class="{ 'is-loading': calendarLoading }"
            role="grid"
            :aria-label="`${calendarMonthLabel}每日计时日历`"
          >
            <span
              v-for="blank in calendarLeadingBlanks"
              :key="`blank-${blank}`"
              class="activity-calendar__blank"
              aria-hidden="true"
            />
            <div
              v-for="day in calendarDays"
              :key="day.date"
              class="activity-calendar__day"
              :class="[`heat-${day.level}`, { 'is-today': day.isToday }]"
              role="gridcell"
              :aria-label="day.label"
              :title="day.label"
            >
              <span>{{ day.day }}</span>
            </div>
          </div>

          <footer class="activity-calendar__footer">
            <span v-if="calendarError" class="activity-calendar__error">{{ calendarError }}</span>
            <span v-else>{{ calendarMonthLabel }}</span>
            <div class="activity-calendar__legend" aria-label="颜色越深表示计时越长">
              <span>少</span>
              <i v-for="level in 5" :key="level" :class="`heat-${level}`" />
              <span>多</span>
            </div>
          </footer>
        </section>
      </div>

      <section class="today-checklist">
        <header class="today-checklist__header">
          <div>
            <h2>今日任务</h2>
            <p>点击任务即可选中；色块表示已使用的计划时间。</p>
          </div>
          <div class="today-summary" aria-label="今日投入概览">
            <span><strong>{{ formatDuration(displayLearningSeconds) }}</strong> 已投入</span>
            <span><strong>{{ daily.checkIn?.completed_items ?? 0 }}/{{ daily.checkIn?.total_items ?? 0 }}</strong> 已完成</span>
            <span><strong>{{ daily.checkIn?.streak_days ?? 0 }} 天</strong> 连续打卡</span>
          </div>
        </header>

        <p v-if="daily.loading" class="empty-state">正在读取计划…</p>
        <div v-else-if="daily.plan?.items.length === 0" class="today-empty">
          <strong>今天还没有任务</strong>
          <span>从项目中挑一项任务，或添加一个临时事项。</span>
        </div>

        <TransitionGroup v-else tag="ol" name="daily-list" class="daily-item-list">
          <li
            v-for="item in orderedDailyItems"
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
                :disabled="startItemDisabled(item)"
                :title="startItemTitle(item)"
                @click="startItem(item)"
              >
                {{ startItemLabel(item) }}
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
        </TransitionGroup>

        <details class="quick-add">
          <summary>+ 添加今日任务</summary>
          <div class="quick-add__body">
            <div class="quick-add__tabs" role="group" aria-label="任务类型">
              <button type="button" :class="{ active: itemKind === 'task' }" @click="itemKind = 'task'">项目任务</button>
              <button type="button" :class="{ active: itemKind === 'adhoc' }" @click="itemKind = 'adhoc'">临时事项</button>
            </div>
            <form class="quick-add__form" @submit.prevent="addItem">
              <select v-if="itemKind === 'task'" v-model="planTaskId" class="quick-add__select" required aria-label="选择项目任务">
                <option value="">选择项目任务…</option>
                <option v-for="task in availableTasks" :key="task.id" :value="task.id">
                  {{ projectPrefixedTaskTitle(task, tasks.items) }}
                </option>
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
import { analyticsService } from '@/services/analytics'
import { useAuthStore } from '@/stores/auth'
import { useDailyPlanStore } from '@/stores/daily-plans'
import { useTaskStore } from '@/stores/tasks'
import { useTimerStore } from '@/stores/timer'
import type { DailyTrendPoint } from '@/types/analytics'
import type { DailyPlanItem } from '@/types/daily-plan'
import { getApiErrorMessage } from '@/utils/api-error'
import { projectPrefixedTaskTitle } from '@/utils/task-title'
import { formatDuration } from '@/utils/time'
import { formatTimer } from '@/utils/timer'

const auth = useAuthStore()
const daily = useDailyPlanStore()
const tasks = useTaskStore()
const timer = useTimerStore()
const todayDate = ref(localDateString())
const calendarMonth = ref(todayDate.value.slice(0, 7))
const calendarTrend = ref<DailyTrendPoint[]>([])
const calendarLoading = ref(false)
const calendarError = ref('')
const itemKind = ref<'task' | 'adhoc'>('task')
const planTaskId = ref('')
const adHocTitle = ref('')
const estimatedMinutes = ref(30)
const selectedItemId = ref('')
const errorMessage = ref('')
let dayRolloverTimer: number | null = null
let lastRealDate = ''
let calendarRequestId = 0

/**
 * The Today page always follows the real local date. Crossing midnight loads
 * the new day's plan without exposing a second historical-date selector.
 */
function startDayRolloverWatch(): void {
  if (dayRolloverTimer !== null) return
  lastRealDate = localDateString()
  dayRolloverTimer = window.setInterval(() => {
    const today = localDateString()
    if (today === lastRealDate) return
    lastRealDate = today
    todayDate.value = today
    void runAction(() => daily.load(today))
    if (calendarMonth.value === today.slice(0, 7)) {
      void loadCalendarMonth()
    }
  }, 30_000)
}

const displayDate = computed(() =>
  new Date(`${todayDate.value}T00:00:00`).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }),
)
const calendarWeekdays = ['一', '二', '三', '四', '五', '六', '日']
const calendarMonthParts = computed(() => {
  const validMonth = /^\d{4}-(0[1-9]|1[0-2])$/.test(calendarMonth.value)
    ? calendarMonth.value
    : todayDate.value.slice(0, 7)
  const [yearText, monthText] = validMonth.split('-')
  return {
    year: Number(yearText),
    month: Number(monthText),
  }
})
const calendarMonthLabel = computed(() =>
  new Date(
    calendarMonthParts.value.year,
    calendarMonthParts.value.month - 1,
    1,
  ).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long' }),
)
const calendarLeadingBlanks = computed(() => {
  const weekday = new Date(
    calendarMonthParts.value.year,
    calendarMonthParts.value.month - 1,
    1,
  ).getDay()
  return (weekday + 6) % 7
})
const calendarSecondsByDate = computed(() => {
  const secondsByDate = new Map(
    calendarTrend.value.map((point) => [point.date, point.seconds]),
  )
  if (calendarMonth.value === todayDate.value.slice(0, 7)) {
    secondsByDate.set(
      todayDate.value,
      Math.max(secondsByDate.get(todayDate.value) ?? 0, displayLearningSeconds.value),
    )
  }
  return secondsByDate
})
const calendarDays = computed(() => {
  const { year, month } = calendarMonthParts.value
  const dayCount = new Date(year, month, 0).getDate()
  return Array.from({ length: dayCount }, (_, index) => {
    const day = index + 1
    const date = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    const seconds = calendarSecondsByDate.value.get(date) ?? 0
    return {
      date,
      day,
      seconds,
      level: calendarHeatLevel(seconds),
      isToday: date === todayDate.value,
      label: `${date}，${seconds > 0 ? `计时 ${formatDuration(seconds)}` : '无计时记录'}`,
    }
  })
})
const calendarTotalSeconds = computed(() =>
  calendarDays.value.reduce((total, day) => total + day.seconds, 0),
)
const calendarActiveDays = computed(() =>
  calendarDays.value.filter((day) => day.seconds > 0).length,
)
const plannedTaskIds = computed(
  () => new Set(daily.plan?.items.flatMap((item) => (item.task_id ? [item.task_id] : []))),
)
const parentTaskIds = computed(
  () => new Set(tasks.items.flatMap((task) => (task.parent_id ? [task.parent_id] : []))),
)
const availableTasks = computed(() =>
  tasks.items.filter(
    (task) => !parentTaskIds.value.has(task.id) && !plannedTaskIds.value.has(task.id),
  ),
)
const canAdd = computed(() =>
  itemKind.value === 'task' ? Boolean(planTaskId.value) : Boolean(adHocTitle.value),
)
const orderedDailyItems = computed(() => {
  const items = [...(daily.plan?.items ?? [])]
  return items.sort((left, right) => {
    const leftTiming = isTiming(left)
    const rightTiming = isTiming(right)
    if (leftTiming !== rightTiming) return leftTiming ? -1 : 1
    const leftDone = left.status === 'DONE'
    const rightDone = right.status === 'DONE'
    if (leftDone !== rightDone) return leftDone ? 1 : -1
    if (leftDone && rightDone) {
      const completionOrder = (right.completed_at ?? '').localeCompare(left.completed_at ?? '')
      if (completionOrder !== 0) return completionOrder
    }
    if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order
    return left.created_at.localeCompare(right.created_at)
  })
})
/**
 * Seconds accrued by the running timer since the last server-persisted
 * snapshot. Added on top of server-known values so learning time, budget
 * remaining and the daily list all tick live while timing. Completed timer
 * actions update the local snapshot immediately and synchronize separately.
 */
const liveTimerExtra = computed(() => {
  if (!timer.active || timer.active.snapshot.status !== 'RUNNING') return 0
  return Math.max(0, timer.displaySeconds - timer.active.snapshot.duration_seconds)
})

const displayLearningSeconds = computed(
  () => (daily.checkIn?.learning_seconds ?? 0) + liveTimerExtra.value,
)
const selectedTimerItem = computed(() =>
  daily.plan?.items.find((item) => item.id === selectedItemId.value && item.status !== 'DONE'),
)
const activeTimerItem = computed(() =>
  daily.plan?.items.find((item) => item.id === timer.active?.snapshot.daily_plan_item_id),
)
const timerTargetItem = computed(() =>
  timer.active ? activeTimerItem.value : selectedTimerItem.value,
)
const timerTargetTitle = computed(() => {
  if (timerTargetItem.value) return timerTargetItem.value.title
  const activeTaskId = timer.active?.snapshot.task_id
  if (activeTaskId) {
    return tasks.items.find((task) => task.id === activeTaskId)?.title ?? '进行中的任务'
  }
  if (timer.active) return '进行中的临时事项'
  return '选择一个今日任务'
})
const timerStateLabel = computed(() => {
  if (!timer.active) return '等待开始'
  return timer.active.snapshot.status === 'RUNNING' ? '计时中' : '已暂停'
})
const timerRemainingSeconds = computed(() => {
  const item = timerTargetItem.value
  if (!item || item.estimated_seconds <= 0) return 0
  return Math.max(0, item.estimated_seconds - displayActual(item))
})

// Selecting a task pre-fills the planned duration with the task's own
// configured initial duration; the user can still adjust it afterwards.
// Empty projects are directly actionable, so their per-task default is the
// closest equivalent to an executable task's estimated duration. A fixed
// project budget is only used when no per-task default was configured.
watch(planTaskId, (taskId) => {
  const task = tasks.items.find((item) => item.id === taskId)
  if (!task) return
  const initialSeconds = task.estimated_seconds > 0
    ? task.estimated_seconds
    : (task.default_estimated_seconds ?? task.fixed_budget_seconds ?? 0)
  if (initialSeconds > 0) {
    estimatedMinutes.value = Math.max(1, Math.round(initialSeconds / 60))
  }
})

watch(calendarMonth, () => {
  void loadCalendarMonth()
})

watch(
  [
    () => daily.plan?.items,
    () => timer.active?.snapshot.daily_plan_item_id,
  ],
  ([items, activeId]) => {
    if (!items?.length) {
      selectedItemId.value = ''
      return
    }
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

function calendarHeatLevel(seconds: number): number {
  if (seconds <= 0) return 0
  if (seconds <= 15 * 60) return 1
  if (seconds <= 30 * 60) return 2
  if (seconds <= 60 * 60) return 3
  if (seconds <= 2 * 60 * 60) return 4
  return 5
}

function formatCalendarDuration(seconds: number): string {
  return seconds > 0 ? formatDuration(seconds) : '0 分钟'
}

function ensureCalendarMonth(): void {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(calendarMonth.value)) {
    calendarMonth.value = todayDate.value.slice(0, 7)
  }
}

function shiftCalendarMonth(offset: number): void {
  const { year, month } = calendarMonthParts.value
  const shifted = new Date(year, month - 1 + offset, 1)
  calendarMonth.value = `${shifted.getFullYear()}-${String(shifted.getMonth() + 1).padStart(2, '0')}`
}

async function loadCalendarMonth(): Promise<void> {
  const { year, month } = calendarMonthParts.value
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    return
  }
  const requestId = ++calendarRequestId
  const dateFrom = `${year}-${String(month).padStart(2, '0')}-01`
  const lastDay = new Date(year, month, 0).getDate()
  const dateTo = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  calendarLoading.value = true
  calendarError.value = ''
  calendarTrend.value = []
  try {
    const summary = await analyticsService.summary(dateFrom, dateTo)
    if (requestId === calendarRequestId) {
      calendarTrend.value = summary.daily_trend
    }
  } catch (error) {
    if (requestId === calendarRequestId) {
      calendarError.value = getApiErrorMessage(error)
    }
  } finally {
    if (requestId === calendarRequestId) {
      calendarLoading.value = false
    }
  }
}

onMounted(async () => {
  startDayRolloverWatch()
  const ownerId = auth.user?.profile.id
  if (!ownerId) return
  await runAction(async () => {
    await timer.initialize(ownerId)
    const activeItemId = timer.active?.snapshot.daily_plan_item_id ?? null
    await Promise.all([
      tasks.initialize(ownerId),
      daily.initialize(ownerId, todayDate.value, activeItemId),
      loadCalendarMonth(),
    ])
    await restoreMissingActiveItem()
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

async function restoreMissingActiveItem(): Promise<void> {
  const snapshot = timer.active?.snapshot
  if (
    !snapshot?.daily_plan_item_id ||
    daily.plan?.items.some((item) => item.id === snapshot.daily_plan_item_id)
  ) {
    return
  }
  const task = snapshot.task_id
    ? tasks.items.find((candidate) => candidate.id === snapshot.task_id)
    : null
  await daily.addItem({
    id: snapshot.daily_plan_item_id,
    task_id: snapshot.task_id,
    title: task ? projectPrefixedTaskTitle(task, tasks.items) : '进行中的临时事项',
    estimated_seconds: task?.estimated_seconds ?? timer.targetSeconds ?? 0,
  })
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

function startItemDisabled(item: DailyPlanItem): boolean {
  return (
    timer.busy
    || item.status === 'DONE'
    || timer.active?.snapshot.status === 'RUNNING'
  )
}

function startItemLabel(item: DailyPlanItem): string {
  if (timer.busy) return '处理中…'
  if (item.status === 'DONE') return '已完成'
  if (timer.active?.snapshot.status === 'PAUSED') return '切换并开始'
  if (timer.active?.snapshot.status === 'RUNNING') return '请先暂停'
  return '开始'
}

function startItemTitle(item: DailyPlanItem): string {
  if (timer.busy) return '正在处理计时状态'
  if (item.status === 'DONE') return '已完成的任务需先重新打开才能计时'
  if (timer.active?.snapshot.status === 'PAUSED') {
    return '保存当前已暂停的计时，然后开始该任务'
  }
  if (timer.active?.snapshot.status === 'RUNNING') return '请先暂停当前计时'
  return '开始该任务的计时'
}

async function runAction(action: () => Promise<void>): Promise<void> {
  errorMessage.value = ''
  try {
    await action()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}

async function runTimerAction(action: () => Promise<void>): Promise<void> {
  await runAction(async () => {
    await action()
    daily.setActiveItem(timer.active?.snapshot.daily_plan_item_id ?? null)
  })
}

async function addItem(): Promise<void> {
  await runAction(async () => {
    const selectedTask = tasks.items.find((task) => task.id === planTaskId.value)
    await daily.addItem({
      task_id: itemKind.value === 'task' ? planTaskId.value : null,
      ...(itemKind.value === 'adhoc'
        ? { title: adHocTitle.value }
        : selectedTask
          ? { title: projectPrefixedTaskTitle(selectedTask, tasks.items) }
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
  const previousItem = activeTimerItem.value
  const previousActualSeconds = previousItem ? displayActual(previousItem) : 0
  await runTimerAction(async () => {
    const remaining = item.estimated_seconds - item.actual_seconds
    const remainingSeconds = item.estimated_seconds > 0 && remaining > 0
      ? remaining
      : null
    const executableTaskId = tasks.items.some((task) => task.id === item.task_id)
      ? item.task_id
      : null
    await timer.start(executableTaskId, item.id, remainingSeconds)
    if (previousItem && previousItem.id !== item.id) {
      await daily.applyStoppedTimer(previousItem.id, previousActualSeconds)
    }
    if (item.status !== 'IN_PROGRESS') {
      await daily.updateItem(item.id, { status: 'IN_PROGRESS' })
    }
  })
}

async function startSelectedItem(): Promise<void> {
  if (!selectedTimerItem.value) return
  await startItem(selectedTimerItem.value)
}

async function pause(): Promise<void> {
  const item = activeTimerItem.value
  const actualSeconds = item ? displayActual(item) : 0
  await runTimerAction(async () => {
    await timer.pause()
    if (item) await daily.applyStoppedTimer(item.id, actualSeconds)
  })
  if (calendarMonth.value === todayDate.value.slice(0, 7)) {
    await loadCalendarMonth()
  }
}

async function resume(): Promise<void> {
  await runTimerAction(() => timer.resume())
}

async function finish(): Promise<void> {
  const item = activeTimerItem.value
  const actualSeconds = item ? displayActual(item) : 0
  await runAction(async () => {
    await timer.finish()
    daily.setActiveItem(null)
    if (item) await daily.applyFinishedTimer(item.id, actualSeconds)
  })
  if (calendarMonth.value === todayDate.value.slice(0, 7)) {
    await loadCalendarMonth()
  }
}

async function removeItem(item: DailyPlanItem): Promise<void> {
  await runAction(() => daily.removeItem(item.id))
}
</script>
