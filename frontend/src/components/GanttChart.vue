<template>
  <section class="activity-gantt" aria-label="计划进度表">
    <header class="activity-gantt__header">
      <div class="activity-gantt__heading">
        <p class="eyebrow">
          计划进度表
          <HintIcon
            text="按项目展示时间跨度。折叠时每个项目一条时间线；展开后按模块分行，模块线上的每个方块是一项任务，点击任务可跳到项目页查看它。这里只用于查看，排期请在任务的“安排时间”里调整。"
          />
        </p>
        <div class="gantt-stats" aria-label="学习统计">
          <div class="gantt-stat">
            <strong>{{ formatSeconds(stats.totalSeconds) }}</strong>
            <span>总学习时长</span>
          </div>
          <div class="gantt-stat">
            <strong>{{ stats.activeTasks }}</strong>
            <span>活跃任务数</span>
          </div>
          <div class="gantt-stat">
            <strong>{{ stats.completionRate }}%</strong>
            <span>完成率</span>
          </div>
          <div class="gantt-stat">
            <strong>{{ stats.streakDays }} 天</strong>
            <span>连续学习</span>
          </div>
        </div>
      </div>
      <div class="activity-gantt__controls">
        <button
          v-if="groups.length > 1"
          class="gantt-expand-all"
          type="button"
          @click="toggleAll"
        >
          {{ allCollapsed ? '全部展开' : '全部折叠' }}
        </button>
        <div class="gantt-scale" role="group" aria-label="时间尺度">
          <button
            v-for="option in SCALE_OPTIONS"
            :key="option.value"
            type="button"
            :class="{ 'is-active': scale === option.value }"
            :aria-pressed="scale === option.value"
            @click="scale = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>
    </header>

    <p v-if="groups.length === 0" class="empty-state">
      {{ loading ? '正在读取学习记录…' : '暂无排期或学习记录；给任务设置安排时间或开始计时后，这里会显示项目的时间跨度。' }}
    </p>

    <div v-else-if="isMobile" class="gantt-cards">
      <section
        v-for="group in groups"
        :key="`card-${group.id}`"
        class="gantt-card-group"
        :style="{ '--group-color': group.theme.primary }"
      >
        <header class="gantt-card-group__header">
          <i class="gantt-dot" aria-hidden="true"></i>
          <strong>{{ group.title }}</strong>
          <span>
            {{ formatDayLabel(group.firstDate) }} – {{ formatDayLabel(group.lastDate) }} ·
            {{ formatSeconds(group.totalSeconds) }}
          </span>
        </header>
        <button
          v-for="row in group.rows"
          :key="`card-${row.id}`"
          type="button"
          class="gantt-card"
          @click="openTask(row)"
        >
          <span class="gantt-card__title" :title="row.title">
            <b v-if="row.moduleTitle">{{ row.moduleTitle }} · </b>{{ row.title }}
          </span>
          <span class="gantt-card__meta">
            {{ formatDayLabel(row.firstDate) }} – {{ formatDayLabel(row.lastDate) }} · 持续 {{ row.spanDays }} 天 · 活跃 {{ row.activeDays }} 天
          </span>
          <span class="gantt-card__progress" aria-hidden="true">
            <i :style="{ width: `${Math.round((row.progressRatio ?? 1) * 100)}%` }"></i>
          </span>
          <span class="gantt-card__foot">
            <b>{{ formatSeconds(row.totalSeconds) }}</b>
            <span>{{ statusLabel(row.status) }}</span>
          </span>
        </button>
      </section>
    </div>

    <div
      v-else
      ref="viewportEl"
      class="gantt-viewport"
      :class="{ 'is-loading': loading, 'is-panning': isPanning }"
    >
      <div
        ref="scrollEl"
        class="gantt-scroll"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @click.capture="onClickCapture"
      >
        <div
          class="gantt-canvas"
          :style="{ width: `${canvasWidth}px`, '--gantt-label-w': `${labelWidth}px` }"
        >
          <div class="gantt-head">
            <div class="gantt-head__corner">项目 / 模块</div>
            <div class="gantt-head__tiers">
              <div class="gantt-tier gantt-tier--primary" aria-hidden="true">
                <span
                  v-for="cell in primaryCells"
                  :key="`primary-${cell.key}`"
                  class="gantt-tier__cell"
                  :style="{ left: `${cell.left}px`, width: `${cell.width}px` }"
                >
                  {{ cell.label }}
                </span>
              </div>
              <div class="gantt-tier gantt-tier--secondary" aria-hidden="true">
                <span
                  v-for="cell in secondaryCells"
                  :key="`secondary-${cell.key}`"
                  class="gantt-tier__cell"
                  :class="{ 'gantt-tier__cell--center': scale === 'day', 'is-weekend': cell.isWeekend }"
                  :style="{ left: `${cell.left}px`, width: `${cell.width}px` }"
                >
                  {{ cell.label }}
                </span>
                <span
                  v-if="todayVisible"
                  class="gantt-head__today-flag"
                  :style="{ left: `${todayX}px` }"
                >
                  今日
                </span>
              </div>
            </div>
          </div>

          <div class="gantt-body">
            <div class="gantt-grid" :style="gridStyle" aria-hidden="true">
              <span
                class="gantt-grid__lines"
                :class="{ 'is-hidden': gridPeriod === 0 }"
              ></span>
              <span
                v-for="band in weekendBands"
                :key="`band-${band.key}`"
                class="gantt-grid__weekend"
                :style="{ left: `${band.left}px`, width: `${band.width}px` }"
              ></span>
              <span
                v-for="line in boundaryLines"
                :key="`line-${line.key}`"
                class="gantt-grid__boundary"
                :style="{ left: `${line.left}px` }"
              ></span>
              <span
                v-if="todayVisible"
                class="gantt-grid__today"
                :style="{ left: `${todayX}px` }"
              ></span>
            </div>

            <div
              v-for="group in groups"
              :key="group.id"
              class="gantt-group"
              :style="{ '--group-color': group.theme.primary, '--group-soft': group.theme.soft }"
            >
              <div class="gantt-row gantt-row--project">
                <button
                  class="gantt-label gantt-label--group"
                  type="button"
                  :aria-expanded="!collapsedGroups.has(group.id)"
                  :title="`${group.title}（点击${collapsedGroups.has(group.id) ? '展开' : '折叠'}模块）`"
                  @click="toggleGroup(group.id)"
                >
                  <i class="gantt-dot" aria-hidden="true"></i>
                  <svg
                    class="gantt-chevron"
                    :class="{ 'is-collapsed': collapsedGroups.has(group.id) }"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                  <span class="gantt-label__text">
                    <span class="gantt-label__title">{{ group.title }}</span>
                    <span class="gantt-label__meta">
                      {{ formatDayLabel(group.firstDate) }}–{{ formatDayLabel(group.lastDate) }} ·
                      {{ formatSeconds(group.totalSeconds) }}
                    </span>
                  </span>
                </button>
                <div class="gantt-track gantt-track--project">
                  <div
                    class="gantt-span gantt-span--project"
                    :style="spanStyle(group.firstDate, group.lastDate, group.theme, 0.26)"
                    tabindex="0"
                    role="img"
                    :aria-label="groupAriaLabel(group)"
                    @mouseenter="showGroupTooltip(group, $event.clientX, $event.clientY)"
                    @mousemove="showGroupTooltip(group, $event.clientX, $event.clientY)"
                    @mouseleave="hideTooltip"
                    @blur="hideTooltip"
                  >
                    <span
                      class="gantt-span__fill"
                      :style="{
                        width: `${Math.round((group.progressRatio ?? 0) * 100)}%`,
                        background: group.theme.primary,
                      }"
                      aria-hidden="true"
                    ></span>
                    <span class="gantt-span__label">
                      {{ formatDayLabel(group.firstDate) }} – {{ formatDayLabel(group.lastDate) }}
                    </span>
                  </div>
                </div>
              </div>

              <template v-if="!collapsedGroups.has(group.id)">
                <div
                  v-for="line in group.modules"
                  :key="line.id"
                  class="gantt-row gantt-row--module"
                  :style="{ '--lane-count': line.lanes }"
                >
                  <div class="gantt-label gantt-label--module">
                    <span class="gantt-label__text">
                      <span class="gantt-label__title">{{ line.title }}</span>
                      <span class="gantt-label__meta">
                        {{ line.rows.length }} 项 · {{ formatSeconds(line.totalSeconds) }}
                      </span>
                    </span>
                  </div>
                  <div class="gantt-track gantt-track--module">
                    <span
                      class="gantt-module-line"
                      :style="spanStyle(line.firstDate, line.lastDate, group.theme, 0.1)"
                      aria-hidden="true"
                    ></span>
                    <template v-for="bar in line.bars" :key="bar.row.id">
                      <span
                        v-if="bar.planStyle"
                        class="gantt-plan-outline"
                        :style="bar.planStyle"
                        aria-hidden="true"
                      ></span>
                      <button
                        class="gantt-bar"
                        type="button"
                        :style="bar.style"
                        :aria-label="barAriaLabel(bar.row)"
                        @pointerdown.stop
                        @mouseenter="showTooltipAt(bar.row, $event.clientX, $event.clientY)"
                        @mousemove="showTooltipAt(bar.row, $event.clientX, $event.clientY)"
                        @mouseleave="hideTooltip"
                        @focus="showTooltipFromElement(bar.row, $event)"
                        @blur="hideTooltip"
                        @click="openTask(bar.row)"
                      >
                        <span
                          class="gantt-bar__fill"
                          :style="{ background: group.theme.primary, width: bar.fillWidth }"
                          aria-hidden="true"
                        ></span>
                        <span v-if="bar.showLabel" class="gantt-bar__label">
                          {{ bar.row.title }}
                        </span>
                      </button>
                    </template>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <p v-if="error" class="activity-gantt__error">{{ error }}</p>
  </section>

  <Teleport to="body">
    <div
      v-if="tooltip"
      class="gantt-tooltip"
      :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
      role="tooltip"
    >
      <strong :title="tooltip.title">{{ tooltip.title }}</strong>
      <span class="gantt-tooltip__project">
        <i :style="{ background: tooltip.color }" aria-hidden="true"></i>
        {{ tooltip.subtitle }}
      </span>
      <div class="gantt-tooltip__grid">
        <span><i>开始</i><b>{{ formatFullDate(tooltip.firstDate) }}</b></span>
        <span><i>结束</i><b>{{ formatFullDate(tooltip.lastDate) }}</b></span>
        <span><i>累计学习</i><b>{{ formatSeconds(tooltip.totalSeconds) }}</b></span>
        <span><i>持续 / 活跃</i><b>{{ tooltip.spanDays }} / {{ tooltip.activeDays }} 天</b></span>
        <span>
          <i>进度</i>
          <b>{{ tooltip.progressRatio === null ? '—' : `${Math.round(tooltip.progressRatio * 100)}%` }}</b>
        </span>
      </div>
      <div
        v-if="tooltip.progressRatio !== null"
        class="gantt-tooltip__progress"
        aria-hidden="true"
      >
        <i :style="{ width: `${Math.round(tooltip.progressRatio * 100)}%`, background: tooltip.color }"></i>
      </div>
      <span class="gantt-tooltip__hint">{{ tooltip.hint }}</span>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import HintIcon from '@/components/HintIcon.vue'
import type { GanttChartRow } from '@/types/analytics'
import type { TaskStatus } from '@/types/task'
import { getProjectTheme, type ProjectTheme } from '@/utils/project-theme'
import { formatDuration } from '@/utils/time'

defineOptions({ name: 'GanttChart' })

type GanttScale = 'day' | 'week' | 'month'

/** One task drawn on a module's line, packed into a non-overlapping lane. */
interface GanttBar {
  row: GanttChartRow
  fillWidth: string
  showLabel: boolean
  style: Record<string, string>
  planStyle: Record<string, string> | null
}

interface GanttModuleLine {
  id: string
  title: string
  rows: GanttChartRow[]
  bars: GanttBar[]
  lanes: number
  totalSeconds: number
  firstDate: string
  lastDate: string
}

interface GanttGroup {
  id: string
  title: string
  theme: ProjectTheme
  rows: GanttChartRow[]
  modules: GanttModuleLine[]
  totalSeconds: number
  firstDate: string
  lastDate: string
  progressRatio: number | null
}

const props = withDefaults(
  defineProps<{
    rows: GanttChartRow[]
    today: string
    loading?: boolean
    error?: string
  }>(),
  { loading: false, error: '' },
)

const router = useRouter()

const MS_DAY = 86_400_000
const SCALE_STORAGE_KEY = 'dayflow:today-gantt-scale'
const TOOLTIP_WIDTH = 252
const TOOLTIP_HEIGHT = 252
const LANE_HEIGHT = 22
const BAR_GAP_DAYS = 1

const SCALE_OPTIONS: { value: GanttScale; label: string }[] = [
  { value: 'day', label: '天' },
  { value: 'week', label: '周' },
  { value: 'month', label: '月' },
]

const SCALE_PRESETS: Record<GanttScale, { dayWidth: number; pastDays: number; futureDays: number }> = {
  day: { dayWidth: 34, pastDays: 21, futureDays: 16 },
  week: { dayWidth: 11, pastDays: 28, futureDays: 70 },
  month: { dayWidth: 2.6, pastDays: 60, futureDays: 184 },
}

const STATUS_LABELS: Record<TaskStatus, string> = {
  TODO: '待开始',
  IN_PROGRESS: '进行中',
  PAUSED: '已暂停',
  BLOCKED: '已阻塞',
  DONE: '已完成',
}

function initialScale(): GanttScale {
  try {
    const stored = localStorage.getItem(SCALE_STORAGE_KEY)
    if (stored === 'day' || stored === 'week' || stored === 'month') return stored
  } catch {
    /* localStorage unavailable */
  }
  return 'day'
}

const scale = ref<GanttScale>(initialScale())
watch(scale, (value) => {
  try {
    localStorage.setItem(SCALE_STORAGE_KEY, value)
  } catch {
    /* localStorage unavailable */
  }
})

const viewportEl = ref<HTMLElement | null>(null)
const viewportWidth = ref(1024)
let resizeObserver: ResizeObserver | null = null

watch(viewportEl, (element) => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (element && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width
      if (width && width > 0) viewportWidth.value = width
    })
    resizeObserver.observe(element)
  }
})

const mobileQuery = window.matchMedia('(max-width: 639px)')
const isMobile = ref(mobileQuery.matches)
function onMobileChange(event: MediaQueryListEvent): void {
  isMobile.value = event.matches
}
onMounted(() => mobileQuery.addEventListener('change', onMobileChange))
onBeforeUnmount(() => {
  mobileQuery.removeEventListener('change', onMobileChange)
  resizeObserver?.disconnect()
  resizeObserver = null
})

const labelWidth = computed(() => (viewportWidth.value < 760 ? 148 : 208))
const widthFactor = computed(() => {
  if (viewportWidth.value < 760) return 0.72
  if (viewportWidth.value < 1080) return 0.86
  return 1
})
const preset = computed(() => SCALE_PRESETS[scale.value])
const dayWidth = computed(() => Math.max(1.8, Math.round(preset.value.dayWidth * widthFactor.value * 10) / 10))

function parseDay(date: string): number {
  return Date.parse(`${date}T00:00:00Z`)
}
function addDays(date: string, days: number): string {
  return new Date(parseDay(date) + days * MS_DAY).toISOString().slice(0, 10)
}
function diffDays(from: string, to: string): number {
  return Math.round((parseDay(to) - parseDay(from)) / MS_DAY)
}
function weekday(date: string): number {
  return new Date(parseDay(date)).getUTCDay()
}

/** Inclusive extent of a row, covering both its planned window and its records. */
function rowStart(row: GanttChartRow): string {
  return row.plannedStart && row.plannedStart < row.firstDate ? row.plannedStart : row.firstDate
}
function rowEnd(row: GanttChartRow): string {
  return row.plannedEnd && row.plannedEnd > row.lastDate ? row.plannedEnd : row.lastDate
}

const earliestDate = computed(() =>
  props.rows.reduce<string | null>(
    (acc, row) => (!acc || rowStart(row) < acc ? rowStart(row) : acc),
    null,
  ),
)
const latestDate = computed(() =>
  props.rows.reduce<string>(
    (acc, row) => (rowEnd(row) > acc ? rowEnd(row) : acc),
    props.today,
  ),
)

function alignStart(date: string): string {
  if (scale.value === 'week') {
    const offset = weekday(date) === 0 ? -6 : 1 - weekday(date)
    return addDays(date, offset)
  }
  if (scale.value === 'month') return `${date.slice(0, 7)}-01`
  return date
}
function alignEnd(date: string): string {
  if (scale.value === 'week') {
    const offset = weekday(date) === 0 ? 0 : 7 - weekday(date)
    return addDays(date, offset)
  }
  if (scale.value === 'month') {
    const year = Number(date.slice(0, 4))
    const month = Number(date.slice(5, 7))
    const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate()
    return `${date.slice(0, 7)}-${String(lastDay).padStart(2, '0')}`
  }
  return date
}

const rangeStart = computed(() => {
  const fallback = addDays(props.today, -preset.value.pastDays)
  const candidate = earliestDate.value && earliestDate.value < fallback
    ? earliestDate.value
    : fallback
  return alignStart(candidate)
})
const rangeEnd = computed(() => {
  const future = addDays(props.today, preset.value.futureDays)
  const candidate = latestDate.value + 7 > future ? addDays(latestDate.value, 7) : future
  return alignEnd(candidate)
})
const totalDays = computed(() => diffDays(rangeStart.value, rangeEnd.value) + 1)

function dayIndex(date: string): number {
  return diffDays(rangeStart.value, date)
}

const canvasWidth = computed(() => labelWidth.value + totalDays.value * dayWidth.value + 16)
const gridPeriod = computed(() =>
  scale.value === 'day' ? dayWidth.value : scale.value === 'week' ? dayWidth.value * 7 : 0,
)
const gridStyle = computed(() => ({
  '--gantt-period': `${gridPeriod.value}px`,
}))

const todayVisible = computed(
  () => dayIndex(props.today) >= 0 && dayIndex(props.today) < totalDays.value,
)
const todayX = computed(() => (dayIndex(props.today) + 0.5) * dayWidth.value)

interface TierCell {
  key: string
  left: number
  width: number
  label: string
  isWeekend?: boolean
}

const primaryCells = computed<TierCell[]>(() => {
  const cells: TierCell[] = []
  if (scale.value === 'month') {
    let year = Number(rangeStart.value.slice(0, 4))
    while (Date.parse(`${year}-01-01`) <= parseDay(rangeEnd.value)) {
      const start = Math.max(0, dayIndex(`${year}-01-01`))
      const nextStart = dayIndex(`${year + 1}-01-01`)
      const end = Math.min(totalDays.value - 1, nextStart - 1)
      if (end >= start) {
        cells.push({
          key: `${year}`,
          left: start * dayWidth.value,
          width: (end - start + 1) * dayWidth.value,
          label: `${year}年`,
        })
      }
      year += 1
    }
    return cells
  }
  let cursor = `${rangeStart.value.slice(0, 7)}-01`
  let first = true
  while (parseDay(cursor) <= parseDay(rangeEnd.value)) {
    const year = Number(cursor.slice(0, 4))
    const month = Number(cursor.slice(5, 7))
    const next = month === 12
      ? `${year + 1}-01-01`
      : `${year}-${String(month + 1).padStart(2, '0')}-01`
    const start = Math.max(0, dayIndex(cursor))
    const end = Math.min(totalDays.value - 1, dayIndex(next) - 1)
    if (end >= start) {
      cells.push({
        key: cursor,
        left: start * dayWidth.value,
        width: (end - start + 1) * dayWidth.value,
        label: first || month === 1 ? `${year}年${month}月` : `${month}月`,
      })
      first = false
    }
    cursor = next
  }
  return cells
})

const secondaryCells = computed<TierCell[]>(() => {
  const cells: TierCell[] = []
  if (scale.value === 'day') {
    for (let index = 0; index < totalDays.value; index += 1) {
      const date = addDays(rangeStart.value, index)
      const day = weekday(date)
      cells.push({
        key: date,
        left: index * dayWidth.value,
        width: dayWidth.value,
        label: String(Number(date.slice(8, 10))),
        isWeekend: day === 0 || day === 6,
      })
    }
    return cells
  }
  if (scale.value === 'week') {
    for (let index = 0; index < totalDays.value; index += 7) {
      const date = addDays(rangeStart.value, index)
      cells.push({
        key: date,
        left: index * dayWidth.value,
        width: 7 * dayWidth.value,
        label: `${Number(date.slice(5, 7))}/${Number(date.slice(8, 10))}`,
      })
    }
    return cells
  }
  let cursor = `${rangeStart.value.slice(0, 7)}-01`
  while (parseDay(cursor) <= parseDay(rangeEnd.value)) {
    const year = Number(cursor.slice(0, 4))
    const month = Number(cursor.slice(5, 7))
    const next = month === 12
      ? `${year + 1}-01-01`
      : `${year}-${String(month + 1).padStart(2, '0')}-01`
    const start = Math.max(0, dayIndex(cursor))
    const end = Math.min(totalDays.value - 1, dayIndex(next) - 1)
    if (end >= start) {
      cells.push({
        key: cursor,
        left: start * dayWidth.value,
        width: (end - start + 1) * dayWidth.value,
        label: `${month}月`,
      })
    }
    cursor = next
  }
  return cells
})

const weekendBands = computed(() => {
  if (scale.value !== 'day') return []
  const bands: { key: string; left: number; width: number }[] = []
  for (let index = 0; index < totalDays.value; index += 1) {
    const day = weekday(addDays(rangeStart.value, index))
    if (day !== 6) continue
    const span = index + 1 < totalDays.value ? 2 : 1
    bands.push({
      key: addDays(rangeStart.value, index),
      left: index * dayWidth.value,
      width: span * dayWidth.value,
    })
  }
  return bands
})

const boundaryLines = computed(() => {
  const lines: { key: string; left: number }[] = []
  // +32 days always lands in the next month without skipping a short month.
  let cursor = monthStartOf(addDays(monthStartOf(rangeStart.value), 32))
  while (parseDay(cursor) <= parseDay(rangeEnd.value)) {
    const index = dayIndex(cursor)
    if (index > 0 && index < totalDays.value) {
      lines.push({ key: cursor, left: index * dayWidth.value })
    }
    cursor = monthStartOf(addDays(cursor, 32))
  }
  return lines
})

function monthStartOf(date: string): string {
  return `${date.slice(0, 7)}-01`
}

/**
 * Pack a module's tasks into lanes so overlapping spans stack instead of
 * covering each other, then lay each task out as one block on its lane.
 */
function buildBars(rows: GanttChartRow[], theme: ProjectTheme): { bars: GanttBar[]; lanes: number } {
  const ordered = [...rows].sort(
    (left, right) => rowStart(left).localeCompare(rowStart(right)) || left.title.localeCompare(right.title),
  )
  const laneEnds: string[] = []
  const bars: GanttBar[] = []
  for (const row of ordered) {
    const start = rowStart(row)
    const end = rowEnd(row)
    let lane = laneEnds.findIndex((occupiedUntil) => occupiedUntil < start)
    if (lane === -1) {
      lane = laneEnds.length
      laneEnds.push(end)
    } else {
      laneEnds[lane] = end
    }
    // Reserve a day of clearance so neighbouring blocks stay readable.
    laneEnds[lane] = addDays(end, BAR_GAP_DAYS)

    const index = dayIndex(start)
    const width = Math.max(6, (diffDays(start, end) + 1) * dayWidth.value - 3)
    bars.push({
      row,
      fillWidth: row.progressRatio === null
        ? '0%'
        : `${Math.min(100, Math.round(row.progressRatio * 100))}%`,
      showLabel: width >= 58 && scale.value !== 'month',
      style: {
        left: `${index * dayWidth.value + 1.5}px`,
        width: `${width}px`,
        top: `${lane * LANE_HEIGHT + 3}px`,
        background: hexToRgba(theme.primary, 0.26),
        borderColor: hexToRgba(theme.primary, 0.7),
      },
      // Only worth drawing when the plan and the records actually differ —
      // otherwise it is a dashed outline tracing the bar it sits behind.
      planStyle:
        row.plannedStart && row.plannedEnd && row.days.length > 0
          && (row.plannedStart !== row.firstDate || row.plannedEnd !== row.lastDate)
          ? {
              left: `${dayIndex(row.plannedStart) * dayWidth.value + 1.5}px`,
              width: `${Math.max(
                dayWidth.value,
                (diffDays(row.plannedStart, row.plannedEnd) + 1) * dayWidth.value - 3,
              )}px`,
              top: `${lane * LANE_HEIGHT + 1}px`,
            }
          : null,
    })
  }
  return { bars, lanes: Math.max(1, laneEnds.length) }
}

const groups = computed<GanttGroup[]>(() => {
  const map = new Map<string, GanttGroup>()
  for (const row of props.rows) {
    const id = row.projectId ?? '__none__'
    let group = map.get(id)
    if (!group) {
      group = {
        id,
        title: row.projectTitle,
        theme: getProjectTheme(row.projectId),
        rows: [],
        modules: [],
        totalSeconds: 0,
        firstDate: rowStart(row),
        lastDate: rowEnd(row),
        progressRatio: null,
      }
      map.set(id, group)
    }
    group.rows.push(row)
    group.totalSeconds += row.totalSeconds
    if (rowStart(row) < group.firstDate) group.firstDate = rowStart(row)
    if (rowEnd(row) > group.lastDate) group.lastDate = rowEnd(row)
  }

  const result = [...map.values()]
  for (const group of result) {
    const byModule = new Map<string, GanttChartRow[]>()
    for (const row of group.rows) {
      const key = row.moduleId ?? '__direct__'
      const bucket = byModule.get(key)
      if (bucket) bucket.push(row)
      else byModule.set(key, [row])
    }
    group.modules = [...byModule.entries()].map(([key, rows]) => {
      const { bars, lanes } = buildBars(rows, group.theme)
      return {
        id: `${group.id}:${key}`,
        title: key === '__direct__' ? '项目直属任务' : (rows[0]!.moduleTitle || '未命名模块'),
        rows,
        bars,
        lanes,
        totalSeconds: rows.reduce((sum, row) => sum + row.totalSeconds, 0),
        firstDate: rows.reduce((acc, row) => (rowStart(row) < acc ? rowStart(row) : acc), rowStart(rows[0]!)),
        lastDate: rows.reduce((acc, row) => (rowEnd(row) > acc ? rowEnd(row) : acc), rowEnd(rows[0]!)),
      }
    })
    group.modules.sort((left, right) => left.firstDate.localeCompare(right.firstDate))

    const rated = group.rows.filter((row) => row.progressRatio !== null)
    group.progressRatio = rated.length > 0
      ? rated.reduce((sum, row) => sum + (row.progressRatio ?? 0), 0) / rated.length
      : null
  }
  return result.sort(
    (left, right) => right.lastDate.localeCompare(left.lastDate) || right.totalSeconds - left.totalSeconds,
  )
})

// Projects start collapsed: the chart is first of all a project-level view of
// how work is spread across time, and the modules are the detail behind it.
const collapsedGroups = ref(new Set<string>())
const decidedGroups = new Set<string>()
watch(
  groups,
  (value) => {
    const next = new Set(collapsedGroups.value)
    let changed = false
    for (const group of value) {
      if (decidedGroups.has(group.id)) continue
      decidedGroups.add(group.id)
      next.add(group.id)
      changed = true
    }
    if (changed) collapsedGroups.value = next
  },
  { immediate: true },
)

const allCollapsed = computed(() => groups.value.every((group) => collapsedGroups.value.has(group.id)))

function toggleGroup(groupId: string): void {
  const next = new Set(collapsedGroups.value)
  if (next.has(groupId)) next.delete(groupId)
  else next.add(groupId)
  collapsedGroups.value = next
}

function toggleAll(): void {
  collapsedGroups.value = allCollapsed.value
    ? new Set()
    : new Set(groups.value.map((group) => group.id))
}

/** Expand the project holding a task, used when the page deep-links into it. */
function revealTask(taskId: string): void {
  const group = groups.value.find((item) => item.rows.some((row) => row.id === taskId))
  if (!group) return
  const next = new Set(collapsedGroups.value)
  next.delete(group.id)
  collapsedGroups.value = next
}

defineExpose({ revealTask })

function spanStyle(
  first: string,
  last: string,
  theme: ProjectTheme,
  alpha: number,
): Record<string, string> {
  const index = dayIndex(first)
  const width = Math.max(6, (diffDays(first, last) + 1) * dayWidth.value - 3)
  return {
    left: `${index * dayWidth.value + 1.5}px`,
    width: `${width}px`,
    background: hexToRgba(theme.primary, alpha),
    borderColor: hexToRgba(theme.primary, 0.5),
  }
}

function hexToRgba(hex: string, alpha: number): string {
  const value = hex.replace('#', '')
  const red = parseInt(value.slice(0, 2), 16)
  const green = parseInt(value.slice(2, 4), 16)
  const blue = parseInt(value.slice(4, 6), 16)
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
}

const stats = computed(() => {
  const totalSeconds = props.rows.reduce((sum, row) => sum + row.totalSeconds, 0)
  const doneCount = props.rows.filter((row) => row.status === 'DONE').length
  const learningDates = new Set<string>()
  for (const row of props.rows) {
    for (const day of row.days) {
      if (day.seconds > 0) learningDates.add(day.date)
    }
  }
  let cursor = learningDates.has(props.today) ? props.today : addDays(props.today, -1)
  let streakDays = 0
  while (learningDates.has(cursor)) {
    streakDays += 1
    cursor = addDays(cursor, -1)
  }
  return {
    totalSeconds,
    activeTasks: props.rows.length,
    completionRate: props.rows.length > 0 ? Math.round((doneCount / props.rows.length) * 100) : 0,
    streakDays,
  }
})

function formatSeconds(seconds: number): string {
  return seconds > 0 ? formatDuration(seconds) : '0 分钟'
}

function formatDayLabel(date: string): string {
  const [, month, day] = date.split('-')
  return `${Number(month)}.${Number(day)}`
}

function formatFullDate(date: string): string {
  const [, month, day] = date.split('-')
  return `${Number(month)}月${Number(day)}日`
}

function statusLabel(status: TaskStatus | null): string {
  return status ? STATUS_LABELS[status] : '历史任务'
}

function barAriaLabel(row: GanttChartRow): string {
  const progress = row.progressRatio === null
    ? ''
    : `，进度 ${Math.round(row.progressRatio * 100)}%`
  return `${row.title}（${row.projectTitle}），${formatFullDate(rowStart(row))}至${formatFullDate(rowEnd(row))}，累计学习 ${formatSeconds(row.totalSeconds)}${progress}，点击查看任务`
}

function groupAriaLabel(group: GanttGroup): string {
  return `${group.title}，${formatFullDate(group.firstDate)}至${formatFullDate(group.lastDate)}，${group.rows.length} 项任务，累计学习 ${formatSeconds(group.totalSeconds)}`
}

function openTask(row: GanttChartRow): void {
  void router.push({ name: 'tasks', query: { task: row.id } })
}

interface TooltipState {
  title: string
  subtitle: string
  color: string
  firstDate: string
  lastDate: string
  totalSeconds: number
  spanDays: number
  activeDays: number
  progressRatio: number | null
  hint: string
  x: number
  y: number
}

const tooltip = ref<TooltipState | null>(null)

function place(pointerX: number, pointerY: number): { x: number; y: number } {
  let x = pointerX + 14
  let y = pointerY + 16
  if (x + TOOLTIP_WIDTH > window.innerWidth - 8) x = pointerX - TOOLTIP_WIDTH - 14
  if (y + TOOLTIP_HEIGHT > window.innerHeight - 8) y = pointerY - TOOLTIP_HEIGHT - 16
  return { x: Math.max(8, x), y: Math.max(8, y) }
}

function showTooltipAt(row: GanttChartRow, pointerX: number, pointerY: number): void {
  tooltip.value = {
    title: row.title,
    subtitle: `${row.projectTitle}${row.moduleTitle ? ` / ${row.moduleTitle}` : ''} · ${statusLabel(row.status)}`,
    color: getProjectTheme(row.projectId).primary,
    firstDate: rowStart(row),
    lastDate: rowEnd(row),
    totalSeconds: row.totalSeconds,
    spanDays: diffDays(rowStart(row), rowEnd(row)) + 1,
    activeDays: row.activeDays,
    progressRatio: row.progressRatio,
    hint: '点击跳转到项目页查看这项任务',
    ...place(pointerX, pointerY),
  }
}

function showGroupTooltip(group: GanttGroup, pointerX: number, pointerY: number): void {
  const activeDates = new Set<string>()
  for (const row of group.rows) {
    for (const day of row.days) {
      if (day.seconds > 0) activeDates.add(day.date)
    }
  }
  tooltip.value = {
    title: group.title,
    subtitle: `${group.modules.length} 个模块 · ${group.rows.length} 项任务`,
    color: group.theme.primary,
    firstDate: group.firstDate,
    lastDate: group.lastDate,
    totalSeconds: group.totalSeconds,
    spanDays: diffDays(group.firstDate, group.lastDate) + 1,
    activeDays: activeDates.size,
    progressRatio: group.progressRatio,
    hint: collapsedGroups.value.has(group.id) ? '点击项目名展开模块时间线' : '点击项目名折叠模块时间线',
    ...place(pointerX, pointerY),
  }
}

function showTooltipFromElement(row: GanttChartRow, event: FocusEvent): void {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  showTooltipAt(row, Math.min(rect.right, window.innerWidth - TOOLTIP_WIDTH - 22), rect.top)
}

function hideTooltip(): void {
  tooltip.value = null
}

const scrollEl = ref<HTMLElement | null>(null)
const isPanning = ref(false)
let panStart: { pointerId: number; startX: number; startScrollLeft: number } | null = null
let panMoved = false

// 打开组件或切换时间尺度时，把今天滚动到可视区中间，避免落在最早的历史数据上。
function scrollToToday(): void {
  const scroll = scrollEl.value
  if (!scroll || !todayVisible.value) return
  void nextTick(() => {
    const target = todayX.value - Math.max(0, (viewportWidth.value - labelWidth.value) / 2)
    scroll.scrollLeft = Math.max(0, Math.min(target, scroll.scrollWidth - scroll.clientWidth))
  })
}

watch(viewportEl, (element) => {
  if (element) scrollToToday()
})
watch(scale, () => scrollToToday())
watch(
  () => props.rows.length,
  (length, previous) => {
    if (length > 0 && previous === 0) scrollToToday()
  },
)

function onPointerDown(event: PointerEvent): void {
  if (event.pointerType !== 'mouse' || event.button !== 0) return
  panStart = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startScrollLeft: scrollEl.value?.scrollLeft ?? 0,
  }
  panMoved = false
}

function onPointerMove(event: PointerEvent): void {
  if (!panStart || event.pointerId !== panStart.pointerId) return
  const delta = event.clientX - panStart.startX
  if (!panMoved && Math.abs(delta) <= 4) return
  panMoved = true
  isPanning.value = true
  if (scrollEl.value) scrollEl.value.scrollLeft = panStart.startScrollLeft - delta
}

function onPointerUp(event: PointerEvent): void {
  if (!panStart || event.pointerId !== panStart.pointerId) return
  panStart = null
  isPanning.value = false
}

function onClickCapture(event: MouseEvent): void {
  if (panMoved) {
    panMoved = false
    event.preventDefault()
    event.stopPropagation()
  }
}
</script>
