<template>
  <AppShell>
    <main class="tasks-page">
      <section class="page-heading tasks-page__heading">
        <p class="eyebrow">学习任务</p>
        <h1>任务与时间预算</h1>
        <p>按课程、章节和练习拆分目标，并提前限定每项学习投入。</p>
      </section>

      <div v-if="!tasks.online || tasks.pendingCount > 0" class="sync-banner">
        <strong>{{ tasks.online ? '等待同步' : '当前离线' }}</strong>
        <span>{{ tasks.pendingCount }} 条任务或计划变更已安全保存在本机。</span>
      </div>

      <section class="task-workspace">
        <div class="task-list-panel">
          <header class="panel-header">
            <div>
              <h2>任务树</h2>
              <p>{{ tasks.items.length }} 个任务</p>
            </div>
            <button class="button button--primary" type="button" @click="openCreate">
              新建任务
            </button>
          </header>

          <p class="task-drag-help">
            拖动任务卡片到另一任务上可设为其子任务；拖到“顶层任务”区域可恢复为顶层。
          </p>

          <FormMessage :message="loadError" />

          <TaskEditor
            v-if="creating"
            :task="null"
            :saving="tasks.saving"
            :external-error="editorError"
            @close="closeEditor"
            @create="createTask"
          />

          <p v-if="tasks.loading" class="loading-state">正在加载任务…</p>

          <div v-else-if="tasks.tree.length === 0 && !creating" class="empty-state">
            <span aria-hidden="true">01</span>
            <h3>从第一个学习目标开始</h3>
            <p>创建课程、章节、练习或项目实践，并为它设置预计时间。</p>
            <button class="button button--primary" type="button" @click="openCreate">
              创建任务
            </button>
          </div>

          <template v-else-if="tasks.tree.length">
            <div
              :class="[
                'task-root-dropzone',
                { 'task-root-dropzone--active': draggingTask?.parent_id },
              ]"
              @dragover.prevent
              @drop.prevent="moveToRoot"
            >
              顶层任务
            </div>

            <ul class="task-tree">
              <TaskTreeNode
                v-for="task in tasks.tree"
                :key="task.id"
                :task="task"
                :editor-task-id="selectedTask?.id ?? null"
                :dragging-id="draggingTask?.id ?? null"
                :saving="tasks.saving"
                :editor-error="editorError"
                @edit="openEdit"
                @remove="removeTask"
                @update="updateTask"
                @close-editor="closeEditor"
                @drag-start="startDrag"
                @drag-end="finishDrag"
                @drop-on="moveUnderTask"
              />
            </ul>
          </template>
        </div>
      </section>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import TaskEditor from '@/components/tasks/TaskEditor.vue'
import TaskTreeNode from '@/components/tasks/TaskTreeNode.vue'
import { useAuthStore } from '@/stores/auth'
import { useTaskStore } from '@/stores/tasks'
import type { Task, TaskCreatePayload, TaskUpdatePayload } from '@/types/task'
import { getApiErrorMessage } from '@/utils/api-error'

const tasks = useTaskStore()
const auth = useAuthStore()
const creating = ref(false)
const selectedTask = ref<Task | null>(null)
const draggingTask = ref<Task | null>(null)
const loadError = ref('')
const editorError = ref('')

onMounted(async () => {
  try {
    const ownerId = auth.user?.profile.id
    if (ownerId) await tasks.initialize(ownerId)
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  }
})

function openCreate(): void {
  selectedTask.value = null
  creating.value = true
  editorError.value = ''
}

function openEdit(task: Task): void {
  if (selectedTask.value?.id === task.id) {
    closeEditor()
    return
  }
  creating.value = false
  selectedTask.value = task
  editorError.value = ''
}

function closeEditor(): void {
  creating.value = false
  selectedTask.value = null
  editorError.value = ''
}

async function createTask(payload: TaskCreatePayload): Promise<void> {
  editorError.value = ''
  try {
    await tasks.create(payload)
    closeEditor()
  } catch (error) {
    editorError.value = getApiErrorMessage(error)
  }
}

async function updateTask(taskId: string, payload: TaskUpdatePayload): Promise<void> {
  editorError.value = ''
  try {
    await tasks.update(taskId, payload)
    closeEditor()
  } catch (error) {
    editorError.value = getApiErrorMessage(error)
  }
}

function startDrag(task: Task): void {
  draggingTask.value = task
  loadError.value = ''
}

function finishDrag(): void {
  draggingTask.value = null
}

function wouldCreateCycle(taskId: string, parentId: string): boolean {
  let current = tasks.items.find((item) => item.id === parentId)
  const visited = new Set<string>()
  while (current && !visited.has(current.id)) {
    if (current.id === taskId) return true
    visited.add(current.id)
    current = current.parent_id
      ? tasks.items.find((item) => item.id === current?.parent_id)
      : undefined
  }
  return false
}

async function moveTask(parentId: string | null): Promise<void> {
  const moving = draggingTask.value
  if (!moving || moving.parent_id === parentId) return
  if (parentId && wouldCreateCycle(moving.id, parentId)) {
    loadError.value = '不能把任务拖到自己的子任务中。'
    return
  }
  try {
    await tasks.update(moving.id, { parent_id: parentId })
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  } finally {
    draggingTask.value = null
  }
}

async function moveUnderTask(parent: Task): Promise<void> {
  await moveTask(parent.id)
}

async function moveToRoot(): Promise<void> {
  await moveTask(null)
}

async function removeTask(task: Task): Promise<void> {
  const confirmed = window.confirm(
    `删除“${task.title}”及其全部子任务？此操作会保留同步记录。`,
  )
  if (!confirmed) return
  try {
    await tasks.remove(task.id)
    if (
      selectedTask.value &&
      !tasks.items.some((remaining) => remaining.id === selectedTask.value?.id)
    ) {
      closeEditor()
    }
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  }
}
</script>
