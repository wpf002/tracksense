import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { getFinishOrder, getRaceState, persistRace } from '../api/races'
import DataTable from '../components/ui/DataTable'
import TimingDisplay from '../components/ui/TimingDisplay'
import StatBadge from '../components/ui/StatBadge'

const CHART_BG = '#111111'
const ACCENT = '#f59e0b'
const MUTED = '#374151'

function SectionalsPanel({ horse }) {
  if (!horse) return null
  const sectionals = horse.sectionals ?? []

  return (
    <div className="mt-6 border border-border bg-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-text-muted">
          Sectionals — {horse.display_name}
        </span>
      </div>

      {sectionals.length === 0 ? (
        <p className="text-text-muted text-xs font-timing">No sectional data available.</p>
      ) : (
        <>
          {/* Table */}
          <table className="w-full text-sm mb-4 border-collapse">
            <thead>
              <tr className="border-b border-border">
                {['Segment', 'Distance', 'Time', 'Speed (km/h)'].map((h) => (
                  <th key={h} className="px-3 py-1.5 text-left text-xs text-text-muted uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sectionals.map((s, i) => (
                <tr key={i} className="border-b border-border">
                  <td className="px-3 py-1.5 text-text-primary">{s.segment}</td>
                  <td className="px-3 py-1.5 font-timing text-text-muted">{s.distance_m}m</td>
                  <td className="px-3 py-1.5">
                    <TimingDisplay ms={s.elapsed_ms} />
                  </td>
                  <td className="px-3 py-1.5 font-timing text-accent">
                    {s.speed_kmh != null ? s.speed_kmh.toFixed(1) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Chart */}
          <div style={{ height: 180, background: CHART_BG }} className="border border-border p-2">
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
                  formatter={(val) => [`${val?.toFixed(1)} km/h`, 'Speed']}
                />
                <Bar dataKey="speed_kmh" fill={ACCENT} radius={0} maxBarSize={48}>
                  {sectionals.map((_, idx) => (
                    <Cell key={idx} fill={idx % 2 === 0 ? ACCENT : '#d97706'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}

export default function RaceResults() {
  const [selectedHorse, setSelectedHorse] = useState(null)
  const [persistRaceId, setPersistRaceId] = useState('')
  const [persistMsg, setPersistMsg] = useState(null)
  const [persistError, setPersistError] = useState(null)

  const { data: finishData, isLoading: loadingFinish } = useQuery({
    queryKey: ['finish-order'],
    queryFn: getFinishOrder,
  })

  const { data: stateData, isLoading: loadingState } = useQuery({
    queryKey: ['race-state-results'],
    queryFn: getRaceState,
  })

  const persistMutation = useMutation({
    mutationFn: () => persistRace(parseInt(persistRaceId, 10)),
    onSuccess: (data) => {
      setPersistMsg(
        `Persisted: ${data.persisted_entries} entries, ${data.persisted_reads} reads, ${data.persisted_results} results.`
      )
      setPersistError(null)
    },
    onError: (err) => {
      setPersistError(err.response?.data?.detail ?? 'Persist failed')
      setPersistMsg(null)
    },
  })

  const results = finishData?.results ?? []
  const stateHorses = stateData?.horses ?? []

  // When a row is clicked, find that horse's full state (with sectionals)
  const handleRowClick = (row) => {
    const full = stateHorses.find((h) => h.horse_id === row.horse_id)
    setSelectedHorse(full ?? row)
  }

  const columns = [
    {
      key: 'position',
      label: 'Pos',
      className: 'w-12',
      render: (row) => (
        <span className="font-timing font-bold text-accent text-base">{row.position}</span>
      ),
    },
    {
      key: 'saddle_cloth',
      label: '#',
      className: 'w-12',
      render: (row) => (
        <span className="font-timing font-bold">{row.saddle_cloth}</span>
      ),
    },
    {
      key: 'display_name',
      label: 'Horse',
      render: (row) => <span className="font-medium">{row.display_name}</span>,
    },
    {
      key: 'elapsed_ms',
      label: 'Time',
      render: (row) => <TimingDisplay ms={row.elapsed_ms} />,
    },
    {
      key: 'split_str',
      label: 'Gap',
      render: (row) => (
        <span className="font-timing text-text-muted">
          {row.position === 1 ? '—' : (row.split_str ?? '—')}
        </span>
      ),
    },
  ]

  const tableRows = results.map((r) => ({ ...r, id: r.position }))

  const loading = loadingFinish || loadingState

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">
          Race Results
        </h1>

        {/* Persist panel */}
        <div className="flex items-center gap-2">
          <input
            type="number"
            placeholder="Race ID"
            value={persistRaceId}
            onChange={(e) => setPersistRaceId(e.target.value)}
            className="w-24 bg-surface border border-border text-text-primary text-sm px-2 py-1.5 font-timing focus:outline-none focus:border-accent"
          />
          <button
            onClick={() => persistMutation.mutate()}
            disabled={!persistRaceId || persistMutation.isPending}
            className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-accent text-accent hover:bg-amber-950 transition-colors disabled:opacity-40"
          >
            {persistMutation.isPending ? 'Saving…' : 'Persist Results'}
          </button>
        </div>
      </div>

      {persistMsg && (
        <p className="text-green-400 text-xs mb-3 font-timing">{persistMsg}</p>
      )}
      {persistError && (
        <p className="text-red-400 text-xs mb-3 font-timing">{persistError}</p>
      )}

      {/* Stats */}
      <div className="flex gap-0 mb-6 border border-border">
        <StatBadge label="Status" value={(finishData?.status ?? '—').toUpperCase()} variant="muted" />
        <StatBadge label="Runners" value={finishData?.total_expected ?? '—'} />
        <StatBadge label="Finished" value={finishData?.total_finished ?? '—'} />
      </div>

      {loading ? (
        <p className="text-text-muted text-xs font-timing tracking-widest">Loading...</p>
      ) : (
        <>
          <div className="border border-border bg-surface">
            <div className="px-4 py-2 border-b border-border flex items-center justify-between">
              <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
                Finish Order
              </span>
              <span className="text-xs text-text-muted font-timing">
                Click a row to view sectionals
              </span>
            </div>
            <DataTable
              columns={columns}
              rows={tableRows}
              onRowClick={handleRowClick}
              emptyMessage="No results — race not yet finished"
            />
          </div>

          <SectionalsPanel horse={selectedHorse} />
        </>
      )}
    </div>
  )
}