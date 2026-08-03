import { http } from './http'
import type {
  Task,
  TaskBulkApplyPayload,
  TaskBulkApplyResponse,
  TaskCreatePayload,
  TaskUpdatePayload,
} from '@/types/task'

export const taskService = {
  async list(): Promise<Task[]> {
    const { data } = await http.get<Task[]>('/tasks')
    return data
  },

  async create(payload: TaskCreatePayload): Promise<Task> {
    const { data } = await http.post<Task>('/tasks', payload)
    return data
  },

  async update(taskId: string, payload: TaskUpdatePayload): Promise<Task> {
    const { data } = await http.patch<Task>(`/tasks/${taskId}`, payload)
    return data
  },

  async remove(taskId: string): Promise<void> {
    await http.delete(`/tasks/${taskId}`)
  },

  async applyDefaults(
    taskId: string,
    payload: TaskBulkApplyPayload,
  ): Promise<TaskBulkApplyResponse> {
    const { data } = await http.post<TaskBulkApplyResponse>(
      `/tasks/${taskId}/apply-defaults`,
      payload,
    )
    return data
  },
}
