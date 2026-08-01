export interface Profile {
  id: string
  username: string
  display_name: string
  avatar_url: string | null
  bio: string | null
  timezone: string
  is_searchable: boolean
  created_at: string
  updated_at: string
}

export interface Account {
  email: string
  profile: Profile
}

export interface AuthResponse {
  access_token: string
  token_type: 'bearer'
  user: Account
}

export interface RegisterPayload {
  email: string
  username: string
  display_name: string
  password: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface ProfileUpdatePayload {
  username?: string
  display_name?: string
  avatar_url?: string | null
  bio?: string | null
  timezone?: string
  is_searchable?: boolean
}

