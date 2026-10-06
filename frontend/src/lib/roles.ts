/** Who may write what. The server enforces this (F09-FR-05); the UI only mirrors it to disable controls. */
export const READ_ONLY_HINT = 'Read-only role'

export const canEditNeedBy = (role: string | undefined) => role === 'planner' || role === 'admin'
export const canSetStatus = (role: string | undefined) =>
  role === 'qc_lead' || role === 'qa_release' || role === 'admin'
export const canComment = (role: string | undefined) => role !== undefined && role !== 'viewer'
/** Place/Release Hold (F18-FR-08): planner, QA release and admin. Release on COA: QA release and admin. */
export const canHold = (role: string | undefined) => role === 'planner' || role === 'qa_release' || role === 'admin'
export const canReleaseOnCoa = (role: string | undefined) => role === 'qa_release' || role === 'admin'
