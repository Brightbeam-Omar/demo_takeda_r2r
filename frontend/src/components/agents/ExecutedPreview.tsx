import type { EmailRecord, ProposalAction, TicketRecord } from '../../api/agents'

/** What approval produced: the ticket record and the rendered email. Nothing is sent: it says so (F12-FR-09). */
export function ExecutedPreview({ actions }: { actions: ProposalAction[] }) {
  const ticket = actions.find((a) => a.action_type === 'ticket_created')?.rendered as TicketRecord | undefined
  const email = actions.find((a) => a.action_type === 'email_queued')?.rendered as EmailRecord | undefined
  if (!ticket || !email) return null
  return (
    <div className="grid grid-cols-2 gap-4" data-testid="executed-preview">
      <section aria-label="Ticket" className="rounded-card border border-hairline bg-white p-4">
        <h3 className="mb-2 text-xs font-semibold tracking-wide text-ink-2 uppercase">Ticket {ticket.ticket_no}</h3>
        <pre className="font-sans text-[13px] whitespace-pre-wrap" data-testid="ticket-text">
          {ticket.text}
        </pre>
      </section>
      <section aria-label="Email" className="rounded-card border border-hairline bg-white p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="text-xs font-semibold tracking-wide text-ink-2 uppercase">Email</h3>
          <span data-testid="delivery" className="rounded-pill border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-800">
            {email.delivery}
          </span>
        </div>
        <dl className="mb-2 space-y-0.5 text-[13px]">
          <div className="flex gap-2">
            <dt className="w-14 shrink-0 text-ink-2">To</dt>
            <dd>{email.to}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="w-14 shrink-0 text-ink-2">Subject</dt>
            <dd className="font-medium" data-testid="email-subject">
              {email.subject}
            </dd>
          </div>
        </dl>
        <pre className="font-sans text-[13px] whitespace-pre-wrap border-t border-hairline pt-2" data-testid="email-body">
          {email.body}
        </pre>
      </section>
    </div>
  )
}
