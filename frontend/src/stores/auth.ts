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
  onboardingCompleted: boolean
}

const FIRST_LOGIN_INTRO_STORAGE_KEY = 'time-budget:first-login-intro-owner'

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: null,
    user: null,
    initialized: false,
    loading: false,
    showPageIntros: false,
    onboardingCompleted: true,
  }),

  getters: {
    isAuthenticated: (state): boolean => Boolean(state.token),
    requiresOnboarding: (state): boolean => Boolean(state.token) && !state.onboardingCompleted,
  },

  actions: {
    saveSession(
      token: string,
      user: Account,
      onboardingCompleted = true,
      showPageIntros = false,
    ): void {
      this.token = token
      this.user = user
      this.onboardingCompleted = onboardingCompleted
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
      this.onboardingCompleted = true
      sessionStorage.removeItem(FIRST_LOGIN_INTRO_STORAGE_KEY)
    },

    async register(payload: RegisterPayload): Promise<void> {
      this.loading = true
      try {
        const response = await authService.register(payload)
        // Registration creates the account's first authenticated session.
        // Keep the introductory page copy visible while this session lasts.
        this.saveSession(
          response.access_token,
          response.user,
          response.onboarding_completed,
          true,
        )
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
        this.saveSession(
          response.access_token,
          response.user,
          response.onboarding_completed,
          false,
        )
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
          this.onboardingCompleted = session.user.user_metadata.onboarding_completed !== false
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

    async completeOnboarding(): Promise<void> {
      this.loading = true
      try {
        await authService.completeOnboarding()
        this.onboardingCompleted = true
        if (this.user) {
          this.showPageIntros = true
          sessionStorage.setItem(FIRST_LOGIN_INTRO_STORAGE_KEY, this.user.profile.id)
        }
      } finally {
        this.loading = false
      }
    },
  },
})
