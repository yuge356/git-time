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
            <div class="panel-header__actions">
              <div class="task-view-switch" role="group" aria-label="项目呈现方式">
                <button
                  type="button"
                  :class="{ 'task-view-switch__button--active': taskViewMode === 'MINDMAP' }"
                  :aria-pressed="taskViewMode === 'MINDMAP'"
                  @click="setTaskViewMode('MINDMAP')"
                >
                  <span aria-hidden="true">⌘</span>
                  任务树
                </button>
                <button
                  type="button"
                  :class="{ 'task-view-switch__button--active': taskViewMode === 'CARDS' }"
                  :aria-pressed="taskViewMode === 'CARDS'"
                  @click="setTaskViewMode('CARDS')"
                >
                  <span aria-hidden="true">▤</span>
                  大纲列表
                </button>
              </div>
              <button class="button button--primary" type="button" @click="openCreate">
                新建项目
              </button>
            </div>
          </header>

          <p class="task-drag-help">
            {{ taskViewHelpText }}
          </p>

          <FormMessage :message="loadError || timer.syncError" />
          <p v-if="actionMessage" class="task-action-feedback">{{ actionMessage }}</p>

          <p v-if="tasks.loading && tasks.items.length === 0" class="loading-state">正在加载任务…</p>

          <div v-else-if="tasks.tree.length === 0" class="empty-state">
            <span aria-hidden="true">01</span>
            <h3>从第一个项目开始</h3>
            <p>创建项目，再添加模块和具体任务。只有具体任务可以计时和完成。</p>
            <button class="button button--primary" type="button" @click="openCreate">
              创建项目
            </button>
          </div>

          <template v-else-if="tasks.tree.length">
            <section v-if="taskViewMode === 'MINDMAP'" class="task-mindmap-shell">
              <header class="task-mindmap-toolbar">
                <div>
                  <strong>任务结构</strong>
                  <span>在面板内滚动或缩放查看导图，点击节点查看详情</span>
                </div>
                <div class="task-mindmap-toolbar__controls" aria-label="导图缩放控制">
                  <button class="icon-button" type="button" aria-label="缩小导图" @click="changeMapZoom(-0.1)">−</button>
                  <output aria-live="polite">{{ mapZoomPercent }}%</output>
                  <button class="icon-button" type="button" aria-label="放大导图" @click="changeMapZoom(0.1)">＋</button>
                  <button class="button button--quiet button--small" type="button" @click="fitMap">适合页面</button>
                </div>
              </header>

            <div
              ref="mapViewport"
              class="task-mindmap"
              aria-label="项目与任务导图"
              @wheel.ctrl.prevent="zoomMapAtPointer"
            >
              <div class="task-mindmap__surface" :style="mapSurfaceStyle">
                <div ref="mapCanvas" class="task-mindmap__canvas" :style="mapCanvasStyle">
                  <ul ref="mapTree" class="task-tree task-tree--mindmap">
                    <TaskTreeNode
                      v-for="task in tasks.tree"
                      :key="`mindmap-${task.id}`"
                      :task="task"
                      presentation="mindmap"
                      :project-theme="getProjectTheme(task.id)"
                      :editor-task-id="selectedTask?.id ?? null"
                      :creating-child-for-id="creatingChildParentId"
                      :dragging-task="draggingTask"
                      :active-task-id="timer.active?.snapshot.task_id ?? null"
                      :has-active-timer="Boolean(timer.active)"
                      :active-timer-paused="timer.active?.snapshot.status === 'PAUSED'"
                      :timer-busy="timer.busy"
                      :parent-node-type="null"
                      @edit="openEdit"
                      @add-child="openCreateChild"
                      @apply-defaults="applyDefaults"
                      @start-task="startTask"
                      @remove="removeTask"
                      @drag-start="startDrag"
                      @drag-end="finishDrag"
                      @drop-on="moveUnderTask"
                      @layout-change="scheduleMapLayout"
                    />
                  </ul>
                </div>
              </div>
            </div>

              <p class="task-mindmap-hint">
                实线表示上下级关系；按住 Ctrl 滚动鼠标滚轮也可缩放。
              </p>
            </section>

            <section v-else class="task-card-view" aria-label="项目与任务大纲视图">
              <header class="task-card-view__header">
                <div>
                  <strong>项目大纲</strong>
                  <span>父任务默认折叠；点击节点前的展开按钮查看子任务，同级子任务保持整齐对齐</span>
                </div>
              </header>
              <ul class="task-tree task-tree--cards">
                <TaskTreeNode
                  v-for="task in tasks.tree"
                  :key="`outline-${task.id}`"
                  :task="task"
                  presentation="outline"
                  :project-theme="getProjectTheme(task.id)"
                  :editor-task-id="selectedTask?.id ?? null"
                  :creating-child-for-id="creatingChildParentId"
                  :dragging-task="draggingTask"
                  :active-task-id="timer.active?.snapshot.task_id ?? null"
                  :has-active-timer="Boolean(timer.active)"
                  :active-timer-paused="timer.active?.snapshot.status === 'PAUSED'"
                  :timer-busy="timer.busy"
                  :parent-node-type="null"
                  @edit="openEdit"
                  @add-child="openCreateChild"
                  @apply-defaults="applyDefaults"
                  @start-task="startTask"
                  @remove="removeTask"
                  @drag-start="startDrag"
                  @drag-end="finishDrag"
                  @drop-on="moveUnderTask"
                />
              </ul>
            </section>
          </template>

          <Teleport to="body">
            <div
              v-if="editorDialogOpen"
              class="task-editor-modal__backdrop"
              @mousedown.self="closeEditor"
              @keydown.esc="closeEditor"
            >
              <section
                class="task-editor-modal"
                role="dialog"
                aria-modal="true"
                :aria-label="editorDialogLabel"
              >
                <div class="task-project-settings">
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
                    v-if="canAddChildTo(selectedTask)"
                    class="button button--quiet button--small"
                    type="button"
                    @click="openCreateChild(selectedTask, 'TASK')"
                  >
                    新建子任务
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

                  <TaskEditor
                    v-else-if="creating"
                    :task="null"
                    node-type="PROJECT"
                    :saving="tasks.saving"
                    :external-error="editorError"
                    @close="closeEditor"
                    @create="createTask"
                  />
                </div>
              </section>
            </div>
          </Teleport>
        </div>
      </section>
    </main>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import type { CSSProperties } from 'vue'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import TaskEditor from '@/components/tasks/TaskEditor.vue'
import TaskTreeNode from '@/components/tasks/TaskTreeNode.vue'
import { useAuthStore } from '@/stores/auth'
import { useDailyPlanStore } from '@/stores/daily-plans'
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
import { getProjectTheme } from '@/utils/project-theme'
import { projectPrefixedTaskTitle } from '@/utils/task-title'

defineOptions({ name: 'TasksView' })

const tasks = useTaskStore()
const auth = useAuthStore()
const daily = useDailyPlanStore()
const timer = useTimerStore()
const creating = ref(false)
const creatingChildParentId = ref<string | null>(null)
const creatingChildNodeType = ref<TaskNodeType | null>(null)
const selectedTask = ref<Task | null>(null)
const draggingTask = ref<Task | null>(null)
const loadError = ref('')
const editorError = ref('')
const actionMessage = ref('')
type TaskViewMode = 'MINDMAP' | 'CARDS'
const TASK_VIEW_MODE_STORAGE_KEY = 'time-budget:project-view-mode'
const storedTaskViewMode = (() => {
  try {
    return localStorage.getItem(TASK_VIEW_MODE_STORAGE_KEY) === 'CARDS'
      ? 'CARDS'
      : 'MINDMAP'
  } catch {
    return 'MINDMAP'
  }
})()
const taskViewMode = ref<TaskViewMode>(storedTaskViewMode)
const mapViewport = ref<HTMLElement | null>(null)
const mapCanvas = ref<HTMLElement | null>(null)
const mapTree = ref<HTMLElement | null>(null)
const mapZoom = ref(1)
const mapNaturalSize = ref({ width: 1114, height: 260 })
let resizeObserver: ResizeObserver | null = null
let viewportObserver: ResizeObserver | null = null
let layoutFrame = 0
let initialLoadFinished = false

const projectCount = computed(() => tasks.items.filter((task) => task.node_type === 'PROJECT').length)
const executableTaskCount = computed(() => tasks.items.filter((task) => task.node_type === 'TASK').length)
const mapZoomPercent = computed(() => Math.round(mapZoom.value * 100))
const mapSurfaceStyle = computed<CSSProperties>(() => ({
  width: `${Math.ceil(mapNaturalSize.value.width * mapZoom.value)}px`,
  height: `${Math.ceil(mapNaturalSize.value.height * mapZoom.value)}px`,
}))
const mapCanvasStyle = computed<CSSProperties>(() => ({
  width: `${mapNaturalSize.value.width}px`,
  minHeight: `${mapNaturalSize.value.height}px`,
  transform: `scale(${mapZoom.value})`,
}))
const selectedTaskTypeLabel = computed(() => {
  if (selectedTask.value?.node_type === 'PROJECT') return '项目'
  if (selectedTask.value?.node_type === 'MODULE') return '模块'
  return '任务'
})
const taskViewHelpText = computed(() => taskViewMode.value === 'MINDMAP'
  ? '每个项目只保留一个主节点，右侧用连线展开模块与任务。导图固定在面板内滚动查看，调整窗口大小时自动缩放适配。'
  : '项目、模块与任务按大纲层级纵向排列。点击名称查看设置，使用左侧拖动手柄调整任务层级。')
const editorDialogOpen = computed(() => Boolean(
  creating.value || selectedTask.value || creatingChildParentId.value,
))
const creatingChildParent = computed<Task | null>(() =>
  tasks.items.find((task) => task.id === creatingChildParentId.value) ?? null,
)
const pendingChildNodeType = computed<TaskNodeType>(() =>
  creatingChildNodeType.value
    ?? (creatingChildParent.value?.node_type === 'PROJECT' ? 'MODULE' : 'TASK'),
)
const pendingChildNodeTypeLabel = computed(() => {
  if (pendingChildNodeType.value === 'MODULE') return '模块'
  if (pendingChildNodeType.value === 'PROJECT') return '项目'
  return '任务'
})
const editorDialogLabel = computed(() => {
  if (selectedTask.value) return `编辑${selectedTaskTypeLabel.value}：${selectedTask.value.title}`
  if (creatingChildParent.value) {
    return `新建${pendingChildNodeTypeLabel.value}，上级为${creatingChildParent.value.title}`
  }
  return '新建项目'
})
const inheritedDefaultEstimatedSeconds = computed<number | null>(() =>
  resolveInheritedDefault('default_estimated_seconds'),
)
const inheritedDefaultRepeatRule = computed<TaskRepeatRule | null>(() =>
  resolveInheritedDefault('default_repeat_rule'),
)
const inheritedDefaultReminderTime = computed<string | null>(() =>
  resolveInheritedDefault('default_daily_reminder_time'),
)

watch(
  editorDialogOpen,
  (open) => document.body.classList.toggle('task-editor-modal-open', open),
  { immediate: true },
)

watch(
  () => tasks.items.map((task) => [
    task.id,
    task.parent_id,
    task.status,
    task.progress_ratio,
    task.due_date,
  ]),
  () => scheduleMapLayout(),
  { deep: true },
)

type ContainerDefaultKey =
  | 'default_estimated_seconds'
  | 'default_repeat_rule'
  | 'default_daily_reminder_time'

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

function setTaskViewMode(mode: TaskViewMode): void {
  if (taskViewMode.value === mode) return
  resizeObserver?.disconnect()
  resizeObserver = null
  viewportObserver?.disconnect()
  viewportObserver = null
  taskViewMode.value = mode
  try {
    localStorage.setItem(TASK_VIEW_MODE_STORAGE_KEY, mode)
  } catch {
    // The selected view remains active for this page even if storage is unavailable.
  }
  if (mode === 'MINDMAP') {
    void nextTick(() => {
      observeMapViewport()
      scheduleMapLayout(fitMap)
    })
  }
}

function scheduleMapLayout(afterLayout?: () => void): void {
  void nextTick(() => {
    if (layoutFrame) window.cancelAnimationFrame(layoutFrame)
    layoutFrame = window.requestAnimationFrame(() => {
      layoutFrame = 0
      syncMapLayout()
      afterLayout?.()
    })
  })
}

function syncMapLayout(): void {
  const tree = mapTree.value
  const canvas = mapCanvas.value
  if (!tree || !canvas) return
  if (!resizeObserver) {
    resizeObserver = new ResizeObserver(() => scheduleMapLayout())
    resizeObserver.observe(tree)
  }
  mapNaturalSize.value = {
    width: Math.max(960, Math.ceil(tree.scrollWidth)),
    height: Math.max(180, Math.ceil(tree.scrollHeight)),
  }
}

function observeMapViewport(): void {
  const viewport = mapViewport.value
  if (!viewport || viewportObserver) return
  // Window and panel resizes re-fit the zoom so the whole tree stays inside
  // the framed viewport instead of spilling out of the page layout.
  viewportObserver = new ResizeObserver(() => {
    if (taskViewMode.value !== 'MINDMAP') return
    window.requestAnimationFrame(() => fitMap())
  })
  viewportObserver.observe(viewport)
}

function setMapZoom(nextZoom: number): void {
  const next = Math.min(1.6, Math.max(0.4, Math.round(nextZoom * 10) / 10))
  if (next === mapZoom.value) return
  mapZoom.value = next
  void nextTick(() => {
    scheduleMapLayout()
  })
}

function changeMapZoom(delta: number): void {
  setMapZoom(mapZoom.value + delta)
}

function zoomMapAtPointer(event: WheelEvent): void {
  setMapZoom(mapZoom.value + (event.deltaY < 0 ? 0.1 : -0.1))
}

function fitMap(): void {
  const viewport = mapViewport.value
  if (!viewport) return
  const availableWidth = Math.max(320, viewport.clientWidth - 28)
  const availableHeight = Math.max(240, viewport.clientHeight - 28)
  const fitScale = Math.min(
    availableWidth / mapNaturalSize.value.width,
    availableHeight / mapNaturalSize.value.height,
    1,
  )
  const nextZoom = Math.min(1, Math.max(0.4, Math.round(fitScale * 20) / 20))
  if (nextZoom === mapZoom.value) return
  mapZoom.value = nextZoom
  void nextTick(() => {
    scheduleMapLayout()
  })
}

onMounted(async () => {
  try {
    const ownerId = auth.user?.profile.id
    if (ownerId) {
      await Promise.all([tasks.initialize(ownerId), timer.initialize(ownerId)])
    }
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  } finally {
    await nextTick()
    if (mapTree.value) {
      resizeObserver = new ResizeObserver(() => scheduleMapLayout())
      resizeObserver.observe(mapTree.value)
    }
    observeMapViewport()
    scheduleMapLayout(fitMap)
    initialLoadFinished = true
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  viewportObserver?.disconnect()
  if (layoutFrame) window.cancelAnimationFrame(layoutFrame)
  document.body.classList.remove('task-editor-modal-open')
})

onActivated(async () => {
  if (!initialLoadFinished) return
  const ownerId = auth.user?.profile.id
  if (ownerId) {
    tasks.load({ silent: true }).catch(() => {
      /* silent background sync */
    })
  }
  await nextTick()
  if (mapTree.value && !resizeObserver) {
    resizeObserver = new ResizeObserver(() => scheduleMapLayout())
    resizeObserver.observe(mapTree.value)
  }
  observeMapViewport()
  scheduleMapLayout(fitMap)
})

onDeactivated(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  viewportObserver?.disconnect()
  viewportObserver = null
  if (layoutFrame) window.cancelAnimationFrame(layoutFrame)
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
  if (parent.node_type === 'TASK') {
    const parentType = tasks.items.find((item) => item.id === parent.parent_id)?.node_type ?? null
    if (parentType === 'TASK') return
  }
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
    const createdTask = await tasks.create(payload)
    closeEditor()
    actionMessage.value = `已创建“${createdTask.title}”。`
  } catch (error) {
    editorError.value = getApiErrorMessage(error)
  }
}

async function updateTask(taskId: string, payload: TaskUpdatePayload): Promise<void> {
  editorError.value = ''
  try {
    const updated = await tasks.update(taskId, payload)
    if (payload.estimated_seconds !== undefined && tasks.ownerId) {
      await daily.syncLinkedTaskEstimate(tasks.ownerId, taskId, updated.estimated_seconds)
      await timer.updateTargetForTask(taskId, updated.estimated_seconds)
    }
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

function canAddChildTo(task: Task): boolean {
  if (task.node_type !== 'TASK') return false
  const parentType = tasks.items.find((item) => item.id === task.parent_id)?.node_type ?? null
  return parentType !== 'TASK'
}

async function moveTask(parent: Task): Promise<void> {
  const moving = draggingTask.value
  if (!moving || moving.parent_id === parent.id) return
  const valid = (
    moving.node_type === 'MODULE' && parent.node_type === 'PROJECT'
  ) || (
    moving.node_type === 'TASK'
    && (
      parent.node_type === 'MODULE'
      || parent.node_type === 'PROJECT'
      || (parent.node_type === 'TASK' && canAddChildTo(parent))
    )
  )
  if (!valid) {
    loadError.value = '模块只能放在项目下，任务可以放在项目、模块或任务（仅一层子任务）下。'
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
  const childCount = tasks.items.filter((item) => item.parent_id === task.id).length
  if (childCount > 0) {
    loadError.value = '含子任务的任务不能直接计时，请从子任务中选择。'
    return
  }
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
