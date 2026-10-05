/** Base URL of the Dagster UI, for the run links on the Sync page (OQ-073). */
export const DAGSTER_URL: string = (import.meta.env.VITE_DAGSTER_URL as string | undefined) ?? 'http://localhost:3001'

export const dagsterRunUrl = (runId: string): string => `${DAGSTER_URL.replace(/\/$/, '')}/runs/${runId}`
