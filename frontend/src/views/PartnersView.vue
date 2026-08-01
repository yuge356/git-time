<template>
  <AppShell>
    <main class="partners-page">
      <section class="page-heading">
        <p class="eyebrow">学习伙伴</p>
        <h1>与伙伴互相督促</h1>
        <p>通过用户名或显示名称查找用户，建立伙伴关系后才能分享每日计划。</p>
      </section>

      <FormMessage :message="errorMessage" />

      <section class="partner-search-card">
        <form class="partner-search" @submit.prevent="search">
          <label class="field">
            <span>搜索用户</span>
            <input
              v-model.trim="query"
              maxlength="80"
              placeholder="输入用户名或显示名称"
              required
            />
          </label>
          <button class="button button--primary" type="submit" :disabled="busy">
            搜索
          </button>
        </form>

        <div v-if="searched" class="search-results">
          <p v-if="searchResults.length === 0" class="empty-state">
            没有找到可添加的用户。
          </p>
          <ProfileRow
            v-for="profile in searchResults"
            v-else
            :key="profile.id"
            :profile="profile"
          >
            <span v-if="profile.direction === 'PARTNER'" class="relation-label">已是伙伴</span>
            <span v-else-if="profile.direction === 'OUTGOING'" class="relation-label">
              已发出邀请
            </span>
            <button
              v-else-if="profile.direction === 'INCOMING' && profile.partnership_id"
              class="button button--primary button--small"
              type="button"
              @click="decide(profile.partnership_id, true)"
            >
              接受邀请
            </button>
            <button
              v-else
              class="button button--primary button--small"
              type="button"
              @click="invite(profile.id)"
            >
              邀请
            </button>
            <button
              class="button button--quiet button--small"
              type="button"
              @click="block(profile.id)"
            >
              屏蔽
            </button>
          </ProfileRow>
        </div>
      </section>

      <section class="partner-hub">
        <header class="partner-hub__header">
          <div>
            <p class="eyebrow">伙伴关系</p>
            <h2>邀请、伙伴与隐私</h2>
          </div>
          <p>在一个区域中查看和处理全部伙伴状态。</p>
        </header>

        <div class="partner-groups">
        <article class="partner-group">
          <header>
            <p class="eyebrow">待处理</p>
            <h2>伙伴邀请</h2>
          </header>
          <p v-if="incoming.length === 0" class="empty-state">暂无待处理邀请。</p>
          <ProfileRow
            v-for="item in incoming"
            v-else
            :key="item.id"
            :profile="item.partner"
          >
            <button
              class="button button--primary button--small"
              type="button"
              @click="decide(item.id, true)"
            >
              接受
            </button>
            <button
              class="button button--quiet button--small"
              type="button"
              @click="decide(item.id, false)"
            >
              拒绝
            </button>
          </ProfileRow>
        </article>

        <article class="partner-group">
          <header>
            <p class="eyebrow">已连接</p>
            <h2>我的伙伴</h2>
          </header>
          <p v-if="partners.length === 0" class="empty-state">还没有学习伙伴。</p>
          <ProfileRow
            v-for="item in partners"
            v-else
            :key="item.id"
            :profile="item.partner"
          >
            <button
              class="button button--quiet button--small"
              type="button"
              @click="remove(item.id)"
            >
              解除伙伴
            </button>
            <button
              class="button button--quiet button--small"
              type="button"
              @click="block(item.partner.id)"
            >
              屏蔽
            </button>
          </ProfileRow>
        </article>

        <article class="partner-group">
          <header>
            <p class="eyebrow">已发送</p>
            <h2>等待回应</h2>
          </header>
          <p v-if="outgoing.length === 0" class="empty-state">没有等待中的邀请。</p>
          <ProfileRow
            v-for="item in outgoing"
            v-else
            :key="item.id"
            :profile="item.partner"
          >
            <button
              class="button button--quiet button--small"
              type="button"
              @click="remove(item.id)"
            >
              取消邀请
            </button>
          </ProfileRow>
        </article>

        <article class="partner-group">
          <header>
            <p class="eyebrow">隐私</p>
            <h2>已屏蔽用户</h2>
          </header>
          <p v-if="blocks.length === 0" class="empty-state">没有已屏蔽用户。</p>
          <ProfileRow
            v-for="item in blocks"
            v-else
            :key="item.id"
            :profile="item.blocked_user"
          >
            <button
              class="button button--quiet button--small"
              type="button"
              @click="unblock(item.id)"
            >
              取消屏蔽
            </button>
          </ProfileRow>
        </article>
        </div>
      </section>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref, type PropType } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import { partnershipService } from '@/services/partnerships'
import type {
  Partnership,
  PublicProfile,
  UserBlock,
  UserSearchResult,
} from '@/types/partnership'
import { getApiErrorMessage } from '@/utils/api-error'

const ProfileRow = defineComponent({
  props: {
    profile: {
      type: Object as PropType<PublicProfile>,
      required: true,
    },
  },
  setup(props, { slots }) {
    return () =>
      h('div', { class: 'profile-row' }, [
        props.profile.avatar_url
          ? h('img', {
              class: 'profile-avatar',
              src: props.profile.avatar_url,
              alt: '',
            })
          : h('span', { class: 'profile-avatar profile-avatar--fallback' }, [
              props.profile.display_name.slice(0, 1).toUpperCase(),
            ]),
        h('div', { class: 'profile-row__identity' }, [
          h('strong', props.profile.display_name),
          h('span', `@${props.profile.username}`),
          props.profile.bio ? h('small', props.profile.bio) : null,
        ]),
        h('div', { class: 'profile-row__actions' }, slots.default?.()),
      ])
  },
})

const query = ref('')
const searched = ref(false)
const searchResults = ref<UserSearchResult[]>([])
const relationships = ref<Partnership[]>([])
const blocks = ref<UserBlock[]>([])
const busy = ref(false)
const errorMessage = ref('')
const incoming = computed(() =>
  relationships.value.filter((item) => item.direction === 'INCOMING'),
)
const outgoing = computed(() =>
  relationships.value.filter((item) => item.direction === 'OUTGOING'),
)
const partners = computed(() =>
  relationships.value.filter((item) => item.direction === 'PARTNER'),
)

onMounted(refresh)

async function runAction(action: () => Promise<void>): Promise<void> {
  errorMessage.value = ''
  busy.value = true
  try {
    await action()
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  } finally {
    busy.value = false
  }
}

async function refresh(): Promise<void> {
  await runAction(async () => {
    ;[relationships.value, blocks.value] = await Promise.all([
      partnershipService.list(),
      partnershipService.listBlocks(),
    ])
  })
}

async function refreshAfterChange(): Promise<void> {
  ;[relationships.value, blocks.value] = await Promise.all([
    partnershipService.list(),
    partnershipService.listBlocks(),
  ])
  if (searched.value && query.value) {
    searchResults.value = await partnershipService.search(query.value)
  }
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
    await refreshAfterChange()
  })
}

async function decide(partnershipId: string, accept: boolean): Promise<void> {
  await runAction(async () => {
    await partnershipService.decide(partnershipId, accept)
    await refreshAfterChange()
  })
}

async function remove(partnershipId: string): Promise<void> {
  await runAction(async () => {
    await partnershipService.remove(partnershipId)
    await refreshAfterChange()
  })
}

async function block(userId: string): Promise<void> {
  await runAction(async () => {
    await partnershipService.block(userId)
    await refreshAfterChange()
  })
}

async function unblock(blockId: string): Promise<void> {
  await runAction(async () => {
    await partnershipService.unblock(blockId)
    await refreshAfterChange()
  })
}
</script>
