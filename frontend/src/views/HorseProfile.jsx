import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import {
  listHorses, getHorse, getHorseCareer, getHorseForm,
  getHorseVet, compareHorses,
  getHorseWorkouts, getHorseCheckins, getHorseTestBarn,
  getHorseBiosensor, getHorseTemperatureAlerts,
  addWorkout,
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
      h.chip_id?.toLowerCase().includes(search.toLowerCase())
  )

  const columns = [
    {
      key: 'chip_id',
      label: 'Chip ID',
      render: (row) => (
        <span className="font-timing text-text-muted text-xs">{row.chip_id}</span>
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
        placeholder="Search by name or chip ID..."
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
            rows={filtered.map((h) => ({ ...h, id: h.chip_id }))}
            onRowClick={(row) => navigate(`/horses/${row.chip_id}`)}
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
function HeadToHead({ chip_id1 }) {
  const [epc2Input, setEpc2Input] = useState('')
  const [chip_id2, setEpc2] = useState(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['h2h', chip_id1, chip_id2],
    queryFn: () => compareHorses(chip_id1, chip_id2),
    enabled: !!chip_id2,
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
            placeholder="Enter opponent chip ID"
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
// Manual clocker-entry modal
function LogWorkoutModal({ chip_id, onClose, onSaved }) {
  const today = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState({
    workout_date: today, distance_m: '800', surface: 'Dirt', duration_ms_s: '',
    track_condition: 'Fast', trainer_name: '', rider_name: '', clocker_name: '', notes: '',
  })
  const [error, setError] = useState(null)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const mut = useMutation({
    mutationFn: () => addWorkout(chip_id, {
      workout_date: form.workout_date,
      distance_m: Number(form.distance_m),
      surface: form.surface || null,
      duration_ms: form.duration_ms_s ? Math.round(Number(form.duration_ms_s) * 1000) : null,
      track_condition: form.track_condition || null,
      trainer_name: form.trainer_name || null,
      rider_name: form.rider_name || null,
      clocker_name: form.clocker_name || null,
      notes: form.notes || null,
    }),
    onSuccess: () => { onSaved(); onClose() },
    onError: (err) => setError(err.response?.data?.detail ?? 'Save failed'),
  })

  const field = 'bg-bg border border-border text-text-primary px-2 py-1.5 text-sm focus:outline-none focus:border-accent'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="bg-surface border border-border w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-text-primary">Log Workout</span>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary text-lg leading-none">×</button>
        </div>
        <div className="p-4 grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 col-span-2">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Date</span>
            <input type="date" value={form.workout_date} onChange={set('workout_date')} className={field} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Distance (m)</span>
            <input type="number" value={form.distance_m} onChange={set('distance_m')} className={`${field} font-timing`} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Time (s)</span>
            <input type="number" step="0.1" placeholder="optional" value={form.duration_ms_s} onChange={set('duration_ms_s')} className={`${field} font-timing`} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Surface</span>
            <select value={form.surface} onChange={set('surface')} className={field}>
              {['Dirt', 'Turf', 'Synthetic'].map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Condition</span>
            <select value={form.track_condition} onChange={set('track_condition')} className={field}>
              {['Fast', 'Good', 'Soft', 'Heavy'].map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Exercise Rider</span>
            <input value={form.rider_name} onChange={set('rider_name')} className={field} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Clocker</span>
            <input value={form.clocker_name} onChange={set('clocker_name')} className={field} />
          </label>
          <label className="flex flex-col gap-1 col-span-2">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Trainer</span>
            <input value={form.trainer_name} onChange={set('trainer_name')} className={field} />
          </label>
          <label className="flex flex-col gap-1 col-span-2">
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Notes</span>
            <input value={form.notes} onChange={set('notes')} className={field} />
          </label>
        </div>
        {error && <p className="px-4 text-red-400 text-xs font-timing">{error}</p>}
        <div className="px-4 py-3 border-t border-border flex justify-end gap-2">
          <button onClick={onClose} className="text-xs font-timing uppercase tracking-widest border border-border text-text-muted px-3 py-1.5 hover:text-text-primary">
            Cancel
          </button>
          <button
            onClick={() => { setError(null); mut.mutate() }}
            disabled={mut.isPending || !form.workout_date || !form.distance_m}
            className="text-xs font-timing font-bold uppercase tracking-widest bg-accent text-bg px-4 py-1.5 hover:bg-accent-dim disabled:opacity-40"
          >
            {mut.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

function HorseDetail({ chip_id }) {
  const [showAllTestBarn, setShowAllTestBarn] = useState(false)

  const { data: horse, isLoading: loadingHorse, error: horseError } = useQuery({
    queryKey: ['horse', chip_id],
    queryFn: () => getHorse(chip_id),
  })
  const { data: career = [], isLoading: loadingCareer } = useQuery({
    queryKey: ['horse-career', chip_id],
    queryFn: () => getHorseCareer(chip_id),
    enabled: !!horse,
  })
  const { data: form = [], isLoading: loadingForm, error: formError } = useQuery({
    queryKey: ['horse-form', chip_id],
    queryFn: () => getHorseForm(chip_id),
    enabled: !!horse,
  })
  const { data: vetRecords = [], isLoading: loadingVet, error: vetError } = useQuery({
    queryKey: ['horse-vet', chip_id],
    queryFn: () => getHorseVet(chip_id),
    enabled: !!horse,
  })
  const { data: workoutsRaw = [], isLoading: loadingWorkouts, error: workoutsError } = useQuery({
    queryKey: ['horse-workouts', chip_id],
    queryFn: () => getHorseWorkouts(chip_id),
    enabled: !!horse,
  })
  const { data: checkinsRaw = [], isLoading: loadingCheckins, error: checkinsError } = useQuery({
    queryKey: ['horse-checkins', chip_id],
    queryFn: () => getHorseCheckins(chip_id),
    enabled: !!horse,
  })
  const { data: testBarnRaw = [], isLoading: loadingTestBarn, error: testBarnError } = useQuery({
    queryKey: ['horse-testbarn', chip_id],
    queryFn: () => getHorseTestBarn(chip_id),
    enabled: !!horse,
  })
  const { data: biosensorRaw = [], isLoading: loadingBiosensor } = useQuery({
    queryKey: ['horse-biosensor', chip_id],
    queryFn: () => getHorseBiosensor(chip_id, 200),
    enabled: !!horse,
  })
  const { data: tempAlerts } = useQuery({
    queryKey: ['horse-temp-alerts', chip_id],
    queryFn: () => getHorseTemperatureAlerts(chip_id),
    enabled: !!horse,
  })
  const qc = useQueryClient()
  const [expandedWorkoutId, setExpandedWorkoutId] = useState(null)
  const [showLogWorkout, setShowLogWorkout] = useState(false)

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
      key: 'rider_name',
      label: 'Rider',
      render: (r) => (
        <span className="text-xs text-text-muted">{r.rider_name ?? '—'}</span>
      ),
    },
    {
      key: 'clocker_name',
      label: 'Clocker',
      render: (r) => (
        <span className="text-xs text-text-muted">{r.clocker_name ?? '—'}</span>
      ),
    },
    {
      key: 'source',
      label: 'Source',
      render: (r) => (
        <span className={`text-[10px] font-timing font-bold uppercase tracking-wide px-1.5 py-0.5 border ${
          r.source === 'sim'
            ? 'border-accent text-accent'
            : 'border-border text-text-muted'
        }`}>
          {r.source === 'sim' ? 'SIM' : 'MANUAL'}
        </span>
      ),
    },
    {
      key: 'splits',
      label: 'Splits',
      render: (r) => {
        let n = 0
        try { n = r.splits_json ? JSON.parse(r.splits_json).length : 0 } catch (_) { n = 0 }
        if (!n) return <span className="text-xs text-text-muted">—</span>
        return (
          <span className="text-xs font-timing text-accent">
            {expandedWorkoutId === r.id ? '▾' : '▸'} {n}
          </span>
        )
      },
    },
  ]

  const splitColumns = [
    { key: 'segment', label: 'Segment', render: (s) => <span className="text-xs text-text-primary">{s.segment}</span> },
    { key: 'distance_m', label: 'Distance', render: (s) => <span className="font-timing text-xs text-text-muted">{s.distance_m}m</span> },
    { key: 'elapsed_str', label: 'Split', render: (s) => <span className="font-timing text-xs text-text-primary">{s.elapsed_str ?? `${(s.elapsed_ms / 1000).toFixed(2)}s`}</span> },
    { key: 'speed_kmh', label: 'Speed', render: (s) => <span className="font-timing text-xs text-text-muted">{s.speed_kmh != null ? `${s.speed_kmh} km/h` : '—'}</span> },
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
      key: 'temperature_c',
      label: 'Temp (°C)',
      render: (r) => {
        const t = r.temperature_c
        if (t == null) return <span className="font-timing text-xs text-text-muted">—</span>
        const cls = t >= 39.0 || t <= 37.0
          ? 'text-red-400 font-bold'
          : t >= 38.5
          ? 'text-amber-400 font-bold'
          : 'text-text-primary'
        return <span className={`font-timing text-xs ${cls}`}>{t.toFixed(1)}°C</span>
      },
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
            Chip ID: <span className="text-accent">{horse.chip_id}</span>
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

      {/* ── SECTION 4: Workout Log ── */}
      <div className="border border-border bg-surface mb-6">
        <div className="px-4 py-2 border-b border-border flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <div className="w-0.5 h-3.5 bg-accent flex-shrink-0" />
            <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">
              Workout Log — Last 15
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowLogWorkout(true)}
              className="text-xs font-timing uppercase tracking-widest border border-border text-text-muted hover:border-accent hover:text-accent px-2 py-1 transition-colors"
            >
              + Log Workout
            </button>
          </div>
        </div>
        {loadingWorkouts ? <SectionLoading /> : workoutsError ? <SectionError /> : (
          <>
            <DataTable
              columns={workoutColumns}
              rows={workouts.map((r) => ({ ...r }))}
              onRowClick={(r) => setExpandedWorkoutId(expandedWorkoutId === r.id ? null : r.id)}
              emptyMessage="No workout records"
            />
            {expandedWorkoutId != null && (() => {
              const w = workouts.find((x) => x.id === expandedWorkoutId)
              let splits = []
              try { splits = w?.splits_json ? JSON.parse(w.splits_json) : [] } catch (_) { splits = [] }
              if (!splits.length) return null
              return (
                <div className="border-t border-border bg-bg">
                  <p className="px-4 pt-3 text-[10px] uppercase tracking-widest text-text-muted">
                    Sectional splits — {w.workout_date}
                  </p>
                  <DataTable
                    columns={splitColumns}
                    rows={splits.map((s, i) => ({ ...s, id: i }))}
                    emptyMessage=""
                  />
                </div>
              )
            })()}
          </>
        )}
      </div>

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

      {/* ── SECTION 9: Biosensor ── */}
      <SectionShell title="Biosensor — Last 200 Readings">
        {loadingBiosensor ? <SectionLoading /> : biosensorRaw.length === 0 ? (
          <p className="px-4 py-3 text-text-muted text-xs font-timing">No biosensor data available</p>
        ) : (() => {
          const sorted = [...biosensorRaw].sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at))
          const hrData  = sorted.filter(r => r.heart_rate_bpm != null).map((r, i) => ({ i, v: r.heart_rate_bpm, t: r.recorded_at }))
          const tmpData = sorted.filter(r => r.temperature_c   != null).map((r, i) => ({ i, v: r.temperature_c,   t: r.recorded_at }))
          const strData = sorted.filter(r => r.stride_hz       != null).map((r, i) => ({ i, v: r.stride_hz,       t: r.recorded_at }))
          return (
            <div className="p-4 grid grid-cols-1 gap-4">
              {hrData.length > 0 && (
                <div>
                  <p className="text-xs text-text-muted font-timing uppercase tracking-widest mb-1">Heart Rate (bpm)</p>
                  <div style={{ height: 120, background: '#111' }} className="border border-border">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={hrData} margin={{ top: 4, right: 8, left: -10, bottom: 4 }}>
                        <XAxis dataKey="i" hide />
                        <YAxis tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'monospace' }} tickLine={false} axisLine={false} unit=" bpm" />
                        <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#f5f5f5', fontSize: 11 }}
                          formatter={(v) => [`${v} bpm`, 'HR']} labelFormatter={() => ''} />
                        <Line type="monotone" dataKey="v" stroke="#ef4444" dot={false} strokeWidth={1.5} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
              {tmpData.length > 0 && (
                <div>
                  <p className="text-xs text-text-muted font-timing uppercase tracking-widest mb-1">Body Temperature (°C)</p>
                  <div style={{ height: 120, background: '#111' }} className="border border-border">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={tmpData} margin={{ top: 4, right: 8, left: -10, bottom: 4 }}>
                        <XAxis dataKey="i" hide />
                        <YAxis domain={['auto', 'auto']} tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'monospace' }} tickLine={false} axisLine={false} unit="°C" />
                        <ReferenceLine y={38.5} stroke="#f59e0b" strokeDasharray="4 2" />
                        <ReferenceLine y={39.0} stroke="#ef4444" strokeDasharray="4 2" />
                        <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#f5f5f5', fontSize: 11 }}
                          formatter={(v) => [`${v?.toFixed(1)}°C`, 'Temp']} labelFormatter={() => ''} />
                        <Line type="monotone" dataKey="v" stroke="#06b6d4" dot={false} strokeWidth={1.5} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
              {strData.length > 0 && (
                <div>
                  <p className="text-xs text-text-muted font-timing uppercase tracking-widest mb-1">Stride Frequency (Hz)</p>
                  <div style={{ height: 120, background: '#111' }} className="border border-border">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={strData} margin={{ top: 4, right: 8, left: -10, bottom: 4 }}>
                        <XAxis dataKey="i" hide />
                        <YAxis tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'monospace' }} tickLine={false} axisLine={false} unit=" Hz" />
                        <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#f5f5f5', fontSize: 11 }}
                          formatter={(v) => [`${v?.toFixed(2)} Hz`, 'Stride']} labelFormatter={() => ''} />
                        <Line type="monotone" dataKey="v" stroke="#22c55e" dot={false} strokeWidth={1.5} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>
          )
        })()}
      </SectionShell>

      {/* ── SECTION 10: Temperature Alerts ── */}
      {tempAlerts?.alert_count > 0 && (
        <SectionShell title={`Temperature Alerts — ${tempAlerts.alert_count} flag${tempAlerts.alert_count !== 1 ? 's' : ''}`}>
          <div className="divide-y divide-border">
            {tempAlerts.alerts.map((a) => (
              <div key={a.id} className="px-4 py-2 flex items-center gap-4">
                <span className={`text-xs font-timing font-bold ${a.severity === 'red' ? 'text-red-400' : 'text-amber-400'}`}>
                  {a.temperature_c?.toFixed(1)}°C
                </span>
                <span className="text-xs text-text-muted font-timing">{fmtDatetime(a.scanned_at)}</span>
                {a.location && <span className="text-xs text-text-muted">{a.location}</span>}
                {a.race_id && <span className="text-xs text-text-muted font-timing">Race #{a.race_id}</span>}
              </div>
            ))}
          </div>
        </SectionShell>
      )}

      {/* ── SECTION 11: Head to Head ── */}
      <HeadToHead chip_id1={chip_id} />

      {showLogWorkout && (
        <LogWorkoutModal
          chip_id={chip_id}
          onClose={() => setShowLogWorkout(false)}
          onSaved={() => qc.invalidateQueries({ queryKey: ['horse-workouts', chip_id] })}
        />
      )}
    </div>
  )
}

// ──────────────────────────────────────────────
// Route wrapper — /horses vs /horses/:chip_id
// ──────────────────────────────────────────────
export default function HorseProfile() {
  const { chip_id } = useParams()
  if (chip_id) return <HorseDetail chip_id={chip_id.toUpperCase()} />
  return <HorseList />
}