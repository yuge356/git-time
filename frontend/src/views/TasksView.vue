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
              <label class="show-completed-toggle">
                <input v-model="showCompletedProjects" type="checkbox" />
                显示已完成项目
              </label>
              <button
                class="button button--quiet"
                type="button"
                @click="templateLibraryOpen = true"
              >
                模板库
              </button>
              <button class="button button--primary" type="button" @click="openCreate">
                新建项目
              </button>
            </div>
          </header>

          <p class="task-drag-help">
            {{ taskViewHelpText }}
          </p>

          <p
            v-if="hiddenCompletedCount > 0 && visibleProjectTree.length > 0"
            class="task-hidden-hint"
          >
            另有 {{ hiddenCompletedCount }} 个已完成项目被隐藏。
            <button type="button" class="text-action" @click="showCompletedProjects = true">
              显示它们
            </button>
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

          <div v-else-if="visibleProjectTree.length === 0" class="empty-state">
            <span aria-hidden="true">✓</span>
            <h3>{{ hiddenCompletedCount }} 个项目已标记完成</h3>
            <p>已完成的项目默认隐藏，计时数据仍保留在时间统计与计划进度表中。</p>
            <button
              class="button button--primary"
              type="button"
              @click="showCompletedProjects = true"
            >
              显示已完成项目
            </button>
          </div>

          <template v-else>
            <section v-if="taskViewMode === 'MINDMAP'" class="task-mindmap-shell">
              <header class="task-mindmap-toolbar">
                <div>
                  <strong>任务结构</strong>
                  <span>每个项目一块独立画布；节点保持固定大小，超出画布的内容滚动查看</span>
                </div>
                <div class="task-mindmap-toolbar__controls" aria-label="导图缩放控制">
                  <button class="icon-button" type="button" aria-label="缩小导图" @click="changeMapZoom(-0.1)">−</button>
                  <output aria-live="polite">{{ mapZoomPercent }}%</output>
                  <button class="icon-button" type="button" aria-label="放大导图" @click="changeMapZoom(0.1)">＋</button>
                </div>
              </header>

              <div class="task-mindmap-board">
                <article
                  v-for="project in visibleProjectTree"
                  :key="`mindmap-board-${project.id}`"
                  class="task-mindmap-project"
                >
                  <header class="task-mindmap-project__header">
                    <div class="task-mindmap-project__title">
                      <i
                        class="task-mindmap-project__dot"
                        aria-hidden="true"
                        :style="{ background: getProjectTheme(project.id).primary }"
                      ></i>
                      <strong>{{ project.title }}</strong>
                      <button
                        class="task-mindmap-project__toggle"
                        type="button"
                        :class="{ 'is-collapsed': collapsedMindmapProjects.has(project.id) }"
                        :aria-expanded="!collapsedMindmapProjects.has(project.id)"
                        :aria-label="`${collapsedMindmapProjects.has(project.id) ? '展开' : '折叠'}${project.title}的任务树`"
                        @click="toggleMindmapProject(project.id)"
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <path d="m6 9 6 6 6-6" />
                        </svg>
                      </button>
                    </div>
                    <span class="task-mindmap-project__meta">
                      已完成 {{ project.completed_task_count ?? 0 }} / {{ project.task_count ?? 0 }} 个任务
                    </span>
                  </header>
                  <div
                    v-show="!collapsedMindmapProjects.has(project.id)"
                    class="task-mindmap"
                    role="group"
                    :aria-label="`${project.title}的导图画布`"
                    :style="mapViewportStyle(project.id)"
                    @wheel.ctrl.prevent="zoomMapAtPointer"
                  >
                    <div class="task-mindmap__surface" :style="mapSurfaceStyle(project.id)">
                      <div class="task-mindmap__canvas" :style="mapCanvasStyle(project.id)">
                        <ul
                          :ref="(element) => registerMapTree(project.id, element)"
                          class="task-tree task-tree--mindmap"
                        >
                          <TaskTreeNode
                            :key="`mindmap-${project.id}`"
                            :task="project"
                            presentation="mindmap"
                            :project-theme="getProjectTheme(project.id)"
                            :editor-task-id="selectedTask?.id ?? null"
                            :expand-task-id="deepLinkTaskId"
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
                            @toggle-complete="toggleProjectComplete"
                            @drag-start="startDrag"
                            @drag-end="finishDrag"
                            @drop-on="moveUnderTask"
                            @layout-change="scheduleMapLayout"
                          />
                        </ul>
                      </div>
                    </div>
                  </div>
                </article>
              </div>

              <p class="task-mindmap-hint">
                实线表示上下级关系；调整窗口大小时节点大小不变，被遮住的部分通过画布滚动查看。
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
                  v-for="task in visibleProjectTree"
                  :key="`outline-${task.id}`"
                  :task="task"
                  presentation="outline"
                  :project-theme="getProjectTheme(task.id)"
                  :editor-task-id="selectedTask?.id ?? null"
                  :expand-task-id="deepLinkTaskId"
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
                  @toggle-complete="toggleProjectComplete"
                  @drag-start="startDrag"
                  @drag-end="finishDrag"
                  @drop-on="moveUnderTask"
                />
              </ul>
            </section>
          </template>

          <Teleport to="body">
            <ProjectTemplateLibrary
              v-if="templateLibraryOpen"
              @close="templateLibraryOpen = false"
            />
          </Teleport>

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
                    :templates="templates.options"
                    :selected-template-key="selectedTemplateKey"
                    @close="closeEditor"
                    @create="createTask"
                    @select-template="selectedTemplateKey = $event"
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
import { computed, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import type { CSSProperties } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppShell from '@/components/AppShell.vue'
import FormMessage from '@/components/FormMessage.vue'
import ProjectTemplateLibrary from '@/components/tasks/ProjectTemplateLibrary.vue'
import TaskEditor from '@/components/tasks/TaskEditor.vue'
import TaskTreeNode from '@/components/tasks/TaskTreeNode.vue'
import { useAuthStore } from '@/stores/auth'
import { useDailyPlanStore } from '@/stores/daily-plans'
import { useProjectTemplateStore } from '@/stores/project-templates'
import { useTaskStore } from '@/stores/tasks'
import { useTimerStore } from '@/stores/timer'
import type { TemplateNode } from '@/types/project-template'
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
const templates = useProjectTemplateStore()
const auth = useAuthStore()
const daily = useDailyPlanStore()
const timer = useTimerStore()
const route = useRoute()
const router = useRouter()
const creating = ref(false)
const creatingChildParentId = ref<string | null>(null)
const creatingChildNodeType = ref<TaskNodeType | null>(null)
const selectedTask = ref<Task | null>(null)
const deepLinkTaskId = ref<string | null>(null)
const draggingTask = ref<Task | null>(null)
const loadError = ref('')
const editorError = ref('')
const templateLibraryOpen = ref(false)
const selectedTemplateKey = ref('')
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
const mapZoom = ref(1)
const collapsedMindmapProjects = reactive(new Set<string>())

// 已标记完成的项目默认从列表隐藏（计时数据保留，历史记录仍可查）。
const showCompletedProjects = ref(false)
const visibleProjectTree = computed(() =>
  showCompletedProjects.value
    ? tasks.tree
    : tasks.tree.filter((project) => project.status !== 'DONE'),
)
// 被“显示已完成项目”开关隐藏的项目数量。之前列表为空时页面既不显示空状态
// 也不显示任何项目，看起来就像项目连同任务一起丢失了。
const hiddenCompletedCount = computed(() =>
  tasks.tree.length - visibleProjectTree.value.length,
)

async function toggleProjectComplete(task: Task): Promise<void> {
  const next: Task['status'] = task.status === 'DONE' ? 'IN_PROGRESS' : 'DONE'
  const noun = task.node_type === 'PROJECT' ? '项目' : '模块'
  actionMessage.value = ''
  try {
    await tasks.update(task.id, { status: next })
    actionMessage.value =
      next === 'DONE'
        ? `已标记${noun}完成：${noun === '项目' ? '项目将从列表隐藏' : '模块将显示完成状态'}，计时数据保留在历史记录中${task.node_type === 'PROJECT' ? '；勾选"显示已完成项目"可恢复' : ''}。`
        : `${noun}已恢复为进行中。`
  } catch (error) {
    actionMessage.value = getApiErrorMessage(error)
  }
}

function toggleMindmapProject(projectId: string): void {
  if (collapsedMindmapProjects.has(projectId)) {
    collapsedMindmapProjects.delete(projectId)
    // A hidden tree measures zero, so re-measure once it is visible again.
    scheduleMapLayout()
  } else {
    collapsedMindmapProjects.add(projectId)
  }
}

interface MapSize {
  width: number
  height: number
}
const mapSizes = ref<Record<string, MapSize>>({})
// Non-reactive registries: template function refs and ResizeObserver targets.
const mapTrees = new Map<string, HTMLElement>()
const observedTrees = new WeakSet<HTMLElement>()
let treeResizeObserver: ResizeObserver | null = null
let layoutFrame = 0
let initialLoadFinished = false

const projectCount = computed(() =>
  visibleProjectTree.value.length,
)
const executableTaskCount = computed(() => tasks.items.filter((task) => task.node_type === 'TASK').length)
const mapZoomPercent = computed(() => Math.round(mapZoom.value * 100))

function mapSurfaceStyle(projectId: string): CSSProperties {
  const size = mapSizes.value[projectId]
  if (!size) return { width: '100%' }
  return {
    width: `${Math.ceil(size.width * mapZoom.value)}px`,
    height: `${Math.ceil(size.height * mapZoom.value)}px`,
  }
}

// The canvas used to be a fixed 360-560px box whatever it held, so a project
// with two tasks sat in a mostly empty panel while a large one scrolled
// inside a small window. Size the viewport to the tree it actually contains,
// bounded so a very large tree still scrolls instead of pushing the page down.
const MAP_VIEWPORT_MIN_HEIGHT = 150
// Generous ceiling rather than a tight window: a project should normally show
// its whole tree without a nested scrollbar, and an unusually large one can be
// collapsed from its title bar instead of stretching the page indefinitely.
const MAP_VIEWPORT_MAX_HEIGHT = 2400
const MAP_VIEWPORT_PADDING = 8

function mapViewportStyle(projectId: string): CSSProperties {
  const size = mapSizes.value[projectId]
  if (!size) return {}
  const content = Math.ceil(size.height * mapZoom.value) + MAP_VIEWPORT_PADDING
  return {
    height: `${Math.min(
      MAP_VIEWPORT_MAX_HEIGHT,
      Math.max(MAP_VIEWPORT_MIN_HEIGHT, content),
    )}px`,
  }
}

function mapCanvasStyle(projectId: string): CSSProperties {
  const size = mapSizes.value[projectId]
  return {
    width: size ? `${size.width}px` : 'max-content',
    minHeight: size ? `${size.height}px` : '260px',
    transformOrigin: '0 0',
    transform: `scale(${mapZoom.value})`,
  }
}
const selectedTaskTypeLabel = computed(() => {
  if (selectedTask.value?.node_type === 'PROJECT') return '项目'
  if (selectedTask.value?.node_type === 'MODULE') return '模块'
  return '任务'
})
const taskViewHelpText = computed(() => taskViewMode.value === 'MINDMAP'
  ? '每个项目只保留一个主节点，右侧用连线展开模块与任务。每个项目拥有独立画布，节点保持固定大小，窗口变化时只裁剪滚动、不缩放内容。'
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

watch(
  editorDialogOpen,
  (open) => document.body.classList.toggle('task-editor-modal-open', open),
  { immediate: true },
)

// Only the tree's shape changes its measured size. Comparing a joined string
// avoids the deep diff over every task the old watcher performed, and avoids
// relaying out on every tick of a running timer's accumulated seconds.
watch(
  () => tasks.items.map((task) => `${task.id}:${task.parent_id ?? ''}:${task.status}`).join('|'),
  () => scheduleMapLayout(),
)

// Deep link from the today page gantt (?task=<id>): open the task editor and
// expand its ancestor chain once the task tree is available, then drop the
// query so refreshing does not reopen the dialog.
watch(
  () => route.query.task,
  (query) => {
    const taskId = typeof query === 'string' ? query : null
    if (!taskId || tasks.items.length === 0) return
    const task = tasks.items.find((item) => item.id === taskId)
    if (!task) return
    deepLinkTaskId.value = taskId
    openEdit(task)
    void router.replace({ query: { ...route.query, task: undefined } })
  },
  { immediate: true },
)

type ContainerDefaultKey =
  | 'default_estimated_seconds'
  | 'default_repeat_rule'

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
  treeResizeObserver?.disconnect()
  treeResizeObserver = null
  mapTrees.clear()
  taskViewMode.value = mode
  try {
    localStorage.setItem(TASK_VIEW_MODE_STORAGE_KEY, mode)
  } catch {
    // The selected view remains active for this page even if storage is unavailable.
  }
  if (mode === 'MINDMAP') scheduleMapLayout()
}

function registerMapTree(projectId: string, element: unknown): void {
  if (element instanceof HTMLElement) {
    mapTrees.set(projectId, element)
  } else {
    mapTrees.delete(projectId)
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
  if (mapTrees.size === 0) return
  if (!treeResizeObserver) {
    // Only re-measures natural content size; window resizes never rescale
    // the nodes — the canvas simply clips and scrolls instead.
    treeResizeObserver = new ResizeObserver(() => scheduleMapLayout())
  }
  const nextSizes: Record<string, MapSize> = {}
  mapTrees.forEach((tree, projectId) => {
    if (!observedTrees.has(tree)) {
      treeResizeObserver?.observe(tree)
      observedTrees.add(tree)
    }
    nextSizes[projectId] = {
      width: Math.max(320, Math.ceil(tree.scrollWidth)),
      height: Math.max(120, Math.ceil(tree.scrollHeight)),
    }
  })
  // Writing the same sizes back would resize the canvas, wake the
  // ResizeObserver and schedule another pass — a loop that showed up as the
  // tree twitching after every render. Only publish real changes.
  const current = mapSizes.value
  const currentIds = Object.keys(current)
  const nextIds = Object.keys(nextSizes)
  const unchanged =
    currentIds.length === nextIds.length &&
    nextIds.every(
      (id) =>
        current[id]?.width === nextSizes[id]!.width &&
        current[id]?.height === nextSizes[id]!.height,
    )
  if (unchanged) return
  mapSizes.value = nextSizes
}

function setMapZoom(nextZoom: number): void {
  const next = Math.min(1.6, Math.max(0.4, Math.round(nextZoom * 10) / 10))
  if (next === mapZoom.value) return
  mapZoom.value = next
}

function changeMapZoom(delta: number): void {
  setMapZoom(mapZoom.value + delta)
}

function zoomMapAtPointer(event: WheelEvent): void {
  setMapZoom(mapZoom.value + (event.deltaY < 0 ? 0.1 : -0.1))
}

onMounted(async () => {
  try {
    const ownerId = auth.user?.profile.id
    if (ownerId) {
      await Promise.all([tasks.initialize(ownerId), timer.initialize(ownerId)])
      // Templates are optional decoration for this page: load them after the
      // task tree so they never delay it or block it on their own failure.
      void templates.initialize(ownerId)
    }
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  } finally {
    await nextTick()
    scheduleMapLayout()
    initialLoadFinished = true
  }
})

onBeforeUnmount(() => {
  treeResizeObserver?.disconnect()
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
  scheduleMapLayout()
})

onDeactivated(() => {
  treeResizeObserver?.disconnect()
  treeResizeObserver = null
  mapTrees.clear()
  if (layoutFrame) window.cancelAnimationFrame(layoutFrame)
})

function openCreate(): void {
  selectedTask.value = null
  creatingChildParentId.value = null
  creatingChildNodeType.value = null
  creating.value = true
  selectedTemplateKey.value = ''
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
  selectedTemplateKey.value = ''
  editorError.value = ''
}

async function createTask(payload: TaskCreatePayload): Promise<void> {
  editorError.value = ''
  try {
    const createdTask = await tasks.create(payload)
    const applied = await applySelectedTemplate(createdTask)
    closeEditor()
    actionMessage.value = applied
      ? `已按模板创建“${createdTask.title}”，共 ${applied} 个模块与任务。`
      : `已创建“${createdTask.title}”。`
  } catch (error) {
    editorError.value = getApiErrorMessage(error)
  }
}

/**
 * Materialize the selected template under a freshly created project. The
 * nodes go through the ordinary task store, so they are cached locally and
 * replayed through the same offline outbox as any hand-made task.
 */
async function applySelectedTemplate(project: Task): Promise<number> {
  const template = templates.options.find((option) => option.key === selectedTemplateKey.value)
  selectedTemplateKey.value = ''
  if (!template || project.node_type !== 'PROJECT') return 0

  let created = 0
  const createNodes = async (nodes: TemplateNode[], parentId: string): Promise<void> => {
    for (const node of nodes) {
      const child = await tasks.create({
        parent_id: parentId,
        node_type: node.node_type,
        title: node.title,
        estimated_seconds: node.node_type === 'TASK' ? node.estimated_seconds : 0,
        budget_mode: 'ROLLUP',
        fixed_budget_seconds: null,
        default_estimated_seconds:
          node.node_type === 'MODULE' ? template.default_estimated_seconds : null,
        default_repeat_rule: node.node_type === 'MODULE' ? template.default_repeat_rule : null,
        default_daily_reminder_time: null,
        repeat_rule:
          node.node_type === 'TASK' ? (template.default_repeat_rule ?? 'NONE') : 'NONE',
        repeat_end_date: null,
        daily_reminder_time: null,
      })
      created += 1
      if (node.children.length > 0) await createNodes(node.children, child.id)
    }
  }
  await createNodes(template.structure, project.id)
  return created
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
