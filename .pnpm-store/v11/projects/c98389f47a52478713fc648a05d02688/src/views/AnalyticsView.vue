<template>
  <AppShell>
    <main class="analytics-page">
      <section class="page-heading analytics-heading">
        <div>
          <p class="eyebrow">时间统计</p>
          <h1>看清时间去了哪里</h1>
          <p>统计来自计时记录、任务预算与每日计划完成状态。</p>
        </div>
        <form class="analytics-filter" @submit.prevent="load">
          <label class="field">
            <span>开始日期</span>
            <input v-model="dateFrom" type="date" required />
          </label>
          <label class="field">
            <span>结束日期</span>
            <input v-model="dateTo" type="date" required />
          </label>
          <button class="button button--primary" type="submit" :disabled="loading">
            {{ loading ? '统计中…' : '应用' }}
          </button>
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

      <section class="analytics-metrics">
        <article>
          <span>总投入时长</span>
          <strong>{{ readableDuration(summary?.total_learning_seconds ?? 0) }}</strong>
        </article>
        <article>
          <span>完成计时</span>
          <strong>{{ summary?.completed_session_count ?? 0 }} 次</strong>
        </article>
        <article>
          <span>完成项目任务</span>
          <strong>
            {{ summary?.completed_task_count ?? 0 }}/{{ summary?.total_task_count ?? 0 }}
          </strong>
        </article>
      </section>

      <section class="analytics-grid">
        <article class="analytics-card analytics-card--wide">
          <header>
            <p class="eyebrow">每日趋势</p>
            <h2>投入时长与完成项</h2>
          </header>
          <p v-if="!hasDailyActivity" class="empty-state">所选日期内还没有计时记录。</p>
          <div v-else class="trend-chart" role="img" aria-label="每日投入时长柱状图">
            <div v-for="point in summary?.daily_trend" :key="point.date" class="trend-column">
              <span class="trend-value">{{ compactDuration(point.seconds) }}</span>
              <div class="trend-track">
                <div
                  class="trend-bar"
                  :style="{ height: `${trendHeight(point.seconds)}%` }"
                />
              </div>
              <strong>{{ shortDate(point.date) }}</strong>
              <small>{{ point.completed_items }} 项</small>
            </div>
          </div>
        </article>

        <article class="analytics-card">
          <header>
            <p class="eyebrow">任务分布</p>
            <h2>直接投入占比</h2>
          </header>
          <p v-if="summary?.task_distribution.length === 0" class="empty-state">
            暂无可分配的投入时长。
          </p>
          <ol v-else class="distribution-list">
            <li v-for="item in summary?.task_distribution" :key="item.task_id ?? 'adhoc'">
              <div>
                <strong>{{ item.title }}</strong>
                <span>{{ readableDuration(item.seconds) }}</span>
              </div>
              <div class="distribution-track">
                <span :style="{ width: `${Math.max(2, item.percentage * 100)}%` }" />
              </div>
              <small>{{ Math.round(item.percentage * 100) }}%</small>
            </li>
          </ol>
        </article>

        <article class="analytics-card analytics-card--full">
          <header>
            <p class="eyebrow">预算偏差</p>
            <h2>计划用时与实际投入</h2>
          </header>
          <p v-if="summary?.budget_comparison.length === 0" class="empty-state">
            还没有设置任务预算或产生投入时长。
          </p>
          <div v-else class="budget-table-wrap">
            <table class="budget-table">
              <thead>
                <tr>
                  <th>任务</th>
                  <th>预算</th>
                  <th>实际</th>
                  <th>偏差</th>
                  <th>使用率</th>
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
                    {{ item.usage_ratio === null ? '未设置' : `${Math.round(item.usage_ratio * 100)}%` }}
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
import type { AnalyticsSummary } from '@/types/analytics'
import { getApiErrorMessage } from '@/utils/api-error'

function localDateString(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const today = new Date()
const weekStart = new Date(today)
weekStart.setDate(today.getDate() - 6)
const dateFrom = ref(localDateString(weekStart))
const dateTo = ref(localDateString(today))
const summary = ref<AnalyticsSummary | null>(null)
const auth = useAuthStore()
const timer = useTimerStore()
const loading = ref(false)
const errorMessage = ref('')
const maxDailySeconds = computed(() =>
  Math.max(1, ...(summary.value?.daily_trend.map((point) => point.seconds) ?? [1])),
)
const hasDailyActivity = computed(() =>
  summary.value?.daily_trend.some((point) => point.seconds > 0),
)

onMounted(load)

watch(
  () => timer.completedRevision,
  () => void load(),
)

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

function readableDuration(seconds: number): string {
  const minutes = Math.round(Math.max(0, seconds) / 60)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours && rest) return `${hours} 小时 ${rest} 分钟`
  if (hours) return `${hours} 小时`
  return `${rest} 分钟`
}

function compactDuration(seconds: number): string {
  if (seconds < 60) return '0m'
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

function signedDuration(seconds: number): string {
  const prefix = seconds > 0 ? '+' : seconds < 0 ? '−' : ''
  return `${prefix}${readableDuration(Math.abs(seconds))}`
}

function trendHeight(seconds: number): number {
  return Math.max(seconds > 0 ? 5 : 0, (seconds / maxDailySeconds.value) * 100)
}

function shortDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  })
}
</script>
