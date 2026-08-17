import type { Session } from '@supabase/supabase-js'

import type {
  Account,
  AuthResponse,
  LoginPayload,
  RegisterPayload,
} from '@/types/auth'
import { http } from './http'
import { requireSupabaseConfiguration, supabase } from './supabase'

function isEmail(identifier: string): boolean {
  return identifier.includes('@')
}

function normalizedIdentifier(identifier: string): string {
  const normalized = identifier.trim()
  return isEmail(normalized) ? normalized.toLowerCase() : normalized.replace(/[\s-]/g, '')
}

function validatedIdentifier(identifier: string): string {
  const normalized = normalizedIdentifier(identifier)
  if (!isEmail(normalized) && !/^\+[1-9]\d{7,14}$/.test(normalized)) {
    throw new Error('手机号必须使用国际格式，例如中国大陆手机号填写为 +8613800138000。')
  }
  return normalized
}

function phonePasswordEmail(phone: string): string {
  return `phone.${phone.slice(1)}@phone.dayflow.invalid`
}

function supabaseEmail(identifier: string): string {
  return isEmail(identifier) ? identifier : phonePasswordEmail(identifier)
}

function requireSession(session: Session | null): Session {
  if (!session) {
    throw new Error('账号已创建，但 Supabase 仍要求验证。请关闭邮箱确认后重试。')
  }
  return session
}

async function accountForSession(session: Session): Promise<AuthResponse> {
  const { data: user } = await http.get<Account>('/auth/me')
  return {
    access_token: session.access_token,
    token_type: 'bearer',
    user,
    // Existing users predate onboarding. Treat a missing flag as completed so
    // the new flow never blocks an established account.
    onboarding_completed: session.user.user_metadata.onboarding_completed !== false,
  }
}

export const authService = {
  async register(payload: RegisterPayload): Promise<AuthResponse> {
    requireSupabaseConfiguration()
    const identifier = validatedIdentifier(payload.identifier)
    const { data, error } = await supabase.auth.signUp({
      email: supabaseEmail(identifier),
      password: payload.password,
      options: {
        data: {
          username: payload.username.trim().toLowerCase(),
          display_name: payload.display_name.trim(),
          identifier_type: isEmail(identifier) ? 'email' : 'phone',
          onboarding_completed: false,
        },
      },
    })
    if (error) throw error
    return accountForSession(requireSession(data.session))
  },

  async login(payload: LoginPayload): Promise<AuthResponse> {
    requireSupabaseConfiguration()
    const identifier = validatedIdentifier(payload.identifier)
    const { data, error } = await supabase.auth.signInWithPassword({
      email: supabaseEmail(identifier),
      password: payload.password,
    })
    if (error) throw error
    return accountForSession(requireSession(data.session))
  },

  async currentAccount(): Promise<Account> {
    const { data } = await http.get<Account>('/auth/me')
    return data
  },

  async currentSession(): Promise<Session | null> {
    requireSupabaseConfiguration()
    const { data, error } = await supabase.auth.getSession()
    if (error) throw error
    return data.session
  },

  async completeOnboarding(): Promise<void> {
    requireSupabaseConfiguration()
    const { error } = await supabase.auth.updateUser({
      data: {
        onboarding_completed: true,
        onboarding_completed_at: new Date().toISOString(),
      },
    })
    if (error) throw error
  },

  async logout(): Promise<void> {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  },
}
