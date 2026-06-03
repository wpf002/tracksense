import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listRaces, getRaceResults } from '../api/races'
import DataTable from '../components/ui/DataTable'
import TimingDisplay from '../components/ui/TimingDisplay'

const STATUS_STYLE = {
  finished: 'border-amber-800 text-accent',
  active:   'border-green-700 text-green-400',
  pending:  'border-border text-text-muted',
}

function fmtTime(ms) {
  if (!ms) return null
  const mins = Math.floor(ms / 60000)
  const secs = ((ms % 60000) / 1000).toFixed(2).padStart(5, '0')
  return mins > 0 ? `${mins}:${secs}` : `${secs}s`
}

export default function RaceResults() {
  const [raceId, setRaceId] = useState('')
  const [showPicker, setShowPicker] = useState(false)

  const { data: races = [] } = useQuery({ queryKey: ['races'], queryFn: listRaces })

  // Group races
  const today = new Date().toDateString()
  const todayRaces = races.filter(r => r.race_date && new Date(r.race_date).toDateString() === today)
  const pastRaces  = races.filter(r => r.race_date && new Date(r.race_date).toDateString() !== today)

  // Default to today's most recent finished race
  useEffect(() => {
    if (!raceId && races.length) {
      const todayFinished = races.find(r => r.status === 'finished' &&
        r.race_date && new Date(r.race_date).toDateString() === today)
      const fallback = races.find(r => r.status === 'finished') || races[0]
      setRaceId(String((todayFinished || fallback).race_id))
    }
  }, [races]) // eslint-disable-line react-hooks/exhaustive-deps

  const selectedRace = races.find(r => String(r.race_id) === raceId)

  const { data: raceData, isLoading } = useQuery({
    queryKey: ['race-results', raceId],
    queryFn: () => getRaceResults(raceId),
    enabled: !!raceId,
  })

  const results = raceData?.results ?? []
  const winnerMs = results[0]?.elapsed_ms

  const columns = [
    {
      key: 'finish_position',
      label: 'Pos',
      className: 'w-12',
      render: (row) => (
        <span className={`font-timing font-bold text-lg ${row.finish_position === 1 ? 'text-accent' : 'text-text-primary'}`}>
          {row.finish_position}
        </span>
      ),
    },
    {
      key: 'saddle_cloth',
      label: '#',
      className: 'w-10',
      render: (row) => <span className="font-timing text-text-secondary">{row.saddle_cloth ?? '—'}</span>,
    },
    {
      key: 'horse_name',
      label: 'Horse',
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-bold text-text-primary">{row.horse_name ?? '—'}</span>
          {row.jockey && <span className="text-xs text-text-secondary">{row.jockey}</span>}
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
        if (row.finish_position === 1 || !row.elapsed_ms || !winnerMs)
          return <span className="text-text-muted font-timing text-xs">—</span>
        const diff = row.elapsed_ms - winnerMs
        return <span className="font-timing text-xs text-text-secondary">+{fmtTime(diff)}</span>
      },
    },
  ]

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase mb-5">Results</h1>

      {/* Race picker — styled like the rest of the app */}
      <div className="relative mb-6">
        <button
          onClick={() => setShowPicker(v => !v)}
          className="w-full flex items-center justify-between bg-surface border border-border px-4 py-3 text-left hover:border-accent transition-colors group"
        >
          {selectedRace ? (
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`text-[10px] font-timing font-bold uppercase px-1.5 py-0.5 border ${STATUS_STYLE[selectedRace.status] ?? 'border-border text-text-muted'}`}>
                {selectedRace.status}
              </span>
              <span className="font-semibold text-text-primary">{selectedRace.name || `Race ${selectedRace.race_id}`}</span>
              <span className="font-timing text-sm text-accent">{selectedRace.venue_id}</span>
              <span className="font-timing text-sm text-text-secondary">{selectedRace.distance_m}m</span>
              {selectedRace.race_date && (
                <span className="font-timing text-xs text-text-muted">
                  {new Date(selectedRace.race_date).toLocaleDateString(undefined, {weekday:'short', month:'short', day:'numeric'})}
                </span>
              )}
            </div>
          ) : (
            <span className="text-text-muted font-timing text-sm">Select a race…</span>
          )}
          <span className="text-text-muted text-xs ml-4 group-hover:text-accent transition-colors">{showPicker ? '▲' : '▼'}</span>
        </button>

        {showPicker && (
          <div className="absolute top-full left-0 right-0 z-30 bg-surface border border-accent max-h-80 overflow-y-auto shadow-xl">
            {todayRaces.length > 0 && (
              <>
                <div className="px-4 py-1.5 bg-surface-2 border-b border-border">
                  <span className="text-[10px] uppercase tracking-widest text-accent font-semibold">Today</span>
                </div>
                {todayRaces.map(r => (
                  <button key={r.race_id}
                    onClick={() => { setRaceId(String(r.race_id)); setShowPicker(false) }}
                    className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-2 transition-colors border-b border-border/50 ${String(r.race_id) === raceId ? 'bg-amber-950/40' : ''}`}>
                    <span className={`text-[10px] font-timing font-bold uppercase px-1.5 py-0.5 border flex-shrink-0 ${STATUS_STYLE[r.status] ?? 'border-border text-text-muted'}`}>{r.status}</span>
                    <span className="font-semibold text-text-primary">{r.name || `Race ${r.race_id}`}</span>
                    <span className="font-timing text-xs text-accent">{r.venue_id}</span>
                    <span className="font-timing text-xs text-text-secondary ml-auto">{r.distance_m}m</span>
                  </button>
                ))}
              </>
            )}
            {pastRaces.length > 0 && (
              <>
                <div className="px-4 py-1.5 bg-surface-2 border-b border-border">
                  <span className="text-[10px] uppercase tracking-widest text-text-muted font-semibold">Previous</span>
                </div>
                {pastRaces.map(r => (
                  <button key={r.race_id}
                    onClick={() => { setRaceId(String(r.race_id)); setShowPicker(false) }}
                    className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-2 transition-colors border-b border-border/50 ${String(r.race_id) === raceId ? 'bg-amber-950/40' : ''}`}>
                    <span className="font-semibold text-text-primary">{r.name || `Race ${r.race_id}`}</span>
                    <span className="font-timing text-xs text-accent">{r.venue_id}</span>
                    {r.race_date && <span className="font-timing text-xs text-text-muted ml-auto">{new Date(r.race_date).toLocaleDateString()}</span>}
                  </button>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* Race context line */}
      {raceData && (
        <div className="flex gap-4 items-center mb-4 text-sm flex-wrap">
          <span className="font-bold text-text-primary">{raceData.name || `Race ${raceData.race_id}`}</span>
          <span className="font-timing text-accent">{raceData.venue_id}</span>
          <span className="font-timing text-text-secondary">{raceData.distance_m}m {raceData.surface}</span>
          {raceData.race_date && (
            <span className="font-timing text-text-secondary">
              {new Date(raceData.race_date).toLocaleDateString(undefined, {weekday:'long', month:'long', day:'numeric', year:'numeric'})}
            </span>
          )}
        </div>
      )}

      {/* Results table */}
      <div className="border border-border bg-surface">
        <div className="px-4 py-2 border-b border-border flex items-center justify-between">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
            Finish Order
          </span>
          {results.length > 0 && (
            <span className="text-xs font-timing text-text-secondary">{results.length} runners</span>
          )}
        </div>
        {isLoading ? (
          <p className="px-4 py-8 text-text-secondary text-xs font-timing text-center tracking-widest">Loading…</p>
        ) : results.length === 0 ? (
          <p className="px-4 py-8 text-text-secondary text-xs font-timing text-center">
            No results yet — race has not finished or results have not been ingested.
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
