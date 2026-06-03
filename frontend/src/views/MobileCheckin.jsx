import { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import client from '../api/client'
import { getHorseSummary } from '../api/horses'

const TEMP_WARN_HIGH  = 38.5
const TEMP_ALERT_HIGH = 39.0
const TEMP_ALERT_LOW  = 37.0

function tempClass(t) {
  if (t == null) return ''
  if (t >= TEMP_ALERT_HIGH || t <= TEMP_ALERT_LOW) return 'text-red-400 font-bold'
  if (t >= TEMP_WARN_HIGH) return 'text-amber-400 font-bold'
  return 'text-green-400'
}

const isValidChip = (s) => /^\d{15}$/.test(s.replace(/\s/g, ''))

function Flag({ label, value, tone = 'muted' }) {
  const toneClass = { red: 'text-red-400', amber: 'text-amber-400', good: 'text-green-400', muted: 'text-text-primary' }[tone]
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
      <span className="text-xs uppercase tracking-wider text-text-muted">{label}</span>
      <span className={`text-sm font-timing ${toneClass}`}>{value}</span>
    </div>
  )
}

export default function MobileCheckin() {
  const [chipId, setChipId] = useState('')
  const [tempInput, setTempInput] = useState('')
  const [horse, setHorse] = useState(null)
  const [error, setError] = useState(null)
  const [flash, setFlash] = useState(null)
  const chipRef = useRef(null)

  useEffect(() => { chipRef.current?.focus() }, [])

  // Today's check-in summary for the landing state
  const { data: todaySummary } = useQuery({
    queryKey: ['checkins-today'],
    queryFn: () => client.get('/checkins/today-summary').then(r => r.data),
    refetchInterval: 15000,
  })

  function reset() {
    setChipId(''); setTempInput(''); setHorse(null); setError(null)
    chipRef.current?.focus()
  }

  const lookupMutation = useMutation({
    mutationFn: (id) => getHorseSummary(id.replace(/\s/g, '')),
    onSuccess: (data) => { setHorse(data); setError(null) },
    onError: (err) => {
      setHorse(null)
      setError(err.response?.status === 404 ? 'No horse found for that chip ID' : 'Lookup failed')
    },
  })

  const checkinMutation = useMutation({
    mutationFn: ({ id, temperature_c }) =>
      client.post(`/horses/${id}/checkins`, {
        scanned_by: 'Check-In Scanner',
        location: 'Paddock Gate B',
        temperature_c: temperature_c ?? null,
      }).then(r => r.data),
    onSuccess: () => {
      setFlash('success')
      setTimeout(() => { setFlash(null); reset() }, 1800)
    },
    onError: (err) => {
      setError(err.response?.data?.detail ?? 'Check-in failed')
      setFlash('error')
      setTimeout(() => setFlash(null), 2500)
    },
  })

  function handleLookup(e) {
    e.preventDefault()
    const id = chipId.replace(/\s/g, '')
    if (!isValidChip(id)) { setError('Chip ID must be 15 digits'); return }
    setError(null)
    lookupMutation.mutate(id)
  }

  function handleCheckIn() {
    const temp = tempInput ? parseFloat(tempInput) : null
    if (tempInput && isNaN(temp)) return
    checkinMutation.mutate({ id: horse.chip_id, temperature_c: temp })
  }

  const tempVal = tempInput ? parseFloat(tempInput) : null

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Header */}
      <div className="px-4 py-4 border-b border-border bg-surface">
        <h1 className="text-lg font-bold tracking-tight text-text-primary uppercase font-timing">
          Check-In
        </h1>
        <p className="text-xs text-text-muted font-timing mt-0.5">
          Scan or enter a Jockey Club LF microchip to verify identity before paddock entry
        </p>
      </div>

      {flash && (
        <div className={[
          'mx-4 mt-4 px-4 py-3 text-sm font-timing font-bold uppercase tracking-widest text-center',
          flash === 'success' ? 'bg-green-950 border border-green-700 text-green-400' : 'bg-red-950 border border-red-700 text-red-400',
        ].join(' ')}>
          {flash === 'success' ? '✓ CHECKED IN' : `✗ ${error ?? 'ERROR'}`}
        </div>
      )}

      {/* Today's progress — visible before scanning */}
      {!horse && todaySummary && (
        <div className="mx-4 mt-4 border border-border bg-surface p-3">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[10px] uppercase tracking-widest text-text-muted">Today's Check-Ins</p>
            <span className="text-xl font-timing font-bold text-accent">{todaySummary.today_count}</span>
          </div>
          {todaySummary.recent?.length > 0 && (
            <div className="flex flex-col gap-1">
              {todaySummary.recent.map((c, i) => (
                <div key={i} className="flex items-center justify-between text-xs font-timing text-text-muted border-t border-border pt-1">
                  <span className="text-text-primary">{c.horse_name ?? c.horse_chip_id}</span>
                  <div className="flex items-center gap-3">
                    {c.temperature_c != null && (
                      <span className={tempClass(c.temperature_c)}>{c.temperature_c.toFixed(1)}°C</span>
                    )}
                    <span className="text-green-400 text-[10px]">✓ VERIFIED</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step 1: chip lookup */}
      <form onSubmit={handleLookup} className="px-4 pt-5">
        <label className="block text-xs font-timing uppercase tracking-widest text-text-muted mb-1">
          Chip ID — 15 digits
        </label>
        <div className="flex gap-2">
          <input
            ref={chipRef}
            type="text"
            inputMode="numeric"
            autoComplete="off"
            placeholder="985112000000001 or scan"
            value={chipId}
            onChange={(e) => { setChipId(e.target.value); setHorse(null) }}
            className="flex-1 bg-surface border border-border text-text-primary text-base px-4 py-3 font-timing focus:outline-none focus:border-accent min-h-[52px]"
          />
          <button
            type="submit"
            disabled={!chipId.trim() || lookupMutation.isPending}
            className="px-4 text-sm font-semibold tracking-widest uppercase border border-accent text-accent hover:bg-amber-950 transition-colors disabled:opacity-40 min-h-[52px]"
          >
            {lookupMutation.isPending ? '…' : 'Look up'}
          </button>
        </div>
        {error && !flash && <p className="text-red-400 text-xs font-timing mt-2">{error}</p>}
      </form>

      {/* Step 2: identity + flags card → check in */}
      {horse && (
        <div className="px-4 pt-5">
          <div className="border border-border bg-surface p-4">
            <div className="flex items-baseline justify-between mb-1">
              <span className="text-base font-bold text-text-primary">{horse.name}</span>
              <span className="text-xs font-timing text-text-muted">{horse.chip_id}</span>
            </div>
            <p className="text-xs text-text-muted mb-3">
              {horse.breed ?? '—'} · {horse.current_trainer ?? 'no trainer'} · {horse.current_owner ?? 'no owner'}
            </p>
            <Flag label="Last Temp" value={horse.latest_temperature_c != null ? `${horse.latest_temperature_c.toFixed(1)}°C` : '—'}
              tone={horse.temperature_alert === 'red' ? 'red' : horse.temperature_alert === 'amber' ? 'amber' : horse.temperature_alert === 'normal' ? 'good' : 'muted'} />
            <Flag label="Workouts" value={horse.workout_count > 0 ? `${horse.workout_count} on record` : 'none'} />
            <Flag label="Open Test Barn" value={horse.open_test_barn ? 'YES — sample pending' : 'No'} tone={horse.open_test_barn ? 'amber' : 'muted'} />
            <Flag label="Vet Records" value={horse.vet_record_count} />
          </div>

          <div className="mt-4">
            <label className="block text-xs font-timing uppercase tracking-widest text-text-muted mb-1">
              Temperature (°C) — optional
            </label>
            <input
              type="number" inputMode="decimal" step="0.1" min="30" max="45"
              placeholder="38.0"
              value={tempInput}
              onChange={(e) => setTempInput(e.target.value)}
              className="w-full bg-surface border border-border text-text-primary text-base px-4 py-3 font-timing focus:outline-none focus:border-accent min-h-[52px]"
            />
            {tempVal != null && !isNaN(tempVal) && (
              <p className={`text-sm font-timing mt-1 ${tempClass(tempVal)}`}>
                {tempVal >= TEMP_ALERT_HIGH ? `⚠ HIGH — ${tempVal.toFixed(1)}°C`
                  : tempVal <= TEMP_ALERT_LOW ? `⚠ LOW — ${tempVal.toFixed(1)}°C`
                  : tempVal >= TEMP_WARN_HIGH ? `⚑ Elevated — ${tempVal.toFixed(1)}°C`
                  : `✓ Normal — ${tempVal.toFixed(1)}°C`}
              </p>
            )}
          </div>

          <div className="flex gap-2 mt-4">
            <button onClick={reset}
              className="px-4 py-3 text-sm uppercase tracking-widest border border-border text-text-muted hover:text-text-primary min-h-[52px]">
              Cancel
            </button>
            <button
              onClick={handleCheckIn}
              disabled={checkinMutation.isPending}
              className="flex-1 py-3 text-base font-semibold tracking-widest uppercase bg-accent text-bg hover:bg-amber-400 transition-colors disabled:opacity-40 min-h-[52px]">
              {checkinMutation.isPending ? 'Checking in…' : `✓ Check In — ${horse.name}`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
