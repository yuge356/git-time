import { http } from './http'
import type { ProjectTemplate, ProjectTemplatePayload } from '@/types/project-template'

export const projectTemplateService = {
  async list(): Promise<ProjectTemplate[]> {
    const { data } = await http.get<ProjectTemplate[]>('/project-templates')
    return data
  },

  async create(payload: ProjectTemplatePayload): Promise<ProjectTemplate> {
    const { data } = await http.post<ProjectTemplate>('/project-templates', payload)
    return data
  },

  async update(
    templateId: string,
    payload: Partial<ProjectTemplatePayload>,
  ): Promise<ProjectTemplate> {
    const { data } = await http.patch<ProjectTemplate>(
      `/project-templates/${templateId}`,
      payload,
    )
    return data
  },

  async remove(templateId: string): Promise<void> {
    await http.delete(`/project-templates/${templateId}`)
  },
}
