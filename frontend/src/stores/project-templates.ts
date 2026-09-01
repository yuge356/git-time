import { defineStore } from 'pinia'

import { projectTemplateService } from '@/services/project-templates'
import {
  BUILT_IN_TEMPLATES,
  type ProjectTemplate,
  type ProjectTemplatePayload,
  type TemplateOption,
} from '@/types/project-template'

interface ProjectTemplateState {
  ownerId: string | null
  saved: ProjectTemplate[]
  loading: boolean
  saving: boolean
  loadError: string
}

function toOption(template: ProjectTemplate): TemplateOption {
  return {
    key: template.preset_key ?? template.id,
    id: template.id,
    name: template.name,
    description: template.description ?? '',
    icon: template.icon ?? '📁',
    budget_mode: template.budget_mode,
    fixed_budget_seconds: template.fixed_budget_seconds,
    default_estimated_seconds: template.default_estimated_seconds,
    default_repeat_rule: template.default_repeat_rule,
    structure: template.structure,
    isPreset: false,
  }
}

export const useProjectTemplateStore = defineStore('project-templates', {
  state: (): ProjectTemplateState => ({
    ownerId: null,
    saved: [],
    loading: false,
    saving: false,
    loadError: '',
  }),

  getters: {
    /**
     * Built-in presets plus the user's own templates. A saved template that
     * carries a `preset_key` is the user's edited copy of that preset and
     * takes its place, so the picker never shows both.
     */
    options(state): TemplateOption[] {
      const savedOptions = state.saved.map(toOption)
      const replacedPresets = new Set(
        state.saved.flatMap((item) => (item.preset_key ? [item.preset_key] : [])),
      )
      const presets = BUILT_IN_TEMPLATES.filter((preset) => !replacedPresets.has(preset.key))
      return [...presets, ...savedOptions]
    },
  },

  actions: {
    async initialize(ownerId: string): Promise<void> {
      if (this.ownerId === ownerId && this.saved.length > 0) return
      this.ownerId = ownerId
      await this.load()
    },

    async load(): Promise<void> {
      this.loading = true
      this.loadError = ''
      try {
        this.saved = await projectTemplateService.list()
      } catch (error) {
        // The built-in presets stay usable even when the list cannot load,
        // so template failures never block creating a project.
        this.loadError = error instanceof Error ? error.message : String(error)
      } finally {
        this.loading = false
      }
    },

    async save(payload: ProjectTemplatePayload, templateId: string | null): Promise<void> {
      this.saving = true
      try {
        const saved = templateId
          ? await projectTemplateService.update(templateId, payload)
          : await projectTemplateService.create(payload)
        const index = this.saved.findIndex((item) => item.id === saved.id)
        if (index >= 0) this.saved[index] = saved
        else this.saved.push(saved)
      } finally {
        this.saving = false
      }
    },

    async remove(templateId: string): Promise<void> {
      this.saving = true
      try {
        await projectTemplateService.remove(templateId)
        this.saved = this.saved.filter((item) => item.id !== templateId)
      } finally {
        this.saving = false
      }
    },
  },
})
