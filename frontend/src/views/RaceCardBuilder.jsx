import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { listVenues } from '../api/venues'
import { createRace } from '../api/races'

const toFurlongs = (m) => (m / 201.168).toFixed(1)
const SURFACES = ['Dirt', 'Turf', 'Synthetic']

const CONDITIONS = [
  'Allowance', 'Stakes', 'Claiming', 'Maiden Special Weight',
  'Maiden Claiming', 'Starter Allowance', 'Graded Stakes (G1)',
  'Graded Stakes (G2)', 'Graded Stakes (G3)',
]

export default function RaceCardBuilder() {
  const navigate = useNavigate()
  const { data: venues = [] } = useQuery({ queryKey: ['venues'], queryFn: listVenues })

  const [venueId, setVenueId] = useState('')
  const [name, setName]       = useState('')
  const [raceDate, setRaceDate] = useState(() => {
    const d = new Date(); d.setHours(14, 0, 0, 0)
    return d.toISOString().slice(0, 16)
  })
  const [distance, setDistance] = useState('1600')
  const [surface, setSurface]   = useState('Dirt')
  const [conditions, setConditions] = useState('')
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  useEffect(() => {
    if (!venueId && venues.length) {
      setVenueId(venues[0].venue_id)
      setDistance(String(Math.round(venues[0].total_distance_m)))
    }
  }, [venues]) // eslint-disable-line react-hooks/exhaustive-deps

  const selectedVenue = venues.find(v => v.venue_id === venueId)

  const createMut = useMutation({
    mutationFn: () => createRace({
      venue_id: venueId,
      name: name || null,
      race_date: new Date(raceDate).toISOString(),
      distance_m: Number(distance),
      surface: surface.toLowerCase(),
      conditions: conditions || null,
    }),
    onSuccess: (data) => {
      setSuccess(`Race card created — Race ${data.race_id}`)
      setTimeout(() => navigate('/live'), 1200)
    },
    onError: (err) => setError(err.response?.data?.detail ?? 'Could not create race'),
  })

  const inputCls = 'w-full bg-bg border border-border text-text-primary px-4 py-3 text-sm focus:outline-none focus:border-accent transition-colors'
  const labelCls = 'block text-[10px] uppercase tracking-widest text-text-secondary mb-1.5'

  return (
    <div className="p-6 max-w-2xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">Races</h1>
        <p className="text-sm text-text-secondary mt-1">
          Create a race card for today's meeting. Entries and results are managed from the Race Day console.
        </p>
      </div>

      {/* Form card */}
      <div className="bg-surface border border-border">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-text-primary">New Race</h2>
        </div>

        <div className="p-5 flex flex-col gap-5">
          {/* Track */}
          <div>
            <label className={labelCls}>Track</label>
            <select value={venueId} onChange={(e) => {
              setVenueId(e.target.value)
              const v = venues.find(x => x.venue_id === e.target.value)
              if (v) setDistance(String(Math.round(v.total_distance_m)))
            }} className={inputCls}>
              {venues.map(v => (
                <option key={v.venue_id} value={v.venue_id}>
                  {v.name}
                </option>
              ))}
            </select>
            {selectedVenue && (
              <p className="mt-1 text-xs text-text-muted font-timing">
                {selectedVenue.venue_id} · {selectedVenue.total_distance_m}m track · {toFurlongs(selectedVenue.total_distance_m)} furlongs
              </p>
            )}
          </div>

          {/* Race name */}
          <div>
            <label className={labelCls}>Race Name <span className="text-text-muted normal-case">(optional)</span></label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. The Kentucky Classic"
              className={inputCls}
            />
          </div>

          {/* Date / Distance / Surface row */}
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-3 sm:col-span-1">
              <label className={labelCls}>Post Time</label>
              <input type="datetime-local" value={raceDate}
                onChange={(e) => setRaceDate(e.target.value)}
                className={`${inputCls} font-timing`} />
            </div>
            <div>
              <label className={labelCls}>Distance (m)</label>
              <input type="number" value={distance}
                onChange={(e) => setDistance(e.target.value)}
                className={`${inputCls} font-timing`} />
              {distance && <p className="mt-1 text-xs text-text-muted font-timing">{toFurlongs(Number(distance))} furlongs</p>}
            </div>
            <div>
              <label className={labelCls}>Surface</label>
              <select value={surface} onChange={(e) => setSurface(e.target.value)} className={inputCls}>
                {SURFACES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* Conditions */}
          <div>
            <label className={labelCls}>Conditions <span className="text-text-muted normal-case">(optional)</span></label>
            <select value={conditions} onChange={(e) => setConditions(e.target.value)} className={inputCls}>
              <option value="">— Select —</option>
              {CONDITIONS.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {error && (
            <p className="text-red-400 text-xs font-timing">{error}</p>
          )}
          {success && (
            <p className="text-green-400 text-xs font-timing">✓ {success} — redirecting to Race Day…</p>
          )}

          {/* Submit */}
          <div className="pt-1">
            <button
              onClick={() => { setError(null); setSuccess(null); createMut.mutate() }}
              disabled={!venueId || !distance || createMut.isPending || !!success}
              className="w-full py-3.5 text-sm font-bold uppercase tracking-widest bg-accent text-bg hover:bg-accent-dim transition-colors disabled:opacity-40"
            >
              {createMut.isPending ? 'Creating…' : 'Create Race Card →'}
            </button>
            <p className="text-center text-xs text-text-muted mt-2 font-timing">
              After creating, open Race Day to add entries and manage the card.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
