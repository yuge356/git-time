<template>
  <li class="task-tree-node">
    <article
      :class="[
        'task-row',
        {
          'task-row--selected': editorTaskId === task.id,
          'task-row--dragging': draggingId === task.id,
          'task-row--drop-target': dragTarget && draggingId !== task.id,
        },
      ]"
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
        <span
          class="task-drag-handle"
          draggable="true"
          role="button"
          tabindex="0"
          :aria-label="`拖动${task.title}调整层级`"
          title="拖到另一任务上可调整层级"
          @dragstart.stop="startDrag"
          @dragend.stop="finishDrag"
        >
          ⋮⋮
        </span>
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

    <ul v-if="task.children.length" class="task-tree task-tree--nested">
      <TaskTreeNode
        v-for="child in task.children"
        :key="child.id"
        :task="child"
        :editor-task-id="editorTaskId"
        :dragging-id="draggingId"
        :saving="saving"
        :editor-error="editorError"
        @edit="$emit('edit', $event)"
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

import type { Task, TaskNode, TaskUpdatePayload } from '@/types/task'
import BudgetIndicator from './BudgetIndicator.vue'
import TaskEditor from './TaskEditor.vue'
import TaskStatusBadge from './TaskStatusBadge.vue'

const props = defineProps<{
  task: TaskNode
  editorTaskId: string | null
  draggingId: string | null
  saving: boolean
  editorError: string
}>()

const emit = defineEmits<{
  edit: [task: Task]
  remove: [task: Task]
  update: [taskId: string, payload: TaskUpdatePayload]
  'close-editor': []
  'drag-start': [task: Task]
  'drag-end': []
  'drop-on': [task: Task]
}>()

const dragTarget = ref(false)
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
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', props.task.id)
  }
  emit('drag-start', props.task)
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
