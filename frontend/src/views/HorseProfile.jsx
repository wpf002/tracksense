import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  listHorses, getHorse, getHorseCareer, getHorseForm,
  getHorseSectionals, getHorseVet, compareHorses,
  getHorseWorkouts, getHorseCheckins, getHorseTestBarn,
} from '../api/horses'
import DataTable from '../components/ui/DataTable'
import TimingDisplay from '../components/ui/TimingDisplay'
import StatBadge from '../components/ui/StatBadge'

const ACCENT = '#f59e0b'

function ordinal(n) {
  if (n == null) return '—'
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}

function fmtDatetime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function SectionHeader({ title }) {
  return (
    <div className="px-4 py-2 border-b border-border flex items-center gap-2">
      <div className="w-0.5 h-3.5 bg-accent flex-shrink-0" />
      <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">
        {title}
      </span>
    </div>
  )
}

function SectionShell({ title, children }) {
  return (
    <div className="border border-border bg-surface mb-6">
      <SectionHeader title={title} />
      {children}
    </div>
  )
}

function SectionLoading() {
  return <p className="px-4 py-3 text-text-muted text-xs font-timing tracking-widest">Loading...</p>
}

function SectionError() {
  return <p className="px-4 py-3 text-red-400 text-xs font-timing">Failed to load</p>
}

function VetBadge({ type }) {
  const map = {
    clearance:   'border-green-700 text-green-400',
    vaccination: 'border-blue-700 text-blue-400',
    treatment:   'border-amber-700 text-amber-400',
    implant:     'border-purple-700 text-purple-400',
  }
  const cls = map[type?.toLowerCase()] ?? 'border-border text-text-muted'
  return (
    <span className={`text-xs font-timing font-bold px-1.5 py-0.5 border uppercase tracking-wide ${cls}`}>
      {type ?? '—'}
    </span>
  )
}

function ResultBadge({ result }) {
  const map = {
    clear:    'border-green-700 text-green-400',
    pending:  'border-yellow-700 text-yellow-400',
    positive: 'border-red-700 text-red-400',
    void:     'border-border text-text-muted',
  }
  const cls = map[result?.toLowerCase()] ?? 'border-border text-text-muted'
  return (
    <span className={`text-xs font-timing font-bold px-1.5 py-0.5 border uppercase tracking-wide ${cls}`}>
      {result ?? '—'}
    </span>
  )
}

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
    <SectionShell title="Head to Head">
      <div className="p-4">
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
    </SectionShell>
  )
}

// ──────────────────────────────────────────────
// Horse Profile Page
// ──────────────────────────────────────────────
function HorseDetail({ epc }) {
  const [showAllTestBarn, setShowAllTestBarn] = useState(false)

  const { data: horse, isLoading: loadingHorse, error: horseError } = useQuery({
    queryKey: ['horse', epc],
    queryFn: () => getHorse(epc),
  })
  const { data: career = [], isLoading: loadingCareer } = useQuery({
    queryKey: ['horse-career', epc],
    queryFn: () => getHorseCareer(epc),
    enabled: !!horse,
  })
  const { data: form = [], isLoading: loadingForm, error: formError } = useQuery({
    queryKey: ['horse-form', epc],
    queryFn: () => getHorseForm(epc),
    enabled: !!horse,
  })
  const { data: sectionals = [], isLoading: loadingSectionals, error: sectionalsError } = useQuery({
    queryKey: ['horse-sectionals', epc],
    queryFn: () => getHorseSectionals(epc),
    enabled: !!horse,
  })
  const { data: vetRecords = [], isLoading: loadingVet, error: vetError } = useQuery({
    queryKey: ['horse-vet', epc],
    queryFn: () => getHorseVet(epc),
    enabled: !!horse,
  })
  const { data: workoutsRaw = [], isLoading: loadingWorkouts, error: workoutsError } = useQuery({
    queryKey: ['horse-workouts', epc],
    queryFn: () => getHorseWorkouts(epc),
    enabled: !!horse,
  })
  const { data: checkinsRaw = [], isLoading: loadingCheckins, error: checkinsError } = useQuery({
    queryKey: ['horse-checkins', epc],
    queryFn: () => getHorseCheckins(epc),
    enabled: !!horse,
  })
  const { data: testBarnRaw = [], isLoading: loadingTestBarn, error: testBarnError } = useQuery({
    queryKey: ['horse-testbarn', epc],
    queryFn: () => getHorseTestBarn(epc),
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

  // Slices
  const workouts = workoutsRaw.slice(0, 15)
  const checkins = checkinsRaw.slice(0, 10)
  const testBarn = showAllTestBarn ? testBarnRaw : testBarnRaw.slice(0, 10)

  // Career stats
  const starts = loadingCareer ? null : career.length
  const wins   = loadingCareer ? null : career.filter((r) => r.finish_position === 1).length
  const places = loadingCareer ? null : career.filter((r) => r.finish_position != null && r.finish_position <= 3).length
  const winPct = starts != null && starts > 0 ? ((wins / starts) * 100).toFixed(0) + '%' : starts === 0 ? '0%' : '—'

  const currentOwner   = horse.owners?.find((o) => !o.to_date)?.owner_name ?? '—'
  const currentTrainer = horse.trainers?.find((t) => !t.to_date)?.trainer_name ?? '—'

  // ── Column definitions ──

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
      key: 'venue_id',
      label: 'Venue',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">{r.venue_id ?? '—'}</span>
      ),
    },
    {
      key: 'distance_m',
      label: 'Distance',
      render: (r) => (
        <span className="font-timing text-text-muted">{r.distance_m != null ? `${r.distance_m}m` : '—'}</span>
      ),
    },
    {
      key: 'finish_position',
      label: 'Pos',
      render: (r) => (
        <span className={`font-timing font-bold ${r.finish_position === 1 ? 'text-accent' : 'text-text-primary'}`}>
          {ordinal(r.finish_position)}
        </span>
      ),
    },
    {
      key: 'elapsed_ms',
      label: 'Time',
      render: (r) => <TimingDisplay ms={r.elapsed_ms} />,
    },
    {
      key: 'surface',
      label: 'Surface',
      render: (r) => (
        <span className="text-xs text-text-muted capitalize">{r.surface ?? '—'}</span>
      ),
    },
  ]

  const workoutColumns = [
    {
      key: 'workout_date',
      label: 'Date',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">{r.workout_date ?? '—'}</span>
      ),
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
      render: (r) => (
        <span className="text-xs text-text-muted capitalize">{r.surface ?? '—'}</span>
      ),
    },
    {
      key: 'track_condition',
      label: 'Condition',
      render: (r) => (
        <span className="text-xs text-text-muted capitalize">{r.track_condition ?? '—'}</span>
      ),
    },
    {
      key: 'duration_ms',
      label: 'Time',
      render: (r) => (
        <span className="font-timing text-text-primary">
          {r.duration_ms != null ? `${(r.duration_ms / 1000).toFixed(1)}s` : '—'}
        </span>
      ),
    },
    {
      key: 'trainer_name',
      label: 'Trainer',
      render: (r) => (
        <span className="text-xs text-text-muted">{r.trainer_name ?? '—'}</span>
      ),
    },
    {
      key: 'notes',
      label: 'Notes',
      render: (r) => (
        <span className="text-xs text-text-muted">{r.notes ?? '—'}</span>
      ),
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
      render: (r) => <VetBadge type={r.event_type} />,
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
  ]

  const checkinColumns = [
    {
      key: 'scanned_at',
      label: 'Scanned At',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">{fmtDatetime(r.scanned_at)}</span>
      ),
    },
    {
      key: 'location',
      label: 'Location',
      render: (r) => (
        <span className="text-xs text-text-muted">{r.location ?? '—'}</span>
      ),
    },
    {
      key: 'scanned_by',
      label: 'Official',
      render: (r) => (
        <span className="text-xs text-text-muted">{r.scanned_by ?? '—'}</span>
      ),
    },
    {
      key: 'verified',
      label: 'Verified',
      render: (r) => (
        r.verified
          ? <span className="text-xs font-timing font-bold text-green-400">✓ VERIFIED</span>
          : <span className="text-xs font-timing font-bold text-red-400">✗ FAILED</span>
      ),
    },
  ]

  const testBarnColumns = [
    {
      key: 'race_id',
      label: 'Race',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">{r.race_id ?? '—'}</span>
      ),
    },
    {
      key: 'checkin_at',
      label: 'Check In',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">{fmtDatetime(r.checkin_at)}</span>
      ),
    },
    {
      key: 'checkout_at',
      label: 'Check Out',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">
          {r.checkout_at ? fmtDatetime(r.checkout_at) : <span className="text-amber-500">In barn</span>}
        </span>
      ),
    },
    {
      key: 'sample_id',
      label: 'Sample ID',
      render: (r) => (
        <span className="font-timing text-xs text-text-muted">{r.sample_id ?? '—'}</span>
      ),
    },
    {
      key: 'result',
      label: 'Result',
      render: (r) => <ResultBadge result={r.result} />,
    },
  ]

  const sectionalTableColumns = [
    {
      key: 'segment',
      label: 'Segment',
      render: (r) => <span className="font-timing text-xs text-text-primary">{r.segment}</span>,
    },
    {
      key: 'sample_count',
      label: 'Races',
      render: (r) => <span className="font-timing text-xs text-text-muted">{r.sample_count}</span>,
    },
    {
      key: 'avg_elapsed_ms',
      label: 'Avg Time',
      render: (r) => <TimingDisplay ms={r.avg_elapsed_ms} />,
    },
    {
      key: 'avg_speed_kmh',
      label: 'Avg Speed',
      render: (r) => (
        <span className="font-timing text-xs text-accent">
          {r.avg_speed_kmh != null ? `${r.avg_speed_kmh.toFixed(1)} km/h` : '—'}
        </span>
      ),
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

      {/* ── SECTION 1: Header ── */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            {horse.name}
          </h1>
          <p className="font-timing text-text-muted text-xs mt-1">
            EPC: <span className="text-accent">{horse.epc}</span>
            {horse.breed && <span className="ml-4">{horse.breed}</span>}
            {horse.date_of_birth && <span className="ml-4">DOB: {horse.date_of_birth}</span>}
          </p>
          <p className="font-timing text-text-muted text-xs mt-1">
            {horse.implant_date && <span>Implanted: {horse.implant_date}</span>}
            {horse.implant_vet && <span className="ml-4">Implant Vet: {horse.implant_vet}</span>}
          </p>
          <p className="text-text-muted text-xs mt-1">
            Owner: <span className="text-text-primary">{currentOwner}</span>
            <span className="mx-3 text-border">|</span>
            Trainer: <span className="text-text-primary">{currentTrainer}</span>
          </p>
        </div>
      </div>

      {/* ── SECTION 2: Career Stats ── */}
      <div className="mb-1">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-0.5 h-3.5 bg-accent flex-shrink-0" />
          <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">Career Stats</span>
        </div>
      </div>
      <div className="flex gap-0 mb-6 border border-border">
        {loadingCareer ? (
          <p className="px-4 py-3 text-text-muted text-xs font-timing">Loading...</p>
        ) : (
          <>
            <StatBadge label="Starts" value={starts ?? '—'} />
            <StatBadge label="Wins" value={wins ?? '—'} variant="accent" />
            <StatBadge label="Places" value={places ?? '—'} />
            <StatBadge label="Win %" value={winPct} variant={wins > 0 ? 'accent' : 'muted'} />
          </>
        )}
      </div>

      {/* ── SECTION 3: Form Guide ── */}
      <SectionShell title="Form Guide — Last 5 Starts">
        {loadingForm ? <SectionLoading /> : formError ? <SectionError /> : (
          <DataTable
            columns={formColumns}
            rows={form.map((r, i) => ({ ...r, id: i }))}
            emptyMessage="No race history"
          />
        )}
      </SectionShell>

      {/* ── SECTION 4: Sectional Averages ── */}
      <SectionShell title="Sectional Averages">
        {loadingSectionals ? <SectionLoading /> : sectionalsError ? <SectionError /> : sectionals.length === 0 ? (
          <p className="px-4 py-3 text-text-muted text-xs font-timing">No sectional data available</p>
        ) : (
          <>
            <div style={{ height: 200, background: '#111111' }} className="border-b border-border p-2">
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
                  <Bar dataKey="avg_speed_kmh" fill={ACCENT} radius={0} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <DataTable
              columns={sectionalTableColumns}
              rows={sectionals.map((r, i) => ({ ...r, id: i }))}
              emptyMessage=""
            />
          </>
        )}
      </SectionShell>

      {/* ── SECTION 5: Workout Log ── */}
      <SectionShell title="Workout Log — Last 15">
        {loadingWorkouts ? <SectionLoading /> : workoutsError ? <SectionError /> : (
          <DataTable
            columns={workoutColumns}
            rows={workouts.map((r) => ({ ...r }))}
            emptyMessage="No workout records"
          />
        )}
      </SectionShell>

      {/* ── SECTION 6: Vet Records ── */}
      <SectionShell title="Vet Records">
        {loadingVet ? <SectionLoading /> : vetError ? <SectionError /> : (
          <DataTable
            columns={vetColumns}
            rows={vetRecords.map((r) => ({ ...r }))}
            emptyMessage="No vet records"
          />
        )}
      </SectionShell>

      {/* ── SECTION 7: Pre-Race Check-ins ── */}
      <SectionShell title="Pre-Race Check-ins — Last 10">
        {loadingCheckins ? <SectionLoading /> : checkinsError ? <SectionError /> : (
          <DataTable
            columns={checkinColumns}
            rows={checkins.map((r) => ({ ...r }))}
            emptyMessage="No check-in records"
          />
        )}
      </SectionShell>

      {/* ── SECTION 8: Test Barn ── */}
      <SectionShell title={`Test Barn${!loadingTestBarn && testBarnRaw.length > 0 ? ` — ${showAllTestBarn ? testBarnRaw.length : Math.min(10, testBarnRaw.length)} of ${testBarnRaw.length}` : ''}`}>
        {loadingTestBarn ? <SectionLoading /> : testBarnError ? <SectionError /> : (
          <>
            <DataTable
              columns={testBarnColumns}
              rows={testBarn.map((r) => ({ ...r }))}
              emptyMessage="No test barn records"
            />
            {testBarnRaw.length > 10 && (
              <div className="px-4 py-2 border-t border-border">
                <button
                  onClick={() => setShowAllTestBarn((v) => !v)}
                  className="text-xs font-timing tracking-widest uppercase text-text-muted hover:text-accent transition-colors"
                >
                  {showAllTestBarn ? `↑ Show less` : `↓ Show all ${testBarnRaw.length} records`}
                </button>
              </div>
            )}
          </>
        )}
      </SectionShell>

      {/* ── SECTION 9: Head to Head ── */}
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