import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import {
  listHorses, getHorse, getHorseCareer, getHorseForm,
  getHorseSectionals, getHorseVet, compareHorses,
} from '../api/horses'
import DataTable from '../components/ui/DataTable'
import TimingDisplay from '../components/ui/TimingDisplay'
import StatBadge from '../components/ui/StatBadge'

const ACCENT = '#f59e0b'

// ──────────────────────────────────────────────
// Horse List / Search
// ──────────────────────────────────────────────
function HorseList() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const { data: horses = [], isLoading } = useQuery({
    queryKey: ['horses'],
    queryFn: listHorses,
  })

  const filtered = horses.filter(
    (h) =>
      h.name?.toLowerCase().includes(search.toLowerCase()) ||
      h.epc?.toLowerCase().includes(search.toLowerCase())
  )

  const columns = [
    {
      key: 'epc',
      label: 'EPC',
      render: (row) => (
        <span className="font-timing text-text-muted text-xs">{row.epc}</span>
      ),
    },
    {
      key: 'name',
      label: 'Name',
      render: (row) => <span className="font-medium">{row.name}</span>,
    },
    {
      key: 'breed',
      label: 'Breed',
      render: (row) => (
        <span className="text-text-muted">{row.breed ?? '—'}</span>
      ),
    },
  ]

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase mb-6">
        Horse Registry
      </h1>

      <input
        type="text"
        placeholder="Search by name or EPC..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-md bg-surface border border-border text-text-primary px-3 py-2 text-sm font-timing focus:outline-none focus:border-accent mb-6"
      />

      {isLoading ? (
        <p className="text-text-muted text-xs font-timing tracking-widest">Loading...</p>
      ) : (
        <div className="border border-border bg-surface">
          <DataTable
            columns={columns}
            rows={filtered.map((h) => ({ ...h, id: h.epc }))}
            onRowClick={(row) => navigate(`/horses/${row.epc}`)}
            emptyMessage="No horses found"
          />
        </div>
      )}
    </div>
  )
}

// ──────────────────────────────────────────────
// Head-to-Head Panel
// ──────────────────────────────────────────────
function HeadToHead({ epc1 }) {
  const [epc2Input, setEpc2Input] = useState('')
  const [epc2, setEpc2] = useState(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['h2h', epc1, epc2],
    queryFn: () => compareHorses(epc1, epc2),
    enabled: !!epc2,
  })

  const meetingColumns = [
    {
      key: 'race_date',
      label: 'Date',
      render: (row) => (
        <span className="font-timing text-xs text-text-muted">
          {row.race_date ? new Date(row.race_date).toLocaleDateString() : '—'}
        </span>
      ),
    },
    {
      key: 'epc1_position',
      label: 'This Horse',
      render: (row) => (
        <span className={`font-timing font-bold ${row.epc1_position === 1 ? 'text-accent' : 'text-text-primary'}`}>
          #{row.epc1_position}
        </span>
      ),
    },
    {
      key: 'epc2_position',
      label: 'Other Horse',
      render: (row) => (
        <span className={`font-timing font-bold ${row.epc2_position === 1 ? 'text-accent' : 'text-text-primary'}`}>
          #{row.epc2_position}
        </span>
      ),
    },
    {
      key: 'winner',
      label: 'Winner',
      render: (row) => (
        <span className="text-xs text-text-muted">
          {row.epc1_position < row.epc2_position ? '← This' : row.epc2_position < row.epc1_position ? 'Other →' : 'Dead Heat'}
        </span>
      ),
    },
  ]

  return (
    <div className="mt-6 border border-border bg-surface p-4">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-3">
        Head to Head
      </h3>
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          placeholder="Enter opponent EPC"
          value={epc2Input}
          onChange={(e) => setEpc2Input(e.target.value.toUpperCase())}
          className="flex-1 max-w-xs bg-bg border border-border text-text-primary px-3 py-1.5 text-sm font-timing focus:outline-none focus:border-accent"
        />
        <button
          onClick={() => setEpc2(epc2Input.trim())}
          disabled={!epc2Input.trim()}
          className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-border text-text-muted hover:border-accent hover:text-accent transition-colors disabled:opacity-40"
        >
          Compare
        </button>
      </div>

      {isLoading && <p className="text-text-muted text-xs font-timing">Loading...</p>}
      {error && (
        <p className="text-red-400 text-xs font-timing">
          {error.response?.data?.detail ?? 'Comparison failed'}
        </p>
      )}

      {data && (
        <>
          <div className="flex gap-0 mb-4 border border-border">
            <StatBadge label="Meetings" value={data.shared_races} />
            <StatBadge label="This Wins" value={data.epc1_wins} variant="accent" />
            <StatBadge label="Other Wins" value={data.epc2_wins} />
            <StatBadge label="Draws" value={data.draws} variant="muted" />
          </div>
          <DataTable
            columns={meetingColumns}
            rows={(data.races ?? []).map((r, i) => ({ ...r, id: i }))}
            emptyMessage="No shared races"
          />
        </>
      )}
    </div>
  )
}

// ──────────────────────────────────────────────
// Horse Profile Page
// ──────────────────────────────────────────────
function HorseDetail({ epc }) {
  const { data: horse, isLoading: loadingHorse, error: horseError } = useQuery({
    queryKey: ['horse', epc],
    queryFn: () => getHorse(epc),
  })
  const { data: career = [] } = useQuery({
    queryKey: ['horse-career', epc],
    queryFn: () => getHorseCareer(epc),
    enabled: !!horse,
  })
  const { data: form = [] } = useQuery({
    queryKey: ['horse-form', epc],
    queryFn: () => getHorseForm(epc),
    enabled: !!horse,
  })
  const { data: sectionals = [] } = useQuery({
    queryKey: ['horse-sectionals', epc],
    queryFn: () => getHorseSectionals(epc),
    enabled: !!horse,
  })
  const { data: vetRecords = [] } = useQuery({
    queryKey: ['horse-vet', epc],
    queryFn: () => getHorseVet(epc),
    enabled: !!horse,
  })

  if (loadingHorse)
    return <p className="p-6 text-text-muted text-xs font-timing tracking-widest">Loading...</p>
  if (horseError)
    return (
      <p className="p-6 text-red-400 text-xs font-timing">
        {horseError.response?.data?.detail ?? 'Horse not found'}
      </p>
    )
  if (!horse) return null

  // Compute career stats
  const starts = career.length
  const wins = career.filter((r) => r.finish_position === 1).length
  const places = career.filter((r) => r.finish_position != null && r.finish_position <= 3).length
  const winPct = starts > 0 ? ((wins / starts) * 100).toFixed(0) + '%' : '—'

  const currentOwner = horse.owners?.find((o) => !o.to_date)?.owner_name ?? '—'
  const currentTrainer = horse.trainers?.find((t) => !t.to_date)?.trainer_name ?? '—'

  const formColumns = [
    {
      key: 'race_date',
      label: 'Date',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">
          {r.race_date ? new Date(r.race_date).toLocaleDateString() : '—'}
        </span>
      ),
    },
    {
      key: 'distance_m',
      label: 'Distance',
      render: (r) => (
        <span className="font-timing text-text-muted">{r.distance_m}m</span>
      ),
    },
    {
      key: 'finish_position',
      label: 'Pos',
      render: (r) => (
        <span
          className={`font-timing font-bold ${r.finish_position === 1 ? 'text-accent' : 'text-text-primary'}`}
        >
          {r.finish_position ?? '—'}
        </span>
      ),
    },
    {
      key: 'elapsed_ms',
      label: 'Time',
      render: (r) => <TimingDisplay ms={r.elapsed_ms} />,
    },
  ]

  const vetColumns = [
    {
      key: 'event_date',
      label: 'Date',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">{r.event_date ?? '—'}</span>
      ),
    },
    {
      key: 'event_type',
      label: 'Type',
      render: (r) => (
        <span className="text-xs uppercase tracking-wide text-text-primary">{r.event_type}</span>
      ),
    },
    {
      key: 'notes',
      label: 'Notes',
      render: (r) => (
        <span className="text-text-muted text-xs">{r.notes ?? '—'}</span>
      ),
    },
    {
      key: 'vet_name',
      label: 'Vet',
      render: (r) => (
        <span className="text-text-muted text-xs">{r.vet_name ?? '—'}</span>
      ),
    },
    {
      key: 'cleared',
      label: 'Cleared',
      render: (r) => {
        const v = r.cleared_to_race
        return (
          <span
            className={`text-xs font-timing font-bold px-1.5 py-0.5 border ${
              v === true
                ? 'border-green-700 text-green-400'
                : v === false
                ? 'border-red-700 text-red-400'
                : 'border-border text-text-muted'
            }`}
          >
            {v === true ? 'YES' : v === false ? 'NO' : '—'}
          </span>
        )
      },
    },
  ]

  return (
    <div className="p-6">
      {/* Back */}
      <Link
        to="/horses"
        className="text-xs text-text-muted hover:text-accent font-timing tracking-widest uppercase mb-4 inline-block"
      >
        ← All Horses
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            {horse.name}
          </h1>
          <p className="font-timing text-text-muted text-xs mt-1">
            EPC: <span className="text-accent">{horse.epc}</span>
            {horse.breed && <span className="ml-4">{horse.breed}</span>}
            {horse.implant_date && (
              <span className="ml-4">Implanted: {horse.implant_date}</span>
            )}
          </p>
          <p className="text-text-muted text-xs mt-1">
            Owner: <span className="text-text-primary">{currentOwner}</span>
            <span className="mx-3 text-border">|</span>
            Trainer: <span className="text-text-primary">{currentTrainer}</span>
          </p>
        </div>
      </div>

      {/* Career stats */}
      <div className="flex gap-0 mb-6 border border-border">
        <StatBadge label="Starts" value={starts} />
        <StatBadge label="Wins" value={wins} variant="accent" />
        <StatBadge label="Places" value={places} />
        <StatBadge label="Win %" value={winPct} variant={wins > 0 ? 'accent' : 'muted'} />
      </div>

      {/* Form guide */}
      <div className="border border-border bg-surface mb-6">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">
            Recent Form (last 5)
          </span>
        </div>
        <DataTable
          columns={formColumns}
          rows={form.map((r, i) => ({ ...r, id: i }))}
          emptyMessage="No race history"
        />
      </div>

      {/* Sectionals chart */}
      {sectionals.length > 0 && (
        <div className="border border-border bg-surface mb-6 p-4">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-3">
            Sectional Averages
          </h3>
          <div style={{ height: 200, background: '#0a0a0a' }} className="border border-border p-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sectionals} margin={{ top: 4, right: 8, left: -10, bottom: 4 }}>
                <XAxis
                  dataKey="segment"
                  tick={{ fill: '#6b7280', fontSize: 10 }}
                  tickLine={false}
                  axisLine={{ stroke: '#2a2a2a' }}
                  interval={0}
                  angle={-20}
                  textAnchor="end"
                  height={40}
                />
                <YAxis
                  tick={{ fill: '#6b7280', fontSize: 10, fontFamily: 'monospace' }}
                  tickLine={false}
                  axisLine={false}
                  unit=" km/h"
                />
                <Tooltip
                  contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#f5f5f5', fontSize: 12 }}
                  cursor={{ fill: 'rgba(245,158,11,0.05)' }}
                  formatter={(val) => [`${val?.toFixed(1)} km/h`, 'Avg Speed']}
                />
                <Bar dataKey="avg_speed_kmh" fill={ACCENT} radius={0} maxBarSize={48}>
                  {sectionals.map((_, idx) => (
                    <Cell key={idx} fill={idx % 2 === 0 ? ACCENT : '#d97706'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Vet records */}
      <div className="border border-border bg-surface mb-6">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">
            Vet Records
          </span>
        </div>
        <DataTable
          columns={vetColumns}
          rows={vetRecords.map((r) => ({ ...r }))}
          emptyMessage="No vet records"
        />
      </div>

      {/* Head to head */}
      <HeadToHead epc1={epc} />
    </div>
  )
}

// ──────────────────────────────────────────────
// Route wrapper — /horses vs /horses/:epc
// ──────────────────────────────────────────────
export default function HorseProfile() {
  const { epc } = useParams()
  if (epc) return <HorseDetail epc={epc.toUpperCase()} />
  return <HorseList />
}