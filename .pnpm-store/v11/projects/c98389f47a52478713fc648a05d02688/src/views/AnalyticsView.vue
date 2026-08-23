<template>
  <AppShell>
    <main class="analytics-page">
      <section v-if="auth.showPageIntros" class="analytics-hero">
        <div class="analytics-hero__copy">
          <p class="eyebrow">时间统计</p>
          <h1>让每一段投入都有回响</h1>
          <p>从日、周、月、年趋势、任务分布和预算偏差中，看见时间真正流向哪里。</p>
        </div>
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
            {{ todayCheckIn?.completed_items ?? 0 }}/{{ todayCheckIn?.total_items ?? 0 }}
          </strong>
          <p>完成今日任务</p>
        </article>
      </section>

      <section class="analytics-dashboard-grid">
        <article class="analytics-card analytics-card--distribution">
          <header class="analytics-card__heading">
            <div>
              <p class="eyebrow">任务分布</p>
              <h2>今日时间投入占比</h2>
            </div>
            <span class="analytics-card__hint">{{ distributionItems.length }} 个圆环</span>
          </header>

          <p v-if="distributionItems.length === 0" class="empty-state">
            今天还没有计时记录，开始学习后这里会显示今日投入分布。
          </p>
          <div v-else class="distribution-overview">
            <div class="distribution-rings">
              <svg
                viewBox="0 0 260 260"
                role="img"
                aria-labelledby="distribution-rings-title distribution-rings-description"
              >
                <title id="distribution-rings-title">任务投入进度圆环图</title>
                <desc id="distribution-rings-description">
                  每个任务对应一个圆环，彩色部分表示该任务在今日投入中的占比，每天零点自动刷新。
                </desc>
                <g
                  v-for="(item, index) in distributionItems"
                  :key="item.key"
                  class="distribution-ring"
                >
                  <circle
                    class="distribution-ring__track"
                    cx="130"
                    cy="130"
                    :r="ringRadius(index)"
                    :stroke-width="ringStrokeWidth()"
                    pathLength="100"
                  />
                  <circle
                    class="distribution-ring__progress"
                    cx="130"
                    cy="130"
                    :r="ringRadius(index)"
                    :stroke-width="ringStrokeWidth()"
                    pathLength="100"
                    :style="{
                      stroke: item.color,
                      strokeDasharray: `${ringArcLength(item.percentage)} 100`,
                    }"
                  >
                    <title>
                      {{ item.title }}：{{ readableDuration(item.seconds) }}，占比
                      {{ Math.round(item.percentage * 100) }}%
                    </title>
                  </circle>
                </g>
                <text x="130" y="124" text-anchor="middle" class="distribution-rings__total">
                  {{ compactDuration(todaySummary?.total_learning_seconds ?? 0) }}
                </text>
                <text x="130" y="145" text-anchor="middle" class="distribution-rings__label">
                  今日投入
                </text>
              </svg>
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
              <p class="eyebrow">时间趋势</p>
              <h2>{{ trendCopy.title }}</h2>
            </div>
            <div class="trend-controls">
              <div class="trend-granularity" role="group" aria-label="统计时间粒度">
                <button
                  v-for="option in trendOptions"
                  :key="option.value"
                  type="button"
                  :class="{ 'is-active': selectedGranularity === option.value }"
                  @click="selectedGranularity = option.value"
                >
                  {{ option.label }}
                </button>
              </div>
              <div class="trend-calendar">
                <button
                  class="trend-calendar__trigger"
                  type="button"
                  aria-label="选择统计日期"
                  :aria-expanded="calendarOpen"
                  :title="`${dateFrom} 至 ${dateTo}`"
                  @click="calendarOpen = !calendarOpen"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <rect x="3" y="5" width="18" height="16" rx="3" />
                    <path d="M8 3v4m8-4v4M3 10h18" />
                    <path d="M8 14h.01M12 14h.01M16 14h.01M8 17.5h.01M12 17.5h.01" />
                  </svg>
                </button>
                <form
                  v-if="calendarOpen"
                  class="trend-calendar__popover"
                  @submit.prevent="applyDateRange"
                  @keydown.esc="calendarOpen = false"
                >
                  <strong>统计日期</strong>
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
                  <div class="trend-calendar__dates">
                    <label>
                      <span>开始日期</span>
                      <input
                        v-model="dateFrom"
                        type="date"
                        required
                        @change="selectedPreset = null"
                      />
                    </label>
                    <label>
                      <span>结束日期</span>
                      <input
                        v-model="dateTo"
                        type="date"
                        required
                        @change="selectedPreset = null"
                      />
                    </label>
                  </div>
                  <button class="button button--primary" type="submit" :disabled="loading">
                    {{ loading ? '统计中…' : '应用日期' }}
                  </button>
                </form>
              </div>
            </div>
          </header>

          <p v-if="!hasDailyActivity" class="empty-state">所选日期内还没有计时记录。</p>
          <div v-else class="weekly-chart" role="img" :aria-label="`${trendCopy.title}折线图`">
            <div
              class="weekly-chart__body"
              :style="{ '--weekly-min-width': `${Math.max(trendPoints.length, 5) * 64 + 46}px` }"
            >
              <div class="trend-line-axis" aria-hidden="true">
                <span
                  v-for="(tick, index) in trendAxisTicks"
                  :key="`tick-${tick}`"
                  :style="{ top: `${trendTickY(index)}px` }"
                >
                  {{ axisDuration(tick) }}
                </span>
              </div>
              <div class="trend-line-main">
                <div class="trend-line-plot">
                  <svg
                    class="trend-line-plot__svg"
                    :viewBox="`0 0 100 ${TREND_PLOT_HEIGHT}`"
                    preserveAspectRatio="none"
                    aria-hidden="true"
                  >
                    <defs>
                      <linearGradient id="trend-area-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#7559f5" stop-opacity="0.34" />
                        <stop offset="55%" stop-color="#7559f5" stop-opacity="0.12" />
                        <stop offset="100%" stop-color="#7559f5" stop-opacity="0" />
                      </linearGradient>
                    </defs>
                    <line
                      v-for="(tick, index) in trendAxisTicks"
                      :key="`grid-${tick}`"
                      class="trend-line-plot__gridline"
                      x1="0"
                      :x2="100"
                      :y1="trendTickY(index)"
                      :y2="trendTickY(index)"
                    />
                    <path
                      class="trend-line-plot__area"
                      :d="trendAreaPath"
                      fill="url(#trend-area-gradient)"
                    />
                    <path class="trend-line-plot__line" :d="trendLinePath" />
                  </svg>
                  <button
                    v-for="(point, index) in trendPoints"
                    :key="point.key"
                    type="button"
                    class="trend-line-plot__dot"
                    :class="{ 'is-flipped': trendPointY(point.seconds) < TREND_TOOLTIP_FLIP_Y }"
                    :style="{
                      left: `${trendPointX(index)}%`,
                      top: `${trendPointY(point.seconds)}px`,
                    }"
                    :aria-label="`${point.label}，投入 ${readableDuration(point.seconds)}，完成 ${point.completedItems} 项`"
                  >
                    <span class="trend-line-plot__tooltip" aria-hidden="true">
                      <strong>{{ point.label }}</strong>
                      <span>投入 {{ readableDuration(point.seconds) }}</span>
                      <span>完成 {{ point.completedItems }} 项</span>
                    </span>
                  </button>
                </div>
                <div class="trend-line-labels" aria-hidden="true">
                  <div
                    v-for="point in trendPoints"
                    :key="`label-${point.key}`"
                    class="trend-line-labels__item"
                  >
                    <strong>{{ point.label }}</strong>
                    <small>{{ point.range }}</small>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </article>

        <section class="analytics-lower-grid">
          <article class="analytics-card analytics-card--budget">
            <header class="analytics-card__heading analytics-card__heading--split">
              <div>
                <p class="eyebrow">预算偏差</p>
                <h2>计划用时与实际投入</h2>
              </div>
              <span class="analytics-card__hint">
                {{ summary?.budget_comparison.length ?? 0 }} 项任务
              </span>
            </header>
            <p v-if="(summary?.budget_comparison.length ?? 0) === 0" class="empty-state">
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

          <article class="analytics-card analytics-card--history">
            <header class="analytics-card__heading analytics-card__heading--split">
              <div>
                <p class="eyebrow">项目历史</p>
                <h2>投入时间查询</h2>
              </div>
              <span class="analytics-card__hint">
                {{ summary?.project_history?.length ?? 0 }} 个项目
              </span>
            </header>

            <label class="project-history-search">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="11" cy="11" r="6.5" />
                <path d="m16 16 4 4" />
              </svg>
              <input
                v-model.trim="historyQuery"
                type="search"
                aria-label="搜索项目历史记录"
                placeholder="搜索项目名称…"
              />
            </label>

            <p v-if="(summary?.project_history?.length ?? 0) === 0" class="empty-state">
              所选日期范围内还没有项目投入记录。
            </p>
            <p v-else-if="filteredProjectHistory.length === 0" class="empty-state">
              没有找到“{{ historyQuery }}”相关项目。
            </p>
            <ol v-else class="project-history-list" aria-live="polite">
              <li v-for="item in filteredProjectHistory" :key="item.project_id">
                <div class="project-history-item__main">
                  <span class="project-history-item__icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <path d="M4 19V8.5A2.5 2.5 0 0 1 6.5 6H10l2 2h5.5A2.5 2.5 0 0 1 20 10.5V19" />
                      <path d="M3 19h18" />
                    </svg>
                  </span>
                  <div>
                    <strong>{{ item.title }}</strong>
                    <small>{{ item.session_count }} 次计时 · {{ item.task_count }} 个任务</small>
                  </div>
                  <b>{{ readableDuration(item.seconds) }}</b>
                </div>
                <div class="project-history-item__meta">
                  <span>最近投入 {{ formatHistoryDate(item.last_tracked_at) }}</span>
                  <span>占项目投入 {{ projectHistoryShare(item.seconds) }}%</span>
                </div>
                <div class="project-history-item__track" aria-hidden="true">
                  <span :style="{ width: `${projectHistoryWidth(item.seconds)}%` }" />
                </div>
              </li>
            </ol>
          </article>
        </section>
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
import { useTaskStore } from '@/stores/tasks'
import { useTimerStore } from '@/stores/timer'
import type {
  AnalyticsDashboard,
  AnalyticsSummary,
  DailyTrendPoint,
} from '@/types/analytics'
import type { CheckIn } from '@/types/daily-plan'
import { getApiErrorMessage } from '@/utils/api-error'

type TrendGranularity = 'day' | 'week' | 'month' | 'year'

interface TrendPoint {
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
  { label: '10 天', days: 10 },
  { label: '4 周', days: 28 },
  { label: '12 周', days: 84 },
  { label: '1 年', days: 366 },
] as const
const trendOptions: Array<{ label: string; value: TrendGranularity }> = [
  { label: '日', value: 'day' },
  { label: '周', value: 'week' },
  { label: '月', value: 'month' },
  { label: '年', value: 'year' },
]
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
// The daily bar chart defaults to the most recent 10 days; users can
// adjust the window freely through the calendar popover.
defaultStart.setDate(today.getDate() - 9)
const dateFrom = ref(localDateString(defaultStart))
const dateTo = ref(localDateString(today))
const selectedPreset = ref<number | null>(10)
// Land on the daily view so 每日投入时间 is the first thing users see.
const selectedGranularity = ref<TrendGranularity>('day')
const calendarOpen = ref(false)
const historyQuery = ref('')
const summary = ref<AnalyticsSummary | null>(null)
// Today-scoped data: powers the 完成今日任务 card and the distribution
// rings, both of which reset every day.
const todaySummary = ref<AnalyticsSummary | null>(null)
const todayCheckIn = ref<CheckIn | null>(null)
const auth = useAuthStore()
const timer = useTimerStore()
const tasksStore = useTaskStore()
const loading = ref(false)
const errorMessage = ref('')
let rolloverTimer: number | null = null
let lastRealDate = ''

const selectedDayCount = computed(() => {
  const difference = parseLocalDate(dateTo.value).getTime() - parseLocalDate(dateFrom.value).getTime()
  return Math.max(1, Math.floor(difference / 86_400_000) + 1)
})
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
  const total = todayCheckIn.value?.total_items ?? 0
  return total > 0
    ? Math.round(((todayCheckIn.value?.completed_items ?? 0) / total) * 100)
    : 0
})
const trendPoints = computed<TrendPoint[]>(() =>
  aggregateTrend(summary.value?.daily_trend ?? [], selectedGranularity.value),
)
const maxTrendSeconds = computed(() =>
  Math.max(1, ...trendPoints.value.map((point) => point.seconds)),
)
const trendAxisMaxSeconds = computed(() => {
  const minutes = Math.ceil(maxTrendSeconds.value / 60)
  if (minutes <= 15) return 15 * 60
  if (minutes <= 60) return Math.ceil(minutes / 15) * 15 * 60
  if (minutes <= 180) return Math.ceil(minutes / 30) * 30 * 60
  if (minutes <= 720) return Math.ceil(minutes / 60) * 60 * 60
  return Math.ceil(minutes / 180) * 180 * 60
})
const trendAxisTicks = computed(() =>
  [1, 0.75, 0.5, 0.25, 0].map((ratio) => Math.round(trendAxisMaxSeconds.value * ratio)),
)

const TREND_PLOT_HEIGHT = 250
const TREND_TOP_RESERVE = 44
const TREND_BOTTOM_PAD = 10
const TREND_TOOLTIP_FLIP_Y = 125

function trendTickY(index: number): number {
  const ratio = [1, 0.75, 0.5, 0.25, 0][index] ?? 0
  return Math.round(
    TREND_TOP_RESERVE
      + (1 - ratio) * (TREND_PLOT_HEIGHT - TREND_TOP_RESERVE - TREND_BOTTOM_PAD),
  )
}

function trendPointX(index: number): number {
  return ((index + 0.5) / Math.max(trendPoints.value.length, 1)) * 100
}

function trendPointY(seconds: number): number {
  const ratio = Math.min(1, Math.max(0, seconds / trendAxisMaxSeconds.value))
  return Math.round(
    TREND_TOP_RESERVE
      + (1 - ratio) * (TREND_PLOT_HEIGHT - TREND_TOP_RESERVE - TREND_BOTTOM_PAD),
  )
}

interface TrendCoord {
  x: number
  y: number
}

const trendPointCoords = computed<TrendCoord[]>(() =>
  trendPoints.value.map((point, index) => ({
    x: trendPointX(index),
    y: trendPointY(point.seconds),
  })),
)

function buildSmoothPath(coords: TrendCoord[]): string {
  if (coords.length === 0) return ''
  if (coords.length === 1) return `M ${coords[0]!.x} ${coords[0]!.y}`
  let d = `M ${coords[0]!.x} ${coords[0]!.y}`
  for (let i = 0; i < coords.length - 1; i += 1) {
    const p0 = coords[Math.max(0, i - 1)]!
    const p1 = coords[i]!
    const p2 = coords[i + 1]!
    const p3 = coords[Math.min(coords.length - 1, i + 2)]!
    const cp1x = (p1.x + (p2.x - p0.x) / 6).toFixed(2)
    const cp1y = (p1.y + (p2.y - p0.y) / 6).toFixed(2)
    const cp2x = (p2.x - (p3.x - p1.x) / 6).toFixed(2)
    const cp2y = (p2.y - (p3.y - p1.y) / 6).toFixed(2)
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`
  }
  return d
}

const trendLinePath = computed(() => buildSmoothPath(trendPointCoords.value))

const trendAreaPath = computed(() => {
  const coords = trendPointCoords.value
  const line = buildSmoothPath(coords)
  if (!line || coords.length < 2) return ''
  const baseline = TREND_PLOT_HEIGHT - TREND_BOTTOM_PAD
  return `${line} L ${coords[coords.length - 1]!.x} ${baseline} L ${coords[0]!.x} ${baseline} Z`
})
const trendCopy = computed(() => {
  const copy: Record<TrendGranularity, { title: string }> = {
    day: { title: '每日投入时间' },
    week: { title: '每周总投入时间' },
    month: { title: '每月总投入时间' },
    year: { title: '每年总投入时间' },
  }
  return copy[selectedGranularity.value]
})
const distributionItems = computed<DistributionChartItem[]>(() => {
  const source = todaySummary.value?.task_distribution ?? []
  return source.map((item, index) => ({
    key: item.task_id ?? `temporary-${index}`,
    title: item.title,
    seconds: item.seconds,
    percentage: item.percentage,
    color: chartColors[index % chartColors.length] ?? '#7559f5',
  }))
})
const filteredProjectHistory = computed(() => {
  const query = historyQuery.value.toLocaleLowerCase('zh-CN')
  const history = summary.value?.project_history ?? []
  if (!query) return history
  return history.filter((item) => item.title.toLocaleLowerCase('zh-CN').includes(query))
})
const projectHistoryTotalSeconds = computed(() =>
  (summary.value?.project_history ?? []).reduce((total, item) => total + item.seconds, 0),
)

function ringRadius(index: number): number {
  const ringCount = distributionItems.value.length
  const spacing = ringCount > 1 ? Math.min(21, 78 / (ringCount - 1)) : 0
  return 112 - index * spacing
}

function ringStrokeWidth(): number {
  const ringCount = distributionItems.value.length
  if (ringCount <= 5) return 12
  return Math.max(2.5, Math.min(12, (78 / Math.max(1, ringCount - 1)) * 0.64))
}

function ringArcLength(percentage: number): number {
  return Math.max(0, Math.min(75, percentage * 75))
}

onMounted(() => {
  startDayRolloverWatch()
  void load()
})

onBeforeUnmount(() => {
  if (rolloverTimer !== null) {
    window.clearInterval(rolloverTimer)
    rolloverTimer = null
  }
})

watch(
  () => timer.completedRevision,
  () => void load(),
)

/**
 * The 完成今日任务 card and the distribution rings are today-scoped, so at
 * midnight they must reset to the new day. A sliding preset window
 * (e.g. the default 10 days) slides along; a hand-picked custom range is
 * left untouched.
 */
function startDayRolloverWatch(): void {
  if (rolloverTimer !== null) return
  lastRealDate = localDateString(new Date())
  rolloverTimer = window.setInterval(() => {
    const now = localDateString(new Date())
    if (now === lastRealDate) return
    lastRealDate = now
    if (selectedPreset.value !== null) {
      applyPreset(selectedPreset.value)
    } else {
      void load()
    }
  }, 30_000)
}

function applyPreset(days: number): void {
  const end = new Date()
  const start = new Date(end)
  start.setDate(end.getDate() - days + 1)
  dateFrom.value = localDateString(start)
  dateTo.value = localDateString(end)
  selectedPreset.value = days
  calendarOpen.value = false
  void load()
}

async function applyDateRange(): Promise<void> {
  calendarOpen.value = false
  await load()
}

async function load(): Promise<void> {
  errorMessage.value = ''
  const ownerId = auth.user?.profile.id
  const wasInitialized = Boolean(ownerId && timer.initialized && timer.ownerId === ownerId)
  const pendingBefore = timer.pendingCount + tasksStore.pendingCount
  const syncPromise = ownerId ? ensureTimerSynced(ownerId) : Promise.resolve()
  try {
    const cached =
      ownerId && !summary.value ? analyticsService.peekDashboard(dashboardCacheKey()) : null
    if (cached) applyDashboard(cached)
    if (!summary.value) loading.value = true
    await fetchDashboard()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
  void syncPromise.then(() => {
    if (errorMessage.value) return
    if (wasInitialized && pendingBefore === 0) return
    void fetchDashboard().catch(() => {})
  })
}

async function ensureTimerSynced(ownerId: string): Promise<void> {
  try {
    if (!timer.initialized || timer.ownerId !== ownerId) {
      await timer.initialize(ownerId)
    } else {
      await timer.syncPending()
    }
  } catch {
    return
  }
}

function applyDashboard(dashboard: AnalyticsDashboard): void {
  summary.value = dashboard.range_summary
  todaySummary.value = dashboard.today_summary
  todayCheckIn.value = dashboard.today_check_in
}

function dashboardCacheKey(): string {
  const ownerId = auth.user?.profile.id ?? 'anonymous'
  return `${ownerId}|${dateFrom.value}|${dateTo.value}|${localDateString(new Date())}`
}

async function fetchDashboard(): Promise<void> {
  const todayString = localDateString(new Date())
  const data = await analyticsService.dashboard(dateFrom.value, dateTo.value, todayString)
  analyticsService.storeDashboard(dashboardCacheKey(), data)
  applyDashboard(data)
}

function aggregateTrend(
  points: DailyTrendPoint[],
  granularity: TrendGranularity,
): TrendPoint[] {
  const groups = new Map<string, { anchor: Date; dates: Date[]; seconds: number; completedItems: number }>()
  for (const point of points) {
    const date = parseLocalDate(point.date)
    const anchor = trendAnchor(date, granularity)
    const key = localDateString(anchor)
    const current = groups.get(key) ?? {
      anchor,
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
      const first = group.dates[0] ?? group.anchor
      const last = group.dates[group.dates.length - 1] ?? group.anchor
      return {
        key,
        label: trendLabel(group.anchor, granularity),
        range:
          granularity === 'day'
            ? first.toLocaleDateString('zh-CN', { weekday: 'short' })
            : `${shortDate(localDateString(first))}–${shortDate(localDateString(last))}`,
        seconds: group.seconds,
        completedItems: group.completedItems,
      }
    })
}

function trendAnchor(date: Date, granularity: TrendGranularity): Date {
  if (granularity === 'week') return mondayOf(date)
  if (granularity === 'month') return new Date(date.getFullYear(), date.getMonth(), 1)
  if (granularity === 'year') return new Date(date.getFullYear(), 0, 1)
  return new Date(date)
}

function trendLabel(date: Date, granularity: TrendGranularity): string {
  if (granularity === 'week') return `${date.getMonth() + 1}.${date.getDate()} 周`
  if (granularity === 'month') return `${date.getFullYear()}年${date.getMonth() + 1}月`
  if (granularity === 'year') return `${date.getFullYear()}年`
  return shortDate(localDateString(date))
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

function axisDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  if (minutes >= 60) {
    const hours = minutes / 60
    return Number.isInteger(hours) ? `${hours}h` : `${hours.toFixed(1)}h`
  }
  return `${minutes}m`
}

function usageWidth(ratio: number | null): number {
  if (ratio === null) return 0
  return Math.min(100, Math.max(2, ratio * 100))
}

function projectHistoryShare(seconds: number): number {
  const total = projectHistoryTotalSeconds.value
  if (total <= 0) return 0
  return Math.round((seconds / total) * 100)
}

function projectHistoryWidth(seconds: number): number {
  const share = projectHistoryShare(seconds)
  return share > 0 ? Math.max(2, share) : 0
}

function formatHistoryDate(value: string): string {
  return new Date(value).toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  })
}

function shortDate(value: string): string {
  const parsed = parseLocalDate(value)
  return `${parsed.getMonth() + 1}.${parsed.getDate()}`
}
</script>
