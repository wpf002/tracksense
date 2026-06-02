import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listRaces, getRace } from '../api/races'
import DataTable from '../components/ui/DataTable'
import TimingDisplay from '../components/ui/TimingDisplay'

export default function RaceResults() {
  const [raceId, setRaceId] = useState('')

  const { data: races = [] } = useQuery({ queryKey: ['races'], queryFn: listRaces })

  // Default to the most recent race once the list loads
  useEffect(() => {
    if (!raceId && races.length) setRaceId(String(races[0].race_id))
  }, [races]) // eslint-disable-line react-hooks/exhaustive-deps

  const { data: race, isLoading } = useQuery({
    queryKey: ['race', raceId],
    queryFn: () => getRace(raceId),
    enabled: !!raceId,
  })

  // saddle cloth lookup from entries
  const clothByEpc = {}
  for (const e of race?.entries ?? []) clothByEpc[e.horse_epc] = e.saddle_cloth
  const results = [...(race?.results ?? [])].sort((a, b) => a.finish_position - b.finish_position)

  const columns = [
    {
      key: 'finish_position',
      label: 'Pos',
      className: 'w-12',
      render: (row) => <span className="font-timing font-bold text-accent text-base">{row.finish_position}</span>,
    },
    {
      key: 'saddle_cloth',
      label: '#',
      className: 'w-12',
      render: (row) => <span className="font-timing font-bold">{clothByEpc[row.horse_epc] ?? '—'}</span>,
    },
    {
      key: 'horse_epc',
      label: 'Horse (chip)',
      render: (row) => <span className="font-timing text-xs text-text-muted">{row.horse_epc}</span>,
    },
    {
      key: 'elapsed_ms',
      label: 'Time',
      render: (row) => <TimingDisplay ms={row.elapsed_ms} />,
    },
  ]

  const rows = results.map((r) => ({ ...r, id: r.finish_position }))

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">
          Race Results
        </h1>
        <select
          value={raceId}
          onChange={(e) => setRaceId(e.target.value)}
          className="bg-surface border border-border text-text-primary text-sm px-2 py-1.5 focus:outline-none focus:border-accent max-w-xs"
        >
          {races.map((r) => (
            <option key={r.race_id} value={r.race_id}>
              {r.venue_id} · {r.name || `Race ${r.race_id}`} · {r.status}
            </option>
          ))}
        </select>
      </div>

      <div className="border border-border bg-surface">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
            Finish Order{race?.name ? ` — ${race.name}` : ''}
          </span>
        </div>
        {isLoading ? (
          <p className="px-4 py-6 text-text-muted text-xs font-timing tracking-widest text-center">Loading…</p>
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            emptyMessage="No results recorded for this race"
          />
        )}
      </div>
    </div>
  )
}
