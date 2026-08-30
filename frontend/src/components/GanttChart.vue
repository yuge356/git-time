<template>
  <section class="activity-gantt" aria-label="计划进度表">
    <header class="activity-gantt__header">
      <div class="activity-gantt__heading">
        <p class="eyebrow">计划进度表</p>
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
    </header>

    <p v-if="rows.length === 0" class="empty-state">
      {{ loading ? '正在读取学习记录…' : '暂无学习记录；开始计时后，这里会展示每个任务的学习时间跨度。' }}
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
          <span>{{ group.rows.length }} 项 · {{ formatSeconds(group.totalSeconds) }}</span>
        </header>
        <button
          v-for="row in group.rows"
          :key="`card-${row.id}`"
          type="button"
          class="gantt-card"
          @click="openTask(row)"
        >
          <span class="gantt-card__title" :title="row.title">{{ row.title }}</span>
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
      :class="{ 'is-loading': loading, 'is-panning': isPanning, 'is-dragging-plan': Boolean(drag) }"
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
            <div class="gantt-head__corner">任务</div>
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
              <div class="gantt-group__header">
                <button
                  class="gantt-label gantt-label--group"
                  type="button"
                  :aria-expanded="!collapsedGroups.has(group.id)"
                  :title="group.title"
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
                  <span class="gantt-label__title">{{ group.title }}</span>
                </button>
                <div class="gantt-group__track">
                  <span class="gantt-group__count">
                    {{ group.rows.length }} 项 · {{ formatSeconds(group.totalSeconds) }}
                  </span>
                </div>
              </div>

              <template v-if="!collapsedGroups.has(group.id)">
                <div v-for="row in group.rows" :key="row.id" class="gantt-row">
                  <button
                    class="gantt-label"
                    type="button"
                    :title="row.title"
                    :aria-label="`查看${row.title}详情`"
                    @click="openTask(row)"
                  >
                    <span class="gantt-label__title">{{ row.title }}</span>
                    <span class="gantt-label__meta">
                      {{ formatSeconds(row.totalSeconds) }} · 持续 {{ row.spanDays }} 天
                    </span>
                  </button>
                  <div
                    class="gantt-track"
                    :class="{ 'is-dragging-track': drag && drag.taskId === row.id }"
                    @pointerdown="onTrackPointerDown(row, $event)"
                  >
                    <span
                      class="gantt-track__span"
                      :style="spanStyle(row)"
                      aria-hidden="true"
                    ></span>
                    <div
                      v-if="planWindow(row)"
                      class="gantt-plan"
                      :class="{ 'is-dragging': drag && drag.taskId === row.id }"
                      :style="planStyle(row, planWindow(row)!)"
                      role="presentation"
                      @pointerdown.stop="onPlanPointerDown(row, $event)"
                    >
                      <span
                        class="gantt-plan__handle gantt-plan__handle--start"
                        data-handle="start"
                        aria-hidden="true"
                      ></span>
                      <span
                        class="gantt-plan__handle gantt-plan__handle--end"
                        data-handle="end"
                        aria-hidden="true"
                      ></span>
                      <span v-if="planLabelVisible(row)" class="gantt-plan__label">
                        {{ planLabel(planWindow(row)!) }}
                      </span>
                    </div>
                    <button
                      v-for="segment in segmentsByRow.get(row.id) ?? []"
                      :key="segment.key"
                      class="gantt-bar"
                      type="button"
                      :style="segment.style"
                      :aria-label="barAriaLabel(row)"
                      @pointerdown.stop
                      @mouseenter="showTooltipAt(row, $event.clientX, $event.clientY)"
                      @mousemove="showTooltipAt(row, $event.clientX, $event.clientY)"
                      @mouseleave="hideTooltip"
                      @focus="showTooltipFromElement(row, $event)"
                      @blur="hideTooltip"
                      @click="openTask(row)"
                    >
                      <span
                        class="gantt-bar__fill"
                        :style="{ background: group.theme.primary, width: segment.fillWidth }"
                        aria-hidden="true"
                      ></span>
                      <span v-if="segment.showLabel" class="gantt-bar__label">
                        {{ row.title }}
                      </span>
                    </button>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <footer class="activity-gantt__footer">
      <span v-if="error" class="activity-gantt__error">{{ error }}</span>
      <span v-else-if="rows.length > 0">
        彩色条为真实学习记录（中断显示间隔）；虚线框为计划窗口，拖动空白排期、拖条或边缘调整起止；悬浮查看详情，点击跳转任务。
      </span>
    </footer>
  </section>

  <Teleport to="body">
    <div
      v-if="dragTip"
      class="gantt-dragtip"
      :style="{ left: `${dragTip.x}px`, top: `${dragTip.y}px` }"
      role="status"
    >
      <strong>{{ dragTip.title }}</strong>
      <span>{{ dragTip.text }}</span>
    </div>
    <div
      v-if="tooltip"
      class="gantt-tooltip"
      :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
      role="tooltip"
    >
      <strong :title="tooltip.row.title">{{ tooltip.row.title }}</strong>
      <span class="gantt-tooltip__project">
        <i
          :style="{ background: getProjectTheme(tooltip.row.projectId).primary }"
          aria-hidden="true"
        ></i>
        {{ tooltip.row.projectTitle }} · {{ statusLabel(tooltip.row.status) }}
      </span>
      <div class="gantt-tooltip__grid">
        <span><i>开始</i><b>{{ formatFullDate(tooltip.row.firstDate) }}</b></span>
        <span><i>结束</i><b>{{ formatFullDate(tooltip.row.lastDate) }}</b></span>
        <span><i>总学习时长</i><b>{{ formatSeconds(tooltip.row.totalSeconds) }}</b></span>
        <span><i>持续 / 活跃</i><b>{{ tooltip.row.spanDays }} / {{ tooltip.row.activeDays }} 天</b></span>
        <span>
          <i>完成进度</i>
          <b>{{ tooltip.row.progressRatio === null ? '—' : `${Math.round(tooltip.row.progressRatio * 100)}%` }}</b>
        </span>
      </div>
      <div
        v-if="tooltip.row.progressRatio !== null"
        class="gantt-tooltip__progress"
        aria-hidden="true"
      >
        <i
          :style="{
            width: `${Math.round(tooltip.row.progressRatio * 100)}%`,
            background: getProjectTheme(tooltip.row.projectId).primary,
          }"
        ></i>
      </div>
      <span class="gantt-tooltip__hint">点击条形查看任务详情</span>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import type { GanttChartRow } from '@/types/analytics'
import type { TaskStatus } from '@/types/task'
import { getProjectTheme, type ProjectTheme } from '@/utils/project-theme'
import { formatDuration } from '@/utils/time'

defineOptions({ name: 'GanttChart' })

type GanttScale = 'day' | 'week' | 'month'

interface GanttGroup {
  id: string
  title: string
  theme: ProjectTheme
  rows: GanttChartRow[]
  totalSeconds: number
  lastDate: string
}

interface GanttSegment {
  key: string
  left: number
  width: number
  fillWidth: string
  showLabel: boolean
  style: Record<string, string>
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

const emit = defineEmits<{
  (event: 'plan-change', payload: { taskId: string; start: string; end: string }): void
}>()

const MS_DAY = 86_400_000
const SCALE_STORAGE_KEY = 'dayflow:today-gantt-scale'
const TOOLTIP_WIDTH = 252
const TOOLTIP_HEIGHT = 252

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
  window.removeEventListener('pointermove', onDragPointerMove)
  window.removeEventListener('pointerup', onDragPointerUp)
  window.removeEventListener('pointercancel', onDragPointerUp)
})

const labelWidth = computed(() => (viewportWidth.value < 760 ? 132 : 184))
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

const earliestDate = computed(() =>
  props.rows.reduce<string | null>(
    (acc, row) => (!acc || row.firstDate < acc ? row.firstDate : acc),
    null,
  ),
)
const latestDate = computed(() =>
  props.rows.reduce<string>(
    (acc, row) => (row.lastDate > acc ? row.lastDate : acc),
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
        totalSeconds: 0,
        lastDate: '',
      }
      map.set(id, group)
    }
    group.rows.push(row)
    group.totalSeconds += row.totalSeconds
    if (row.lastDate > group.lastDate) group.lastDate = row.lastDate
  }
  const result = [...map.values()]
  for (const group of result) {
    group.rows.sort((left, right) => right.lastDate.localeCompare(left.lastDate))
  }
  return result.sort(
    (left, right) => right.lastDate.localeCompare(left.lastDate) || right.totalSeconds - left.totalSeconds,
  )
})

const collapsedGroups = ref(new Set<string>())
function toggleGroup(groupId: string): void {
  const next = new Set(collapsedGroups.value)
  if (next.has(groupId)) next.delete(groupId)
  else next.add(groupId)
  collapsedGroups.value = next
}

const segmentsByRow = computed(() => {
  const map = new Map<string, GanttSegment[]>()
  for (const group of groups.value) {
    for (const row of group.rows) {
      map.set(row.id, buildSegments(row, group.theme))
    }
  }
  return map
})

function buildSegments(row: GanttChartRow, theme: ProjectTheme): GanttSegment[] {
  const sorted = [...row.days].sort((left, right) => left.date.localeCompare(right.date))
  const runs: { start: string; days: number }[] = []
  for (const point of sorted) {
    const last = runs[runs.length - 1]
    if (
      last
      && diffDays(addDays(last.start, last.days - 1), point.date) === 1
    ) {
      last.days += 1
    } else {
      runs.push({ start: point.date, days: 1 })
    }
  }
  const base = hexToRgba(theme.primary, 0.5)
  const border = hexToRgba(theme.primary, 0.72)
  const fillWidth = row.progressRatio === null
    ? '100%'
    : `${Math.min(100, Math.round(row.progressRatio * 100))}%`
  const widest = runs.reduce((best, run) => (run.days > best.days ? run : best), runs[0] ?? { start: '', days: 0 })
  const showLabelOn = widest.days * dayWidth.value - 3 >= 64 ? widest.start : null
  return runs.map((run) => {
    const index = dayIndex(run.start)
    const width = Math.max(6, run.days * dayWidth.value - 3)
    return {
      key: `${row.id}:${run.start}`,
      left: index * dayWidth.value + 1.5,
      width,
      fillWidth,
      showLabel: run.start === showLabelOn && scale.value !== 'month',
      style: {
        left: `${index * dayWidth.value + 1.5}px`,
        width: `${width}px`,
        background: base,
        borderColor: border,
      },
    }
  })
}

function spanStyle(row: GanttChartRow): Record<string, string> {
  const theme = getProjectTheme(row.projectId)
  const index = dayIndex(row.firstDate)
  const width = Math.max(4, (diffDays(row.firstDate, row.lastDate) + 1) * dayWidth.value - 3)
  return {
    left: `${index * dayWidth.value + 1.5}px`,
    width: `${width}px`,
    background: hexToRgba(theme.primary, 0.13),
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
  return `${row.title}（${row.projectTitle}），${formatFullDate(row.firstDate)}至${formatFullDate(row.lastDate)}，累计学习 ${formatSeconds(row.totalSeconds)}${progress}`
}

function openTask(row: GanttChartRow): void {
  void router.push({ name: 'tasks', query: { task: row.id } })
}

const tooltip = ref<{ row: GanttChartRow; x: number; y: number } | null>(null)

function showTooltipAt(row: GanttChartRow, pointerX: number, pointerY: number): void {
  let x = pointerX + 14
  let y = pointerY + 16
  if (x + TOOLTIP_WIDTH > window.innerWidth - 8) x = pointerX - TOOLTIP_WIDTH - 14
  if (y + TOOLTIP_HEIGHT > window.innerHeight - 8) y = pointerY - TOOLTIP_HEIGHT - 16
  tooltip.value = { row, x: Math.max(8, x), y: Math.max(8, y) }
}

function showTooltipFromElement(row: GanttChartRow, event: FocusEvent): void {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  showTooltipAt(row, Math.min(rect.right, window.innerWidth - TOOLTIP_WIDTH - 22), rect.top)
}

function hideTooltip(): void {
  tooltip.value = null
}

/* ---- 计划窗口拖拽：拖动平移、拖边缘缩放、在轨道空白处拖出新窗口 ---- */

interface PlanWindow {
  start: string
  end: string
}

interface DragState {
  mode: 'move' | 'resize-start' | 'resize-end' | 'create'
  taskId: string
  title: string
  origStart: string
  origEnd: string
  startDate: string
  endDate: string
  anchorDate: string
  pointerId: number
  trackRect: DOMRect
  moved: boolean
  startX: number
}

const drag = ref<DragState | null>(null)
const dragTip = ref<{ title: string; text: string; x: number; y: number } | null>(null)

function planWindow(row: GanttChartRow): PlanWindow | null {
  if (drag.value && drag.value.taskId === row.id) {
    return { start: drag.value.startDate, end: drag.value.endDate }
  }
  if (row.plannedStart && row.plannedEnd) {
    return { start: row.plannedStart, end: row.plannedEnd }
  }
  return null
}

function planStyle(row: GanttChartRow, plan: PlanWindow): Record<string, string> {
  const theme = getProjectTheme(row.projectId)
  const index = dayIndex(plan.start)
  const width = Math.max(
    dayWidth.value,
    (diffDays(plan.start, plan.end) + 1) * dayWidth.value - 3,
  )
  return {
    left: `${index * dayWidth.value + 1.5}px`,
    width: `${width}px`,
    borderColor: theme.primary,
    background: theme.soft,
  }
}

function planLabel(plan: PlanWindow): string {
  return `${formatDayLabel(plan.start)} – ${formatDayLabel(plan.end)}`
}

function planLabelVisible(row: GanttChartRow): boolean {
  const plan = planWindow(row)
  if (!plan) return false
  return (diffDays(plan.start, plan.end) + 1) * dayWidth.value >= 76
}

function dateFromClient(clientX: number, rect: DOMRect): string {
  const index = Math.min(
    totalDays.value - 1,
    Math.max(0, Math.floor((clientX - rect.left) / dayWidth.value)),
  )
  return addDays(rangeStart.value, index)
}

function startPlanDrag(
  row: GanttChartRow,
  event: PointerEvent,
  mode: DragState['mode'],
  trackRect: DOMRect,
): void {
  hideTooltip()
  const anchor = dateFromClient(event.clientX, trackRect)
  drag.value = {
    mode,
    taskId: row.id,
    title: row.title,
    origStart: row.plannedStart ?? anchor,
    origEnd: row.plannedEnd ?? anchor,
    startDate: anchor,
    endDate: anchor,
    anchorDate: anchor,
    pointerId: event.pointerId,
    trackRect,
    moved: false,
    startX: event.clientX,
  }
  window.addEventListener('pointermove', onDragPointerMove)
  window.addEventListener('pointerup', onDragPointerUp)
  window.addEventListener('pointercancel', onDragPointerUp)
}

function onPlanPointerDown(row: GanttChartRow, event: PointerEvent): void {
  if (event.pointerType !== 'mouse' && !isResizeHandle(event.target)) return
  if (event.pointerType === 'mouse' && event.button !== 0) return
  const track = (event.currentTarget as HTMLElement).closest('.gantt-track')
  if (!track) return
  const handle = isResizeHandle(event.target)
  startPlanDrag(row, event, handle ? handle : 'move', track.getBoundingClientRect())
}

function isResizeHandle(target: EventTarget | null): 'resize-start' | 'resize-end' | null {
  const handle = (target as HTMLElement | null)?.closest?.('[data-handle]')
  const kind = handle?.getAttribute('data-handle')
  if (kind === 'start') return 'resize-start'
  if (kind === 'end') return 'resize-end'
  return null
}

function onTrackPointerDown(row: GanttChartRow, event: PointerEvent): void {
  // 空白处拖出新计划窗口仅限鼠标；触屏留给原生滚动。
  if (event.pointerType !== 'mouse' || event.button !== 0) return
  const track = event.currentTarget as HTMLElement
  startPlanDrag(row, event, 'create', track.getBoundingClientRect())
}

function onDragPointerMove(event: PointerEvent): void {
  const state = drag.value
  if (!state || event.pointerId !== state.pointerId) return
  if (Math.abs(event.clientX - state.startX) > 3) state.moved = true
  const date = dateFromClient(event.clientX, state.trackRect)
  if (state.mode === 'move') {
    const span = diffDays(state.origStart, state.origEnd)
    let start = addDays(state.origStart, diffDays(state.anchorDate, date))
    if (dayIndex(start) < 0) start = rangeStart.value
    if (dayIndex(start) + span > totalDays.value - 1) {
      start = addDays(rangeStart.value, totalDays.value - 1 - span)
    }
    state.startDate = start
    state.endDate = addDays(start, span)
  } else if (state.mode === 'resize-start') {
    state.startDate = date < state.origEnd ? date : state.origEnd
    state.endDate = state.origEnd
  } else if (state.mode === 'resize-end') {
    state.startDate = state.origStart
    state.endDate = date > state.origStart ? date : state.origStart
  } else {
    state.startDate = date < state.anchorDate ? date : state.anchorDate
    state.endDate = date > state.anchorDate ? date : state.anchorDate
  }
  dragTip.value = {
    title: state.title,
    text: `${formatFullDate(state.startDate)} – ${formatFullDate(state.endDate)}`,
    x: event.clientX + 14,
    y: event.clientY + 18,
  }
}

function onDragPointerUp(event: PointerEvent): void {
  const state = drag.value
  if (!state || event.pointerId !== state.pointerId) return
  drag.value = null
  dragTip.value = null
  window.removeEventListener('pointermove', onDragPointerMove)
  window.removeEventListener('pointerup', onDragPointerUp)
  window.removeEventListener('pointercancel', onDragPointerUp)
  // 空白处单击视为误触；窗口未变化时不打扰后端。
  if (state.mode === 'create' && !state.moved) return
  if (state.startDate === state.origStart && state.endDate === state.origEnd) return
  emit('plan-change', {
    taskId: state.taskId,
    start: state.startDate,
    end: state.endDate,
  })
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
