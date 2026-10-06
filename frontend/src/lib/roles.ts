/** Who may write what. The server enforces this (F09-FR-05); the UI only mirrors it to disable controls. */
export const READ_ONLY_HINT = 'Read-only role'

export const canEditNeedBy = (role: string | undefined) => role === 'planner' || role === 'admin'
/** The status log (F19-FR-05): everyone except the viewer may add an entry (supersedes OQ-071). */
export const canLogStatus = (role: string | undefined) => role !== undefined && role !== 'viewer'
export const canSetStatus = canLogStatus
export const canComment = canLogStatus
/** Place/Release Hold (F18-FR-08): planner, QA release and admin. Release on COA: QA release and admin. */
export const canHold = (role: string | undefined) => role === 'planner' || role === 'qa_release' || role === 'admin'
export const canReleaseOnCoa = (role: string | undefined) => role === 'qa_release' || role === 'admin'
