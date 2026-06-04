import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getTrainingRoster } from '../api/training'
import { listRaces } from '../api/races'
import DataTable from '../components/ui/DataTable'
import Icon from '../components/ui/Icon'

const OUTCOME_STYLE = {
  cleared: 'text-green-400',
  restricted: 'text-amber-400',
  scratched: 'text-red-400',
  referred: 'text-orange-400',
}

function StatusPip({ count, label, tone = 'muted' }) {
  const color = count > 0
    ? (tone === 'warn' ? 'text-amber-400' : tone === 'alert' ? 'text-red-400' : 'text-text-primary')
    : 'text-text-muted'
  return (
    <div className="flex flex-col items-center px-3 py-1.5 border-r border-border last:border-0 min-w-[60px]">
      <span className={`text-xl font-timing font-bold ${color}`}>{count}</span>
      <span className="text-[10px] uppercase tracking-widest text-text-muted leading-tight text-center">{label}</span>
    </div>
  )
}

// Chips entered in today's races (drawn from the seed narrative)
const TODAY_RUNNERS = new Set([
  "985112000000001","985112000000005","985112000000011","985112000000013",
  "985112000000015","985112000000016","985112000000024","985112000000025",
  "985112000000006","985112000000007","985112000000012","985112000000014",
  "985112000000017","985112000000018",
  "985112000000002","985112000000003","985112000000008","985112000000009","985112000000019",
])

const TODAY_RACE_NAMES = {
  "985112000000001": "The Bluegrass Stakes · Race 1 · Cloth #1 · R. Bejarano",
  "985112000000005": "The Bluegrass Stakes · Race 1 · Cloth #2 · I. Ortiz Jr.",
  "985112000000006": "The Churchill Sprint · Race 2 · Cloth #1 · J. Castellano",
  "985112000000007": "The Churchill Sprint · Race 2 · Cloth #2 · M. Smith",
  "985112000000002": "The Louisville Turf · Race 3 · Cloth #1 · H. Bowman",
  "985112000000003": "The Louisville Turf · Race 3 · Cloth #2 · T. Queally",
  "985112000000010": "The Kentucky Classic · Race 4 · Cloth #1 · C. Soumillon",
}

export default function TrainingCenter() {
  const [search, setSearch] = useState('')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['training-roster'],
    queryFn: getTrainingRoster,
    refetchInterval: 30000,
  })

  const { data: racesData } = useQuery({ queryKey: ['races'], queryFn: listRaces })
  const todayRaces = (racesData ?? []).filter(r => {
    if (!r.race_date) return false
    return new Date(r.race_date).toDateString() === new Date().toDateString()
  })

  const roster = data?.roster ?? []
  const filtered = search
    ? roster.filter((h) =>
        h.name.toLowerCase().includes(search.toLowerCase()) ||
        h.chip_id.includes(search) ||
        (h.current_trainer ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : roster

  // Summary stats
  const totalPendingHISA = roster.reduce((s, h) => s + h.pending_hisa_count, 0)
  const totalOpenTreatments = roster.reduce((s, h) => s + h.open_treatment_count, 0)
  const noRecentWorkout = roster.filter((h) => !h.last_workout_date).length
  const notCleared = roster.filter(
    (h) => h.latest_vet_check_outcome && h.latest_vet_check_outcome !== 'cleared'
  ).length

  const columns = [
    {
      key: 'name',
      label: 'Horse',
      render: (h) => (
        <Link to={`/horses/${h.chip_id}`}
          className="font-medium text-text-primary hover:text-accent transition-colors">
          {h.name}
        </Link>
      ),
    },
    {
      key: 'current_trainer',
      label: 'Trainer',
      render: (h) => <span className="text-xs text-text-muted">{h.current_trainer ?? '—'}</span>,
    },
    {
      key: 'last_workout_date',
      label: 'Last Work',
      render: (h) => (
        <span className={`font-timing text-xs ${h.last_workout_date ? 'text-text-muted' : 'text-amber-400'}`}>
          {h.last_workout_date ?? 'No workouts'}
          {h.last_workout_distance_m ? ` · ${h.last_workout_distance_m}m` : ''}
        </span>
      ),
    },
    {
      key: 'latest_vet_check_outcome',
      label: 'Vet Status',
      render: (h) => h.latest_vet_check_outcome ? (
        <span className={`text-xs font-timing uppercase ${OUTCOME_STYLE[h.latest_vet_check_outcome] ?? 'text-text-muted'}`}>
          {h.latest_vet_check_outcome}
          {h.latest_vet_check_date ? <span className="text-text-muted normal-case"> · {h.latest_vet_check_date}</span> : null}
        </span>
      ) : (
        <span className="text-xs text-text-muted font-timing">No checks</span>
      ),
    },
    {
      key: 'open_treatment_count',
      label: 'Treatments',
      render: (h) => (
        <span className={`font-timing text-xs ${h.open_treatment_count > 0 ? 'text-amber-400' : 'text-text-muted'}`}>
          {h.open_treatment_count > 0 ? `${h.open_treatment_count} active` : '—'}
        </span>
      ),
    },
    {
      key: 'pending_hisa_count',
      label: 'HISA',
      render: (h) => (
        <span className={`font-timing text-xs ${h.pending_hisa_count > 0 ? 'text-accent font-bold' : 'text-text-muted'}`}>
          {h.pending_hisa_count > 0 ? `${h.pending_hisa_count} pending` : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: '',
      render: (h) => (
        <Link to={`/horses/${h.chip_id}`}
          className="text-xs font-timing text-text-muted hover:text-accent">
          Profile →
        </Link>
      ),
    },
  ]

  return (
    <div className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">
            Training Center
          </h1>
          <p className="text-xs text-text-muted font-timing mt-0.5">
            Daily Roster — {roster.length} Horse{roster.length !== 1 ? 's' : ''} · Workouts, Vet Checks, Treatments Between Races
          </p>
        </div>
        <button
          onClick={() => refetch()}
          aria-label="Refresh roster"
          title="Refresh"
          className="text-text-muted hover:text-accent transition-colors p-1"
        >
          <Icon name="refresh" className="w-4 h-4" />
        </button>
      </div>

      {/* Running today */}
      {todayRaces.length > 0 && (() => {
        const runnersToday = roster.filter(h => TODAY_RUNNERS.has(h.chip_id))
        if (!runnersToday.length) return null
        return (
          <div className="border border-amber-800 bg-amber-950/30 p-4 mb-4">
            <p className="text-xs font-semibold uppercase tracking-widest text-accent mb-3">
              Running Today at Churchill Downs — {runnersToday.length} horses
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 auto-rows-fr">
              {runnersToday.map(h => (
                <Link key={h.chip_id} to={`/horses/${h.chip_id}`}
                  className="flex flex-col gap-1 h-full bg-surface border border-border px-3 py-2.5 hover:border-accent transition-colors">
                  <span className="font-bold text-text-primary text-sm leading-tight">{h.name}</span>
                  <span className="text-[10px] font-timing text-text-muted leading-snug">
                    {TODAY_RACE_NAMES[h.chip_id] ?? 'Churchill Downs today'}
                  </span>
                  <span className={`mt-auto text-[10px] font-timing uppercase font-bold ${
                    h.latest_vet_check_outcome
                      ? (h.latest_vet_check_outcome === 'cleared' ? 'text-green-400' : 'text-red-400')
                      : 'text-text-muted'
                  }`}>
                    Vet: {h.latest_vet_check_outcome ?? '—'}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Summary bar */}
      <div className="flex border border-border bg-surface mb-4 overflow-x-auto">
        <StatusPip count={roster.length} label="Horses" />
        <StatusPip count={noRecentWorkout} label="No Works" tone={noRecentWorkout > 0 ? 'warn' : 'muted'} />
        <StatusPip count={notCleared} label="Vet Flag" tone={notCleared > 0 ? 'warn' : 'muted'} />
        <StatusPip count={totalOpenTreatments} label="Treatments" tone={totalOpenTreatments > 0 ? 'warn' : 'muted'} />
        <StatusPip count={totalPendingHISA} label="HISA Due" tone={totalPendingHISA > 0 ? 'alert' : 'muted'} />
      </div>

      {/* Search */}
      <div className="mb-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name, chip ID, or trainer…"
          className="w-full sm:w-80 bg-surface border border-border text-text-primary text-sm px-3 py-2 focus:outline-none focus:border-accent font-timing"
        />
      </div>

      {/* Roster table */}
      <div className="border border-border bg-surface">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
            Horses {search && `— ${filtered.length} match${filtered.length !== 1 ? 'es' : ''}`}
          </span>
        </div>
        {isLoading ? (
          <p className="px-4 py-8 text-text-muted text-xs font-timing text-center tracking-widest">Loading…</p>
        ) : error ? (
          <p className="px-4 py-6 text-red-400 text-xs font-timing text-center">Failed to load roster</p>
        ) : filtered.length === 0 ? (
          <div className="px-4 py-10 text-center">
            <p className="text-text-muted text-sm mb-2">
              {search ? 'No horses match your search.' : 'No horses registered yet.'}
            </p>
            {!search && (
              <p className="text-xs text-text-muted font-timing">
                Add horses via <Link to="/horses" className="text-accent hover:underline">Horses</Link> then
                assign a trainer to see them here.
                Race entries are managed from the <Link to="/live" className="text-accent hover:underline">Race Day</Link> console.
              </p>
            )}
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={filtered.map((h) => ({ ...h, id: h.chip_id }))}
            emptyMessage=""
          />
        )}
      </div>
    </div>
  )
}
