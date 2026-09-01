<template>
  <div class="template-library__backdrop" @mousedown.self="$emit('close')" @keydown.esc="$emit('close')">
    <section class="template-library" role="dialog" aria-modal="true" aria-label="项目模板库">
      <header class="template-library__header">
        <div>
          <p class="eyebrow">项目模板</p>
          <h2>{{ editing ? editorHeading : '模板库' }}</h2>
        </div>
        <button class="icon-button" type="button" aria-label="关闭模板库" @click="$emit('close')">
          ×
        </button>
      </header>

      <FormMessage :message="errorMessage" />

      <div v-if="!editing" class="template-library__list">
        <p class="template-library__hint">
          创建项目时可以直接套用模板；内置模板可以改成自己的版本，也可以新建属于自己的模板。
        </p>

        <article v-for="option in templates" :key="option.key" class="template-card">
          <div class="template-card__identity">
            <span class="template-card__icon" aria-hidden="true">{{ option.icon }}</span>
            <div>
              <strong>{{ option.name }}</strong>
              <span v-if="option.isPreset" class="template-card__badge">内置</span>
              <p>{{ option.description || '没有说明。' }}</p>
              <small>{{ summarize(option) }}</small>
            </div>
          </div>
          <div class="template-card__actions">
            <button class="button button--quiet button--small" type="button" @click="startEdit(option)">
              {{ option.isPreset ? '另存为我的模板' : '编辑' }}
            </button>
            <button
              v-if="!option.isPreset && option.id"
              class="text-action text-action--danger"
              type="button"
              :disabled="saving"
              @click="remove(option.id)"
            >
              删除
            </button>
          </div>
        </article>

        <button class="button button--primary" type="button" @click="startCreate">
          新建模板
        </button>
      </div>

      <form v-else class="form-stack template-library__editor" @submit.prevent="submit">
        <div class="task-schedule-grid">
          <label class="field">
            <span>模板名称</span>
            <input v-model.trim="form.name" type="text" maxlength="80" required />
          </label>
          <label class="field">
            <span>图标</span>
            <input v-model.trim="form.icon" type="text" maxlength="2" placeholder="📚" />
          </label>
        </div>

        <label class="field">
          <span>说明</span>
          <input v-model.trim="form.description" type="text" maxlength="300" />
        </label>

        <div class="task-schedule-grid">
          <label class="field">
            <span>新任务默认时长（分钟）</span>
            <input v-model.number="form.defaultMinutes" type="number" min="0" max="1440" />
          </label>
          <label class="field">
            <span>默认重复规则</span>
            <select v-model="form.defaultRepeatRule">
              <option value="">不设置</option>
              <option value="NONE">不重复</option>
              <option value="DAILY">每天</option>
              <option value="WEEKDAYS">仅工作日</option>
              <option value="WEEKLY">每周</option>
              <option value="MONTHLY">每月</option>
            </select>
          </label>
        </div>

        <fieldset class="budget-fieldset">
          <legend>模板结构</legend>
          <p class="field-help">模块用于分组，任务是可以计时的最小单位。</p>

          <ul class="template-outline">
            <li v-for="(item, index) in form.structure" :key="`root-${index}`">
              <div class="template-outline__row">
                <span class="template-outline__type">
                  {{ item.node_type === 'MODULE' ? '模块' : '任务' }}
                </span>
                <input
                  v-model.trim="item.title"
                  type="text"
                  maxlength="200"
                  :aria-label="`第 ${index + 1} 项名称`"
                  required
                />
                <input
                  v-if="item.node_type === 'TASK'"
                  v-model.number="item.minutes"
                  type="number"
                  min="0"
                  max="1440"
                  aria-label="计划分钟"
                />
                <button
                  v-if="item.node_type === 'MODULE'"
                  class="text-action"
                  type="button"
                  @click="addChild(item)"
                >
                  ＋任务
                </button>
                <button class="text-action text-action--danger" type="button" @click="removeRoot(index)">
                  删除
                </button>
              </div>

              <ul v-if="item.children.length" class="template-outline template-outline--nested">
                <li v-for="(child, childIndex) in item.children" :key="`child-${index}-${childIndex}`">
                  <div class="template-outline__row">
                    <span class="template-outline__type">任务</span>
                    <input
                      v-model.trim="child.title"
                      type="text"
                      maxlength="200"
                      :aria-label="`${item.title} 下第 ${childIndex + 1} 个任务名称`"
                      required
                    />
                    <input
                      v-model.number="child.minutes"
                      type="number"
                      min="0"
                      max="1440"
                      aria-label="计划分钟"
                    />
                    <button
                      class="text-action text-action--danger"
                      type="button"
                      @click="item.children.splice(childIndex, 1)"
                    >
                      删除
                    </button>
                  </div>
                </li>
              </ul>
            </li>
          </ul>

          <div class="template-outline__actions">
            <button class="button button--quiet button--small" type="button" @click="addRoot('MODULE')">
              ＋ 添加模块
            </button>
            <button class="button button--quiet button--small" type="button" @click="addRoot('TASK')">
              ＋ 添加任务
            </button>
          </div>
        </fieldset>

        <div class="task-editor__actions">
          <button class="button button--quiet" type="button" @click="cancelEdit">返回</button>
          <button class="button button--primary" type="submit" :disabled="saving">
            {{ saving ? '保存中…' : '保存模板' }}
          </button>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import FormMessage from '@/components/FormMessage.vue'
import { useProjectTemplateStore } from '@/stores/project-templates'
import type { TemplateNode, TemplateOption } from '@/types/project-template'
import { countTemplateNodes, templateTotalSeconds } from '@/types/project-template'
import type { TaskRepeatRule } from '@/types/task'
import { getApiErrorMessage } from '@/utils/api-error'
import { formatDuration } from '@/utils/time'

defineEmits<{ close: [] }>()

const store = useProjectTemplateStore()
const templates = computed(() => store.options)
const saving = computed(() => store.saving)
const errorMessage = ref('')
const editing = ref(false)
const editorHeading = ref('新建模板')

/** Editable mirror of a template node; minutes are easier to type than seconds. */
interface OutlineDraft {
  node_type: 'MODULE' | 'TASK'
  title: string
  minutes: number
  children: OutlineDraft[]
}

interface TemplateForm {
  templateId: string | null
  presetKey: string | null
  name: string
  icon: string
  description: string
  defaultMinutes: number
  defaultRepeatRule: TaskRepeatRule | ''
  structure: OutlineDraft[]
}

const form = reactive<TemplateForm>({
  templateId: null,
  presetKey: null,
  name: '',
  icon: '📁',
  description: '',
  defaultMinutes: 30,
  defaultRepeatRule: '',
  structure: [],
})

function summarize(option: TemplateOption): string {
  const { modules, tasks } = countTemplateNodes(option.structure)
  const total = templateTotalSeconds(option.structure)
  const parts = [`${modules} 个模块`, `${tasks} 个任务`]
  if (total > 0) parts.push(`合计 ${formatDuration(total)}`)
  return parts.join(' · ')
}

function toDraft(nodes: TemplateNode[]): OutlineDraft[] {
  return nodes.map((node) => ({
    node_type: node.node_type,
    title: node.title,
    minutes: Math.round(node.estimated_seconds / 60),
    children: toDraft(node.children),
  }))
}

function toNodes(drafts: OutlineDraft[]): TemplateNode[] {
  return drafts
    .filter((draft) => draft.title.trim().length > 0)
    .map((draft) => ({
      node_type: draft.node_type,
      title: draft.title.trim(),
      estimated_seconds: Math.max(0, Math.round(draft.minutes || 0)) * 60,
      children: toNodes(draft.children),
    }))
}

function startCreate(): void {
  errorMessage.value = ''
  editorHeading.value = '新建模板'
  Object.assign(form, {
    templateId: null,
    presetKey: null,
    name: '',
    icon: '📁',
    description: '',
    defaultMinutes: 30,
    defaultRepeatRule: '' as const,
    structure: [],
  })
  editing.value = true
}

function startEdit(option: TemplateOption): void {
  errorMessage.value = ''
  // A built-in preset has no server row: editing one saves the user's own
  // copy, which then replaces the preset in the picker.
  editorHeading.value = option.isPreset ? `另存“${option.name}”` : `编辑“${option.name}”`
  Object.assign(form, {
    templateId: option.id,
    presetKey: option.isPreset ? option.key : null,
    name: option.name,
    icon: option.icon,
    description: option.description,
    defaultMinutes: Math.round((option.default_estimated_seconds ?? 0) / 60),
    defaultRepeatRule: option.default_repeat_rule ?? '',
    structure: toDraft(option.structure),
  })
  editing.value = true
}

function cancelEdit(): void {
  editing.value = false
  errorMessage.value = ''
}

function addRoot(nodeType: 'MODULE' | 'TASK'): void {
  form.structure.push({
    node_type: nodeType,
    title: '',
    minutes: nodeType === 'TASK' ? Math.max(0, form.defaultMinutes) : 0,
    children: [],
  })
}

function addChild(item: OutlineDraft): void {
  item.children.push({
    node_type: 'TASK',
    title: '',
    minutes: Math.max(0, form.defaultMinutes),
    children: [],
  })
}

function removeRoot(index: number): void {
  form.structure.splice(index, 1)
}

async function submit(): Promise<void> {
  errorMessage.value = ''
  const structure = toNodes(form.structure)
  if (structure.length === 0) {
    errorMessage.value = '模板至少需要一个模块或任务。'
    return
  }
  const defaultSeconds = Math.max(0, Math.round(form.defaultMinutes || 0)) * 60
  try {
    await store.save(
      {
        name: form.name,
        description: form.description || null,
        icon: form.icon || null,
        preset_key: form.presetKey,
        budget_mode: 'ROLLUP',
        fixed_budget_seconds: null,
        default_estimated_seconds: defaultSeconds > 0 ? defaultSeconds : null,
        default_repeat_rule: form.defaultRepeatRule || null,
        structure,
      },
      form.templateId,
    )
    editing.value = false
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}

async function remove(templateId: string): Promise<void> {
  if (!window.confirm('删除这个模板？已经用它创建的项目不受影响。')) return
  errorMessage.value = ''
  try {
    await store.remove(templateId)
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}
</script>
