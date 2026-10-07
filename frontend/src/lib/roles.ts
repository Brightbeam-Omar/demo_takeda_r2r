/** Who may write what. The server enforces this (F09-FR-05); the UI only mirrors it to disable controls. */
export const READ_ONLY_HINT = 'Read-only role'

export const canEditNeedBy = (role: string | undefined) => role === 'planner' || role === 'admin'
/** The status log (F19-FR-05): everyone except the viewer may add an entry (supersedes OQ-071). */
export const canLogStatus = (role: string | undefined) => role !== undefined && role !== 'viewer'
/** Place/Release Hold (F18-FR-08): planner, QA release and admin. Release on COA: QA release and admin. */
export const canHold = (role: string | undefined) => role === 'planner' || role === 'qa_release' || role === 'admin'
export const canReleaseOnCoa = (role: string | undefined) => role === 'qa_release' || role === 'admin'
/** Running the air-gap agent (F12-FR-08): QA release and admin. */
export const canRunAgent = (role: string | undefined) => role === 'qa_release' || role === 'admin'
/** Approving or rejecting a proposal needs the proposal's required role, or admin. */
export const canDecideProposal = (role: string | undefined, required: string) => role === required || role === 'admin'
