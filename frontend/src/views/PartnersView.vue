<template>
  <AppShell>
    <main class="partners-page">
      <section class="page-heading collaboration-heading">
        <div>
          <p class="eyebrow">伙伴协作</p>
          <h1>一起推进，彼此看见</h1>
          <p>分享计划、查看伙伴进度和管理关系，现在都在这里。</p>
        </div>
        <label class="field collaboration-date">
          <span>计划日期</span>
          <input v-model="planDate" type="date" @change="loadPlan" />
        </label>
      </section>

      <FormMessage :message="errorMessage" />
      <p v-if="successMessage" class="form-message form-message--success">
        {{ successMessage }}
      </p>

      <section class="collaboration-grid">
        <article class="collaboration-card share-plan-card">
          <header class="collaboration-card__header">
            <div>
              <p class="eyebrow">我的计划</p>
              <h2>分享给伙伴</h2>
            </div>
            <span class="plan-progress-pill">
              {{ plan?.completed_items ?? 0 }}/{{ plan?.total_items ?? 0 }} 完成
            </span>
          </header>

          <p class="share-plan-summary">
            {{ formattedPlanDate }}
            <template v-if="plan?.total_items">
              · 共 {{ plan.total_items }} 项
            </template>
          </p>

          <form class="share-plan-form" @submit.prevent="sharePlan">
            <select v-model="partnerId" required aria-label="选择分享伙伴">
              <option value="">选择伙伴…</option>
              <option
                v-for="relationship in availablePartners"
                :key="relationship.partner.id"
                :value="relationship.partner.id"
              >
                {{ relationship.partner.display_name }}
              </option>
            </select>
            <label class="share-duration-toggle">
              <input v-model="shareDuration" type="checkbox" />
              <span>公开用时</span>
            </label>
            <button
              class="button button--primary"
              type="submit"
              :disabled="busy || !plan || !partnerId || plan.total_items === 0"
            >
              分享
            </button>
          </form>

          <p v-if="partners.length === 0" class="inline-empty">
            还没有伙伴，请在下方“伙伴管理”中发送邀请。
          </p>
          <p v-else-if="plan?.total_items === 0" class="inline-empty">
            当天还没有任务，添加任务后即可分享。
          </p>
          <p v-else-if="availablePartners.length === 0 && sentForPlan.length > 0" class="inline-empty">
            这份计划已经分享给所有伙伴。
          </p>

          <div v-if="sentForPlan.length > 0" class="sent-share-strip" aria-label="已分享的伙伴">
            <span>已分享</span>
            <div>
              <button
                v-for="share in sentForPlan"
                :key="share.id"
                type="button"
                :title="`撤销与${share.partner.display_name}的分享`"
                :disabled="busy"
                @click="revoke(share.id)"
              >
                {{ share.partner.display_name }}
                <small>{{ share.share_duration ? '· 含用时' : '' }}</small>
                ×
              </button>
            </div>
          </div>
        </article>

        <article class="collaboration-card partner-feed-card">
          <header class="collaboration-card__header">
            <div>
              <p class="eyebrow">伙伴动态</p>
              <h2>分享给我的计划</h2>
            </div>
            <span v-if="received.length > 0" class="feed-count">{{ received.length }}</span>
          </header>

          <p v-if="received.length === 0" class="partner-feed-empty">
            暂时没有伙伴分享的计划。
          </p>
          <div v-else class="partner-feed">
            <article v-for="shared in received" :key="shared.share_id" class="partner-plan">
              <header>
                <div class="partner-plan__owner">
                  <ProfileAvatar :profile="shared.owner" />
                  <div>
                    <strong>{{ shared.owner.display_name }}</strong>
                    <span>{{ displayDate(shared.plan_date) }}</span>
                  </div>
                </div>
                <strong>{{ shared.completed_items }}/{{ shared.total_items }}</strong>
              </header>
              <div class="partner-plan__progress" aria-hidden="true">
                <span :style="{ width: sharedProgress(shared) }"></span>
              </div>
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
              <div class="encouragements encouragements--compact" aria-label="发送鼓励">
                <button type="button" :disabled="busy" @click="encourage(shared.share_id, 'KEEP_GOING')">
                  💪 加油
                </button>
                <button type="button" :disabled="busy" @click="encourage(shared.share_id, 'GREAT_JOB')">
                  ✨ 很棒
                </button>
              </div>
            </article>
          </div>
        </article>
      </section>

      <details class="partner-management" :open="incoming.length > 0">
        <summary>
          <span>
            <strong>伙伴管理</strong>
            <small>查找伙伴、处理邀请和调整关系</small>
          </span>
          <i v-if="incoming.length > 0">{{ incoming.length }} 个待处理</i>
        </summary>

        <div class="partner-management__body">
          <form class="partner-search partner-search--compact" @submit.prevent="search">
            <label class="field">
              <span>查找新伙伴</span>
              <input
                v-model.trim="query"
                maxlength="80"
                placeholder="输入用户名或显示名称"
                required
              />
            </label>
            <button class="button button--primary" type="submit" :disabled="busy">查找</button>
          </form>

          <div v-if="searched" class="search-results">
            <p v-if="searchResults.length === 0" class="empty-state">没有找到可添加的用户。</p>
            <ProfileRow v-for="profile in searchResults" v-else :key="profile.id" :profile="profile">
              <span v-if="profile.direction === 'PARTNER'" class="relation-label">已是伙伴</span>
              <span v-else-if="profile.direction === 'OUTGOING'" class="relation-label">已邀请</span>
              <button
                v-else-if="profile.direction === 'INCOMING' && profile.partnership_id"
                class="button button--primary button--small"
                type="button"
                @click="decide(profile.partnership_id, true)"
              >
                接受
              </button>
              <button v-else class="button button--primary button--small" type="button" @click="invite(profile.id)">
                邀请
              </button>
            </ProfileRow>
          </div>

          <div class="partner-management__groups">
            <article v-if="incoming.length > 0" class="relationship-group relationship-group--notice">
              <header>
                <h3>待处理邀请</h3>
                <span>{{ incoming.length }}</span>
              </header>
              <ProfileRow v-for="item in incoming" :key="item.id" :profile="item.partner">
                <button class="button button--primary button--small" type="button" @click="decide(item.id, true)">接受</button>
                <button class="button button--quiet button--small" type="button" @click="decide(item.id, false)">拒绝</button>
              </ProfileRow>
            </article>

            <article class="relationship-group">
              <header>
                <h3>我的伙伴</h3>
                <span>{{ partners.length }}</span>
              </header>
              <p v-if="partners.length === 0" class="empty-state">还没有协作伙伴。</p>
              <ProfileRow v-for="item in partners" v-else :key="item.id" :profile="item.partner">
                <button class="button button--quiet button--small" type="button" @click="remove(item.id)">解除</button>
                <button class="text-action text-action--danger" type="button" @click="block(item.partner.id)">屏蔽</button>
              </ProfileRow>
            </article>
          </div>

          <details v-if="outgoing.length > 0 || blocks.length > 0" class="relationship-more">
            <summary>其他关系（{{ outgoing.length + blocks.length }}）</summary>
            <div class="partner-management__groups">
              <article v-if="outgoing.length > 0" class="relationship-group">
                <header><h3>等待回应</h3></header>
                <ProfileRow v-for="item in outgoing" :key="item.id" :profile="item.partner">
                  <button class="text-action" type="button" @click="remove(item.id)">取消邀请</button>
                </ProfileRow>
              </article>
              <article v-if="blocks.length > 0" class="relationship-group">
                <header><h3>已屏蔽</h3></header>
                <ProfileRow v-for="item in blocks" :key="item.id" :profile="item.blocked_user">
                  <button class="text-action" type="button" @click="unblock(item.id)">取消屏蔽</button>
                </ProfileRow>
              </article>
            </div>
          </details>
        </div>
      </details>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import axios from 'axios'
import { computed, defineComponent, h, onMounted, ref, type PropType } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import { dailyPlanService } from '@/services/daily-plans'
import { partnershipService } from '@/services/partnerships'
import { sharingService } from '@/services/sharing'
import type { DailyPlan } from '@/types/daily-plan'
import type { Partnership, PublicProfile, UserBlock, UserSearchResult } from '@/types/partnership'
import type { EncouragementType, ReceivedSharedPlan, SentPlanShare } from '@/types/sharing'
import { getApiErrorMessage } from '@/utils/api-error'

const ProfileAvatar = defineComponent({
  props: {
    profile: { type: Object as PropType<PublicProfile>, required: true },
  },
  setup(props) {
    return () =>
      props.profile.avatar_url
        ? h('img', { class: 'profile-avatar', src: props.profile.avatar_url, alt: '' })
        : h('span', { class: 'profile-avatar profile-avatar--fallback' }, props.profile.display_name.slice(0, 1).toUpperCase())
  },
})

const ProfileRow = defineComponent({
  props: {
    profile: { type: Object as PropType<PublicProfile>, required: true },
  },
  setup(props, { slots }) {
    return () =>
      h('div', { class: 'profile-row' }, [
        h(ProfileAvatar, { profile: props.profile }),
        h('div', { class: 'profile-row__identity' }, [
          h('strong', props.profile.display_name),
          h('span', `@${props.profile.username}`),
          props.profile.bio ? h('small', props.profile.bio) : null,
        ]),
        h('div', { class: 'profile-row__actions' }, slots.default?.()),
      ])
  },
})

function localDateString(date = new Date()): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const planDate = ref(localDateString())
const plan = ref<DailyPlan | null>(null)
const relationships = ref<Partnership[]>([])
const blocks = ref<UserBlock[]>([])
const sent = ref<SentPlanShare[]>([])
const received = ref<ReceivedSharedPlan[]>([])
const query = ref('')
const searched = ref(false)
const searchResults = ref<UserSearchResult[]>([])
const partnerId = ref('')
const shareDuration = ref(false)
const busy = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const incoming = computed(() => relationships.value.filter((item) => item.direction === 'INCOMING'))
const outgoing = computed(() => relationships.value.filter((item) => item.direction === 'OUTGOING'))
const partners = computed(() => relationships.value.filter((item) => item.direction === 'PARTNER'))
const sentForPlan = computed(() => sent.value.filter((share) => share.daily_plan_id === plan.value?.id))
const sharedPartnerIds = computed(() => new Set(sentForPlan.value.map((share) => share.partner.id)))
const availablePartners = computed(() =>
  partners.value.filter((item) => !sharedPartnerIds.value.has(item.partner.id)),
)
const formattedPlanDate = computed(() => displayDate(planDate.value))

onMounted(async () => {
  await runAction(async () => {
    await Promise.all([loadPlanData(), refreshAll()])
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
  partnerId.value = ''
}

async function refreshAll(): Promise<void> {
  ;[relationships.value, blocks.value, sent.value, received.value] = await Promise.all([
    partnershipService.list(),
    partnershipService.listBlocks(),
    sharingService.sent(),
    sharingService.received(),
  ])
}

async function refreshRelationships(): Promise<void> {
  ;[relationships.value, blocks.value] = await Promise.all([
    partnershipService.list(),
    partnershipService.listBlocks(),
  ])
  if (searched.value && query.value) {
    searchResults.value = await partnershipService.search(query.value)
  }
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
    sent.value = await sharingService.sent()
    successMessage.value = '计划已分享。'
  })
}

async function revoke(shareId: string): Promise<void> {
  await runAction(async () => {
    await sharingService.revoke(shareId)
    sent.value = await sharingService.sent()
    successMessage.value = '分享已撤销。'
  })
}

async function encourage(shareId: string, type: EncouragementType): Promise<void> {
  await runAction(async () => {
    await sharingService.encourage(shareId, type)
    successMessage.value = '鼓励已发送。'
  })
}

async function search(): Promise<void> {
  await runAction(async () => {
    searchResults.value = await partnershipService.search(query.value)
    searched.value = true
  })
}

async function invite(userId: string): Promise<void> {
  await runAction(async () => {
    await partnershipService.invite(userId)
    await refreshRelationships()
    successMessage.value = '邀请已发送。'
  })
}

async function decide(partnershipId: string, accept: boolean): Promise<void> {
  await runAction(async () => {
    await partnershipService.decide(partnershipId, accept)
    await refreshRelationships()
    successMessage.value = accept ? '已成为协作伙伴。' : '邀请已拒绝。'
  })
}

async function remove(partnershipId: string): Promise<void> {
  await runAction(async () => {
    await partnershipService.remove(partnershipId)
    await refreshRelationships()
    successMessage.value = '伙伴关系已解除。'
  })
}

async function block(userId: string): Promise<void> {
  await runAction(async () => {
    await partnershipService.block(userId)
    await refreshRelationships()
    successMessage.value = '用户已屏蔽。'
  })
}

async function unblock(blockId: string): Promise<void> {
  await runAction(async () => {
    await partnershipService.unblock(blockId)
    await refreshRelationships()
    successMessage.value = '已取消屏蔽。'
  })
}

function displayDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
  })
}

function sharedProgress(shared: ReceivedSharedPlan): string {
  if (shared.total_items <= 0) return '0%'
  return `${Math.round((shared.completed_items / shared.total_items) * 100)}%`
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
