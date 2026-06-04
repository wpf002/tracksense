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

  // Default to the latest race (most recent finished race, else most recent overall)
  useEffect(() => {
    if (!raceId && races.length) {
      const byLatest = (a, b) => {
        const da = a.race_date ? new Date(a.race_date).getTime() : 0
        const db = b.race_date ? new Date(b.race_date).getTime() : 0
        return db !== da ? db - da : (b.race_id ?? 0) - (a.race_id ?? 0)
      }
      const finished = races.filter(r => r.status === 'finished').sort(byLatest)
      const latest = finished[0] ?? [...races].sort(byLatest)[0]
      setRaceId(String(latest.race_id))
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
        <label className="block text-[10px] uppercase tracking-widest text-text-secondary mb-1.5">Viewing race</label>
        <button
          onClick={() => setShowPicker(v => !v)}
          className={`w-full flex items-center justify-between bg-surface border px-4 py-3 text-left transition-colors group ${showPicker ? 'border-accent' : 'border-border hover:border-accent/60'}`}
        >
          {selectedRace ? (
            <div className="flex items-center gap-3 flex-wrap min-w-0">
              <span className={`text-[10px] font-timing font-bold uppercase px-1.5 py-0.5 border ${STATUS_STYLE[selectedRace.status] ?? 'border-border text-text-muted'}`}>
                {selectedRace.status}
              </span>
              <span className="font-semibold text-text-primary truncate">{selectedRace.name || `Race ${selectedRace.race_id}`}</span>
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
          <svg
            className={`w-4 h-4 ml-4 flex-shrink-0 text-text-muted group-hover:text-accent transition-all duration-200 ${showPicker ? 'rotate-180 text-accent' : ''}`}
            viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"
          >
            <path d="M5 7.5l5 5 5-5" />
          </svg>
        </button>

        {showPicker && (
          <>
            <div className="fixed inset-0 z-20" onClick={() => setShowPicker(false)} />
            <div className="absolute top-full left-0 right-0 mt-1 z-30 bg-surface border border-accent max-h-80 overflow-y-auto shadow-2xl">
              {todayRaces.length > 0 && (
                <>
                  <div className="sticky top-0 px-4 py-1.5 bg-surface-2 border-b border-border z-10">
                    <span className="text-[10px] uppercase tracking-widest text-accent font-semibold">Today</span>
                  </div>
                  {todayRaces.map(r => {
                    const isSel = String(r.race_id) === raceId
                    return (
                      <button key={r.race_id}
                        onClick={() => { setRaceId(String(r.race_id)); setShowPicker(false) }}
                        className={`w-full flex items-center gap-3 pl-4 pr-4 py-3 text-left transition-colors border-b border-border/50 border-l-2 ${isSel ? 'bg-amber-950/40 border-l-accent' : 'border-l-transparent hover:bg-surface-2'}`}>
                        <span className={`text-[10px] font-timing font-bold uppercase px-1.5 py-0.5 border flex-shrink-0 ${STATUS_STYLE[r.status] ?? 'border-border text-text-muted'}`}>{r.status}</span>
                        <span className="font-semibold text-text-primary truncate">{r.name || `Race ${r.race_id}`}</span>
                        <span className="font-timing text-xs text-accent flex-shrink-0">{r.venue_id}</span>
                        <span className="font-timing text-xs text-text-secondary ml-auto flex-shrink-0">{r.distance_m}m</span>
                      </button>
                    )
                  })}
                </>
              )}
              {pastRaces.length > 0 && (
                <>
                  <div className="sticky top-0 px-4 py-1.5 bg-surface-2 border-b border-border z-10">
                    <span className="text-[10px] uppercase tracking-widest text-text-muted font-semibold">Previous</span>
                  </div>
                  {pastRaces.map(r => {
                    const isSel = String(r.race_id) === raceId
                    return (
                      <button key={r.race_id}
                        onClick={() => { setRaceId(String(r.race_id)); setShowPicker(false) }}
                        className={`w-full flex items-center gap-3 pl-4 pr-4 py-3 text-left transition-colors border-b border-border/50 border-l-2 ${isSel ? 'bg-amber-950/40 border-l-accent' : 'border-l-transparent hover:bg-surface-2'}`}>
                        <span className="font-semibold text-text-primary truncate">{r.name || `Race ${r.race_id}`}</span>
                        <span className="font-timing text-xs text-accent flex-shrink-0">{r.venue_id}</span>
                        {r.race_date && <span className="font-timing text-xs text-text-muted ml-auto flex-shrink-0">{new Date(r.race_date).toLocaleDateString()}</span>}
                      </button>
                    )
                  })}
                </>
              )}
            </div>
          </>
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
