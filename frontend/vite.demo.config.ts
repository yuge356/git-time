import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Standalone visual-demo build for the gantt chart; excluded from the app build.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: 'dist-demo',
    rollupOptions: {
      input: fileURLToPath(new URL('./demo.html', import.meta.url)),
    },
  },
})
