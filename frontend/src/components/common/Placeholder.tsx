export function Placeholder({ title, note, about, tag }: { title: string; note: string; about?: string; tag?: string }) {
  return (
    <div className="p-6">
      <div className="rounded-card border border-dashed border-hairline bg-white p-8 text-center text-ink-2">
        <p className="text-base font-medium text-ink">
          {title}
          {tag ? (
            <span data-testid="tier-tag" className="ml-2 rounded-pill bg-accent-tint px-2 py-0.5 align-middle text-[11px] font-semibold text-accent">
              {tag}
            </span>
          ) : null}
        </p>
        {about ? (
          <p className="mx-auto mt-2 max-w-2xl text-left text-sm text-ink" data-testid="placeholder-about">
            {about}
          </p>
        ) : null}
        <p className="mt-2">{note}</p>
      </div>
    </div>
  )
}
