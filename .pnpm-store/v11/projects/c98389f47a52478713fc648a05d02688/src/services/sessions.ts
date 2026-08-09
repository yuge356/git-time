import type { SessionSnapshot, StudySession } from '@/types/session'
import { http, TOKEN_STORAGE_KEY } from './http'

export const sessionService = {
  async upsert(sessionId: string, snapshot: SessionSnapshot): Promise<StudySession> {
    const { data } = await http.put<StudySession>(`/sessions/${sessionId}`, snapshot)
    return data
  },

  pauseOnPageExit(sessionId: string, snapshot: SessionSnapshot): void {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY)
    if (!token) return
    const baseUrl = String(http.defaults.baseURL ?? '/api/v1').replace(/\/$/, '')
    void fetch(`${baseUrl}/sessions/${sessionId}`, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(snapshot),
      keepalive: true,
    }).catch(() => {
      // The synchronous local exit marker is replayed on the next visit.
    })
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
