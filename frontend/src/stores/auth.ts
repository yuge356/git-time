import { defineStore } from 'pinia'

import { authService } from '@/services/auth'
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
  showPageIntros: boolean
}

const FIRST_LOGIN_INTRO_STORAGE_KEY = 'time-budget:first-login-intro-owner'

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: null,
    user: null,
    initialized: false,
    loading: false,
    showPageIntros: false,
  }),

  getters: {
    isAuthenticated: (state): boolean => Boolean(state.token),
  },

  actions: {
    saveSession(token: string, user: Account, showPageIntros = false): void {
      this.token = token
      this.user = user
      this.showPageIntros = showPageIntros
      if (showPageIntros) {
        sessionStorage.setItem(FIRST_LOGIN_INTRO_STORAGE_KEY, user.profile.id)
      } else {
        sessionStorage.removeItem(FIRST_LOGIN_INTRO_STORAGE_KEY)
      }
    },

    clearSession(): void {
      this.token = null
      this.user = null
      this.showPageIntros = false
      sessionStorage.removeItem(FIRST_LOGIN_INTRO_STORAGE_KEY)
    },

    async register(payload: RegisterPayload): Promise<void> {
      this.loading = true
      try {
        const response = await authService.register(payload)
        // Registration creates the account's first authenticated session.
        // Keep the introductory page copy visible while this session lasts.
        this.saveSession(response.access_token, response.user, true)
      } finally {
        this.loading = false
      }
    },

    async login(payload: LoginPayload): Promise<void> {
      this.loading = true
      try {
        const response = await authService.login(payload)
        // Any explicit login happens after account creation, so the repeated
        // page introductions stay hidden.
        this.saveSession(response.access_token, response.user, false)
      } finally {
        this.loading = false
      }
    },

    async initialize(): Promise<void> {
      if (this.initialized) return
      try {
        const session = await authService.currentSession()
        if (session) {
          this.token = session.access_token
          this.user = await authService.currentAccount()
          this.showPageIntros =
            sessionStorage.getItem(FIRST_LOGIN_INTRO_STORAGE_KEY) === this.user.profile.id
        }
      } catch {
        this.clearSession()
      } finally {
        this.initialized = true
      }
    },

    async logout(): Promise<void> {
      try {
        await authService.logout()
      } finally {
        this.clearSession()
      }
    },
  },
})
