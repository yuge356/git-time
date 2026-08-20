<template>
  <li class="task-tree-node">
    <div
      :class="[
        'task-mind-branch',
        { 'task-mind-branch--expanded': isContainer && expanded && task.children.length },
      ]"
      :style="themeVars"
    >
      <article
        :class="[
          'task-row',
          `task-row--${task.node_type.toLowerCase()}`,
          {
            'task-row--selected': editorTaskId === task.id || creatingChildForId === task.id,
            'task-row--dragging': draggingTask?.id === task.id,
            'task-row--drop-target': dragTarget && canAcceptDrop,
            'task-row--done': task.node_type === 'TASK' && task.status === 'DONE',
          },
        ]"
        :data-task-id="task.id"
        :aria-label="rowAriaLabel"
        @click="selectNode"
        @dragenter.prevent="enterDrag"
        @dragover.prevent="overDrag"
        @dragleave="leaveDrag"
        @drop.stop.prevent="dropOnTask"
      >
      <div
        v-if="task.node_type === 'TASK' && task.status === 'DONE'"
        class="task-row__done-mark"
        aria-hidden="true"
        title="已完成"
      >
        <svg viewBox="0 0 24 24" class="task-row__done-svg">
          <path
            d="m4.5 12.75 5 5 10-10.5"
            fill="none"
            stroke="currentColor"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </div>
      <button
        class="task-drag-handle"
        type="button"
        draggable="true"
        :aria-label="`移动${task.title}`"
        title="拖动调整位置"
        @dragstart.stop="startDrag"
        @dragend.stop="finishDrag"
        @click.stop
      >
        ⠿
      </button>

      <div class="task-row__main">
        <span class="task-row__title-line">
          <span class="task-row__title">
            <button
              v-if="isContainer"
              class="task-disclosure"
              type="button"
              :aria-label="`${expanded ? '收起' : '展开'}${task.title}`"
              :aria-expanded="expanded"
              @click.stop="toggleExpanded"
            >
              <svg
                v-if="presentation === 'outline'"
                class="task-disclosure__chevron"
                viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <path d="m5 7.5 5 5 5-5" />
              </svg>
              <span v-else aria-hidden="true">{{ expanded ? '−' : '+' }}</span>
              <small v-if="presentation !== 'outline' && !expanded && task.children.length">
                {{ task.children.length }}
              </small>
            </button>
            <button
              class="task-row__name"
              type="button"
              :title="`查看${task.title}的具体设置`"
              @click.stop="editTask"
            >
              <strong>{{ task.title }}</strong>
            </button>
            <span v-if="isContainer" class="node-type-badge">{{ nodeTypeLabel }}</span>
          </span>
        </span>

        <span class="task-map-node__meta">
          <TaskStatusBadge :status="displayStatus" />
          <span class="task-map-node__progress-text">{{ progressPercent }}%</span>
          <span v-if="priorityLabel" class="task-map-node__priority">{{ priorityLabel }}</span>
          <span v-if="task.due_date" class="task-map-node__due">截止 {{ shortDueDate }}</span>
        </span>

        <span class="task-map-node__progress" aria-hidden="true">
          <span :style="{ width: `${progressPercent}%` }"></span>
        </span>

        <span v-if="isContainer" class="container-summary">
          <span>{{ progressLabel }}</span>
          <span v-if="task.task_count > 0">完成度 {{ progressPercent }}%</span>
          <span v-if="task.budget_mode === 'FIXED_CAP'">固定上限</span>
          <span v-else>自动汇总</span>
        </span>

        <span
          v-if="task.node_type === 'TASK' && (task.repeat_rule !== 'NONE' || task.daily_reminder_time || task.repeat_end_date)"
          class="task-row__schedule"
        >
          <span v-if="task.repeat_rule !== 'NONE'">{{ repeatLabel }}</span>
          <span v-if="task.repeat_end_date" class="task-row__schedule-end">
            截止 {{ task.repeat_end_date }}
          </span>
          <span v-if="task.daily_reminder_time">
            每日 {{ task.daily_reminder_time.slice(0, 5) }} 提醒
          </span>
        </span>

        <BudgetIndicator
          :estimated-seconds="task.planned_seconds"
          :actual-seconds="task.actual_seconds"
          :level="task.budget_level"
          :show-track="presentation !== 'outline'"
        />
      </div>

      <div class="task-row__actions">
        <button
          v-if="task.node_type === 'TASK'"
          class="button button--small"
          :class="activeTaskId === task.id ? 'button--primary' : 'button--quiet'"
          type="button"
          :disabled="startDisabled"
          :title="startButtonTitle"
          @click.stop="$emit('start-task', task)"
        >
          {{ startButtonLabel }}
        </button>
        <div class="task-action-menu" @focusout="closeMenuOnFocusOut" @keydown.esc.stop="actionMenuOpen = false">
          <button
            class="icon-button task-action-menu__trigger"
            type="button"
            aria-haspopup="menu"
            :aria-expanded="actionMenuOpen"
            :aria-controls="actionMenuId"
            :aria-label="`${task.title}的更多操作`"
            @click.stop="actionMenuOpen = !actionMenuOpen"
          >
            ⋮
          </button>
          <div v-if="actionMenuOpen" :id="actionMenuId" class="task-action-menu__panel" role="menu">
            <button type="button" role="menuitem" @click="editTask">
              <span aria-hidden="true">✎</span>
              {{ isContainer ? '编辑 / 默认设置' : '编辑任务' }}
            </button>
            <button
              v-if="task.node_type === 'PROJECT'"
              type="button"
              role="menuitem"
              @click="addChildTask('TASK')"
            >
              <span aria-hidden="true">＋</span>
              新建任务
            </button>
            <button
              v-if="isContainer"
              type="button"
              role="menuitem"
              @click="addChildTask(childNodeType)"
            >
              <span aria-hidden="true">＋</span>
              新建{{ childTypeLabel }}
            </button>
            <button v-if="isContainer" type="button" role="menuitem" @click="applyDefaults">
              <span aria-hidden="true">↧</span>
              应用默认值
            </button>
            <button class="task-action-menu__danger" type="button" role="menuitem" @click="removeTask">
              <span aria-hidden="true">×</span>
              删除{{ nodeTypeLabel }}
            </button>
          </div>
        </div>
      </div>
      </article>

      <ul v-if="isContainer && expanded && task.children.length" class="task-tree task-tree--nested">
        <TaskTreeNode
          v-for="child in task.children"
          :key="child.id"
          :task="child"
          :presentation="presentation"
          :project-theme="theme"
          :editor-task-id="editorTaskId"
          :creating-child-for-id="creatingChildForId"
          :dragging-task="draggingTask"
          :active-task-id="activeTaskId"
          :has-active-timer="hasActiveTimer"
          :active-timer-paused="activeTimerPaused"
          :timer-busy="timerBusy"
          @edit="$emit('edit', $event)"
          @add-child="(parent, nodeType) => $emit('add-child', parent, nodeType)"
          @apply-defaults="$emit('apply-defaults', $event)"
          @start-task="$emit('start-task', $event)"
          @remove="$emit('remove', $event)"
          @drag-start="$emit('drag-start', $event)"
          @drag-end="$emit('drag-end')"
          @drop-on="$emit('drop-on', $event)"
          @layout-change="$emit('layout-change')"
        />
      </ul>
    </div>
  </li>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { Task, TaskNode, TaskNodeType } from '@/types/task'
import { getProjectTheme, type ProjectTheme } from '@/utils/project-theme'
import BudgetIndicator from './BudgetIndicator.vue'
import TaskStatusBadge from './TaskStatusBadge.vue'

const props = withDefaults(defineProps<{
  task: TaskNode
  presentation?: 'mindmap' | 'outline'
  editorTaskId: string | null
  creatingChildForId: string | null
  draggingTask: Task | null
  activeTaskId: string | null
  hasActiveTimer: boolean
  activeTimerPaused: boolean
  timerBusy: boolean
  projectTheme?: ProjectTheme
}>(), {
  presentation: 'mindmap',
})

const emit = defineEmits<{
  edit: [task: Task]
  'add-child': [task: Task, nodeType: TaskNodeType]
  'apply-defaults': [task: Task]
  'start-task': [task: Task]
  remove: [task: Task]
  'drag-start': [task: Task]
  'drag-end': []
  'drop-on': [task: Task]
  'layout-change': []
}>()

const expanded = ref(
  props.task.node_type !== 'TASK' && props.presentation !== 'outline',
)
const dragTarget = ref(false)
const actionMenuOpen = ref(false)
const actionMenuId = computed(() => `task-actions-${props.task.id}`)
const isContainer = computed(() => props.task.node_type !== 'TASK')

const theme = computed<ProjectTheme>(() =>
  props.projectTheme ?? getProjectTheme(props.task.node_type === 'PROJECT' ? props.task.id : (props.task.parent_id ?? props.task.id)),
)

const themeVars = computed(() => ({
  '--theme-primary': theme.value.primary,
  '--theme-primary-hover': theme.value.primaryHover,
  '--theme-soft': theme.value.soft,
  '--theme-soft-hover': theme.value.softHover,
  '--theme-line': theme.value.line,
  '--theme-border': theme.value.border,
  '--theme-module-bar': theme.value.moduleBar,
  '--theme-task-bar': theme.value.taskBar,
  '--theme-glow': theme.value.glow,
  '--theme-text': theme.value.text,
}))
const childNodeType = computed<TaskNodeType>(() =>
  props.task.node_type === 'PROJECT' ? 'MODULE' : 'TASK',
)
const typeLabels: Record<TaskNodeType, string> = {
  PROJECT: '项目',
  MODULE: '模块',
  TASK: '任务',
}
const nodeTypeLabel = computed(() => typeLabels[props.task.node_type])
const childTypeLabel = computed(() => typeLabels[childNodeType.value])
const progressRatio = computed(() => {
  if (props.task.node_type !== 'TASK') return props.task.progress_ratio ?? 0
  if (props.task.status === 'DONE') return 1
  if (props.task.planned_seconds <= 0) return 0
  return Math.min(1, props.task.actual_seconds / props.task.planned_seconds)
})
const progressPercent = computed(() => Math.round(progressRatio.value * 100))
const displayStatus = computed(() => {
  if (props.task.node_type === 'TASK') return props.task.status
  if (props.task.task_count > 0 && props.task.completed_task_count === props.task.task_count) {
    return 'DONE' as const
  }
  if (props.task.actual_seconds > 0 || props.task.completed_task_count > 0) {
    return 'IN_PROGRESS' as const
  }
  return 'TODO' as const
})
const priorityLabels = {
  LOW: '',
  MEDIUM: '',
  HIGH: '高优先级',
  URGENT: '紧急',
} as const
const priorityLabel = computed(() => priorityLabels[props.task.priority ?? 'MEDIUM'])
const shortDueDate = computed(() => {
  if (!props.task.due_date) return ''
  const [, month, day] = props.task.due_date.split('-')
  return `${Number(month)}/${Number(day)}`
})
const progressLabel = computed(() =>
  props.task.task_count > 0
    ? `${props.task.completed_task_count} / ${props.task.task_count}`
    : '尚无任务',
)
const rowAriaLabel = computed(() =>
  `${props.task.title}，点击名称查看具体设置`,
)
const canAcceptDrop = computed(() => {
  const moving = props.draggingTask
  if (!moving || moving.id === props.task.id) return false
  return (
    (props.task.node_type === 'PROJECT' && moving.node_type === 'MODULE')
    || (props.task.node_type === 'MODULE' && moving.node_type === 'TASK')
  )
})
const repeatLabels = {
  DAILY: '每天重复',
  WEEKDAYS: '工作日重复',
  WEEKLY: '每周重复',
  MONTHLY: '每月重复',
} as const
const repeatLabel = computed(() =>
  props.task.repeat_rule === 'NONE' ? '' : repeatLabels[props.task.repeat_rule],
)
const startDisabled = computed(() =>
  props.timerBusy || (props.hasActiveTimer && !props.activeTimerPaused),
)
const startButtonLabel = computed(() => {
  if (props.timerBusy) return '处理中…'
  if (props.activeTaskId === props.task.id) {
    return props.activeTimerPaused ? '继续' : '计时中'
  }
  if (props.activeTimerPaused) return '切换并开始'
  if (props.hasActiveTimer) return '请先暂停'
  return '开始'
})
const startButtonTitle = computed(() => {
  if (props.timerBusy) return '正在处理计时状态'
  if (props.activeTaskId === props.task.id) {
    return props.activeTimerPaused ? '继续该任务的计时' : '该任务正在计时'
  }
  if (props.activeTimerPaused) return '保存当前已暂停的计时，然后开始该任务'
  if (props.hasActiveTimer) return '请先暂停当前计时，再切换任务'
  return '开始该任务的计时'
})

watch(
  () => props.creatingChildForId,
  (parentId) => {
    if (parentId === props.task.id) expanded.value = true
  },
)

function toggleExpanded(): void {
  expanded.value = !expanded.value
  emit('layout-change')
}

function startDrag(event: DragEvent): void {
  actionMenuOpen.value = false
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', props.task.id)
  }
  emit('drag-start', props.task)
}

function closeMenuOnFocusOut(event: FocusEvent): void {
  const menu = event.currentTarget as HTMLElement
  const nextTarget = event.relatedTarget as Node | null
  if (!nextTarget || !menu.contains(nextTarget)) actionMenuOpen.value = false
}

function editTask(): void {
  actionMenuOpen.value = false
  emit('edit', props.task)
}

function selectNode(event: MouseEvent): void {
  const target = event.target as HTMLElement
  if (target.closest('button, input, select, textarea')) return
  editTask()
}

function addChildTask(nodeType: TaskNodeType): void {
  actionMenuOpen.value = false
  expanded.value = true
  emit('add-child', props.task, nodeType)
}

function applyDefaults(): void {
  actionMenuOpen.value = false
  emit('apply-defaults', props.task)
}

function removeTask(): void {
  actionMenuOpen.value = false
  emit('remove', props.task)
}

function enterDrag(): void {
  if (canAcceptDrop.value) dragTarget.value = true
}

function overDrag(event: DragEvent): void {
  if (event.dataTransfer) event.dataTransfer.dropEffect = canAcceptDrop.value ? 'move' : 'none'
}

function finishDrag(): void {
  dragTarget.value = false
  emit('drag-end')
}

function leaveDrag(event: DragEvent): void {
  const row = event.currentTarget as HTMLElement
  const nextTarget = event.relatedTarget as Node | null
  if (!nextTarget || !row.contains(nextTarget)) dragTarget.value = false
}

function dropOnTask(): void {
  dragTarget.value = false
  if (canAcceptDrop.value) emit('drop-on', props.task)
}
</script>
