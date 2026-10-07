import { useState } from 'react'
import { useAgents, useProposals } from '../api/agents'
import { useReference } from '../api/queries'
import { PageIntro } from '../components/admin/PageIntro'
import { AgentCard } from '../components/agents/AgentCard'
import { Inbox, type Tab } from '../components/agents/Inbox'
import { ErrorState, Skeleton } from '../components/common/States'

/** `/agents`: the agent card and the proposals inbox (F12-FR-12 a, b). */
export function Agents() {
  const [tab, setTab] = useState<Tab>('all')
  const agents = useAgents()
  const listing = useProposals(tab === 'all' ? undefined : tab)
  const reference = useReference()
  const timezone = reference.data?.site_timezone ?? 'UTC'
  return (
    <main className="flex-1 space-y-5 overflow-auto p-6 pb-20" data-testid="agents-page">
      <PageIntro subtitle="Agents gather the evidence and draft; a rule validator checks every claim; a person with the right role decides." />
      {agents.isError ? (
        <ErrorState what="the agents" error={agents.error} onRetry={() => void agents.refetch()} />
      ) : !agents.data ? (
        <Skeleton label="agents" height="h-40" />
      ) : (
        agents.data.map((agent) => <AgentCard key={agent.key} agent={agent} timezone={timezone} />)
      )}
      {listing.isError && !listing.data ? (
        <ErrorState what="the proposals" error={listing.error} onRetry={() => void listing.refetch()} />
      ) : !listing.data ? (
        <Skeleton label="proposals" height="h-40" />
      ) : (
        <Inbox listing={listing.data} tab={tab} onTab={setTab} timezone={timezone} />
      )}
    </main>
  )
}
