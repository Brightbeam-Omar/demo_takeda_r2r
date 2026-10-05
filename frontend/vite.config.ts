/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server proxies the API like nginx does in the production image (docker/frontend).
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'
const agentsTarget = process.env.AGENTS_PROXY_TARGET ?? 'http://localhost:8200'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': apiTarget,
      '/agents-api': { target: agentsTarget, rewrite: (path) => path.replace(/^\/agents-api/, '') },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    passWithNoTests: false,
    exclude: ['node_modules', 'dist'],
  },
})
