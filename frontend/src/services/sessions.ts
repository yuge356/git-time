import type { SessionSnapshot, StudySession } from '@/types/session'
import { http } from './http'

export const sessionService = {
  async upsert(sessionId: string, snapshot: SessionSnapshot): Promise<StudySession> {
    const { data } = await http.put<StudySession>(`/sessions/${sessionId}`, snapshot)
    return data
  },

  async active(): Promise<StudySession | null> {
    const { data } = await http.get<StudySession | null>('/sessions/active')
    return data
  },

  async list(limit = 30): Promise<StudySession[]> {
    const { data } = await http.get<StudySession[]>('/sessions', {
      params: { limit },
    })
    return data
  },
}

