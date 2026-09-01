<template>
  <main class="welcome-page">
    <div class="welcome-aurora" aria-hidden="true">
      <span class="welcome-aurora__blob welcome-aurora__blob--violet" />
      <span class="welcome-aurora__blob welcome-aurora__blob--pink" />
      <span class="welcome-aurora__blob welcome-aurora__blob--blue" />
    </div>

    <header class="welcome-header" :class="{ 'is-scrolled': scrolled }">
      <div class="welcome-header__inner">
        <AppLogo />
        <nav class="welcome-header__actions" aria-label="账户入口">
          <RouterLink class="button button--quiet" :to="{ name: 'login' }">登录</RouterLink>
          <RouterLink class="button button--primary" :to="{ name: 'login', query: { mode: 'register' } }">
            免费注册
          </RouterLink>
        </nav>
      </div>
    </header>

    <section
      class="welcome-hero"
      aria-labelledby="welcome-title"
      :style="tiltStyle"
      @pointermove.passive="trackPointer"
      @pointerleave="resetTilt"
    >
      <div class="welcome-hero__copy">
        <p class="eyebrow welcome-rise" :style="{ '--rise': 1 }">DAYFLOW · 时间预算</p>
        <h1 id="welcome-title" class="welcome-rise" :style="{ '--rise': 2 }">
          让每一分钟<br />流向<em>重要的事</em>
        </h1>
        <p class="welcome-hero__lead welcome-rise" :style="{ '--rise': 3 }">
          计划、专注、复盘串成一条线。<br class="welcome-only-wide" />
          先看清时间去哪了，再谈管理时间。
        </p>
        <div class="welcome-hero__actions welcome-rise" :style="{ '--rise': 4 }">
          <RouterLink
            class="button button--primary welcome-hero__primary"
            :to="{ name: 'login', query: { mode: 'register' } }"
          >
            免费开始
          </RouterLink>
          <a class="welcome-text-link" href="#product-preview" @click="pauseAutoplay">
            看看 DayFlow
          </a>
        </div>
        <ul class="welcome-hero__notes welcome-rise" :style="{ '--rise': 5 }" aria-label="产品特点">
          <li>项目结构</li>
          <li>专注计时</li>
          <li>趋势分析</li>
          <li>离线可用</li>
        </ul>
      </div>

      <div id="product-preview" class="welcome-showcase welcome-fade" :style="{ '--rise': 3 }">
        <div class="welcome-stage">
          <article
            v-for="(slide, index) in slides"
            :key="slide.id"
            class="welcome-frame"
            :class="{ 'is-active': activeSlide === index }"
            :aria-hidden="activeSlide === index ? undefined : 'true'"
          >
            <div class="welcome-frame__visual">
              <div
                v-if="slide.kind === 'demo'"
                v-show="activeSlide === index"
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
              <img v-else :src="slide.image" :alt="slide.alt" loading="eager" decoding="async" />
            </div>
          </article>

          <p class="welcome-stage__caption" aria-live="polite">
            <span>{{ activeSlideMeta.kicker }}</span>
            <strong>{{ activeSlideMeta.title }}</strong>
          </p>
        </div>

        <div class="welcome-showcase__controls">
          <div class="welcome-carousel__dots" aria-label="选择预览页面">
            <button
              v-for="(slide, index) in slides"
              :key="slide.id"
              type="button"
              :class="{ 'is-active': activeSlide === index }"
              :aria-label="`查看预览：${slide.title}`"
              :aria-current="activeSlide === index ? 'true' : undefined"
              @click="showSlide(index)"
            />
          </div>
          <p class="welcome-showcase__hint">{{ activeSlide + 1 }} / {{ slides.length }}</p>
        </div>

        <div class="welcome-float-card welcome-float-card--one" aria-hidden="true">
          <span>今日专注</span>
          <strong>2h 15m</strong>
        </div>
        <div class="welcome-float-card welcome-float-card--two" aria-hidden="true">
          <span>连续打卡</span>
          <strong>7 天</strong>
        </div>
      </div>
    </section>

    <section class="welcome-highlights" ref="highlightsSection" aria-label="核心能力">
      <article
        v-for="(item, index) in highlights"
        :key="item.title"
        class="welcome-highlight"
        :class="{ 'is-visible': highlightsVisible }"
        :style="{ '--rise': index + 1 }"
      >
        <span class="welcome-highlight__icon" aria-hidden="true" v-html="item.icon" />
        <h3>{{ item.title }}</h3>
        <p>{{ item.text }}</p>
      </article>
    </section>

    <section class="welcome-closing">
      <div>
        <h2>今天就让计划流动起来。</h2>
        <p>注册即用，数据存在你自己的空间里。</p>
      </div>
      <RouterLink class="button button--primary" :to="{ name: 'login', query: { mode: 'register' } }">
        免费开始
      </RouterLink>
    </section>

    <footer class="welcome-footer">
      <span>DayFlow · 让计划流动起来</span>
    </footer>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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

const highlights = [
  {
    title: '组织任务',
    text: '用项目、模块和任务拆解复杂计划，结构清楚才执行得动。',
    icon: '<svg viewBox="0 0 24 24"><path d="M4 6h7v5H4zM13 6h7v5h-7zM4 13h7v5H4zM13 13h7v5h-7z"/></svg>',
  },
  {
    title: '记录投入',
    text: '专注计时自动归集到任务与当日清单，不用手动记账。',
    icon: '<svg viewBox="0 0 24 24"><circle cx="12" cy="13" r="7.5"/><path d="M12 9.5V13l2.6 1.6M9.5 3.5h5"/></svg>',
  },
  {
    title: '看见趋势',
    text: '日、周、月、年多粒度回看节奏，及时调整下一轮计划。',
    icon: '<svg viewBox="0 0 24 24"><path d="M4 19h16M6.5 19V11M11 19V6M15.5 19v-6M20 19V9"/></svg>',
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

const activeSlide = ref(0)
const demoCycle = ref(0)
const scrolled = ref(false)
const highlightsVisible = ref(false)
const highlightsSection = ref<HTMLElement | null>(null)
const tiltX = ref(0)
const tiltY = ref(0)

let autoplayTimer: number | undefined
let observer: IntersectionObserver | undefined

const activeSlideMeta = computed(() => slides[activeSlide.value] ?? slides[0])

const tiltStyle = computed(() => ({
  '--tilt-x': `${tiltX.value}deg`,
  '--tilt-y': `${tiltY.value}deg`,
}))

onMounted(() => {
  startAutoplay()
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()

  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) highlightsVisible.value = true
    },
    { threshold: 0.2 },
  )
  if (highlightsSection.value) observer.observe(highlightsSection.value)
})

onBeforeUnmount(() => {
  stopAutoplay()
  window.removeEventListener('scroll', onScroll)
  observer?.disconnect()
})

function startAutoplay(): void {
  stopAutoplay()
  autoplayTimer = window.setInterval(() => {
    showSlide(activeSlide.value + 1)
  }, 5_600)
}

function stopAutoplay(): void {
  if (autoplayTimer !== undefined) window.clearInterval(autoplayTimer)
  autoplayTimer = undefined
}

function pauseAutoplay(): void {
  stopAutoplay()
}

function showSlide(index: number): void {
  const normalized = (index + slides.length) % slides.length
  if (normalized === 0) demoCycle.value += 1
  activeSlide.value = normalized
}

function onScroll(): void {
  scrolled.value = window.scrollY > 12
}

/** Subtle pointer-driven tilt for the hero visual; clamped so it never distracts. */
function trackPointer(event: PointerEvent): void {
  if (event.pointerType !== 'mouse') return
  const hero = event.currentTarget
  if (!(hero instanceof HTMLElement)) return
  const bounds = hero.getBoundingClientRect()
  const ratioX = (event.clientX - bounds.left) / bounds.width - 0.5
  const ratioY = (event.clientY - bounds.top) / bounds.height - 0.5
  tiltY.value = Number((ratioX * 5).toFixed(2))
  tiltX.value = Number((-ratioY * 4).toFixed(2))
}

function resetTilt(): void {
  tiltX.value = 0
  tiltY.value = 0
}
</script>
