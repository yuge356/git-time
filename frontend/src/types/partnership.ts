export type PartnershipStatus = 'PENDING' | 'ACCEPTED' | 'DECLINED'
export type RelationshipDirection = 'INCOMING' | 'OUTGOING' | 'PARTNER'

export interface PublicProfile {
  id: string
  username: string
  display_name: string
  avatar_url: string | null
  bio: string | null
}

export interface UserSearchResult extends PublicProfile {
  partnership_id: string | null
  partnership_status: PartnershipStatus | null
  direction: RelationshipDirection | null
}

export interface Partnership {
  id: string
  status: PartnershipStatus
  direction: RelationshipDirection
  partner: PublicProfile
  created_at: string
  responded_at: string | null
}

export interface UserBlock {
  id: string
  blocked_user: PublicProfile
  created_at: string
}
