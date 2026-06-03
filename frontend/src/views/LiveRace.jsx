import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listRaces, getRaceEntries, addEntry, scratchHorse,
  ingestResults, updateRaceStatus,
} from '../api/raceday'

const STATUS_STYLE = {
  pending: 'border-border text-text-muted bg-surface',
  active:  'border-green-700 text-green-400 bg-green-950',
  finished:'border-amber-700 text-accent bg-amber-950',
}

function StatusBadge({ status }) {
  return (
    <span className={`text-[10px] font-timing font-bold uppercase tracking-wide px-2 py-0.5 border ${STATUS_STYLE[status] ?? 'border-border text-text-muted'}`}>
      {status}
    </span>
  )
}

// ── Race ops panel (expanded when a race is selected) ────────────────────────
function RaceOpsPanel({ race, onClose }) {
  const qc = useQueryClient()
  const [addChipId, setAddChipId]   = useState('')
  const [addCloth, setAddCloth]     = useState('')
  const [addJockey, setAddJockey]   = useState('')
  const [addError, setAddError]     = useState(null)
  const [resultRows, setResultRows] = useState('')
  const [resultError, setResultError] = useState(null)
  const [statusError, setStatusError] = useState(null)

  const { data: entriesData, isLoading: loadingEntries } = useQuery({
    queryKey: ['race-entries', race.race_id],
    queryFn: () => getRaceEntries(race.race_id),
  })
  const entries   = entriesData?.entries  ?? []
  const scratches = entriesData?.scratches ?? []

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['race-entries', race.race_id] })
    qc.invalidateQueries({ queryKey: ['races'] })
  }

  const addMut = useMutation({
    mutationFn: () => addEntry(race.race_id, {
      horse_chip_id: addChipId.trim(),
      saddle_cloth: addCloth.trim(),
      jockey: addJockey.trim() || null,
    }),
    onSuccess: () => { setAddError(null); setAddChipId(''); setAddCloth(''); setAddJockey(''); invalidate() },
    onError: (e) => setAddError(e.response?.data?.detail ?? 'Add failed'),
  })

  const scratchMut = useMutation({
    mutationFn: ({ chipId }) => scratchHorse(race.race_id, chipId,
      { scratch_type: 'steward', declared_by: 'Race Day Console' }),
    onSuccess: () => invalidate(),
  })

  const statusMut = useMutation({
    mutationFn: (status) => updateRaceStatus(race.race_id, status),
    onSuccess: () => { setStatusError(null); invalidate() },
    onError: (e) => setStatusError(e.response?.data?.detail ?? 'Update failed'),
  })

  const ingestMut = useMutation({
    mutationFn: () => {
      // Parse "1. CHIPID 60000ms" or "1 CHIPID 60000" or just "1 CHIPID"
      const parsed = resultRows.trim().split('\n').map((line, i) => {
        const parts = line.trim().split(/[\s,]+/)
        const pos = parseInt(parts[0]) || (i + 1)
        const chip = (parts[1] || '').replace(/\.$/, '').toUpperCase()
        const ms = parts[2] ? parseInt(parts[2]) : null
        return { finish_position: pos, horse_chip_id: chip, elapsed_ms: ms }
      }).filter(r => r.horse_chip_id)
      if (!parsed.length) throw new Error('No valid result rows')
      return ingestResults(race.race_id, parsed)
    },
    onSuccess: () => { setResultError(null); setResultRows(''); invalidate() },
    onError: (e) => setResultError(e.response?.data?.detail ?? e.message ?? 'Ingest failed'),
  })

  const field = 'bg-bg border border-border text-text-primary px-2 py-1.5 text-sm font-timing focus:outline-none focus:border-accent'

  return (
    <div className="mt-2 border border-border bg-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">
          {race.name || `Race ${race.race_id}`} — {race.venue_id} · {race.distance_m}m
        </span>
        <button onClick={onClose} className="text-text-muted hover:text-text-primary text-sm font-timing">✕ Close</button>
      </div>

      {/* Lifecycle controls */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs text-text-muted font-timing uppercase">Status:</span>
        <StatusBadge status={race.status} />
        {race.status === 'pending' && (
          <button onClick={() => statusMut.mutate('active')} disabled={statusMut.isPending}
            className="text-xs font-timing font-bold uppercase tracking-widest border border-green-700 text-green-400 hover:bg-green-950 px-3 py-0.5 disabled:opacity-40">
            → Start Race
          </button>
        )}
        {race.status === 'active' && (
          <button onClick={() => statusMut.mutate('finished')} disabled={statusMut.isPending}
            className="text-xs font-timing font-bold uppercase tracking-widest border border-amber-700 text-accent hover:bg-amber-950 px-3 py-0.5 disabled:opacity-40">
            → Finish Race
          </button>
        )}
        {statusError && <span className="text-red-400 text-xs font-timing">{statusError}</span>}
      </div>

      {/* Entries table */}
      <div className="mb-4">
        <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1">
          Entries ({entries.length}){scratches.length > 0 && ` · ${scratches.length} scratch${scratches.length !== 1 ? 'es' : ''}`}
        </p>
        {loadingEntries ? (
          <p className="text-text-muted text-xs font-timing">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="text-text-muted text-xs font-timing">No entries yet</p>
        ) : (
          <table className="w-full text-xs border-collapse mb-2">
            <thead>
              <tr className="border-b border-border">
                {['#', 'Chip ID', 'Jockey', ''].map(h => (
                  <th key={h} className="px-2 py-1 text-left text-[10px] uppercase tracking-wider text-text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.horse_chip_id} className="border-b border-border">
                  <td className="px-2 py-1 font-timing font-bold text-accent">{e.saddle_cloth}</td>
                  <td className="px-2 py-1 font-timing text-text-muted">{e.horse_chip_id}</td>
                  <td className="px-2 py-1 text-text-muted">{e.jockey || '—'}</td>
                  <td className="px-2 py-1">
                    <button
                      onClick={() => { if (confirm(`Scratch ${e.horse_chip_id}?`)) scratchMut.mutate({ chipId: e.horse_chip_id }) }}
                      disabled={scratchMut.isPending}
                      className="text-red-500 hover:text-red-400 font-timing text-[10px] uppercase">
                      Scratch
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {scratches.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {scratches.map(s => (
              <span key={s.horse_chip_id} className="text-[10px] font-timing text-red-400 border border-red-800 px-1.5 py-0.5">
                SCRATCHED: {s.horse_chip_id} ({s.scratch_type})
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Add entry */}
      {race.status !== 'finished' && (
        <div className="mb-4 border-t border-border pt-3">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-2">Add Entry</p>
          <div className="flex flex-wrap gap-2 items-end">
            <div className="flex flex-col gap-1">
              <span className="text-[10px] text-text-muted">Chip ID</span>
              <input value={addChipId} onChange={e => setAddChipId(e.target.value)}
                placeholder="985112000000001" className={`${field} w-40`} />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[10px] text-text-muted">Cloth #</span>
              <input value={addCloth} onChange={e => setAddCloth(e.target.value)}
                placeholder="1" className={`${field} w-16`} />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[10px] text-text-muted">Jockey</span>
              <input value={addJockey} onChange={e => setAddJockey(e.target.value)}
                placeholder="optional" className={`${field} w-32`} />
            </div>
            <button onClick={() => { setAddError(null); addMut.mutate() }}
              disabled={!addChipId || !addCloth || addMut.isPending}
              className="text-xs font-timing font-bold uppercase tracking-widest border border-accent text-accent hover:bg-amber-950 px-3 py-1.5 disabled:opacity-40">
              Add
            </button>
          </div>
          {addError && <p className="text-red-400 text-xs font-timing mt-1">{addError}</p>}
        </div>
      )}

      {/* Ingest results */}
      {race.status !== 'pending' && (
        <div className="border-t border-border pt-3">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1">
            Ingest Results (from FinishLynx / manual)
          </p>
          <p className="text-[10px] text-text-muted font-timing mb-2">
            One per line: <code className="text-accent">position chip_id elapsed_ms</code> e.g. <code className="text-accent">1 985112000000001 64250</code>
          </p>
          <textarea
            value={resultRows}
            onChange={e => setResultRows(e.target.value)}
            rows={4}
            placeholder={"1 985112000000001 64250\n2 985112000000002 64890\n3 985112000000003 65100"}
            className={`${field} w-full font-timing text-[11px] mb-2 resize-none`}
          />
          <button onClick={() => { setResultError(null); ingestMut.mutate() }}
            disabled={!resultRows.trim() || ingestMut.isPending}
            className="text-xs font-timing font-bold uppercase tracking-widest bg-accent text-bg hover:bg-accent-dim px-4 py-1.5 disabled:opacity-40">
            {ingestMut.isPending ? 'Saving…' : 'Record Results →'}
          </button>
          {ingestMut.isSuccess && <span className="text-green-400 text-xs font-timing ml-3">✓ Results recorded</span>}
          {resultError && <p className="text-red-400 text-xs font-timing mt-1">{resultError}</p>}
        </div>
      )}
    </div>
  )
}

// ── Main Race Day view ────────────────────────────────────────────────────────
export default function LiveRace() {
  const role = localStorage.getItem('ts_role') ?? ''
  const [selectedId, setSelectedId] = useState(null)

  const { data: races = [], isLoading, error } = useQuery({
    queryKey: ['races'],
    queryFn: listRaces,
    refetchInterval: 10000,
  })

  const activeRaces   = races.filter(r => r.status === 'active')
  const pendingRaces  = races.filter(r => r.status === 'pending')
  const finishedRaces = races.filter(r => r.status === 'finished')

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">Race Day</h1>
          <p className="text-xs text-text-muted font-timing mt-0.5">
            Operations console — click a race to manage entries, scratches, and results.
          </p>
        </div>
        {role === 'admin' && (
          <Link to="/builder"
            className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-accent text-accent hover:bg-amber-950 transition-colors">
            + Add Race
          </Link>
        )}
      </div>

      {isLoading ? (
        <p className="text-text-muted text-xs font-timing py-10 text-center tracking-widest">Loading…</p>
      ) : error ? (
        <p className="text-red-400 text-xs font-timing py-6 text-center">Failed to load races</p>
      ) : races.length === 0 ? (
        <div className="py-12 text-center">
          <p className="text-text-muted text-sm mb-2">No races scheduled.</p>
          {role === 'admin' && (
            <Link to="/builder" className="text-accent text-sm hover:underline">Create a race card →</Link>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {[
            { label: 'Active', items: activeRaces },
            { label: 'Pending', items: pendingRaces },
            { label: 'Finished', items: finishedRaces },
          ].map(({ label, items }) => items.length > 0 && (
            <div key={label}>
              <p className="text-[10px] uppercase tracking-widest text-text-muted mb-2">{label}</p>
              <div className="flex flex-col gap-2">
                {items.map(race => (
                  <div key={race.race_id} className="border border-border bg-surface">
                    <button
                      className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-surface-2 transition-colors"
                      onClick={() => setSelectedId(selectedId === race.race_id ? null : race.race_id)}
                    >
                      <div className="flex items-center gap-3 flex-wrap">
                        <StatusBadge status={race.status} />
                        <span className="font-medium text-text-primary">
                          {race.name || `Race ${race.race_id}`}
                        </span>
                        <span className="font-timing text-xs text-accent">{race.venue_id}</span>
                        <span className="font-timing text-xs text-text-muted">{race.distance_m}m</span>
                        {race.race_date && (
                          <span className="font-timing text-xs text-text-muted">
                            {new Date(race.race_date).toLocaleString()}
                          </span>
                        )}
                      </div>
                      <span className="text-text-muted text-xs font-timing ml-3">
                        {selectedId === race.race_id ? '▲' : '▼'}
                      </span>
                    </button>
                    {selectedId === race.race_id && (
                      <div className="px-4 pb-4">
                        <RaceOpsPanel
                          race={race}
                          onClose={() => setSelectedId(null)}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
