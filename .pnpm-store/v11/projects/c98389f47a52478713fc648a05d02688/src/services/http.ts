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

http.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token ?? localStorage.getItem(TOKEN_STORAGE_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export { TOKEN_STORAGE_KEY }
