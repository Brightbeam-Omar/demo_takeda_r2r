interface Props {
  values: (number | null)[]
  width?: number
  height?: number
}

/** 0–100 % over time as an inline SVG polyline. A week without completions leaves a gap. */
export function Sparkline({ values, width = 96, height = 24 }: Props) {
  const step = values.length > 1 ? width / (values.length - 1) : 0
  const segments: string[][] = [[]]
  values.forEach((value, index) => {
    if (value === null) {
      if (segments[segments.length - 1].length > 0) segments.push([])
      return
    }
    const y = height - (Math.min(100, Math.max(0, value)) / 100) * (height - 2) - 1
    segments[segments.length - 1].push(`${(index * step).toFixed(1)},${y.toFixed(1)}`)
  })
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden data-testid="sparkline">
      {segments
        .filter((points) => points.length > 0)
        .map((points, index) =>
          points.length === 1 ? (
            <circle key={index} cx={points[0].split(',')[0]} cy={points[0].split(',')[1]} r="1.5" className="fill-slate-500" />
          ) : (
            <polyline key={index} points={points.join(' ')} fill="none" strokeWidth="1.5" className="stroke-slate-500" />
          ),
        )}
    </svg>
  )
}
