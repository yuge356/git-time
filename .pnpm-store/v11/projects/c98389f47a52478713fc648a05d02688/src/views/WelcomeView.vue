<template>
  <main class="welcome-page">
    <header class="welcome-header">
      <AppLogo />
      <nav class="welcome-header__actions" aria-label="账户入口">
        <RouterLink class="button button--quiet" :to="{ name: 'login' }">登录</RouterLink>
        <RouterLink class="button button--primary" :to="{ name: 'login', query: { mode: 'register' } }">
          注册
        </RouterLink>
      </nav>
    </header>

    <section class="welcome-hero" aria-labelledby="welcome-title">
      <div class="welcome-hero__copy">
        <p class="eyebrow">DAYFLOW · 项目与时间管理</p>
        <h1 id="welcome-title">让计划真正<br />流动起来。</h1>
        <p class="welcome-hero__lead">把任务、专注计时和投入趋势放在同一条清晰的工作流里。</p>
        <div class="welcome-hero__actions">
          <RouterLink
            class="button button--primary welcome-hero__primary"
            :to="{ name: 'login', query: { mode: 'register' } }"
          >
            免费开始
          </RouterLink>
          <a class="welcome-text-link" href="#product-preview">看看 DayFlow</a>
        </div>
        <ul class="welcome-hero__notes" aria-label="产品特点">
          <li>项目结构</li>
          <li>专注计时</li>
          <li>趋势分析</li>
        </ul>
      </div>

      <div id="product-preview" class="welcome-showcase">
        <div
          ref="carousel"
          class="welcome-carousel"
          tabindex="0"
          aria-label="DayFlow 产品界面预览，可左右滑动"
          @scroll.passive="updateActiveSlide"
        >
          <article
            v-for="(slide, index) in slides"
            :key="slide.id"
            class="welcome-slide"
            :aria-label="`${index + 1} / ${slides.length}：${slide.title}`"
          >
            <header>
              <span>{{ slide.kicker }}</span>
              <strong>{{ slide.title }}</strong>
              <p>{{ slide.description }}</p>
            </header>
            <div class="welcome-slide__image">
              <div
                v-if="slide.kind === 'demo'"
                :key="demoCycle"
                class="welcome-task-tree-demo"
                role="img"
                aria-label="横向任务树动画：叶子任务完成后，进度沿连接线逐级汇聚，最终完成整个项目"
              >
                <div class="welcome-task-tree-demo__scene">
                  <svg
                    class="welcome-task-tree-demo__lines"
                    viewBox="0 0 1000 590"
                    preserveAspectRatio="none"
                    aria-hidden="true"
                  >
                    <g v-for="connection in demoConnections" :key="connection.id">
                      <path class="welcome-task-tree-demo__line-base" :d="connection.path" pathLength="1" />
                      <path
                        class="welcome-task-tree-demo__line-progress"
                        :d="connection.path"
                        pathLength="1"
                        :style="{ '--delay': connection.delay }"
                      />
                    </g>
                  </svg>

                  <article
                    v-for="node in demoNodes"
                    :key="node.id"
                    class="welcome-task-tree-demo__node"
                    :class="[
                      `welcome-task-tree-demo__node--${node.level}`,
                      `welcome-task-tree-demo__node--${node.branch}`,
                    ]"
                    :style="{
                      left: node.left,
                      top: node.top,
                      width: node.width,
                      '--delay': node.delay,
                    }"
                  >
                    <span class="welcome-task-tree-demo__fill" aria-hidden="true" />
                    <div class="welcome-task-tree-demo__node-content">
                      <div class="welcome-task-tree-demo__node-heading">
                        <strong>{{ node.title }}</strong>
                        <span>{{ node.estimate }}</span>
                      </div>
                      <div class="welcome-task-tree-demo__status">
                        <span class="welcome-task-tree-demo__status-pending">待开始</span>
                        <span class="welcome-task-tree-demo__status-complete">
                          <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M5 12.5 9.4 17 19 7.5" pathLength="1" />
                          </svg>
                          已完成
                        </span>
                      </div>
                    </div>
                  </article>
                </div>
              </div>
              <img v-else :src="slide.image" :alt="slide.alt" loading="eager" />
            </div>
          </article>
        </div>

        <div class="welcome-carousel__controls">
          <div class="welcome-carousel__dots" aria-label="选择预览页面">
            <button
              v-for="(_, index) in slides"
              :key="index"
              type="button"
              :class="{ 'is-active': activeSlide === index }"
              :aria-label="`查看第 ${index + 1} 张预览`"
              :aria-current="activeSlide === index ? 'true' : undefined"
              @click="showSlide(index)"
            />
          </div>
          <div class="welcome-carousel__arrows">
            <button type="button" aria-label="上一张" @click="showSlide(activeSlide - 1)">←</button>
            <button type="button" aria-label="下一张" @click="showSlide(activeSlide + 1)">→</button>
          </div>
        </div>
      </div>
    </section>

    <section class="welcome-features" aria-labelledby="welcome-features-title">
      <div>
        <p class="eyebrow">一条更自然的工作流</p>
        <h2 id="welcome-features-title">从计划，到专注，再到复盘。</h2>
      </div>
      <div class="welcome-feature-grid">
        <article>
          <span>01</span>
          <h3>组织任务</h3>
          <p>用项目、模块和任务保持结构清楚。</p>
        </article>
        <article>
          <span>02</span>
          <h3>记录投入</h3>
          <p>今天做什么、用了多久，一目了然。</p>
        </article>
        <article>
          <span>03</span>
          <h3>看见趋势</h3>
          <p>通过日、周、月、年数据持续调整节奏。</p>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import AppLogo from '@/components/AppLogo.vue'

const slides = [
  {
    id: 'task-tree-demo',
    kind: 'demo',
    kicker: '进度汇聚',
    title: '看见每个任务如何推动项目完成',
    description: '时间预算从叶子任务逐级汇聚，清晰呈现项目完成逻辑。',
    image: '',
    alt: '',
  },
  {
    id: 'today',
    kind: 'image',
    kicker: '今天',
    title: '把注意力留给眼前的一项任务',
    description: '计时日历、专注计时和今日任务在同一页自然衔接。',
    image: '/welcome-today.png',
    alt: 'DayFlow 今日任务与专注计时界面',
  },
  {
    id: 'analytics',
    kind: 'image',
    kicker: '时间统计',
    title: '让每一段投入都有回响',
    description: '从时间分布和趋势中看见节奏，及时修正计划。',
    image: '/welcome-analytics.png',
    alt: 'DayFlow 时间统计与趋势分析界面',
  },
  {
    id: 'tasks',
    kind: 'image',
    kicker: '项目',
    title: '用清晰结构承接复杂计划',
    description: '在项目、模块和任务之间建立可执行的层级关系。',
    image: '/welcome-tasks.png',
    alt: 'DayFlow 项目与任务管理界面',
  },
] as const

const demoNodes = [
  {
    id: 'project',
    title: 'DayFlow 发布',
    estimate: '50h',
    level: 'root',
    branch: 'mixed',
    left: '5%',
    top: '40%',
    width: '22%',
    delay: '9.8s',
  },
  {
    id: 'experience',
    title: '体验设计',
    estimate: '22h',
    level: 'parent',
    branch: 'experience',
    left: '37%',
    top: '17%',
    width: '23%',
    delay: '3.5s',
  },
  {
    id: 'data',
    title: '数据能力',
    estimate: '28h',
    level: 'parent',
    branch: 'data',
    left: '37%',
    top: '65%',
    width: '23%',
    delay: '7.7s',
  },
  {
    id: 'prototype',
    title: '界面原型',
    estimate: '6h',
    level: 'leaf',
    branch: 'experience',
    left: '70%',
    top: '5%',
    width: '24%',
    delay: '0.5s',
  },
  {
    id: 'motion',
    title: '任务树动效',
    estimate: '16h',
    level: 'leaf',
    branch: 'experience',
    left: '70%',
    top: '27%',
    width: '24%',
    delay: '1.9s',
  },
  {
    id: 'analytics',
    title: '时间统计',
    estimate: '8h',
    level: 'leaf',
    branch: 'data',
    left: '70%',
    top: '56%',
    width: '24%',
    delay: '4.7s',
  },
  {
    id: 'sync',
    title: '数据同步',
    estimate: '20h',
    level: 'leaf',
    branch: 'data',
    left: '70%',
    top: '78%',
    width: '24%',
    delay: '6.1s',
  },
] as const

const demoConnections = [
  { id: 'prototype-experience', path: 'M700 80 C650 80 650 153 600 153', delay: '1.7s' },
  { id: 'motion-experience', path: 'M700 209 C650 209 650 153 600 153', delay: '3.1s' },
  { id: 'experience-project', path: 'M370 153 C320 153 320 295 270 295', delay: '4.7s' },
  { id: 'analytics-data', path: 'M700 380 C650 380 650 437 600 437', delay: '5.9s' },
  { id: 'sync-data', path: 'M700 510 C650 510 650 437 600 437', delay: '7.3s' },
  { id: 'data-project', path: 'M370 437 C320 437 320 295 270 295', delay: '8.9s' },
] as const

const carousel = ref<HTMLElement | null>(null)
const activeSlide = ref(0)
const demoCycle = ref(0)
let demoCycleTimer: number | undefined

onMounted(() => {
  demoCycleTimer = window.setInterval(() => {
    demoCycle.value += 1
  }, 14_400)
})

onBeforeUnmount(() => {
  if (demoCycleTimer !== undefined) window.clearInterval(demoCycleTimer)
})

function showSlide(index: number): void {
  const normalized = (index + slides.length) % slides.length
  activeSlide.value = normalized
  if (normalized === 0) demoCycle.value += 1
  const target = carousel.value?.children.item(normalized)
  if (target instanceof HTMLElement) {
    target.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' })
  }
}

function updateActiveSlide(): void {
  const element = carousel.value
  if (!element) return
  const firstSlide = element.firstElementChild
  if (!(firstSlide instanceof HTMLElement)) return
  const gap = Number.parseFloat(getComputedStyle(element).columnGap || '0')
  const slideWidth = firstSlide.offsetWidth + gap
  if (slideWidth <= 0) return
  activeSlide.value = Math.min(slides.length - 1, Math.max(0, Math.round(element.scrollLeft / slideWidth)))
}
</script>
