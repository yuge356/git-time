<template>
  <main class="onboarding-page">
    <header class="onboarding-header">
      <AppLogo />
      <button class="onboarding-skip" type="button" :disabled="auth.loading" @click="finish">
        跳过指引
      </button>
    </header>

    <section class="onboarding-shell" aria-labelledby="onboarding-title">
      <div class="onboarding-progress">
        <div>
          <span>首次使用指引</span>
          <strong>{{ currentStep + 1 }} / {{ steps.length }}</strong>
        </div>
        <div class="onboarding-progress__track" aria-hidden="true">
          <span :style="{ width: `${progressPercent}%` }" />
        </div>
      </div>

      <div class="onboarding-content">
        <div class="onboarding-copy" aria-live="polite">
          <p class="eyebrow">{{ step.kicker }}</p>
          <h1 id="onboarding-title">{{ step.title }}</h1>
          <p>{{ step.description }}</p>
          <ul>
            <li v-for="point in step.points" :key="point">{{ point }}</li>
          </ul>
        </div>

        <div class="onboarding-preview">
          <img :src="step.image" :alt="step.alt" />
          <span>{{ step.caption }}</span>
        </div>
      </div>

      <FormMessage :message="errorMessage" />

      <footer class="onboarding-footer">
        <button
          class="button button--quiet"
          type="button"
          :disabled="currentStep === 0 || auth.loading"
          @click="currentStep -= 1"
        >
          上一步
        </button>
        <div class="onboarding-footer__steps" aria-label="指引进度">
          <span
            v-for="(_, index) in steps"
            :key="index"
            :class="{ 'is-active': index <= currentStep }"
          />
        </div>
        <button
          v-if="currentStep < steps.length - 1"
          class="button button--primary"
          type="button"
          @click="currentStep += 1"
        >
          下一步
        </button>
        <button
          v-else
          class="button button--primary"
          type="button"
          :disabled="auth.loading"
          @click="finish"
        >
          {{ auth.loading ? '正在进入…' : '进入 DayFlow' }}
        </button>
      </footer>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppLogo from '@/components/AppLogo.vue'
import FormMessage from '@/components/FormMessage.vue'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/utils/api-error'

const steps = [
  {
    kicker: '01 · 今天',
    title: '从今天最重要的一项开始',
    description: '“今日任务”是你的工作台。安排任务、选择目标，然后直接开始专注计时。',
    points: ['日历显示每天的投入深浅', '暂停、继续和结束都会保留真实时长'],
    image: '/welcome-today.png',
    alt: 'DayFlow 今日任务工作台',
    caption: '今日任务 · 专注计时 · 月度节奏',
  },
  {
    kicker: '02 · 项目与任务',
    title: '把目标拆成可以行动的结构',
    description: '用“项目 → 模块 → 任务”组织工作，也可以在任务树与大纲列表之间切换。',
    points: ['为任务设置预算、重复频次和截止日期', '把具体任务加入今天，再专注执行'],
    image: '/welcome-tasks.png',
    alt: 'DayFlow 项目任务界面',
    caption: '项目结构 · 任务预算 · 进度管理',
  },
  {
    kicker: '03 · 时间统计',
    title: '用数据找到更适合自己的节奏',
    description: '时间统计会根据你的计时记录，汇总任务分布、投入趋势和预算偏差。',
    points: ['自由查看日、周、月、年趋势', '用历史投入复盘项目与任务'],
    image: '/welcome-analytics.png',
    alt: 'DayFlow 时间统计界面',
    caption: '投入分布 · 时间趋势 · 预算复盘',
  },
] as const

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const currentStep = ref(0)
const errorMessage = ref('')

const step = computed(() => steps[currentStep.value] ?? steps[0])
const progressPercent = computed(() => ((currentStep.value + 1) / steps.length) * 100)

function requestedDestination(): string {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')
    ? redirect
    : '/today'
}

async function finish(): Promise<void> {
  errorMessage.value = ''
  try {
    await auth.completeOnboarding()
    await router.replace(requestedDestination())
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}
</script>
