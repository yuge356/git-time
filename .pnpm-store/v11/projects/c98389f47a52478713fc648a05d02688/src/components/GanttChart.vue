<template>
  <section class="activity-gantt" aria-label="计划进度表">
    <header class="activity-gantt__header">
      <div>
        <p class="eyebrow">计划进度表</p>
      </div>
      <div class="activity-gantt__summary">
        <strong>{{ formatSeconds(totalSeconds) }}</strong>
        <span>{{ rows.length }} 个任务的学习跨度</span>
      </div>
    </header>

    <p v-if="rows.length === 0" class="empty-state">
      {{ loading ? '正在读取学习记录…' : '暂无学习记录；开始计时后，这里会展示每个任务的学习时间跨度。' }}
    </p>

    <div v-else class="activity-gantt__scroll" :class="{ 'is-loading': loading }">
      <div class="activity-gantt__canvas" :style="{ width: `${canvasWidth}px` }">
        <div class="activity-gantt__dates">
          <span class="activity-gantt__corner">任务</span>
          <span
            v-for="tick in ticks"
            :key="tick.date"
            class="activity-gantt__date"
            :style="{ left: `${tick.labelLeft}px` }"
            aria-hidden="true"
          >
            {{ tick.label }}
          </span>
        </div>
        <div class="activity-gantt__body">
          <span
            v-for="tick in ticks"
            :key="`line-${tick.date}`"
            class="activity-gantt__gridline"
            :style="{ left: `${tick.lineLeft}px` }"
            aria-hidden="true"
          ></span>
          <div v-for="row in rows" :key="row.id" class="activity-gantt__row">
            <span class="activity-gantt__label" :title="row.title">{{ row.title }}</span>
            <div class="activity-gantt__track">
              <div
                class="activity-gantt__bar"
                :style="barStyle(row)"
                tabindex="0"
                :aria-label="`${row.title}，累计学习 ${formatSeconds(row.totalSeconds)}`"
                @mouseenter="showTooltipAt(row, $event.clientX, $event.clientY)"
                @mousemove="showTooltipAt(row, $event.clientX, $event.clientY)"
                @mouseleave="hideTooltip"
                @focus="showTooltipFromElement(row, $event)"
                @blur="hideTooltip"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <footer class="activity-gantt__footer">
      <span v-if="error" class="activity-gantt__error">{{ error }}</span>
      <span v-else-if="rows.length > 0">
        条形为任务学习时间跨度，悬浮查看累计时长与每日明细；横向滚动查看更多日期。
      </span>
    </footer>
  </section>

  <Teleport to="body">
    <div
      v-if="tooltip"
      class="gantt-tooltip"
      :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
      role="tooltip"
    >
      <strong>{{ tooltip.row.title }}</strong>
      <span class="gantt-tooltip__total">累计学习 {{ formatSeconds(tooltip.row.totalSeconds) }}</span>
      <div class="gantt-tooltip__days">
        <span v-for="day in tooltip.row.days" :key="day.date">
          <i>{{ formatDayLabel(day.date) }}</i>
          <b>{{ formatSeconds(day.seconds) }}</b>
        </span>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import type { GanttChartRow } from '@/types/analytics'
import { formatDuration } from '@/utils/time'

defineOptions({ name: 'GanttChart' })

const props = withDefaults(
  defineProps<{
    rows: GanttChartRow[]
    today: string
    loading?: boolean
    error?: string
  }>(),
  { loading: false, error: '' },
)

const LABEL_WIDTH = 176
const DAY_WIDTH = 32
const MIN_WINDOW_DAYS = 13
const TOOLTIP_WIDTH = 248
const TOOLTIP_HEIGHT = 320

const tooltip = ref<{ row: GanttChartRow; x: number; y: number } | null>(null)

const windowStart = computed(() => {
  let earliest = addDays(props.today, -MIN_WINDOW_DAYS)
  for (const row of props.rows) {
    if (row.firstDate < earliest) earliest = row.firstDate
  }
  return earliest
})

const totalDays = computed(() => dayIndex(props.today) + 1)

const canvasWidth = computed(() => LABEL_WIDTH + totalDays.value * DAY_WIDTH)

const ticks = computed(() => {
  const step = niceStep(Math.ceil(totalDays.value / 36))
  const result: { date: string; label: string; lineLeft: number; labelLeft: number }[] = []
  for (let day = 0; day < totalDays.value; day += step) {
    const date = addDays(windowStart.value, day)
    result.push({
      date,
      label: formatDayLabel(date),
      lineLeft: LABEL_WIDTH + day * DAY_WIDTH,
      labelLeft: LABEL_WIDTH + day * DAY_WIDTH + 8,
    })
  }
  return result
})

const totalSeconds = computed(() =>
  props.rows.reduce((total, row) => total + row.totalSeconds, 0),
)

function formatSeconds(seconds: number): string {
  return seconds > 0 ? formatDuration(seconds) : '0 分钟'
}

function parseDay(date: string): number {
  return Date.parse(`${date}T00:00:00Z`)
}

function addDays(date: string, days: number): string {
  return new Date(parseDay(date) + days * 86_400_000).toISOString().slice(0, 10)
}

function dayIndex(date: string): number {
  return Math.round((parseDay(date) - parseDay(windowStart.value)) / 86_400_000)
}

function niceStep(raw: number): number {
  const steps = [1, 2, 3, 5, 7, 10, 14, 21, 30]
  return steps.find((candidate) => candidate >= raw) ?? 30
}

function formatDayLabel(date: string): string {
  const [, month, day] = date.split('-')
  return `${Number(month)}.${Number(day)}`
}

function barStyle(row: GanttChartRow): Record<string, string> {
  const start = dayIndex(row.firstDate)
  const end = dayIndex(row.lastDate)
  return {
    left: `${LABEL_WIDTH + start * DAY_WIDTH + 3}px`,
    width: `${Math.max(10, (end - start + 1) * DAY_WIDTH - 6)}px`,
  }
}

function showTooltipAt(row: GanttChartRow, pointerX: number, pointerY: number): void {
  let x = pointerX + 14
  let y = pointerY + 16
  if (x + TOOLTIP_WIDTH > window.innerWidth - 8) x = pointerX - TOOLTIP_WIDTH - 14
  if (y + TOOLTIP_HEIGHT > window.innerHeight - 8) y = pointerY - TOOLTIP_HEIGHT - 16
  tooltip.value = {
    row,
    x: Math.max(8, x),
    y: Math.max(8, y),
  }
}

function showTooltipFromElement(row: GanttChartRow, event: FocusEvent): void {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  showTooltipAt(row, Math.min(rect.right, window.innerWidth - TOOLTIP_WIDTH - 22), rect.top)
}

function hideTooltip(): void {
  tooltip.value = null
}
</script>
