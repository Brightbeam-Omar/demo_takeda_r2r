export function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <div className="p-6">
      <div className="rounded-card border border-dashed border-hairline bg-white p-8 text-center text-ink-2">
        <p className="text-base font-medium text-ink">{title}</p>
        <p className="mt-1">{note}</p>
      </div>
    </div>
  )
}
