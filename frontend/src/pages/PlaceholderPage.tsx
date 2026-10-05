import { Placeholder } from '../components/common/Placeholder'

export function PlaceholderPage({ title, note }: { title: string; note: string }) {
  return (
    <main className="flex-1 overflow-auto" data-testid="placeholder-page">
      <Placeholder title={title} note={note} />
    </main>
  )
}
