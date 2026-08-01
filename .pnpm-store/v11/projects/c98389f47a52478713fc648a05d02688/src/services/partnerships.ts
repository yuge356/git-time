import { http } from './http'
import type {
  Partnership,
  UserBlock,
  UserSearchResult,
} from '@/types/partnership'

export const partnershipService = {
  async search(query: string): Promise<UserSearchResult[]> {
    const { data } = await http.get<UserSearchResult[]>('/users/search', {
      params: { q: query },
    })
    return data
  },

  async list(): Promise<Partnership[]> {
    const { data } = await http.get<Partnership[]>('/partnerships')
    return data
  },

  async invite(addresseeId: string): Promise<Partnership> {
    const { data } = await http.post<Partnership>('/partnerships/invitations', {
      addressee_id: addresseeId,
    })
    return data
  },

  async decide(partnershipId: string, accept: boolean): Promise<Partnership> {
    const { data } = await http.patch<Partnership>(
      `/partnerships/${partnershipId}`,
      { accept },
    )
    return data
  },

  async remove(partnershipId: string): Promise<void> {
    await http.delete(`/partnerships/${partnershipId}`)
  },

  async listBlocks(): Promise<UserBlock[]> {
    const { data } = await http.get<UserBlock[]>('/blocks')
    return data
  },

  async block(userId: string): Promise<UserBlock> {
    const { data } = await http.post<UserBlock>(`/blocks/${userId}`)
    return data
  },

  async unblock(blockId: string): Promise<void> {
    await http.delete(`/blocks/${blockId}`)
  },
}
