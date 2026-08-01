import type { Profile, ProfileUpdatePayload } from '@/types/auth'
import { http } from './http'

export const profileService = {
  async updateCurrent(payload: ProfileUpdatePayload): Promise<Profile> {
    const { data } = await http.patch<Profile>('/profiles/me', payload)
    return data
  },
}

