/**
 * Compact stat display: label + value side by side.
 * Variant: 'default' | 'accent' | 'muted'
 */
export default function StatBadge({ label, value, variant = 'default' }) {
  const valueClass =
    variant === 'accent'
      ? 'text-accent font-timing font-bold'
      : variant === 'muted'
      ? 'text-text-muted font-timing'
      : 'text-text-primary font-timing'

  return (
    <div className="flex flex-col items-center px-4 py-2 bg-surface-2 border border-border min-w-[80px]">
      <span className={`text-lg font-bold tabular-nums ${valueClass}`}>
        {value ?? '—'}
      </span>
      <span className="text-xs text-text-muted uppercase tracking-widest mt-0.5">
        {label}
      </span>
    </div>
  )
}