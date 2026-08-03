<template>
  <li class="task-tree-node">
    <article
      draggable="true"
      :class="[
        'task-row',
        {
          'task-row--selected': editorTaskId === task.id || creatingChildForId === task.id,
          'task-row--dragging': draggingId === task.id,
          'task-row--drop-target': dragTarget && draggingId !== task.id,
        },
      ]"
      :aria-label="`${task.title}，按住卡片可拖动调整层级`"
      @dragstart.stop="startDrag"
      @dragend.stop="finishDrag"
      @dragenter.prevent="dragTarget = true"
      @dragover.prevent
      @dragleave="leaveDrag"
      @drop.stop="dropOnTask"
    >
      <button class="task-row__main" type="button" @click="$emit('edit', task)">
        <span class="task-row__title-line">
          <strong>{{ task.title }}</strong>
          <TaskStatusBadge :status="task.status" />
        </span>
        <span
          v-if="task.repeat_rule !== 'NONE' || task.daily_reminder_time || task.repeat_end_date"
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
          :estimated-seconds="task.is_leaf ? task.estimated_seconds : task.children_estimated_seconds"
          :actual-seconds="task.actual_seconds"
          :level="task.budget_level"
        />
      </button>

      <div class="task-row__actions">
        <div class="task-action-menu" @focusout="closeMenuOnFocusOut" @keydown.esc.stop="actionMenuOpen = false">
          <button
            class="icon-button task-action-menu__trigger"
            type="button"
            aria-haspopup="menu"
            :aria-expanded="actionMenuOpen"
            :aria-controls="actionMenuId"
            :aria-label="`${task.title}的更多操作`"
            title="修改、设置或添加子任务"
            @click.stop="actionMenuOpen = !actionMenuOpen"
          >
            ⋮
          </button>
          <div v-if="actionMenuOpen" :id="actionMenuId" class="task-action-menu__panel" role="menu">
            <button type="button" role="menuitem" @click="editTask">
              <span aria-hidden="true">✎</span>
              修改 / 设置
            </button>
            <button type="button" role="menuitem" @click="addChildTask">
              <span aria-hidden="true">＋</span>
              添加子任务
            </button>
          </div>
        </div>
        <button
          class="icon-button icon-button--danger"
          type="button"
          :aria-label="`删除${task.title}`"
          title="删除任务"
          @click="$emit('remove', task)"
        >
          ×
        </button>
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
      :parent-id="task.id"
      :parent-title="task.title"
      :saving="saving"
      :external-error="editorError"
      @close="$emit('close-editor')"
      @create="(payload) => $emit('create-child', payload)"
    />

    <ul v-if="task.children.length" class="task-tree task-tree--nested">
      <TaskTreeNode
        v-for="child in task.children"
        :key="child.id"
        :task="child"
        :editor-task-id="editorTaskId"
        :creating-child-for-id="creatingChildForId"
        :dragging-id="draggingId"
        :saving="saving"
        :editor-error="editorError"
        @edit="$emit('edit', $event)"
        @add-child="$emit('add-child', $event)"
        @create-child="$emit('create-child', $event)"
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
import { computed, ref } from 'vue'

import type { Task, TaskCreatePayload, TaskNode, TaskUpdatePayload } from '@/types/task'
import BudgetIndicator from './BudgetIndicator.vue'
import TaskEditor from './TaskEditor.vue'
import TaskStatusBadge from './TaskStatusBadge.vue'

const props = defineProps<{
  task: TaskNode
  editorTaskId: string | null
  creatingChildForId: string | null
  draggingId: string | null
  saving: boolean
  editorError: string
}>()

const emit = defineEmits<{
  edit: [task: Task]
  'add-child': [task: Task]
  'create-child': [payload: TaskCreatePayload]
  remove: [task: Task]
  update: [taskId: string, payload: TaskUpdatePayload]
  'close-editor': []
  'drag-start': [task: Task]
  'drag-end': []
  'drop-on': [task: Task]
}>()

const dragTarget = ref(false)
const actionMenuOpen = ref(false)
const actionMenuId = computed(() => `task-actions-${props.task.id}`)
const repeatLabels = {
  DAILY: '每天重复',
  WEEKDAYS: '工作日重复',
  WEEKLY: '每周重复',
  MONTHLY: '每月重复',
} as const
const repeatLabel = computed(() =>
  props.task.repeat_rule === 'NONE' ? '' : repeatLabels[props.task.repeat_rule],
)

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

function addChildTask(): void {
  actionMenuOpen.value = false
  emit('add-child', props.task)
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
  if (props.draggingId !== props.task.id) emit('drop-on', props.task)
}
</script>
