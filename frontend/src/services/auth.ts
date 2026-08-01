import type {
  Account,
  AuthResponse,
  LoginPayload,
  RegisterPayload,
} from '@/types/auth'
import { http } from './http'

export const authService = {
  async register(payload: RegisterPayload): Promise<AuthResponse> {
    const { data } = await http.post<AuthResponse>('/auth/register', payload)
    return data
  },

  async login(payload: LoginPayload): Promise<AuthResponse> {
    const { data } = await http.post<AuthResponse>('/auth/login', payload)
    return data
  },

  async currentAccount(): Promise<Account> {
    const { data } = await http.get<Account>('/auth/me')
    return data
  },
}

