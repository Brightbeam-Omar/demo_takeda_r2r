import { defineConfig } from '@playwright/test'

// Runs against the already-running stack (`make up`). `make e2e` resets the demo first (F13/F14), so every run
// starts from the demo-start state. The built frontend on 8080 is the one the demo is presented from (OQ-159); set
// FRONTEND_URL=http://localhost:5173 to run against the Vite dev server instead.
//
// Two projects (OQ-162): `run-of-show` is the presenter's path (acts 2, 3, 5, 6) and needs the untouched demo-start
// state, so it runs first; `specs` holds every other spec. `make e2e` resets between them.
const SIZE = { width: 1440, height: 900 }

export default defineConfig({
  testDir: './specs',
  timeout: 120_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: process.env.E2E_REPORT_DIR ?? '../../artifacts/e2e', open: 'never' }]],
  outputDir: '../../artifacts/e2e-results',
  use: {
    baseURL: process.env.FRONTEND_URL ?? 'http://localhost:8080',
    viewport: SIZE,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'run-of-show', testMatch: '00-run-of-show.spec.ts' },
    { name: 'specs', testIgnore: '00-run-of-show.spec.ts' },
  ],
})
