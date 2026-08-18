<template>
  <section class="task-editor task-editor--inline" :aria-labelledby="editorTitleId">
    <header class="task-editor__header">
      <div>
        <p class="eyebrow">{{ editorEyebrow }}</p>
        <h2 :id="editorTitleId">{{ editorTitle }}</h2>
      </div>
      <button class="icon-button" type="button" aria-label="关闭编辑窗口" @click="$emit('close')">
        ×
      </button>
    </header>

    <form class="form-stack" @submit.prevent="submit">
      <label class="field">
        <span>{{ titleFieldLabel }}</span>
        <input
          v-model.trim="form.title"
          type="text"
          maxlength="200"
          required
          autofocus
          :placeholder="titlePlaceholder"
        />
      </label>

      <div class="task-schedule-grid">
        <label class="field">
          <span>优先级</span>
          <select v-model="form.priority">
            <option value="LOW">低</option>
            <option value="MEDIUM">普通</option>
            <option value="HIGH">高</option>
            <option value="URGENT">紧急</option>
          </select>
        </label>
        <label class="field">
          <span>截止日期</span>
          <input v-model="form.due_date" type="date" />
          <small>留空表示不设置截止日期。</small>
        </label>
      </div>

      <template v-if="isExecutableTask">
        <fieldset class="budget-fieldset">
          <legend>预计投入时间</legend>
          <div class="duration-grid">
            <label class="field">
              <span>小时</span>
              <input v-model.number="form.hours" type="number" min="0" max="87600" />
            </label>
            <label class="field">
              <span>分钟</span>
              <input v-model.number="form.minutes" type="number" min="0" max="59" />
            </label>
          </div>
          <small>
            {{ task ? '已有任务可暂时保留 0 分钟。' : '新建任务必须设置大于 0 的计划用时。' }}
          </small>
        </fieldset>

        <div class="task-schedule-grid">
          <label class="field">
            <span>重复</span>
            <select v-model="form.repeat_rule">
              <option value="NONE">不重复</option>
              <option value="DAILY">每天</option>
              <option value="WEEKDAYS">仅工作日</option>
              <option value="WEEKLY">每周</option>
              <option value="MONTHLY">每月</option>
            </select>
          </label>

          <label v-if="form.repeat_rule !== 'NONE'" class="field">
            <span>重复截止日期</span>
            <input v-model="form.repeat_end_date" type="date" />
            <small>留空表示永不截止。</small>
          </label>

          <div class="reminder-setting">
            <label class="toggle-field">
              <input v-model="form.reminder_enabled" type="checkbox" />
              <span>每日提醒</span>
            </label>
            <label v-if="form.reminder_enabled" class="field">
              <span>提醒时间</span>
              <input v-model="form.reminder_time" type="time" required />
            </label>
            <small v-else>开启后可设置每天的提醒时间。</small>
          </div>
        </div>

        <label v-if="task" class="field">
          <span>任务状态</span>
          <select v-model="form.status">
            <option value="TODO">待开始</option>
            <option value="IN_PROGRESS">进行中</option>
            <option value="PAUSED">已暂停</option>
            <option value="BLOCKED">阻塞</option>
            <option value="DONE">已完成</option>
          </select>
        </label>
      </template>

      <template v-else>
        <fieldset class="budget-fieldset">
          <legend>总体时间预算</legend>
          <label class="field">
            <span>预算方式</span>
            <select v-model="form.budget_mode">
              <option value="ROLLUP">自动汇总下属任务</option>
              <option value="FIXED_CAP">设置固定上限</option>
            </select>
          </label>
          <div v-if="form.budget_mode === 'FIXED_CAP'" class="duration-grid">
            <label class="field">
              <span>上限小时</span>
              <input v-model.number="form.fixed_hours" type="number" min="0" max="87600" />
            </label>
            <label class="field">
              <span>上限分钟</span>
              <input v-model.number="form.fixed_minutes" type="number" min="0" max="59" />
            </label>
          </div>
          <p v-if="task && form.budget_mode === 'ROLLUP'" class="budget-readonly">
            当前任务预算合计：{{ formatDuration(task.children_estimated_seconds) }}
          </p>
        </fieldset>

        <fieldset class="budget-fieldset container-defaults">
          <legend>新任务默认值</legend>
          <p class="field-help">用于以后新建的任务；模块默认值优先于项目默认值。</p>
          <div class="duration-grid">
            <label class="field">
              <span>默认小时</span>
              <input v-model.number="form.default_hours" type="number" min="0" max="87600" />
            </label>
            <label class="field">
              <span>默认分钟</span>
              <input v-model.number="form.default_minutes" type="number" min="0" max="59" />
            </label>
          </div>
          <div class="task-schedule-grid">
            <label class="field">
              <span>默认重复规则</span>
              <select v-model="form.default_repeat_rule">
                <option value="">继承上级 / 不设置</option>
                <option value="NONE">不重复</option>
                <option value="DAILY">每天</option>
                <option value="WEEKDAYS">仅工作日</option>
                <option value="WEEKLY">每周</option>
                <option value="MONTHLY">每月</option>
              </select>
            </label>
            <div class="reminder-setting">
              <label class="toggle-field">
                <input v-model="form.default_reminder_enabled" type="checkbox" />
                <span>设置默认提醒</span>
              </label>
              <label v-if="form.default_reminder_enabled" class="field">
                <span>默认提醒时间</span>
                <input v-model="form.default_reminder_time" type="time" required />
              </label>
            </div>
          </div>
        </fieldset>
      </template>

      <FormMessage :message="externalError || errorMessage" />

      <div class="task-editor__actions">
        <button class="button button--quiet" type="button" @click="$emit('close')">
          取消
        </button>
        <button class="button button--primary" type="submit" :disabled="saving">
          {{ saving ? '保存中…' : task ? '保存修改' : createButtonLabel }}
        </button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import FormMessage from '@/components/FormMessage.vue'
import type {
  Task,
  TaskBudgetMode,
  TaskCreatePayload,
  TaskNodeType,
  TaskPriority,
  TaskRepeatRule,
  TaskStatus,
  TaskUpdatePayload,
} from '@/types/task'
import { getApiErrorMessage } from '@/utils/api-error'
import { formatDuration } from '@/utils/time'

const props = withDefaults(defineProps<{
  task: Task | null
  saving: boolean
  externalError?: string
  parentId?: string | null
  parentTitle?: string
  nodeType?: TaskNodeType
  parentTask?: Task | null
  inheritedDefaultEstimatedSeconds?: number | null
  inheritedDefaultRepeatRule?: TaskRepeatRule | null
  inheritedDefaultReminderTime?: string | null
}>(), {
  externalError: '',
  parentId: null,
  parentTitle: '',
  nodeType: 'PROJECT',
  parentTask: null,
  inheritedDefaultEstimatedSeconds: null,
  inheritedDefaultRepeatRule: null,
  inheritedDefaultReminderTime: null,
})

const resolvedNodeType = computed(() => props.task?.node_type ?? props.nodeType)
const isExecutableTask = computed(() => resolvedNodeType.value === 'TASK')
const typeLabels: Record<TaskNodeType, string> = {
  PROJECT: '项目',
  MODULE: '模块',
  TASK: '任务',
}
const editorEyebrow = computed(() => `${props.task ? '编辑' : '新建'}${typeLabels[resolvedNodeType.value]}`)
const editorTitle = computed(() => {
  if (props.task) return props.task.title
  if (props.parentTitle) return `添加到“${props.parentTitle}”`
  return `创建${typeLabels[resolvedNodeType.value]}`
})
const titleFieldLabel = computed(() => `${typeLabels[resolvedNodeType.value]}名称`)
const titlePlaceholder = computed(() => ({
  PROJECT: '例如：技术信息学',
  MODULE: '例如：练习',
  TASK: '例如：练习 1',
})[resolvedNodeType.value])
const createButtonLabel = computed(() => `创建${typeLabels[resolvedNodeType.value]}`)
const editorTitleId = computed(() =>
  `task-editor-title-${props.task?.id ?? props.parentId ?? resolvedNodeType.value}`,
)

const emit = defineEmits<{
  close: []
  create: [payload: TaskCreatePayload]
  update: [taskId: string, payload: TaskUpdatePayload]
}>()

interface EditorForm {
  title: string
  priority: TaskPriority
  due_date: string
  hours: number
  minutes: number
  status: TaskStatus
  repeat_rule: TaskRepeatRule
  repeat_end_date: string
  reminder_enabled: boolean
  reminder_time: string
  budget_mode: TaskBudgetMode
  fixed_hours: number
  fixed_minutes: number
  default_hours: number
  default_minutes: number
  default_repeat_rule: TaskRepeatRule | ''
  default_reminder_enabled: boolean
  default_reminder_time: string
}

const errorMessage = ref('')
const form = reactive<EditorForm>({
  title: '',
  priority: 'MEDIUM',
  due_date: '',
  hours: 0,
  minutes: 0,
  status: 'TODO',
  repeat_rule: 'NONE',
  repeat_end_date: '',
  reminder_enabled: false,
  reminder_time: '08:00',
  budget_mode: 'ROLLUP',
  fixed_hours: 0,
  fixed_minutes: 0,
  default_hours: 0,
  default_minutes: 0,
  default_repeat_rule: '',
  default_reminder_enabled: false,
  default_reminder_time: '08:00',
})

function splitDuration(seconds: number | null | undefined): [number, number] {
  const value = seconds ?? 0
  return [Math.floor(value / 3600), Math.floor((value % 3600) / 60)]
}

function resetForm(): void {
  const source = props.task
  const taskSeconds = source?.estimated_seconds
    ?? (resolvedNodeType.value === 'TASK' ? props.inheritedDefaultEstimatedSeconds : 0)
    ?? 0
  ;[form.hours, form.minutes] = splitDuration(taskSeconds)
  ;[form.fixed_hours, form.fixed_minutes] = splitDuration(source?.fixed_budget_seconds)
  ;[form.default_hours, form.default_minutes] = splitDuration(source?.default_estimated_seconds)
  form.title = source?.title ?? ''
  form.priority = source?.priority ?? 'MEDIUM'
  form.due_date = source?.due_date ?? ''
  form.status = source?.status ?? 'TODO'
  form.repeat_rule = source?.repeat_rule
    ?? (resolvedNodeType.value === 'TASK' ? props.inheritedDefaultRepeatRule : null)
    ?? 'NONE'
  form.repeat_end_date = source?.repeat_end_date ?? ''
  const taskReminder = source?.daily_reminder_time
    ?? (resolvedNodeType.value === 'TASK' ? props.inheritedDefaultReminderTime : null)
  form.reminder_enabled = Boolean(taskReminder)
  form.reminder_time = taskReminder?.slice(0, 5) ?? '08:00'
  form.budget_mode = source?.budget_mode ?? 'ROLLUP'
  form.default_repeat_rule = source?.default_repeat_rule ?? ''
  form.default_reminder_enabled = Boolean(source?.default_daily_reminder_time)
  form.default_reminder_time = source?.default_daily_reminder_time?.slice(0, 5) ?? '08:00'
  errorMessage.value = ''
}

watch(
  () => [props.task?.id, props.parentId, props.nodeType],
  resetForm,
  { immediate: true },
)

function seconds(hours: number, minutes: number): number | null {
  const value = hours * 3600 + minutes * 60
  return Number.isInteger(value) && value >= 0 && value <= 315_360_000 ? value : null
}

function submit(): void {
  errorMessage.value = ''
  const estimatedSeconds = seconds(form.hours, form.minutes)
  const fixedBudgetSeconds = seconds(form.fixed_hours, form.fixed_minutes)
  const defaultEstimatedSeconds = seconds(form.default_hours, form.default_minutes)
  if (estimatedSeconds === null || fixedBudgetSeconds === null || defaultEstimatedSeconds === null) {
    errorMessage.value = '时间必须是有效的非负整数，且不能超过 87600 小时。'
    return
  }
  if (!props.task && isExecutableTask.value && estimatedSeconds === 0) {
    errorMessage.value = '请先设置任务的计划用时，小时和分钟不能同时为 0。'
    return
  }
  if (form.budget_mode === 'FIXED_CAP' && fixedBudgetSeconds === 0) {
    errorMessage.value = '固定上限必须大于 0。'
    return
  }

  try {
    if (props.task) {
      const payload: TaskUpdatePayload = {
        title: form.title,
        priority: form.priority,
        due_date: form.due_date || null,
      }
      if (isExecutableTask.value) {
        Object.assign(payload, {
          estimated_seconds: estimatedSeconds,
          status: form.status,
          repeat_rule: form.repeat_rule,
          repeat_end_date: form.repeat_end_date || null,
          daily_reminder_time: form.reminder_enabled ? form.reminder_time : null,
        })
      } else {
        Object.assign(payload, {
          budget_mode: form.budget_mode,
          fixed_budget_seconds: form.budget_mode === 'FIXED_CAP' ? fixedBudgetSeconds : null,
          default_estimated_seconds: defaultEstimatedSeconds > 0 ? defaultEstimatedSeconds : null,
          default_repeat_rule: form.default_repeat_rule || null,
          default_daily_reminder_time: form.default_reminder_enabled
            ? form.default_reminder_time
            : null,
        })
      }
      emit('update', props.task.id, payload)
      return
    }

    emit('create', {
      title: form.title,
      parent_id: props.parentId,
      node_type: resolvedNodeType.value,
      priority: form.priority,
      due_date: form.due_date || null,
      estimated_seconds: isExecutableTask.value ? estimatedSeconds : 0,
      budget_mode: isExecutableTask.value ? 'ROLLUP' : form.budget_mode,
      fixed_budget_seconds: !isExecutableTask.value && form.budget_mode === 'FIXED_CAP'
        ? fixedBudgetSeconds
        : null,
      default_estimated_seconds: !isExecutableTask.value && defaultEstimatedSeconds > 0
        ? defaultEstimatedSeconds
        : null,
      default_repeat_rule: !isExecutableTask.value
        ? (form.default_repeat_rule || null)
        : null,
      default_daily_reminder_time: !isExecutableTask.value && form.default_reminder_enabled
        ? form.default_reminder_time
        : null,
      repeat_rule: isExecutableTask.value ? form.repeat_rule : 'NONE',
      repeat_end_date: isExecutableTask.value ? (form.repeat_end_date || null) : null,
      daily_reminder_time: isExecutableTask.value && form.reminder_enabled
        ? form.reminder_time
        : null,
    })
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}
</script>
