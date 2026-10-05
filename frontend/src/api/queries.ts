import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiGet, type Schemas } from './client'
import { usePersona } from '../state/persona'

export const POLL_MS = 10_000

export type Me = Schemas['UserOut']
export type Clock = Schemas['ClockOut']
export type Reference = Schemas['ReferenceOut']
export type SyncStatus = Schemas['SyncStatusOut']
export type Overview = Schemas['OverviewOut']
export type Row = Schemas['RowOut']
export type Metrics = Schemas['MetricsOut']
export type RowDetail = Schemas['RowDetail']

/** Query keys carry the persona so a switch refetches everything (F10-FR-02). */
function useKey(...parts: unknown[]) {
  return [...parts, usePersona()]
}

export function useMe() {
  return useQuery({ queryKey: useKey('me'), queryFn: () => apiGet<Me>('/me') })
}

export function useUsers() {
  return useQuery({ queryKey: ['users'], queryFn: () => apiGet<Schemas['UserOut'][]>('/users'), retry: false })
}

export function useReference() {
  return useQuery({ queryKey: useKey('reference'), queryFn: () => apiGet<Reference>('/reference') })
}

export function useClock() {
  return useQuery({
    queryKey: useKey('clock'),
    queryFn: () => apiGet<Clock>('/clock'),
    refetchInterval: POLL_MS,
  })
}

export function useSyncStatus(intervalMs: number = POLL_MS) {
  return useQuery({
    queryKey: useKey('sync-status'),
    queryFn: () => apiGet<SyncStatus>('/sync/status'),
    refetchInterval: intervalMs,
  })
}

export function useOverview(params: URLSearchParams) {
  return useQuery({
    queryKey: useKey('overview', params.toString()),
    queryFn: () => apiGet<Overview>('/overview', params),
    refetchInterval: POLL_MS,
    placeholderData: keepPreviousData,
  })
}

/** Metrics are unfiltered, so they refetch only when the contract run changes (OQ-065). */
export function useMetrics(contractRunId: string | null | undefined) {
  return useQuery({
    queryKey: useKey('metrics', contractRunId),
    queryFn: () => apiGet<Metrics>('/metrics'),
    enabled: contractRunId !== undefined,
  })
}

/** The drawer loads one row by itself, so it works when the row is filtered out of the table (OQ-072). */
export function useRowDetail(rowKey: string | null) {
  return useQuery({
    queryKey: useKey('row', rowKey),
    queryFn: () => apiGet<RowDetail>(`/rows/${encodeURIComponent(rowKey ?? '')}`),
    enabled: rowKey !== null,
    refetchInterval: POLL_MS,
    retry: false,
  })
}
