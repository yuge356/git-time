<template>
  <section class="task-editor task-editor--inline" :aria-labelledby="editorTitleId">
    <header class="task-editor__header">
      <div>
        <p class="eyebrow">{{ editorEyebrow }}</p>
        <h2 :id="editorTitleId">{{ editorTitle }}</h2>
      </div>
      <button class="icon-button" type="button" aria-label="关闭编辑面板" @click="$emit('close')">
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
          :placeholder="titlePlaceholder"
        />
      </label>

      <fieldset class="budget-fieldset">
        <legend>预计投入时间</legend>
        <div v-if="!isParentTask" class="duration-grid">
          <label class="field">
            <span>小时</span>
            <input v-model.number="form.hours" type="number" min="0" max="87600" />
          </label>
          <label class="field">
            <span>分钟</span>
            <input v-model.number="form.minutes" type="number" min="0" max="59" />
          </label>
        </div>
        <p v-else class="budget-readonly">子任务预算合计: {{ formatDuration(task!.children_estimated_seconds) }}</p>
        <small>设为 0 表示暂不设置时间预算。</small>
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
          <option value="DONE">已完成</option>
        </select>
      </label>

      <FormMessage :message="externalError || errorMessage" />

      <div class="task-editor__actions">
        <button class="button button--quiet" type="button" @click="$emit('close')">
          取消
        </button>
        <button class="button button--primary" type="submit" :disabled="saving">
          {{ saving ? '保存中…' : task ? '保存修改' : parentId ? '创建子任务' : '创建项目' }}
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
  TaskCreatePayload,
  TaskRepeatRule,
  TaskStatus,
  TaskUpdatePayload,
} from '@/types/task'
import { getApiErrorMessage } from '@/utils/api-error'
import { formatDuration } from '@/utils/time'

const props = defineProps<{
  task: Task | null
  saving: boolean
  externalError?: string
  parentId?: string | null
  parentTitle?: string
}>()

const isParentTask = computed(() => props.task && !props.task.is_leaf)
const editorEyebrow = computed(() => {
  if (props.task) return props.task.parent_id ? '编辑任务' : '编辑项目'
  return props.parentId ? '添加子任务' : '新建项目'
})
const editorTitle = computed(() => {
  if (props.task) return props.task.title
  return props.parentId ? `添加到“${props.parentTitle ?? '父任务'}”` : '规划项目投入'
})
const isProjectEditor = computed(() => !props.parentId && !props.task?.parent_id)
const titleFieldLabel = computed(() => (isProjectEditor.value ? '项目名称' : '任务标题'))
const titlePlaceholder = computed(() =>
  isProjectEditor.value ? '例如：网站改版项目' : '例如：完成首页原型',
)
const editorTitleId = computed(() =>
  `task-editor-title-${props.task?.id ?? props.parentId ?? 'root'}`,
)

const emit = defineEmits<{
  close: []
  create: [payload: TaskCreatePayload]
  update: [taskId: string, payload: TaskUpdatePayload]
}>()

interface EditorForm {
  title: string
  hours: number
  minutes: number
  status: TaskStatus
  repeat_rule: TaskRepeatRule
  repeat_end_date: string
  reminder_enabled: boolean
  reminder_time: string
}

const errorMessage = ref('')
const form = reactive<EditorForm>({
  title: '',
  hours: 0,
  minutes: 0,
  status: 'TODO',
  repeat_rule: 'NONE',
  repeat_end_date: '',
  reminder_enabled: false,
  reminder_time: '08:00',
})

function resetForm(): void {
  const seconds = props.task?.estimated_seconds ?? 0
  form.title = props.task?.title ?? ''
  form.hours = Math.floor(seconds / 3600)
  form.minutes = Math.floor((seconds % 3600) / 60)
  form.status = props.task?.status ?? 'TODO'
  form.repeat_rule = props.task?.repeat_rule ?? 'NONE'
  form.repeat_end_date = props.task?.repeat_end_date ?? ''
  form.reminder_enabled = Boolean(props.task?.daily_reminder_time)
  form.reminder_time = props.task?.daily_reminder_time?.slice(0, 5) ?? '08:00'
  errorMessage.value = ''
}

watch(
  () => [props.task?.id, props.parentId],
  resetForm,
  { immediate: true },
)

function submit(): void {
  errorMessage.value = ''
  const estimatedSeconds = form.hours * 3600 + form.minutes * 60
  if (!Number.isInteger(estimatedSeconds) || estimatedSeconds < 0) {
    errorMessage.value = '预计时间必须是有效的非负整数。'
    return
  }
  if (estimatedSeconds > 315360000) {
    errorMessage.value = '预计时间不能超过 87600 小时。'
    return
  }
  if (form.reminder_enabled && !form.reminder_time) {
    errorMessage.value = '请选择每日提醒时间。'
    return
  }

  const dailyReminderTime = form.reminder_enabled ? form.reminder_time : null

  try {
    if (props.task) {
      emit('update', props.task.id, {
        title: form.title,
        estimated_seconds: estimatedSeconds,
        status: form.status,
        repeat_rule: form.repeat_rule,
        repeat_end_date: form.repeat_end_date || null,
        daily_reminder_time: dailyReminderTime,
      })
    } else {
      emit('create', {
        title: form.title,
        parent_id: props.parentId ?? null,
        estimated_seconds: estimatedSeconds,
        repeat_rule: form.repeat_rule,
        repeat_end_date: form.repeat_end_date || null,
        daily_reminder_time: dailyReminderTime,
      })
    }
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}

</script>
