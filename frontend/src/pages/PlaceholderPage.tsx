import { Placeholder } from '../components/common/Placeholder'

interface Props {
  title: string
  note: string
  /** One paragraph on the capability the page stands for. */
  about?: string
  /** The roadmap item behind it (`T2-07`). */
  roadmap?: string
}

export function PlaceholderPage({ title, note, about, roadmap }: Props) {
  return (
    <main className="flex-1 overflow-auto pb-20" data-testid="placeholder-page">
      <Placeholder title={title} note={note} about={about} tag={note === 'Tier 2' ? ['Tier 2', roadmap].filter(Boolean).join(' · ') : undefined} />
    </main>
  )
}
