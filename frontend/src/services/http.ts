import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

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

/**
 * The backend runs on a deliberately tiny database pool: the managed
 * session-mode pooler caps the whole project at a handful of client slots,
 * and each in-flight request holds one. A page that opened five or six
 * requests at once therefore pushed the surplus into a pool wait that
 * outlived the request timeout, and the today and partners pages rendered
 * empty charts behind a red "server error" banner.
 *
 * Requests queue here instead: at most `MAX_CONCURRENT_REQUESTS` reach the
 * network together and the rest start as soon as a slot frees up. The page
 * still issues everything it needs; it just stops asking for more parallel
 * work than the server can serve.
 */
const MAX_CONCURRENT_REQUESTS = 3
let inFlight = 0
const waiting: Array<() => void> = []

function acquireSlot(): Promise<void> {
  if (inFlight < MAX_CONCURRENT_REQUESTS) {
    inFlight += 1
    return Promise.resolve()
  }
  return new Promise((resolve) => {
    waiting.push(() => {
      inFlight += 1
      resolve()
    })
  })
}

function releaseSlot(): void {
  inFlight = Math.max(0, inFlight - 1)
  waiting.shift()?.()
}

interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  /** Attempts already spent on this request, including the first one. */
  retryAttempt?: number
  /** Set once the request has taken a concurrency slot, so it releases once. */
  slotHeld?: boolean
}

const MAX_RETRY_ATTEMPTS = 3
const RETRY_BASE_DELAY_MS = 350
// Transient conditions only: a saturated pool, a restarting backend or a
// dropped connection. Application-level rejections (4xx) are never replayed.
const RETRYABLE_STATUSES = [500, 502, 503, 504]

function isRetryable(error: AxiosError): boolean {
  const method = (error.config?.method ?? 'get').toLowerCase()
  // Only replay reads. A retried POST/PATCH could duplicate a write whose
  // response was merely lost, and the offline outbox already owns write replay.
  if (method !== 'get') return false
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') return true
  if (!error.response) return error.code === 'ERR_NETWORK'
  return RETRYABLE_STATUSES.includes(error.response.status)
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

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
  // Taken last: a rejected request interceptor never reaches the response
  // interceptor, so nothing may throw between claiming a slot and dispatch.
  const request = config as RetryableRequestConfig
  if (!request.slotHeld) {
    await acquireSlot()
    request.slotHeld = true
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    const request = response.config as RetryableRequestConfig
    if (request.slotHeld) {
      request.slotHeld = false
      releaseSlot()
    }
    return response
  },
  async (error: AxiosError) => {
    const request = error.config as RetryableRequestConfig | undefined
    if (request?.slotHeld) {
      request.slotHeld = false
      releaseSlot()
    }
    if (!request || !isRetryable(error)) throw error
    const attempt = (request.retryAttempt ?? 1) + 1
    if (attempt > MAX_RETRY_ATTEMPTS) throw error
    request.retryAttempt = attempt
    await delay(RETRY_BASE_DELAY_MS * 2 ** (attempt - 2))
    return http.request(request)
  },
)

export { TOKEN_STORAGE_KEY }
