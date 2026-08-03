<template>
  <AppShell>
    <main class="sharing-page">
      <section class="page-heading sharing-heading">
        <div>
          <p class="eyebrow">计划分享</p>
          <h1>让伙伴看见你的进度</h1>
          <p>仅已建立关系的伙伴可查看；是否公开时间数据由你单独选择。</p>
        </div>
        <label class="field sharing-date">
          <span>要分享的日期</span>
          <input v-model="planDate" type="date" @change="loadPlan" />
        </label>
      </section>

      <FormMessage :message="errorMessage" />
      <p v-if="successMessage" class="form-message form-message--success">
        {{ successMessage }}
      </p>

      <section class="sharing-layout">
        <article class="sharing-card">
          <header>
            <p class="eyebrow">发出分享</p>
            <h2>{{ formattedPlanDate }}</h2>
          </header>
          <p class="sharing-summary">
            计划包含 {{ plan?.total_items ?? 0 }} 项，已完成
            {{ plan?.completed_items ?? 0 }} 项。
          </p>
          <form class="share-form" @submit.prevent="sharePlan">
            <label class="field">
              <span>选择伙伴</span>
              <select v-model="partnerId" required>
                <option value="">请选择伙伴</option>
                <option
                  v-for="relationship in availablePartners"
                  :key="relationship.partner.id"
                  :value="relationship.partner.id"
                >
                  {{ relationship.partner.display_name }}
                </option>
              </select>
            </label>
            <label class="privacy-check">
              <input v-model="shareDuration" type="checkbox" />
              <span>
                <strong>同时公开时长</strong>
                <small>伙伴将看到每项的计划用时和实际投入时长。</small>
              </span>
            </label>
            <button
              class="button button--primary"
              type="submit"
              :disabled="busy || !plan || !partnerId"
            >
              分享计划
            </button>
          </form>
        </article>

        <article class="sharing-card">
          <header>
            <p class="eyebrow">已发出</p>
            <h2>当前分享</h2>
          </header>
          <p v-if="sent.length === 0" class="empty-state">还没有有效的计划分享。</p>
          <ol v-else class="sent-share-list">
            <li v-for="share in sent" :key="share.id">
              <div>
                <strong>{{ share.partner.display_name }}</strong>
                <span>{{ displayDate(share.plan_date) }}</span>
                <small>{{ share.share_duration ? '公开时长' : '仅公开进度' }}</small>
              </div>
              <button
                class="button button--quiet button--small"
                type="button"
                @click="revoke(share.id)"
              >
                撤销
              </button>
            </li>
          </ol>
        </article>
      </section>

      <section class="received-section">
        <header>
          <p class="eyebrow">伙伴动态</p>
          <h2>分享给我的计划</h2>
        </header>
        <p v-if="received.length === 0" class="empty-state">暂时没有伙伴分享的计划。</p>
        <div v-else class="received-grid">
          <article v-for="shared in received" :key="shared.share_id" class="shared-plan-card">
            <header>
              <div>
                <strong>{{ shared.owner.display_name }}</strong>
                <span>@{{ shared.owner.username }} · {{ displayDate(shared.plan_date) }}</span>
              </div>
              <span>{{ shared.completed_items }}/{{ shared.total_items }}</span>
            </header>
            <ol>
              <li v-for="item in shared.items" :key="item.id">
                <span :class="{ complete: item.status === 'DONE' }">
                  {{ item.status === 'DONE' ? '✓' : '○' }} {{ item.title }}
                </span>
                <small v-if="shared.share_duration">
                  {{ readableDuration(item.actual_seconds ?? 0) }} /
                  {{ readableDuration(item.estimated_seconds ?? 0) }}
                </small>
              </li>
            </ol>
            <div class="encouragements" aria-label="发送鼓励">
              <button
                v-for="option in encouragementOptions"
                :key="option.value"
                type="button"
                :disabled="busy"
                @click="encourage(shared.share_id, option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </article>
        </div>
      </section>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import { dailyPlanService } from '@/services/daily-plans'
import { partnershipService } from '@/services/partnerships'
import { sharingService } from '@/services/sharing'
import type { DailyPlan } from '@/types/daily-plan'
import type { Partnership } from '@/types/partnership'
import type {
  EncouragementType,
  ReceivedSharedPlan,
  SentPlanShare,
} from '@/types/sharing'
import { getApiErrorMessage } from '@/utils/api-error'

function localDateString(date = new Date()): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const encouragementOptions: { value: EncouragementType; label: string }[] = [
  { value: 'KEEP_GOING', label: '继续加油' },
  { value: 'GREAT_JOB', label: '做得很棒' },
  { value: 'WELL_DONE', label: '完成得好' },
  { value: 'YOU_CAN_DO_IT', label: '你可以的' },
]
const planDate = ref(localDateString())
const plan = ref<DailyPlan | null>(null)
const relationships = ref<Partnership[]>([])
const sent = ref<SentPlanShare[]>([])
const received = ref<ReceivedSharedPlan[]>([])
const partnerId = ref('')
const shareDuration = ref(false)
const busy = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const sharedPartnerIds = computed(
  () =>
    new Set(
      sent.value
        .filter((share) => share.daily_plan_id === plan.value?.id)
        .map((share) => share.partner.id),
    ),
)
const availablePartners = computed(() =>
  relationships.value.filter(
    (item) =>
      item.direction === 'PARTNER' && !sharedPartnerIds.value.has(item.partner.id),
  ),
)
const formattedPlanDate = computed(() => displayDate(planDate.value))

onMounted(async () => {
  await runAction(async () => {
    await Promise.all([loadPlanData(), refreshSocial()])
  })
})

async function runAction(action: () => Promise<void>): Promise<void> {
  errorMessage.value = ''
  successMessage.value = ''
  busy.value = true
  try {
    await action()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    busy.value = false
  }
}

async function loadPlanData(): Promise<void> {
  try {
    plan.value = await dailyPlanService.readByDate(planDate.value)
  } catch (error) {
    if (!axios.isAxiosError(error) || error.response?.status !== 404) throw error
    plan.value = await dailyPlanService.create(planDate.value)
  }
}

async function refreshSocial(): Promise<void> {
  ;[relationships.value, sent.value, received.value] = await Promise.all([
    partnershipService.list(),
    sharingService.sent(),
    sharingService.received(),
  ])
}

async function loadPlan(): Promise<void> {
  await runAction(loadPlanData)
}

async function sharePlan(): Promise<void> {
  if (!plan.value || !partnerId.value) return
  await runAction(async () => {
    await sharingService.share(plan.value!.id, partnerId.value, shareDuration.value)
    partnerId.value = ''
    shareDuration.value = false
    await refreshSocial()
    successMessage.value = '计划已分享给伙伴。'
  })
}

async function revoke(shareId: string): Promise<void> {
  await runAction(async () => {
    await sharingService.revoke(shareId)
    await refreshSocial()
  })
}

async function encourage(
  shareId: string,
  encouragementType: EncouragementType,
): Promise<void> {
  await runAction(async () => {
    await sharingService.encourage(shareId, encouragementType)
    successMessage.value = '鼓励已发送。'
  })
}

function displayDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function readableDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours && rest) return `${hours}小时${rest}分`
  if (hours) return `${hours}小时`
  return `${rest}分钟`
}
</script>
