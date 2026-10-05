import { createContext, useContext, type ReactNode } from 'react'
import { useReference } from '../api/queries'

/** Profile vocabulary (F15-FR-05). Generic defaults apply until the reference loads, and in isolated tests. */
export interface Terms {
  erp: string
  lims: string
  qms: string
  qc_lab: string
  insights_banner: string
  erp_blocked_tag: string
  planner_overrides: string
}

export const DEFAULT_TERMS: Terms = {
  erp: 'ERP',
  lims: 'LIMS',
  qms: 'QMS',
  qc_lab: 'QC Lab',
  insights_banner: 'LIMS–ERP Insights',
  erp_blocked_tag: 'ERP BLOCKED',
  planner_overrides: 'planner overrides',
}

export const TermsContext = createContext<Terms>(DEFAULT_TERMS)

/** Reads `terms` from `/api/reference` once and shares it with the whole shell. */
export function TermsProvider({ children }: { children: ReactNode }) {
  const reference = useReference()
  return (
    <TermsContext.Provider value={{ ...DEFAULT_TERMS, ...(reference.data?.terms ?? {}) }}>
      {children}
    </TermsContext.Provider>
  )
}

export function useTerms(): Terms {
  return useContext(TermsContext)
}
