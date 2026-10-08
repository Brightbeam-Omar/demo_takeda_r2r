import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiHeaders } from './client'
import { usePersona } from '../state/persona'

/** The agents service (F12). The proxy strips `/agents-api`; it is a separate service, so its types live here. */
const BASE = '/agents-api'
export const AGENTS_POLL_MS = 5_000

export type ProposalStatus = 'pending_approval' | 'rejected_by_validator' | 'approved' | 'rejected' | 'executed'
export const STATUSES: ProposalStatus[] = ['pending_approval', 'rejected_by_validator', 'executed', 'rejected', 'approved']

export interface AgentCardData {
  key: string
  name: string
  purpose: string
  provider: string
  model_id: string
  prompt_version: string
  tools: string[]
  can_run: boolean
  last_run_at: string | null
  proposals_total: number
}

export interface ProposalSummary {
  id: number
  agent_key: string
  kind: string
  row_key: string | null
  batch_no: string | null
  status: ProposalStatus
  required_role: string
  created_at: string
  decided_by: string | null
  decided_at: string | null
  decision_reason: string | null
  trace_id: string | null
  title: string | null
  priority: 'high' | 'normal' | null
  recommended_action: string | null
  hours_in_gap: number | null
  error: string | null
}

export interface ProposalListing {
  counts: Record<ProposalStatus, number>
  rows: ProposalSummary[]
}

export interface EvidenceItem {
  system: 'ERP' | 'LIMS' | 'QMS'
  ref: string
  field: string
  value: string
}

export interface ValidatorRule {
  id: string
  name: string
  passed: boolean
  message: string
}

export interface Validator {
  passed: boolean
  headline: string | null
  rules: ValidatorRule[]
  evidence: { index: number; verified: boolean; message: string }[]
  checked_at: string
}

export interface TicketRecord {
  ticket_no: string
  title: string
  priority: string
  batch_no: string
  recommended_action: string
  assigned_role: string
  text: string
  created_by: string
}

export interface EmailRecord {
  to: string
  subject: string
  body: string
  delivery: string
}

export interface ProposalAction {
  id: number
  action_type: 'ticket_created' | 'email_queued'
  rendered: TicketRecord & EmailRecord
  executed_at: string
}

export interface Ticket {
  row_key: string
  title: string
  summary: string
  evidence: EvidenceItem[]
  hours_in_gap: number
  open_deviations: string[]
  recommended_action: string
  priority: 'high' | 'normal'
  recipient_role: string
}

export interface ProposalDetailData extends ProposalSummary {
  payload: (Ticket & { error?: string; run_status?: string }) | null
  evidence: EvidenceItem[]
  validator: Validator | null
  actions: ProposalAction[]
}

export interface TraceStep {
  seq: number
  step_type: 'input' | 'tool_call' | 'tool_result' | 'model_request' | 'model_response' | 'validation' | 'decision' | 'action'
  payload: Record<string, unknown> | null
  tokens_in: number | null
  tokens_out: number | null
  latency_ms: number | null
  at: string
}

export interface TraceData {
  trace_id: string
  proposal_id: number | null
  row_key: string | null
  provider: string | null
  model_id: string | null
  replayed: boolean
  steps: TraceStep[]
  totals: { tokens_in: number; tokens_out: number; latency_ms: number; cost_usd: number; model_calls: number }
}

export interface RunResult {
  row_key: string
  outcome: string
  proposal_id: number | null
  status: ProposalStatus | null
  trace_id: string | null
  message: string
  replay_miss: { key: string; hint: string } | null
}

export interface RunOut {
  created: RunResult[]
  skipped: RunResult[]
  errors: RunResult[]
}

async function failure(response: Response): Promise<ApiError> {
  let message = response.statusText
  let raw: unknown
  try {
    raw = ((await response.json()) as { detail?: unknown }).detail
    if (typeof raw === 'string') message = raw
    else if (raw && typeof raw === 'object' && typeof (raw as { message?: unknown }).message === 'string') message = (raw as { message: string }).message
  } catch {
    // keep the status text
  }
  return new ApiError(response.status, message || `HTTP ${response.status}`, raw)
}

async function agentsGet<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { headers: apiHeaders() })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

async function agentsPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...apiHeaders() },
    body: JSON.stringify(body ?? {}),
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

const useKey = (...parts: unknown[]) => ['agents-api', ...parts, usePersona()]

export function useAgents() {
  return useQuery({ queryKey: useKey('agents'), queryFn: () => agentsGet<AgentCardData[]>('/agents'), refetchInterval: AGENTS_POLL_MS })
}

export function useProposals(status?: ProposalStatus) {
  return useQuery({
    queryKey: useKey('proposals', status ?? 'all'),
    queryFn: () => agentsGet<ProposalListing>(`/proposals${status ? `?status=${status}` : ''}`),
    refetchInterval: AGENTS_POLL_MS,
  })
}

export function useProposal(id: number) {
  return useQuery({ queryKey: useKey('proposal', id), queryFn: () => agentsGet<ProposalDetailData>(`/proposals/${id}`), refetchInterval: AGENTS_POLL_MS })
}

export function useTrace(traceId: string) {
  return useQuery({ queryKey: useKey('trace', traceId), queryFn: () => agentsGet<TraceData>(`/traces/${encodeURIComponent(traceId)}`), enabled: traceId !== '' })
}

/** A run, an approval or a rejection changes proposals and what the Insights window and the drawer show. */
function useRefreshAfter() {
  const client = useQueryClient()
  return () => {
    void client.invalidateQueries({ queryKey: ['agents-api'] })
    void client.invalidateQueries()
  }
}

export function useRunAgent() {
  const refresh = useRefreshAfter()
  return useMutation({
    mutationFn: (rowKey?: string) => agentsPost<RunOut>('/agents/air_gap/run', rowKey ? { row_key: rowKey } : {}),
    onSettled: refresh,
  })
}

export function useApprove(id: number) {
  const refresh = useRefreshAfter()
  return useMutation({ mutationFn: () => agentsPost<ProposalDetailData>(`/proposals/${id}/approve`), onSettled: refresh })
}

export function useReject(id: number) {
  const refresh = useRefreshAfter()
  return useMutation({
    mutationFn: (reason: string) => agentsPost<ProposalDetailData>(`/proposals/${id}/reject`, { reason }),
    onSettled: refresh,
  })
}

/** The words for a run that failed: a replay miss names the key and the way out. */
export function runErrorText(error: unknown): { message: string; hint?: string; key?: string } {
  if (error instanceof ApiError) {
    const detail = error.detail as { replay_miss?: { key: string; hint: string } | null } | undefined
    const miss = detail?.replay_miss
    if (miss) return { message: 'No recording for this situation.', hint: miss.hint, key: miss.key }
    return { message: error.message }
  }
  return { message: error instanceof Error ? error.message : 'The run failed.' }
}
