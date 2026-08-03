<template>
  <li class="task-tree-node">
    <article
      :class="[
        'task-row',
        `task-row--${task.node_type.toLowerCase()}`,
        {
          'task-row--selected': editorTaskId === task.id || creatingChildForId === task.id,
          'task-row--dragging': draggingTask?.id === task.id,
          'task-row--drop-target': dragTarget && canAcceptDrop,
        },
      ]"
      :aria-label="rowAriaLabel"
      @dragenter.prevent="enterDrag"
      @dragover.prevent="overDrag"
      @dragleave="leaveDrag"
      @drop.stop.prevent="dropOnTask"
    >
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

      <button class="task-row__main" type="button" @click="openOrToggle">
        <span class="task-row__title-line">
          <span class="task-row__title">
            <span v-if="isContainer" class="task-disclosure" aria-hidden="true">
              {{ expanded ? '⌄' : '›' }}
            </span>
            <strong>{{ task.title }}</strong>
            <span v-if="isContainer" class="node-type-badge">{{ nodeTypeLabel }}</span>
          </span>
          <TaskStatusBadge v-if="task.node_type === 'TASK'" :status="task.status" />
          <span v-else class="task-progress-label">{{ progressLabel }}</span>
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
        />
      </button>

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

    <TaskEditor
      v-if="editorTaskId === task.id"
      :task="task"
      :saving="saving"
      :external-error="editorError"
      @close="$emit('close-editor')"
      @update="(taskId, payload) => $emit('update', taskId, payload)"
    />

    <TaskEditor
      v-if="creatingChildForId === task.id"
      :task="null"
      :node-type="creatingChildNodeType ?? childNodeType"
      :parent-id="task.id"
      :parent-title="task.title"
      :parent-task="task"
      :inherited-default-estimated-seconds="effectiveDefaultEstimatedSeconds"
      :inherited-default-repeat-rule="effectiveDefaultRepeatRule"
      :inherited-default-reminder-time="effectiveDefaultReminderTime"
      :saving="saving"
      :external-error="editorError"
      @close="$emit('close-editor')"
      @create="(payload) => $emit('create-child', payload)"
    />

    <ul v-if="isContainer && expanded && task.children.length" class="task-tree task-tree--nested">
      <TaskTreeNode
        v-for="child in task.children"
        :key="child.id"
        :task="child"
        :editor-task-id="editorTaskId"
        :creating-child-for-id="creatingChildForId"
        :creating-child-node-type="creatingChildNodeType"
        :dragging-task="draggingTask"
        :saving="saving"
        :editor-error="editorError"
        :active-task-id="activeTaskId"
        :has-active-timer="hasActiveTimer"
        :active-timer-paused="activeTimerPaused"
        :timer-busy="timerBusy"
        :inherited-default-estimated-seconds="effectiveDefaultEstimatedSeconds"
        :inherited-default-repeat-rule="effectiveDefaultRepeatRule"
        :inherited-default-reminder-time="effectiveDefaultReminderTime"
        @edit="$emit('edit', $event)"
        @add-child="(parent, nodeType) => $emit('add-child', parent, nodeType)"
        @create-child="$emit('create-child', $event)"
        @apply-defaults="$emit('apply-defaults', $event)"
        @start-task="$emit('start-task', $event)"
        @remove="$emit('remove', $event)"
        @update="(taskId, payload) => $emit('update', taskId, payload)"
        @close-editor="$emit('close-editor')"
        @drag-start="$emit('drag-start', $event)"
        @drag-end="$emit('drag-end')"
        @drop-on="$emit('drop-on', $event)"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  Task,
  TaskCreatePayload,
  TaskNode,
  TaskNodeType,
  TaskUpdatePayload,
} from '@/types/task'
import BudgetIndicator from './BudgetIndicator.vue'
import TaskEditor from './TaskEditor.vue'
import TaskStatusBadge from './TaskStatusBadge.vue'

const props = defineProps<{
  task: TaskNode
  editorTaskId: string | null
  creatingChildForId: string | null
  creatingChildNodeType: TaskNodeType | null
  draggingTask: Task | null
  saving: boolean
  editorError: string
  activeTaskId: string | null
  hasActiveTimer: boolean
  activeTimerPaused: boolean
  timerBusy: boolean
  inheritedDefaultEstimatedSeconds?: number | null
  inheritedDefaultRepeatRule?: Task['default_repeat_rule']
  inheritedDefaultReminderTime?: string | null
}>()

const emit = defineEmits<{
  edit: [task: Task]
  'add-child': [task: Task, nodeType: TaskNodeType]
  'create-child': [payload: TaskCreatePayload]
  'apply-defaults': [task: Task]
  'start-task': [task: Task]
  remove: [task: Task]
  update: [taskId: string, payload: TaskUpdatePayload]
  'close-editor': []
  'drag-start': [task: Task]
  'drag-end': []
  'drop-on': [task: Task]
}>()

const expanded = ref(false)
const dragTarget = ref(false)
const actionMenuOpen = ref(false)
const actionMenuId = computed(() => `task-actions-${props.task.id}`)
const isContainer = computed(() => props.task.node_type !== 'TASK')
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
const effectiveDefaultEstimatedSeconds = computed(() =>
  props.task.default_estimated_seconds ?? props.inheritedDefaultEstimatedSeconds ?? null,
)
const effectiveDefaultRepeatRule = computed(() =>
  props.task.default_repeat_rule ?? props.inheritedDefaultRepeatRule ?? null,
)
const effectiveDefaultReminderTime = computed(() =>
  props.task.default_daily_reminder_time ?? props.inheritedDefaultReminderTime ?? null,
)
const progressPercent = computed(() => Math.round((props.task.progress_ratio ?? 0) * 100))
const progressLabel = computed(() =>
  props.task.task_count > 0
    ? `${props.task.completed_task_count} / ${props.task.task_count}`
    : '尚无任务',
)
const rowAriaLabel = computed(() =>
  isContainer.value
    ? `${props.task.title}，${progressLabel.value}，点击${expanded.value ? '折叠' : '展开'}`
    : `${props.task.title}，点击编辑任务`,
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

function openOrToggle(): void {
  if (isContainer.value) expanded.value = !expanded.value
  else emit('edit', props.task)
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
