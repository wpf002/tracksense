import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { listVenues } from '../api/venues'
import { createRace } from '../api/races'

const toFurlongs = (m) => (m / 201.168).toFixed(1)
const SURFACES = ['Dirt', 'Turf', 'Synthetic']

export default function RaceCardBuilder() {
  const navigate = useNavigate()
  const { data: venues = [] } = useQuery({ queryKey: ['venues'], queryFn: listVenues })

  const [venueId, setVenueId] = useState('')
  const [name, setName] = useState('')
  const [raceDate, setRaceDate] = useState(() => new Date().toISOString().slice(0, 16))
  const [distance, setDistance] = useState('1600')
  const [surface, setSurface] = useState('Dirt')
  const [conditions, setConditions] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!venueId && venues.length) {
      setVenueId(venues[0].venue_id)
      setDistance(String(Math.round(venues[0].total_distance_m)))
    }
  }, [venues]) // eslint-disable-line react-hooks/exhaustive-deps

  const createMut = useMutation({
    mutationFn: () =>
      createRace({
        venue_id: venueId,
        name: name || null,
        race_date: new Date(raceDate).toISOString(),
        distance_m: Number(distance),
        surface: surface.toLowerCase(),
        conditions: conditions || null,
      }),
    onSuccess: () => navigate('/live'),
    onError: (err) => setError(err.response?.data?.detail ?? 'Could not create race'),
  })

  const field = 'bg-bg border border-border text-text-primary px-3 py-2.5 text-sm focus:outline-none focus:border-accent'

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase mb-6">
        Race Builder
      </h1>

      <div className="flex justify-center pt-4">
        <div className="border border-border bg-surface p-8 w-full max-w-2xl">
          <h2 className="text-lg font-bold uppercase tracking-widest text-text-primary mb-1">
            New Race Card
          </h2>
          <p className="text-xs text-text-muted font-timing tracking-wide mb-6">
            Create a race-day card. Entry/scratch management and FinishLynx results
            ingestion arrive with the Phase 5 Race Day Operations module.
          </p>

          <div className="flex flex-col gap-5">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-text-muted uppercase tracking-wider">Track</span>
              <select value={venueId} onChange={(e) => setVenueId(e.target.value)} className={field}>
                {venues.map((v) => (
                  <option key={v.venue_id} value={v.venue_id}>
                    {v.name} ({v.total_distance_m}m · {toFurlongs(v.total_distance_m)}f)
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-text-muted uppercase tracking-wider">Race Name (optional)</span>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. The Spring Handicap" className={field} />
            </label>

            <div className="flex gap-4 flex-wrap">
              <label className="flex flex-col gap-1.5 flex-1 min-w-48">
                <span className="text-xs text-text-muted uppercase tracking-wider">Date &amp; Time</span>
                <input type="datetime-local" value={raceDate} onChange={(e) => setRaceDate(e.target.value)} className={`${field} font-timing`} />
              </label>
              <label className="flex flex-col gap-1.5 w-40">
                <span className="text-xs text-text-muted uppercase tracking-wider">Distance (m)</span>
                <input type="number" value={distance} onChange={(e) => setDistance(e.target.value)} className={`${field} font-timing`} />
              </label>
              <label className="flex flex-col gap-1.5 w-40">
                <span className="text-xs text-text-muted uppercase tracking-wider">Surface</span>
                <select value={surface} onChange={(e) => setSurface(e.target.value)} className={field}>
                  {SURFACES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </label>
            </div>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-text-muted uppercase tracking-wider">Conditions (optional)</span>
              <input value={conditions} onChange={(e) => setConditions(e.target.value)} placeholder="e.g. 3yo+ maiden" className={field} />
            </label>

            <button
              onClick={() => { setError(null); createMut.mutate() }}
              disabled={!venueId || !distance || createMut.isPending}
              className="mt-2 px-6 py-3 text-sm font-bold uppercase tracking-widest bg-accent text-bg hover:bg-accent-dim transition-colors disabled:opacity-40 w-full"
            >
              {createMut.isPending ? 'Creating…' : 'Create Race Card →'}
            </button>

            {error && <p className="text-red-400 text-xs font-timing">{error}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
