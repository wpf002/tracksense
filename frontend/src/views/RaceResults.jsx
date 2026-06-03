import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listRaces, getRaceResults } from '../api/races'
import DataTable from '../components/ui/DataTable'
import TimingDisplay from '../components/ui/TimingDisplay'

function fmtTime(ms) {
  if (!ms) return '—'
  const mins = Math.floor(ms / 60000)
  const secs = ((ms % 60000) / 1000).toFixed(2).padStart(5, '0')
  return mins > 0 ? `${mins}:${secs}` : `${secs}s`
}

export default function RaceResults() {
  const [raceId, setRaceId] = useState('')

  const { data: races = [] } = useQuery({ queryKey: ['races'], queryFn: listRaces })

  // Default to most recent finished race
  useEffect(() => {
    if (!raceId && races.length) {
      const finished = races.find(r => r.status === 'finished') || races[0]
      setRaceId(String(finished.race_id))
    }
  }, [races]) // eslint-disable-line react-hooks/exhaustive-deps

  const { data: raceData, isLoading } = useQuery({
    queryKey: ['race-results', raceId],
    queryFn: () => getRaceResults(raceId),
    enabled: !!raceId,
  })

  const results = raceData?.results ?? []
  const winner = results[0]
  const winnerMs = winner?.elapsed_ms

  const columns = [
    {
      key: 'finish_position',
      label: 'Pos',
      className: 'w-12',
      render: (row) => (
        <span className={`font-timing font-bold text-base ${row.finish_position === 1 ? 'text-accent' : 'text-text-primary'}`}>
          {row.finish_position}
        </span>
      ),
    },
    {
      key: 'saddle_cloth',
      label: '#',
      className: 'w-12',
      render: (row) => <span className="font-timing font-bold text-text-muted">{row.saddle_cloth ?? '—'}</span>,
    },
    {
      key: 'horse_name',
      label: 'Horse',
      render: (row) => (
        <div>
          <span className="font-medium text-text-primary">{row.horse_name ?? '—'}</span>
          {row.jockey && <span className="text-xs text-text-muted ml-2">({row.jockey})</span>}
        </div>
      ),
    },
    {
      key: 'elapsed_ms',
      label: 'Time',
      render: (row) => <TimingDisplay ms={row.elapsed_ms} />,
    },
    {
      key: 'margin',
      label: 'Margin',
      render: (row) => {
        if (row.finish_position === 1 || !row.elapsed_ms || !winnerMs) return <span className="text-text-muted font-timing text-xs">—</span>
        const diff = row.elapsed_ms - winnerMs
        return <span className="font-timing text-xs text-text-muted">+{fmtTime(diff)}</span>
      },
    },
  ]

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">Results</h1>
        <select
          value={raceId}
          onChange={(e) => setRaceId(e.target.value)}
          className="bg-surface border border-border text-text-primary text-sm px-2 py-1.5 focus:outline-none focus:border-accent max-w-sm font-timing"
        >
          {races.map((r) => (
            <option key={r.race_id} value={r.race_id}>
              {r.venue_id} · {r.name || `Race ${r.race_id}`} · {r.race_date ? new Date(r.race_date).toLocaleDateString() : '—'}
            </option>
          ))}
        </select>
      </div>

      {raceData && (
        <div className="flex gap-3 mb-4 text-xs font-timing text-text-muted flex-wrap">
          <span className="text-accent">{raceData.venue_id}</span>
          <span>{raceData.distance_m}m {raceData.surface}</span>
          {raceData.race_date && <span>{new Date(raceData.race_date).toLocaleDateString(undefined, { weekday:'short', month:'short', day:'numeric', year:'numeric' })}</span>}
          {raceData.name && <span className="text-text-primary">{raceData.name}</span>}
        </div>
      )}

      <div className="border border-border bg-surface">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
            Finish Order {results.length > 0 && `— ${results.length} runners`}
          </span>
        </div>
        {isLoading ? (
          <p className="px-4 py-6 text-text-muted text-xs font-timing text-center tracking-widest">Loading…</p>
        ) : results.length === 0 ? (
          <p className="px-4 py-6 text-text-muted text-xs font-timing text-center">
            No results recorded for this race yet.
            {' '}Use the Race Day console to ingest results.
          </p>
        ) : (
          <DataTable
            columns={columns}
            rows={results.map((r) => ({ ...r, id: r.finish_position }))}
            emptyMessage=""
          />
        )}
      </div>
    </div>
  )
}
