/**
 * Formats elapsed_ms into m:ss.mmm monospace display.
 * Falls back to '—' for null/undefined.
 */
export function formatMs(ms) {
  if (ms == null) return '—'
  const totalSec = Math.floor(ms / 1000)
  const mins = Math.floor(totalSec / 60)
  const secs = totalSec % 60
  const milli = ms % 1000
  return `${mins}:${String(secs).padStart(2, '0')}.${String(milli).padStart(3, '0')}`
}

export default function TimingDisplay({ ms, className = '' }) {
  return (
    <span className={`font-timing tabular-nums ${className}`}>
      {formatMs(ms)}
    </span>
  )
}