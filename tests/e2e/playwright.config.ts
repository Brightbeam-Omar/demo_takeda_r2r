import { defineConfig } from '@playwright/test'

// Runs against the already-running stack (`make up`, then `make seed`). F13/F14 add the demo reset in front.
export default defineConfig({
  testDir: './specs',
  timeout: 120_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.FRONTEND_URL ?? 'http://localhost:5173',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
  },
})
