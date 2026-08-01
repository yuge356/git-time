import { defineStore } from 'pinia'

import { authService } from '@/services/auth'
import { TOKEN_STORAGE_KEY } from '@/services/http'
import type {
  Account,
  LoginPayload,
  RegisterPayload,
} from '@/types/auth'

interface AuthState {
  token: string | null
  user: Account | null
  initialized: boolean
  loading: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem(TOKEN_STORAGE_KEY),
    user: null,
    initialized: false,
    loading: false,
  }),

  getters: {
    isAuthenticated: (state): boolean => Boolean(state.token),
  },

  actions: {
    saveSession(token: string, user: Account): void {
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_STORAGE_KEY, token)
    },

    clearSession(): void {
      this.token = null
      this.user = null
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    },

    async register(payload: RegisterPayload): Promise<void> {
      this.loading = true
      try {
        const response = await authService.register(payload)
        this.saveSession(response.access_token, response.user)
      } finally {
        this.loading = false
      }
    },

    async login(payload: LoginPayload): Promise<void> {
      this.loading = true
      try {
        const response = await authService.login(payload)
        this.saveSession(response.access_token, response.user)
      } finally {
        this.loading = false
      }
    },

    async initialize(): Promise<void> {
      if (this.initialized) return
      try {
        if (this.token) {
          this.user = await authService.currentAccount()
        }
      } catch {
        this.clearSession()
      } finally {
        this.initialized = true
      }
    },

    logout(): void {
      this.clearSession()
    },
  },
})

