export function Placeholder({ title, feature }: { title: string; feature: string }) {
  return (
    <div className="p-6">
      <div className="rounded-card border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
        <p className="text-base font-medium text-slate-700">{title}</p>
        <p className="mt-1">Built in {feature}.</p>
      </div>
    </div>
  )
}
