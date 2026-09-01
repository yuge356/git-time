<template>
  <AppShell>
    <main class="partners-page">
      <section class="partners-topbar">
        <div class="partners-topbar__title">
          <h1>
            伙伴协作
            <HintIcon
              text="把某一天的计划分享给伙伴，对方就能看到你的任务和完成情况；是否公开用时由你决定。收到的分享会出现在“伙伴动态”里，可以回一个鼓励。"
            />
          </h1>
          <p>{{ partners.length }} 位伙伴 · 收到 {{ received.length }} 份分享</p>
        </div>
        <div class="partners-topbar__actions">
          <label class="field partners-date">
            <span>计划日期</span>
            <input v-model="planDate" type="date" @change="loadPlan" />
          </label>
          <button
            class="button button--quiet"
            type="button"
            :disabled="busy"
            title="重新拉取邀请、伙伴与分享"
            @click="reload"
          >
            刷新
          </button>
        </div>
      </section>

      <FormMessage :message="errorMessage" />
      <p v-if="successMessage" class="form-message form-message--success">
        {{ successMessage }}
      </p>

      <section v-if="incoming.length > 0" class="invitation-banner">
        <header>
          <strong>{{ incoming.length }} 个待处理的伙伴邀请</strong>
          <span>接受后你们可以互相分享每日计划。</span>
        </header>
        <ul>
          <li v-for="item in incoming" :key="item.id">
            <ProfileRow :profile="item.partner">
              <button
                class="button button--primary button--small"
                type="button"
                :disabled="busy"
                @click="decide(item.id, true)"
              >
                接受
              </button>
              <button
                class="button button--quiet button--small"
                type="button"
                :disabled="busy"
                @click="decide(item.id, false)"
              >
                拒绝
              </button>
            </ProfileRow>
          </li>
        </ul>
      </section>

      <div class="partners-layout">
        <section class="collaboration-card partner-feed-card">
          <header class="collaboration-card__header">
            <h2>
              伙伴动态
              <HintIcon text="伙伴分享给你的每日计划。勾选状态实时反映他们的进度，可以给对方发送一句固定鼓励。" />
            </h2>
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
        </section>

        <aside class="partners-side">
          <section class="collaboration-card share-plan-card">
            <header class="collaboration-card__header">
              <h2>
                分享我的计划
                <HintIcon text="分享的是选定日期那一天的计划快照，伙伴能看到任务标题和完成状态；勾选“公开用时”后才会一并显示计划与实际时长。" />
              </h2>
              <span class="plan-progress-pill">
                {{ plan?.completed_items ?? 0 }}/{{ plan?.total_items ?? 0 }} 完成
              </span>
            </header>

            <p class="share-plan-summary">{{ formattedPlanDate }}</p>

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
              还没有伙伴，先在下方查找并邀请。
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
          </section>

          <section class="collaboration-card partner-list-card">
            <header class="collaboration-card__header">
              <h2>
                我的伙伴
                <HintIcon text="输入用户名或显示名称查找并发送邀请；对方接受后才会成为伙伴。解除伙伴会同时撤销双方之间的计划分享。" />
              </h2>
              <span class="feed-count">{{ partners.length }}</span>
            </header>

            <form class="partner-search" @submit.prevent="search">
              <input
                v-model.trim="query"
                maxlength="80"
                placeholder="查找用户名或显示名称"
                aria-label="查找新伙伴"
                required
              />
              <button class="button button--primary button--small" type="submit" :disabled="busy">
                查找
              </button>
            </form>

            <div v-if="searched" class="search-results">
              <p v-if="searchResults.length === 0" class="inline-empty">没有找到可添加的用户。</p>
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

            <p v-if="partners.length === 0" class="inline-empty">还没有协作伙伴。</p>
            <ProfileRow v-for="item in partners" v-else :key="item.id" :profile="item.partner">
              <button class="text-action" type="button" :disabled="busy" @click="remove(item.id)">解除</button>
              <button class="text-action text-action--danger" type="button" :disabled="busy" @click="block(item.partner.id)">
                屏蔽
              </button>
            </ProfileRow>

            <details v-if="outgoing.length > 0 || blocks.length > 0" class="relationship-more">
              <summary>其他关系（{{ outgoing.length + blocks.length }}）</summary>
              <div class="relationship-more__body">
                <template v-if="outgoing.length > 0">
                  <h3>等待回应</h3>
                  <ProfileRow v-for="item in outgoing" :key="item.id" :profile="item.partner">
                    <button class="text-action" type="button" :disabled="busy" @click="remove(item.id)">
                      取消邀请
                    </button>
                  </ProfileRow>
                </template>
                <template v-if="blocks.length > 0">
                  <h3>已屏蔽</h3>
                  <ProfileRow v-for="item in blocks" :key="item.id" :profile="item.blocked_user">
                    <button class="text-action" type="button" :disabled="busy" @click="unblock(item.id)">
                      取消屏蔽
                    </button>
                  </ProfileRow>
                </template>
              </div>
            </details>
          </section>
        </aside>
      </div>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import axios from 'axios'
import { computed, defineComponent, h, onMounted, ref, watch, type PropType } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import HintIcon from '@/components/HintIcon.vue'
import { dailyPlanService } from '@/services/daily-plans'
import { partnershipService } from '@/services/partnerships'
import { sharingService } from '@/services/sharing'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import type { DailyPlan } from '@/types/daily-plan'
import type { Partnership, PublicProfile, UserBlock, UserSearchResult } from '@/types/partnership'
import type { EncouragementType, ReceivedSharedPlan, SentPlanShare } from '@/types/sharing'
import { getApiErrorMessage } from '@/utils/api-error'

const auth = useAuthStore()
const notifications = useNotificationStore()

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

const pageLoaded = ref(false)

onMounted(async () => {
  busy.value = true
  try {
    await loadPage()
  } finally {
    busy.value = false
    pageLoaded.value = true
  }
})

// A partner invitation arrives over the notification socket. Reload the
// relationship lists straight away so the request shows up while the page is
// open, instead of only after a manual reload. The notification store fills
// itself on app start, so wait for the initial page load before reacting --
// otherwise that first fill would duplicate the load we just did.
const partnerNotificationCount = computed(
  () =>
    notifications.items.filter((item) =>
      ['PARTNER_INVITE', 'PARTNER_ACCEPTED'].includes(item.notification_type),
    ).length,
)

watch(partnerNotificationCount, (current, previous) => {
  if (!pageLoaded.value || current <= previous) return
  void refreshRelationships().catch(() => {
    // The manual refresh button and the next page visit both retry.
  })
})

async function reload(): Promise<void> {
  await runAction(loadPage)
}

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

/**
 * Load every panel independently. The page used to await one `Promise.all`
 * whose results were destructured together, so a single failing request left
 * *all* of the lists empty — most visibly the pending invitations, which then
 * looked as if no one had ever sent a partner request. Each section now keeps
 * whatever it managed to load and only the failures are reported.
 */
async function loadPage(): Promise<void> {
  errorMessage.value = ''
  successMessage.value = ''
  const results = await Promise.allSettled([
    loadPlanData(),
    partnershipService.list().then((value) => {
      relationships.value = value
    }),
    partnershipService.listBlocks().then((value) => {
      blocks.value = value
    }),
    sharingService.sent().then((value) => {
      sent.value = value
    }),
    sharingService.received().then((value) => {
      received.value = value
    }),
  ])
  reportFirstFailure(results)
}

function reportFirstFailure(results: PromiseSettledResult<unknown>[]): void {
  const failure = results.find(
    (result): result is PromiseRejectedResult => result.status === 'rejected',
  )
  if (failure) errorMessage.value = getApiErrorMessage(failure.reason)
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

async function refreshRelationships(): Promise<void> {
  const results = await Promise.allSettled([
    partnershipService.list().then((value) => {
      relationships.value = value
    }),
    partnershipService.listBlocks().then((value) => {
      blocks.value = value
    }),
    searched.value && query.value
      ? partnershipService.search(query.value).then((value) => {
          searchResults.value = value
        })
      : Promise.resolve(),
  ])
  const failure = results.find((result) => result.status === 'rejected')
  if (failure) throw (failure as PromiseRejectedResult).reason
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
