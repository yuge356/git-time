<template>
  <AppShell>
    <main class="tasks-page">
      <section v-if="auth.showPageIntros" class="page-heading tasks-page__heading">
        <p class="eyebrow">项目</p>
        <h1>项目与时间预算</h1>
        <p>按“项目 → 模块 → 任务”组织学习内容；容器负责管理，任务负责执行。</p>
      </section>

      <div v-if="!tasks.online || tasks.pendingCount > 0" class="sync-banner">
        <strong>{{ tasks.online ? '等待同步' : '当前离线' }}</strong>
        <span>{{ tasks.pendingCount }} 条任务或计划变更已安全保存在本机。</span>
      </div>

      <section class="task-workspace">
        <div class="task-list-panel">
          <header class="panel-header">
            <div>
              <h2>我的项目</h2>
              <p>{{ projectCount }} 个项目 · {{ executableTaskCount }} 个可执行任务</p>
            </div>
            <button class="button button--primary" type="button" @click="openCreate">
              新建项目
            </button>
          </header>

          <p class="task-drag-help">
            每个项目只保留一个主节点，右侧用连线展开模块与任务。点击名称查看具体设置，点击箭头展开分支。
          </p>

          <FormMessage :message="loadError || timer.syncError" />
          <p v-if="actionMessage" class="task-action-feedback">{{ actionMessage }}</p>

          <TaskEditor
            v-if="creating"
            :task="null"
            node-type="PROJECT"
            :saving="tasks.saving"
            :external-error="editorError"
            @close="closeEditor"
            @create="createTask"
          />

          <p v-if="tasks.loading" class="loading-state">正在加载任务…</p>

          <div v-else-if="tasks.tree.length === 0 && !creating" class="empty-state">
            <span aria-hidden="true">01</span>
            <h3>从第一个项目开始</h3>
            <p>创建项目，再添加模块和具体任务。只有具体任务可以计时和完成。</p>
            <button class="button button--primary" type="button" @click="openCreate">
              创建项目
            </button>
          </div>

          <template v-else-if="tasks.tree.length">
            <div class="task-mindmap" aria-label="项目与任务导图">
              <ul class="task-tree task-tree--mindmap">
                <template v-for="task in tasks.tree" :key="task.id">
                  <TaskTreeNode
                    :task="task"
                    :editor-task-id="selectedTask?.id ?? null"
                    :creating-child-for-id="creatingChildParentId"
                    :dragging-task="draggingTask"
                    :active-task-id="timer.active?.snapshot.task_id ?? null"
                    :has-active-timer="Boolean(timer.active)"
                    :active-timer-paused="timer.active?.snapshot.status === 'PAUSED'"
                    :timer-busy="timer.busy"
                    @edit="openEdit"
                    @add-child="openCreateChild"
                    @apply-defaults="applyDefaults"
                    @start-task="startTask"
                    @remove="removeTask"
                    @drag-start="startDrag"
                    @drag-end="finishDrag"
                    @drop-on="moveUnderTask"
                  />

                  <li v-if="activeProjectId === task.id" class="task-project-settings">
                    <div v-if="selectedTask" class="task-node-toolbar">
                      <div>
                        <span>已选择{{ selectedTaskTypeLabel }}</span>
                        <strong>{{ selectedTask.title }}</strong>
                      </div>
                      <div class="task-node-toolbar__actions">
                        <button
                          v-if="selectedTask.node_type === 'PROJECT'"
                          class="button button--quiet button--small"
                          type="button"
                          @click="openCreateChild(selectedTask, 'MODULE')"
                        >
                          新建模块
                        </button>
                        <button
                          v-if="selectedTask.node_type !== 'TASK'"
                          class="button button--quiet button--small"
                          type="button"
                          @click="openCreateChild(selectedTask, 'TASK')"
                        >
                          新建任务
                        </button>
                        <button
                          v-if="selectedTask.node_type !== 'TASK'"
                          class="button button--quiet button--small"
                          type="button"
                          @click="applyDefaults(selectedTask)"
                        >
                          应用默认值
                        </button>
                        <button
                          v-if="selectedTask.node_type === 'TASK'"
                          class="button button--primary button--small"
                          type="button"
                          :disabled="timer.busy || Boolean(timer.active && timer.active.snapshot.status !== 'PAUSED')"
                          @click="startTask(selectedTask)"
                        >
                          开始计时
                        </button>
                        <button
                          class="button button--finish button--small"
                          type="button"
                          @click="removeTask(selectedTask)"
                        >
                          删除{{ selectedTaskTypeLabel }}
                        </button>
                      </div>
                    </div>

                    <TaskEditor
                      v-if="selectedTask"
                      :task="selectedTask"
                      :saving="tasks.saving"
                      :external-error="editorError"
                      @close="closeEditor"
                      @update="updateTask"
                    />

                    <TaskEditor
                      v-else-if="creatingChildParent"
                      :task="null"
                      :node-type="pendingChildNodeType"
                      :parent-id="creatingChildParent.id"
                      :parent-title="creatingChildParent.title"
                      :parent-task="creatingChildParent"
                      :inherited-default-estimated-seconds="inheritedDefaultEstimatedSeconds"
                      :inherited-default-repeat-rule="inheritedDefaultRepeatRule"
                      :inherited-default-reminder-time="inheritedDefaultReminderTime"
                      :saving="tasks.saving"
                      :external-error="editorError"
                      @close="closeEditor"
                      @create="createTask"
                    />
                  </li>
                </template>
              </ul>
            </div>
          </template>
        </div>
      </section>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import TaskEditor from '@/components/tasks/TaskEditor.vue'
import TaskTreeNode from '@/components/tasks/TaskTreeNode.vue'
import { useAuthStore } from '@/stores/auth'
import { useTaskStore } from '@/stores/tasks'
import { useTimerStore } from '@/stores/timer'
import type {
  Task,
  TaskCreatePayload,
  TaskNodeType,
  TaskRepeatRule,
  TaskUpdatePayload,
} from '@/types/task'
import { getApiErrorMessage } from '@/utils/api-error'

const tasks = useTaskStore()
const auth = useAuthStore()
const timer = useTimerStore()
const creating = ref(false)
const creatingChildParentId = ref<string | null>(null)
const creatingChildNodeType = ref<TaskNodeType | null>(null)
const selectedTask = ref<Task | null>(null)
const draggingTask = ref<Task | null>(null)
const loadError = ref('')
const editorError = ref('')
const actionMessage = ref('')
const projectCount = computed(() => tasks.items.filter((task) => task.node_type === 'PROJECT').length)
const executableTaskCount = computed(() => tasks.items.filter((task) => task.node_type === 'TASK').length)
const selectedTaskTypeLabel = computed(() => {
  if (selectedTask.value?.node_type === 'PROJECT') return '项目'
  if (selectedTask.value?.node_type === 'MODULE') return '模块'
  return '任务'
})
const creatingChildParent = computed<Task | null>(() =>
  tasks.items.find((task) => task.id === creatingChildParentId.value) ?? null,
)
const activeProjectId = computed<string | null>(() =>
  resolveProjectId(selectedTask.value ?? creatingChildParent.value),
)
const pendingChildNodeType = computed<TaskNodeType>(() =>
  creatingChildNodeType.value
    ?? (creatingChildParent.value?.node_type === 'PROJECT' ? 'MODULE' : 'TASK'),
)
const inheritedDefaultEstimatedSeconds = computed<number | null>(() =>
  resolveInheritedDefault('default_estimated_seconds'),
)
const inheritedDefaultRepeatRule = computed<TaskRepeatRule | null>(() =>
  resolveInheritedDefault('default_repeat_rule'),
)
const inheritedDefaultReminderTime = computed<string | null>(() =>
  resolveInheritedDefault('default_daily_reminder_time'),
)

type ContainerDefaultKey =
  | 'default_estimated_seconds'
  | 'default_repeat_rule'
  | 'default_daily_reminder_time'

function resolveProjectId(task: Task | null): string | null {
  let current = task
  const visited = new Set<string>()
  while (current && !visited.has(current.id)) {
    visited.add(current.id)
    if (current.node_type === 'PROJECT') return current.id
    current = current.parent_id
      ? tasks.items.find((item) => item.id === current?.parent_id) ?? null
      : null
  }
  return null
}

function resolveInheritedDefault<K extends ContainerDefaultKey>(key: K): Task[K] | null {
  let current = creatingChildParent.value
  const visited = new Set<string>()
  while (current && !visited.has(current.id)) {
    visited.add(current.id)
    const value = current[key]
    if (value !== null) return value
    current = current.parent_id
      ? tasks.items.find((task) => task.id === current?.parent_id) ?? null
      : null
  }
  return null
}

onMounted(async () => {
  try {
    const ownerId = auth.user?.profile.id
    if (ownerId) {
      await Promise.all([tasks.initialize(ownerId), timer.initialize(ownerId)])
    }
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  }
})

function openCreate(): void {
  selectedTask.value = null
  creatingChildParentId.value = null
  creatingChildNodeType.value = null
  creating.value = true
  editorError.value = ''
  actionMessage.value = ''
}

function openEdit(task: Task): void {
  if (selectedTask.value?.id === task.id) {
    closeEditor()
    return
  }
  creating.value = false
  creatingChildParentId.value = null
  selectedTask.value = task
  editorError.value = ''
}

function openCreateChild(parent: Task, nodeType: TaskNodeType): void {
  if (parent.node_type === 'TASK') return
  creating.value = false
  selectedTask.value = null
  creatingChildParentId.value = parent.id
  creatingChildNodeType.value = nodeType
  editorError.value = ''
  actionMessage.value = ''
}

function closeEditor(): void {
  creating.value = false
  creatingChildParentId.value = null
  creatingChildNodeType.value = null
  selectedTask.value = null
  editorError.value = ''
}

async function createTask(payload: TaskCreatePayload): Promise<void> {
  editorError.value = ''
  try {
    let targetPayload = payload
    const requestedParent = payload.parent_id
      ? tasks.items.find((task) => task.id === payload.parent_id)
      : null
    if (payload.node_type === 'TASK' && requestedParent?.node_type === 'PROJECT') {
      let uncategorizedModule = tasks.items.find(
        (task) =>
          task.node_type === 'MODULE'
          && task.parent_id === requestedParent.id
          && task.title === '未分类',
      )
      if (!uncategorizedModule) {
        uncategorizedModule = await tasks.create({
          title: '未分类',
          parent_id: requestedParent.id,
          node_type: 'MODULE',
          estimated_seconds: 0,
          budget_mode: 'ROLLUP',
          repeat_rule: 'NONE',
          daily_reminder_time: null,
        })
      }
      targetPayload = { ...payload, parent_id: uncategorizedModule.id }
    }
    const createdTask = await tasks.create(targetPayload)
    closeEditor()
    actionMessage.value = `已创建“${createdTask.title}”。`
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

async function moveTask(parent: Task): Promise<void> {
  const moving = draggingTask.value
  if (!moving || moving.parent_id === parent.id) return
  const valid = (
    moving.node_type === 'MODULE' && parent.node_type === 'PROJECT'
  ) || (
    moving.node_type === 'TASK' && parent.node_type === 'MODULE'
  )
  if (!valid) {
    loadError.value = '模块只能放在项目下，任务只能放在模块下。'
    return
  }
  try {
    await tasks.update(moving.id, { parent_id: parent.id })
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  } finally {
    draggingTask.value = null
  }
}

async function moveUnderTask(parent: Task): Promise<void> {
  await moveTask(parent)
}

async function applyDefaults(container: Task): Promise<void> {
  const confirmed = window.confirm(
    `把“${container.title}”的默认值应用到下属任务？只会填充尚未设置的字段，不会覆盖已有设置。`,
  )
  if (!confirmed) return
  loadError.value = ''
  actionMessage.value = ''
  try {
    const result = await tasks.applyDefaults(container.id, { overwrite: false })
    actionMessage.value = result.affected_count > 0
      ? `已更新 ${result.affected_count} 个任务，跳过 ${result.skipped_count} 个任务。`
      : '没有需要更新的任务。'
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  }
}

async function startTask(task: Task): Promise<void> {
  if (task.node_type !== 'TASK') return
  loadError.value = ''
  actionMessage.value = ''
  const availableSeconds = task.estimated_seconds - task.direct_actual_seconds
  const remaining = task.estimated_seconds > 0 && availableSeconds > 0
    ? availableSeconds
    : null
  const wasSwitching = timer.active?.snapshot.status === 'PAUSED'
  try {
    if (
      timer.active?.snapshot.status === 'PAUSED'
      && timer.active.snapshot.task_id === task.id
    ) {
      await timer.resume()
      actionMessage.value = `已继续“${task.title}”的计时。`
      return
    }
    await timer.start(task.id, null, remaining)
    actionMessage.value = wasSwitching
      ? `已切换到“${task.title}”并开始计时。`
      : `已开始“${task.title}”的计时。`
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  }
}

async function removeTask(task: Task): Promise<void> {
  const confirmed = window.confirm(
    `删除“${task.title}”${task.node_type === 'TASK' ? '' : '及其全部下属内容'}？此操作会保留同步记录。`,
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
