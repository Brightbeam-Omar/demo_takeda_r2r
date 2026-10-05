/** Outline icons, 16 px, in the current text colour. Use these instead of emoji (05 v2 section 2). */
const outline = {
  'aria-hidden': true,
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

export function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg {...outline} className={className}>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
      <path d="M3.5 10h17M8 3v4M16 3v4" />
    </svg>
  )
}

export function ChatIcon({ className }: { className?: string }) {
  return (
    <svg {...outline} className={className}>
      <path d="M4 5.5h16a1 1 0 0 1 1 1v9.5a1 1 0 0 1-1 1h-8l-4.5 3.5V17H4a1 1 0 0 1-1-1V6.5a1 1 0 0 1 1-1z" />
    </svg>
  )
}
