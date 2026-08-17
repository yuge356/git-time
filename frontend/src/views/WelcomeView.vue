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
            :key="slide.image"
            class="welcome-slide"
            :aria-label="`${index + 1} / ${slides.length}：${slide.title}`"
          >
            <header>
              <span>{{ slide.kicker }}</span>
              <strong>{{ slide.title }}</strong>
              <p>{{ slide.description }}</p>
            </header>
            <div class="welcome-slide__image">
              <img :src="slide.image" :alt="slide.alt" loading="eager" />
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
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import AppLogo from '@/components/AppLogo.vue'

const slides = [
  {
    kicker: '今天',
    title: '把注意力留给眼前的一项任务',
    description: '计时日历、专注计时和今日任务在同一页自然衔接。',
    image: '/welcome-today.png',
    alt: 'DayFlow 今日任务与专注计时界面',
  },
  {
    kicker: '项目',
    title: '用清晰结构承接复杂计划',
    description: '在项目、模块和任务之间建立可执行的层级关系。',
    image: '/welcome-tasks.png',
    alt: 'DayFlow 项目与任务管理界面',
  },
  {
    kicker: '时间统计',
    title: '让每一段投入都有回响',
    description: '从时间分布和趋势中看见节奏，及时修正计划。',
    image: '/welcome-analytics.png',
    alt: 'DayFlow 时间统计与趋势分析界面',
  },
] as const

const carousel = ref<HTMLElement | null>(null)
const activeSlide = ref(0)

function showSlide(index: number): void {
  const normalized = (index + slides.length) % slides.length
  activeSlide.value = normalized
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
