import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

import { localBackendPlugin } from './vite.local-backend'

export default defineConfig({
  // The dev server owns the local API lifecycle so the login page cannot be
  // left running without its backend.
  plugins: [vue(), localBackendPlugin()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // Keep one stable browser origin so auth and IndexedDB outboxes are not
    // silently split between 5173/5174 when an old dev server is still alive.
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
