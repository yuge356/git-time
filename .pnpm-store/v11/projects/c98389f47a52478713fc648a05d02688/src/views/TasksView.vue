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
                  <span>通过整个网页滚动查看导图，点击节点查看详情</span>
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

                  <svg
                    v-if="dependencyPaths.length"
                    class="task-dependency-layer"
                    :width="mapNaturalSize.width"
                    :height="mapNaturalSize.height"
                    :viewBox="`0 0 ${mapNaturalSize.width} ${mapNaturalSize.height}`"
                    aria-label="任务依赖关系"
                  >
                    <defs>
                      <marker id="task-dependency-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                        <path d="M 0 0 L 8 4 L 0 8 z" />
                      </marker>
                    </defs>
                    <path
                      v-for="edge in dependencyPaths"
                      :key="edge.id"
                      class="task-dependency-line"
                      :d="edge.path"
                      marker-end="url(#task-dependency-arrow)"
                    >
                      <title>{{ edge.label }}</title>
                    </path>
                  </svg>
                </div>
              </div>
            </div>

              <p class="task-mindmap-hint">
                实线表示上下级关系，带箭头的虚线表示前置依赖；按住 Ctrl 滚动鼠标滚轮也可缩放。
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

              <section v-if="selectedTask?.node_type === 'TASK'" class="task-dependency-editor">
                <div class="task-dependency-editor__heading">
                  <div>
                    <span class="eyebrow">任务依赖</span>
                    <h3>设置前置任务</h3>
                  </div>
                  <span>{{ dependencyDraft.length }} 项依赖</span>
                </div>
                <p>被勾选的任务需要先完成，导图中会以带箭头的虚线连接到当前任务。</p>
                <div v-if="dependencyOptions.length" class="task-dependency-options">
                  <label v-for="option in dependencyOptions" :key="option.id">
                    <input v-model="dependencyDraft" type="checkbox" :value="option.id" />
                    <span>{{ option.label }}</span>
                  </label>
                </div>
                <p v-else class="field-help">还没有其他可设置为前置依赖的任务。</p>
                <div class="task-dependency-editor__actions">
                  <button
                    class="button button--quiet button--small"
                    type="button"
                    :disabled="!dependencyChanged || tasks.saving"
                    @click="resetDependencyDraft"
                  >
                    撤销
                  </button>
                  <button
                    class="button button--primary button--small"
                    type="button"
                    :disabled="!dependencyChanged || tasks.saving"
                    @click="saveDependencies"
                  >
                    保存依赖
                  </button>
                </div>
              </section>

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
const dependencyDraft = ref<string[]>([])
const dependencyPaths = ref<DependencyPath[]>([])
let resizeObserver: ResizeObserver | null = null
let layoutFrame = 0
let initialLoadFinished = false

interface DependencyPath {
  id: string
  path: string
  label: string
}

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
  ? '每个项目只保留一个主节点，右侧用连线展开模块与任务。导图随内容撑开页面，通过网页滚动查看全部节点。'
  : '项目、模块与任务按大纲层级纵向排列。点击名称查看设置，使用左侧拖动手柄调整任务层级。')
const editorDialogOpen = computed(() => Boolean(
  creating.value || selectedTask.value || creatingChildParentId.value,
))
const creatingChildParent = computed<Task | null>(() =>
  tasks.items.find((task) => task.id === creatingChildParentId.value) ?? null,
)
const dependencyOptions = computed(() => tasks.items
  .filter((task) => task.node_type === 'TASK' && task.id !== selectedTask.value?.id)
  .map((task) => ({
    id: task.id,
    label: projectPrefixedTaskTitle(task, tasks.items),
  }))
  .sort((left, right) => left.label.localeCompare(right.label, 'zh-CN')))
const dependencyChanged = computed(() => {
  const current = [...(selectedTask.value?.dependency_ids ?? [])].sort()
  const draft = [...dependencyDraft.value].sort()
  return current.length !== draft.length
    || current.some((item, index) => item !== draft[index])
})
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
  () => selectedTask.value?.id,
  resetDependencyDraft,
  { immediate: true },
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
    (task.dependency_ids ?? []).join(','),
  ]),
  scheduleMapLayout,
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
  taskViewMode.value = mode
  try {
    localStorage.setItem(TASK_VIEW_MODE_STORAGE_KEY, mode)
  } catch {
    // The selected view remains active for this page even if storage is unavailable.
  }
  if (mode === 'MINDMAP') scheduleMapLayout()
}

function resetDependencyDraft(): void {
  dependencyDraft.value = [...(selectedTask.value?.dependency_ids ?? [])]
}

async function saveDependencies(): Promise<void> {
  const task = selectedTask.value
  if (!task || task.node_type !== 'TASK' || !dependencyChanged.value) return
  editorError.value = ''
  actionMessage.value = ''
  try {
    const updated = await tasks.update(task.id, {
      dependency_ids: [...dependencyDraft.value],
    })
    selectedTask.value = updated
    resetDependencyDraft()
    actionMessage.value = `已更新“${updated.title}”的前置依赖。`
    scheduleMapLayout()
  } catch (error) {
    editorError.value = getApiErrorMessage(error)
  }
}

function scheduleMapLayout(): void {
  void nextTick(() => {
    if (layoutFrame) window.cancelAnimationFrame(layoutFrame)
    layoutFrame = window.requestAnimationFrame(() => {
      layoutFrame = 0
      syncMapLayout()
    })
  })
}

function syncMapLayout(): void {
  const tree = mapTree.value
  const canvas = mapCanvas.value
  if (!tree || !canvas) return
  if (!resizeObserver) {
    resizeObserver = new ResizeObserver(scheduleMapLayout)
    resizeObserver.observe(tree)
  }
  mapNaturalSize.value = {
    width: Math.max(960, Math.ceil(tree.scrollWidth)),
    height: Math.max(180, Math.ceil(tree.scrollHeight)),
  }
  updateDependencyPaths()
}

function updateDependencyPaths(): void {
  const canvas = mapCanvas.value
  if (!canvas) {
    dependencyPaths.value = []
    return
  }
  const canvasRect = canvas.getBoundingClientRect()
  const zoom = mapZoom.value
  const taskById = new Map(tasks.items.map((task) => [task.id, task]))
  const edges: DependencyPath[] = []
  tasks.items.forEach((targetTask) => {
    ;(targetTask.dependency_ids ?? []).forEach((sourceId, index) => {
      const sourceTask = taskById.get(sourceId)
      const source = canvas.querySelector<HTMLElement>(`[data-task-id="${CSS.escape(sourceId)}"]`)
      const target = canvas.querySelector<HTMLElement>(`[data-task-id="${CSS.escape(targetTask.id)}"]`)
      if (!sourceTask || !source || !target) return
      const sourceRect = source.getBoundingClientRect()
      const targetRect = target.getBoundingClientRect()
      const sourceCenterX = (sourceRect.left + sourceRect.right) / 2
      const targetCenterX = (targetRect.left + targetRect.right) / 2
      const movesRight = sourceCenterX <= targetCenterX
      const startX = (
        (movesRight ? sourceRect.right + 8 * zoom : sourceRect.left - 8 * zoom)
        - canvasRect.left
      ) / zoom
      const endX = (
        (movesRight ? targetRect.left - 12 * zoom : targetRect.right + 12 * zoom)
        - canvasRect.left
      ) / zoom
      const startY = ((sourceRect.top + sourceRect.bottom) / 2 - canvasRect.top) / zoom
      const endY = ((targetRect.top + targetRect.bottom) / 2 - canvasRect.top) / zoom
      const direction = movesRight ? 1 : -1
      const curve = Math.max(52, Math.abs(endX - startX) * 0.42)
      const laneOffset = (index % 4) * 8
      const controlY = startY <= endY ? -laneOffset : laneOffset
      const round = (value: number): number => Math.round(value * 10) / 10
      edges.push({
        id: `${sourceId}-${targetTask.id}`,
        path: [
          `M ${round(startX)} ${round(startY)}`,
          `C ${round(startX + direction * curve)} ${round(startY + controlY)},`,
          `${round(endX - direction * curve)} ${round(endY - controlY)},`,
          `${round(endX)} ${round(endY)}`,
        ].join(' '),
        label: `${sourceTask.title} → ${targetTask.title}`,
      })
    })
  })
  dependencyPaths.value = edges
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
  const availableWidth = Math.max(320, document.documentElement.clientWidth - 196)
  const horizontalScale = availableWidth / mapNaturalSize.value.width
  mapZoom.value = Math.min(1, Math.max(0.4, horizontalScale))
  mapZoom.value = Math.round(mapZoom.value * 10) / 10
  void nextTick(() => {
    viewport.scrollIntoView({ block: 'start', inline: 'start', behavior: 'smooth' })
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
      resizeObserver = new ResizeObserver(scheduleMapLayout)
      resizeObserver.observe(mapTree.value)
    }
    scheduleMapLayout()
    initialLoadFinished = true
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
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
    resizeObserver = new ResizeObserver(scheduleMapLayout)
    resizeObserver.observe(mapTree.value)
  }
  scheduleMapLayout()
})

onDeactivated(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
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
