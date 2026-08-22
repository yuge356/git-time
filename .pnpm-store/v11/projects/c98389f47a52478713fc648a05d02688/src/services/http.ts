import axios from 'axios'

import { supabase } from './supabase'

const TOKEN_STORAGE_KEY = 'time-budget-access-token'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

interface CachedAccessToken {
  token: string
  expiresAtMs: number
}

const TOKEN_EXPIRY_MARGIN_MS = 30_000
let cachedToken: CachedAccessToken | null = null

supabase.auth.onAuthStateChange((event, session) => {
  if (event === 'SIGNED_OUT') {
    cachedToken = null
    return
  }
  if (event === 'TOKEN_REFRESHED' && session?.access_token && session.expires_at) {
    cachedToken = { token: session.access_token, expiresAtMs: session.expires_at * 1000 }
  }
})

http.interceptors.request.use(async (config) => {
  let token =
    cachedToken && cachedToken.expiresAtMs - TOKEN_EXPIRY_MARGIN_MS > Date.now()
      ? cachedToken.token
      : null
  if (!token) {
    const { data } = await supabase.auth.getSession()
    const accessToken = data.session?.access_token
    if (accessToken) {
      token = accessToken
      if (data.session?.expires_at) {
        cachedToken = { token: accessToken, expiresAtMs: data.session.expires_at * 1000 }
      }
    } else {
      token = localStorage.getItem(TOKEN_STORAGE_KEY)
    }
  }
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export { TOKEN_STORAGE_KEY }
