import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import client from '../api/client'

const TEMP_WARN_HIGH  = 38.5
const TEMP_ALERT_HIGH = 39.0
const TEMP_ALERT_LOW  = 37.0

function tempClass(t) {
  if (t == null) return ''
  if (t >= TEMP_ALERT_HIGH || t <= TEMP_ALERT_LOW) return 'text-red-400 font-bold'
  if (t >= TEMP_WARN_HIGH) return 'text-amber-400 font-bold'
  return 'text-green-400'
}

export default function MobileCheckin() {
  const [epc, setEpc] = useState('')
  const [tempInput, setTempInput] = useState('')
  const [result, setResult] = useState(null)  // { ok, horse_name?, error? }
  const [flash, setFlash] = useState(null)     // 'success' | 'error'
  const epcRef = useRef(null)

  // Auto-focus EPC input on mount
  useEffect(() => {
    epcRef.current?.focus()
  }, [])

  const checkinMutation = useMutation({
    mutationFn: ({ epc: e, temperature_c }) =>
      client.post(`/horses/${e.toUpperCase()}/checkins`, {
        scanned_by: 'Mobile Check-In',
        location: 'Paddock',
        temperature_c: temperature_c ?? null,
      }).then(r => r.data),
    onSuccess: (data) => {
      setResult({ ok: true, id: data.id })
      setFlash('success')
      setTimeout(() => {
        setFlash(null)
        setEpc('')
        setTempInput('')
        setResult(null)
        epcRef.current?.focus()
      }, 2000)
    },
    onError: (err) => {
      const detail = err.response?.data?.detail ?? 'Check-in failed'
      setResult({ ok: false, error: detail })
      setFlash('error')
      setTimeout(() => setFlash(null), 3000)
    },
  })

  function handleSubmit(e) {
    e.preventDefault()
    if (!epc.trim()) return
    const temp = tempInput ? parseFloat(tempInput) : null
    if (tempInput && isNaN(temp)) return
    checkinMutation.mutate({ epc: epc.trim(), temperature_c: temp })
  }

  const tempVal = tempInput ? parseFloat(tempInput) : null

  return (
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Header */}
      <div className="px-4 py-4 border-b border-border bg-surface">
        <h1 className="text-lg font-bold tracking-tight text-text-primary uppercase font-timing">
          Quick Check-In
        </h1>
        <p className="text-xs text-text-muted font-timing mt-0.5">Scan or enter horse EPC</p>
      </div>

      {/* Flash indicator */}
      {flash && (
        <div className={[
          'mx-4 mt-4 px-4 py-3 text-sm font-timing font-bold uppercase tracking-widest text-center transition-all',
          flash === 'success' ? 'bg-green-950 border border-green-700 text-green-400' : 'bg-red-950 border border-red-700 text-red-400',
        ].join(' ')}>
          {flash === 'success' ? '✓ CHECKED IN' : `✗ ${result?.error ?? 'ERROR'}`}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="flex-1 flex flex-col gap-4 px-4 pt-6">
        {/* EPC field — large, autofocus, receives scanner input */}
        <div>
          <label className="block text-xs font-timing uppercase tracking-widest text-text-muted mb-1">
            Horse EPC / Chip ID
          </label>
          <input
            ref={epcRef}
            type="text"
            inputMode="text"
            autoComplete="off"
            autoCapitalize="characters"
            placeholder="E2006811... or scan"
            value={epc}
            onChange={(e) => setEpc(e.target.value)}
            className="w-full bg-surface border border-border text-text-primary text-base px-4 py-3 font-timing focus:outline-none focus:border-accent min-h-[52px]"
          />
        </div>

        {/* Temperature field */}
        <div>
          <label className="block text-xs font-timing uppercase tracking-widest text-text-muted mb-1">
            Temperature (°C) — optional
          </label>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            min="30"
            max="45"
            placeholder="38.0"
            value={tempInput}
            onChange={(e) => setTempInput(e.target.value)}
            className="w-full bg-surface border border-border text-text-primary text-base px-4 py-3 font-timing focus:outline-none focus:border-accent min-h-[52px]"
          />
          {tempVal != null && !isNaN(tempVal) && (
            <p className={`text-sm font-timing mt-1 ${tempClass(tempVal)}`}>
              {tempVal >= TEMP_ALERT_HIGH
                ? `⚠ HIGH TEMP — ${tempVal.toFixed(1)}°C`
                : tempVal <= TEMP_ALERT_LOW
                ? `⚠ LOW TEMP — ${tempVal.toFixed(1)}°C`
                : tempVal >= TEMP_WARN_HIGH
                ? `⚑ Elevated — ${tempVal.toFixed(1)}°C`
                : `✓ Normal — ${tempVal.toFixed(1)}°C`}
            </p>
          )}
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={!epc.trim() || checkinMutation.isPending}
          className="w-full py-4 text-base font-semibold tracking-widest uppercase bg-accent text-bg hover:bg-amber-400 transition-colors disabled:opacity-40 min-h-[56px] mt-2"
        >
          {checkinMutation.isPending ? 'Checking in…' : 'Check In'}
        </button>

        <p className="text-center text-xs text-text-muted font-timing">
          Clears automatically after 2 seconds
        </p>
      </form>
    </div>
  )
}
