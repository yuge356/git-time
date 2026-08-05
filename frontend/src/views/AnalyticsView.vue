<template>
  <AppShell>
    <main class="analytics-page">
      <section class="analytics-hero">
        <div class="analytics-hero__copy">
          <p class="eyebrow">时间统计</p>
          <h1>让每一段投入都有回响</h1>
          <p>从周趋势、任务分布和预算偏差中，看见时间真正流向哪里。</p>
        </div>

        <form class="analytics-filter" @submit.prevent="load">
          <div class="analytics-presets" aria-label="快捷统计周期">
            <button
              v-for="preset in rangePresets"
              :key="preset.days"
              type="button"
              :class="{ 'is-active': selectedPreset === preset.days }"
              @click="applyPreset(preset.days)"
            >
              {{ preset.label }}
            </button>
          </div>
          <div class="analytics-filter__dates">
            <label>
              <span>开始</span>
              <input v-model="dateFrom" type="date" required @change="selectedPreset = null" />
            </label>
            <span class="analytics-filter__arrow" aria-hidden="true">→</span>
            <label>
              <span>结束</span>
              <input v-model="dateTo" type="date" required @change="selectedPreset = null" />
            </label>
            <button class="button button--primary" type="submit" :disabled="loading">
              {{ loading ? '统计中…' : '更新统计' }}
            </button>
          </div>
        </form>
      </section>

      <FormMessage :message="errorMessage || timer.syncError" />

      <div v-if="timer.pendingCount > 0" class="sync-banner">
        <strong>统计等待同步</strong>
        <span>
          {{ timer.pendingCount }} 条本地计时尚未写入服务器；服务恢复后会自动重试，
          当前统计暂不包含这些记录。
        </span>
      </div>

      <section class="analytics-metrics" aria-label="统计概览">
        <article class="metric-card metric-card--violet">
          <div class="metric-card__topline">
            <span class="metric-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M12 7v5l3 2"/><circle cx="12" cy="12" r="8"/></svg>
            </span>
            <span class="metric-card__tag">{{ selectedDayCount }} 天</span>
          </div>
          <strong>{{ metricDuration(summary?.total_learning_seconds ?? 0) }}</strong>
          <p>总投入时长</p>
        </article>

        <article class="metric-card metric-card--yellow">
          <div class="metric-card__topline">
            <span class="metric-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M4 19h16M7 16v-4m5 4V7m5 9V4"/></svg>
            </span>
            <span class="metric-card__tag">{{ activeDayCount }} 个活跃日</span>
          </div>
          <strong>{{ metricDuration(averageDailySeconds) }}</strong>
          <p>日均投入</p>
        </article>

        <article class="metric-card metric-card--lilac">
          <div class="metric-card__topline">
            <span class="metric-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="m7 12 3 3 7-7"/><circle cx="12" cy="12" r="8"/></svg>
            </span>
            <span class="metric-card__tag">已完成</span>
          </div>
          <strong>{{ summary?.completed_session_count ?? 0 }} 次</strong>
          <p>完成计时</p>
        </article>

        <article class="metric-card metric-card--sky">
          <div class="metric-card__topline">
            <span class="metric-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M5 19V8l7-4 7 4v11M9 19v-5h6v5"/></svg>
            </span>
            <span class="metric-card__tag">{{ taskCompletionRate }}%</span>
          </div>
          <strong>
            {{ summary?.completed_task_count ?? 0 }}/{{ summary?.total_task_count ?? 0 }}
          </strong>
          <p>完成项目任务</p>
        </article>
      </section>

      <section class="analytics-dashboard-grid">
        <article class="analytics-card analytics-card--distribution">
          <header class="analytics-card__heading">
            <div>
              <p class="eyebrow">任务分布</p>
              <h2>时间投入占比</h2>
            </div>
            <span class="analytics-card__hint">TOP {{ distributionItems.length }}</span>
          </header>

          <p v-if="distributionItems.length === 0" class="empty-state">
            暂无可分配的投入时长。
          </p>
          <div v-else class="distribution-overview">
            <div
              class="distribution-donut"
              :style="{ background: distributionGradient }"
              role="img"
              aria-label="任务投入时间占比环形图"
            >
              <div class="distribution-donut__center">
                <strong>{{ compactDuration(summary?.total_learning_seconds ?? 0) }}</strong>
                <span>总投入</span>
              </div>
            </div>
            <ol class="distribution-legend">
              <li v-for="item in distributionItems" :key="item.key">
                <span class="distribution-legend__dot" :style="{ background: item.color }" />
                <div>
                  <strong>{{ item.title }}</strong>
                  <small>{{ readableDuration(item.seconds) }}</small>
                </div>
                <b>{{ Math.round(item.percentage * 100) }}%</b>
              </li>
            </ol>
          </div>
        </article>

        <article class="analytics-card analytics-card--weekly">
          <header class="analytics-card__heading analytics-card__heading--split">
            <div>
              <p class="eyebrow">周度趋势</p>
              <h2>每周总投入时间</h2>
            </div>
            <div class="chart-summary">
              <span>周均投入</span>
              <strong>{{ readableDuration(averageWeeklySeconds) }}</strong>
            </div>
          </header>

          <p v-if="!hasDailyActivity" class="empty-state">所选日期内还没有计时记录。</p>
          <div v-else class="weekly-chart" role="img" aria-label="每周总投入时间柱状图">
            <div class="weekly-chart__grid" aria-hidden="true">
              <span v-for="line in 4" :key="line" />
            </div>
            <div class="weekly-chart__bars">
              <div v-for="point in weeklyTrend" :key="point.key" class="weekly-column">
                <span class="weekly-column__value">{{ compactDuration(point.seconds) }}</span>
                <div class="weekly-column__track">
                  <div
                    class="weekly-column__bar"
                    :style="{ height: `${weeklyHeight(point.seconds)}%` }"
                  />
                </div>
                <strong>{{ point.label }}</strong>
                <small>{{ point.range }}</small>
              </div>
            </div>
          </div>
        </article>

        <article class="analytics-card analytics-card--daily">
          <header class="analytics-card__heading analytics-card__heading--split">
            <div>
              <p class="eyebrow">每日节奏</p>
              <h2>投入时长与完成项</h2>
            </div>
            <div class="chart-legend">
              <span><i class="chart-legend__time" />投入时长</span>
              <span><i class="chart-legend__done" />完成项</span>
            </div>
          </header>
          <p v-if="!hasDailyActivity" class="empty-state">所选日期内还没有计时记录。</p>
          <div v-else class="trend-chart" role="img" aria-label="每日投入时长柱状图">
            <div v-for="point in summary?.daily_trend" :key="point.date" class="trend-column">
              <span class="trend-value">{{ compactDuration(point.seconds) }}</span>
              <div class="trend-track">
                <div class="trend-bar" :style="{ height: `${trendHeight(point.seconds)}%` }" />
              </div>
              <strong>{{ shortDate(point.date) }}</strong>
              <small>{{ point.completed_items }} 项</small>
            </div>
          </div>
        </article>

        <article class="analytics-card analytics-card--budget">
          <header class="analytics-card__heading analytics-card__heading--split">
            <div>
              <p class="eyebrow">预算偏差</p>
              <h2>计划用时与实际投入</h2>
            </div>
            <span class="analytics-card__hint">{{ summary?.budget_comparison.length ?? 0 }} 项任务</span>
          </header>
          <p v-if="summary?.budget_comparison.length === 0" class="empty-state">
            还没有设置任务预算或产生投入时长。
          </p>
          <div v-else class="budget-table-wrap">
            <table class="budget-table">
              <thead>
                <tr>
                  <th>任务</th>
                  <th>计划用时</th>
                  <th>实际投入</th>
                  <th>偏差</th>
                  <th>预算使用率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in summary?.budget_comparison" :key="item.task_id">
                  <td>{{ item.title }}</td>
                  <td>{{ readableDuration(item.estimated_seconds) }}</td>
                  <td>{{ readableDuration(item.actual_seconds) }}</td>
                  <td :class="{ 'is-over-budget': item.deviation_seconds > 0 }">
                    {{ signedDuration(item.deviation_seconds) }}
                  </td>
                  <td>
                    <div class="budget-usage">
                      <div class="budget-usage__track">
                        <span :style="{ width: `${usageWidth(item.usage_ratio)}%` }" />
                      </div>
                      <strong>
                        {{ item.usage_ratio === null ? '未设置' : `${Math.round(item.usage_ratio * 100)}%` }}
                      </strong>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import { analyticsService } from '@/services/analytics'
import { useAuthStore } from '@/stores/auth'
import { useTimerStore } from '@/stores/timer'
import type { AnalyticsSummary, DailyTrendPoint } from '@/types/analytics'
import { getApiErrorMessage } from '@/utils/api-error'

interface WeeklyTrendPoint {
  key: string
  label: string
  range: string
  seconds: number
  completedItems: number
}

interface DistributionChartItem {
  key: string
  title: string
  seconds: number
  percentage: number
  color: string
}

const rangePresets = [
  { label: '7 天', days: 7 },
  { label: '4 周', days: 28 },
  { label: '12 周', days: 84 },
] as const
const chartColors = ['#7559f5', '#ffd45f', '#83d4eb', '#b8a6ff', '#ff9cb7']

function localDateString(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseLocalDate(value: string): Date {
  return new Date(`${value}T00:00:00`)
}

function mondayOf(date: Date): Date {
  const result = new Date(date)
  const weekday = result.getDay() || 7
  result.setDate(result.getDate() - weekday + 1)
  return result
}

const today = new Date()
const defaultStart = new Date(today)
defaultStart.setDate(today.getDate() - 27)
const dateFrom = ref(localDateString(defaultStart))
const dateTo = ref(localDateString(today))
const selectedPreset = ref<number | null>(28)
const summary = ref<AnalyticsSummary | null>(null)
const auth = useAuthStore()
const timer = useTimerStore()
const loading = ref(false)
const errorMessage = ref('')

const selectedDayCount = computed(() => {
  const difference = parseLocalDate(dateTo.value).getTime() - parseLocalDate(dateFrom.value).getTime()
  return Math.max(1, Math.floor(difference / 86_400_000) + 1)
})
const maxDailySeconds = computed(() =>
  Math.max(1, ...(summary.value?.daily_trend.map((point) => point.seconds) ?? [1])),
)
const hasDailyActivity = computed(() =>
  Boolean(summary.value?.daily_trend.some((point) => point.seconds > 0)),
)
const activeDayCount = computed(
  () => summary.value?.daily_trend.filter((point) => point.seconds > 0).length ?? 0,
)
const averageDailySeconds = computed(() =>
  Math.round((summary.value?.total_learning_seconds ?? 0) / selectedDayCount.value),
)
const taskCompletionRate = computed(() => {
  const total = summary.value?.total_task_count ?? 0
  return total > 0 ? Math.round(((summary.value?.completed_task_count ?? 0) / total) * 100) : 0
})
const weeklyTrend = computed<WeeklyTrendPoint[]>(() => aggregateWeeks(summary.value?.daily_trend ?? []))
const maxWeeklySeconds = computed(() =>
  Math.max(1, ...weeklyTrend.value.map((point) => point.seconds)),
)
const averageWeeklySeconds = computed(() => {
  if (weeklyTrend.value.length === 0) return 0
  return Math.round(
    weeklyTrend.value.reduce((total, point) => total + point.seconds, 0) /
      weeklyTrend.value.length,
  )
})
const distributionItems = computed<DistributionChartItem[]>(() => {
  const source = summary.value?.task_distribution ?? []
  const visible = source.slice(0, 4).map((item, index) => ({
    key: item.task_id ?? `temporary-${index}`,
    title: item.title,
    seconds: item.seconds,
    percentage: item.percentage,
    color: chartColors[index],
  }))
  if (source.length > 4) {
    const remaining = source.slice(4)
    visible.push({
      key: 'other-tasks',
      title: '其他任务',
      seconds: remaining.reduce((total, item) => total + item.seconds, 0),
      percentage: remaining.reduce((total, item) => total + item.percentage, 0),
      color: chartColors[4],
    })
  }
  return visible
})
const distributionGradient = computed(() => {
  if (distributionItems.value.length === 0) return '#efedf8'
  let cursor = 0
  const segments = distributionItems.value.map((item) => {
    const start = cursor
    cursor = Math.min(100, cursor + item.percentage * 100)
    return `${item.color} ${start}% ${cursor}%`
  })
  if (cursor < 100) segments.push(`#efedf8 ${cursor}% 100%`)
  return `conic-gradient(${segments.join(', ')})`
})

onMounted(load)

watch(
  () => timer.completedRevision,
  () => void load(),
)

function applyPreset(days: number): void {
  const end = new Date()
  const start = new Date(end)
  start.setDate(end.getDate() - days + 1)
  dateFrom.value = localDateString(start)
  dateTo.value = localDateString(end)
  selectedPreset.value = days
  void load()
}

async function load(): Promise<void> {
  errorMessage.value = ''
  loading.value = true
  try {
    const ownerId = auth.user?.profile.id
    if (ownerId) {
      if (!timer.initialized || timer.ownerId !== ownerId) {
        await timer.initialize(ownerId)
      } else {
        await timer.syncPending()
      }
    }
    summary.value = await analyticsService.summary(dateFrom.value, dateTo.value)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function aggregateWeeks(points: DailyTrendPoint[]): WeeklyTrendPoint[] {
  const groups = new Map<string, { start: Date; dates: Date[]; seconds: number; completedItems: number }>()
  for (const point of points) {
    const date = parseLocalDate(point.date)
    const weekStart = mondayOf(date)
    const key = localDateString(weekStart)
    const current = groups.get(key) ?? {
      start: weekStart,
      dates: [],
      seconds: 0,
      completedItems: 0,
    }
    current.dates.push(date)
    current.seconds += point.seconds
    current.completedItems += point.completed_items
    groups.set(key, current)
  }
  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, group]) => {
      const first = group.dates[0] ?? group.start
      const last = group.dates[group.dates.length - 1] ?? group.start
      return {
        key,
        label: `${group.start.getMonth() + 1}/${group.start.getDate()} 周`,
        range: `${shortDate(localDateString(first))}–${shortDate(localDateString(last))}`,
        seconds: group.seconds,
        completedItems: group.completedItems,
      }
    })
}

function readableDuration(seconds: number): string {
  const minutes = Math.round(Math.max(0, seconds) / 60)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours && rest) return `${hours} 小时 ${rest} 分钟`
  if (hours) return `${hours} 小时`
  return `${rest} 分钟`
}

function metricDuration(seconds: number): string {
  const minutes = Math.round(Math.max(0, seconds) / 60)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `${rest} 分钟`
  if (rest === 0) return `${hours} 小时`
  return `${hours}时 ${rest}分`
}

function compactDuration(seconds: number): string {
  if (seconds <= 0) return '0m'
  if (seconds < 60) return '<1m'
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

function signedDuration(seconds: number): string {
  const prefix = seconds > 0 ? '+' : seconds < 0 ? '−' : ''
  return `${prefix}${readableDuration(Math.abs(seconds))}`
}

function trendHeight(seconds: number): number {
  return Math.max(seconds > 0 ? 6 : 0, (seconds / maxDailySeconds.value) * 100)
}

function weeklyHeight(seconds: number): number {
  return Math.max(seconds > 0 ? 8 : 0, (seconds / maxWeeklySeconds.value) * 100)
}

function usageWidth(ratio: number | null): number {
  if (ratio === null) return 0
  return Math.min(100, Math.max(2, ratio * 100))
}

function shortDate(value: string): string {
  return parseLocalDate(value).toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  })
}
</script>
