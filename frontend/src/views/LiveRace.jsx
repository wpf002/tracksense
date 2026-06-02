import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listRaces } from '../api/races'
import DataTable from '../components/ui/DataTable'

const STATUS_STYLE = {
  pending: 'border-border bg-surface text-text-muted',
  active: 'border-green-700 bg-green-950 text-green-400',
  finished: 'border-amber-700 bg-amber-950 text-accent',
}

function StatusBadge({ status }) {
  return (
    <span
      className={[
        'text-xs font-timing font-bold tracking-widest uppercase px-2 py-0.5 border',
        STATUS_STYLE[status] ?? 'border-border bg-surface text-text-muted',
      ].join(' ')}
    >
      {status ?? '—'}
    </span>
  )
}

export default function LiveRace() {
  const { data: races = [], isLoading, error } = useQuery({
    queryKey: ['races'],
    queryFn: listRaces,
    refetchInterval: 5000,
  })

  const columns = [
    {
      key: 'race_date',
      label: 'Date',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">
          {r.race_date ? new Date(r.race_date).toLocaleString() : '—'}
        </span>
      ),
    },
    {
      key: 'venue_id',
      label: 'Venue',
      render: (r) => <span className="font-timing text-xs text-accent">{r.venue_id}</span>,
    },
    {
      key: 'name',
      label: 'Race',
      render: (r) => <span className="font-medium">{r.name || `Race ${r.race_id}`}</span>,
    },
    {
      key: 'distance_m',
      label: 'Distance',
      render: (r) => (
        <span className="font-timing text-text-muted">{r.distance_m != null ? `${r.distance_m}m` : '—'}</span>
      ),
    },
    {
      key: 'surface',
      label: 'Surface',
      render: (r) => <span className="text-xs text-text-muted capitalize">{r.surface ?? '—'}</span>,
    },
    {
      key: 'status',
      label: 'Status',
      render: (r) => <StatusBadge status={r.status} />,
    },
  ]

  const rows = races.map((r) => ({ ...r, id: r.race_id }))

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">
          Race Day
        </h1>
        <Link
          to="/builder"
          className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-accent text-accent hover:bg-amber-950 transition-colors"
        >
          + New Race Card
        </Link>
      </div>

      <p className="text-xs text-text-muted font-timing tracking-wide mb-4">
        Race-day operations board. Official timing is provided by FinishLynx; results
        are ingested into TrackSense (Phase 5).
      </p>

      <div className="border border-border bg-surface">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
            Races
          </span>
        </div>
        {isLoading ? (
          <p className="px-4 py-6 text-text-muted text-xs font-timing tracking-widest text-center">
            Loading…
          </p>
        ) : error ? (
          <p className="px-4 py-6 text-red-400 text-xs font-timing text-center">Failed to load races</p>
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            emptyMessage="No races — use the Race Builder to create a race card"
          />
        )}
      </div>
    </div>
  )
}
