import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listSubmissions, buildAllSubmissions, submitHISA, getSubmission,
} from '../api/compliance'
import StatBadge from '../components/ui/StatBadge'
import DataTable from '../components/ui/DataTable'

const CATEGORY_LABELS = {
  WORKOUTS: 'Timed Workout',
  ADMC_TREATMENT: 'ADMC Treatment',
  ADMC_SAMPLE: 'ADMC Sample',
  SURFACE: 'Surface Condition',
  STEWARDS_RULING: "Stewards' Ruling",
  CHECKIN: 'Pre-race Check-In',
}

const STATUS_STYLE = {
  pending: 'border-amber-700 bg-amber-950 text-amber-400',
  submitted: 'border-blue-700 bg-blue-950 text-blue-400',
  accepted: 'border-green-700 bg-green-950 text-green-400',
  rejected: 'border-red-700 bg-red-950 text-red-400',
  needs_correction: 'border-orange-700 bg-orange-950 text-orange-400',
}

function StatusBadge({ status }) {
  return (
    <span className={`text-[10px] font-timing font-bold uppercase tracking-wide px-1.5 py-0.5 border ${STATUS_STYLE[status] ?? 'border-border text-text-muted'}`}>
      {status?.replace('_', ' ')}
    </span>
  )
}

function PayloadModal({ submission, onClose }) {
  if (!submission) return null
  let payload = null
  try { payload = JSON.parse(submission.payload_json) } catch (_) { payload = submission.payload_json }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="bg-surface border border-border w-full max-w-2xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-text-primary">
            Submission #{submission.id} — {CATEGORY_LABELS[submission.rule_category] ?? submission.rule_category}
          </span>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary text-lg">×</button>
        </div>
        <div className="flex-1 overflow-auto p-4">
          <div className="flex items-center gap-3 mb-3">
            <StatusBadge status={submission.status} />
            {submission.deadline_at && (
              <span className="text-xs font-timing text-text-muted">
                Deadline: {new Date(submission.deadline_at).toLocaleString()}
              </span>
            )}
          </div>
          <pre className="text-xs text-text-muted font-timing bg-bg border border-border p-3 overflow-auto whitespace-pre-wrap">
            {JSON.stringify(payload, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  )
}

export default function ComplianceDashboard() {
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState(null)
  const [filterStatus, setFilterStatus] = useState('')
  const [filterCategory, setFilterCategory] = useState('')

  const { data: allSubs = [], isLoading } = useQuery({
    queryKey: ['hisa-submissions', filterStatus, filterCategory],
    queryFn: () => listSubmissions({
      ...(filterStatus && { status: filterStatus }),
      ...(filterCategory && { rule_category: filterCategory }),
    }),
    refetchInterval: 15000,
  })

  const { data: selectedSub } = useQuery({
    queryKey: ['hisa-submission', selectedId],
    queryFn: () => getSubmission(selectedId),
    enabled: !!selectedId,
  })

  const buildMut = useMutation({
    mutationFn: buildAllSubmissions,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hisa-submissions'] }),
  })

  const submitMut = useMutation({
    mutationFn: (id) => submitHISA(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['hisa-submissions'] })
      qc.invalidateQueries({ queryKey: ['hisa-submission', selectedId] })
    },
  })

  const now = new Date()
  const overdue = allSubs.filter(
    (s) => s.deadline_at && new Date(s.deadline_at) < now && s.status === 'pending'
  )
  const pending = allSubs.filter((s) => s.status === 'pending')
  const submitted = allSubs.filter((s) => s.status === 'submitted')
  const accepted = allSubs.filter((s) => s.status === 'accepted')

  const columns = [
    {
      key: 'rule_category',
      label: 'Report Type',
      render: (r) => <span className="text-text-primary text-sm">{CATEGORY_LABELS[r.rule_category] ?? r.rule_category}</span>,
    },
    {
      key: 'horse_chip_id',
      label: 'Chip ID',
      render: (r) => <span className="font-timing text-xs text-text-muted">{r.horse_chip_id ?? '—'}</span>,
    },
    {
      key: 'deadline_at',
      label: 'Deadline',
      render: (r) => {
        if (!r.deadline_at) return <span className="text-text-muted text-xs">—</span>
        const d = new Date(r.deadline_at)
        const late = d < now && r.status === 'pending'
        return <span className={`font-timing text-xs ${late ? 'text-red-400 font-bold' : 'text-text-muted'}`}>{d.toLocaleString()}</span>
      },
    },
    {
      key: 'status',
      label: 'Status',
      render: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: 'actions',
      label: '',
      render: (r) => (
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); setSelectedId(r.id) }}
            className="text-xs font-timing text-accent hover:underline"
          >
            View
          </button>
          {r.status === 'pending' && (
            <button
              onClick={(e) => { e.stopPropagation(); submitMut.mutate(r.id) }}
              disabled={submitMut.isPending}
              className="text-xs font-timing font-bold uppercase tracking-widest border border-accent text-accent hover:bg-amber-950 px-2 py-0.5 transition-colors disabled:opacity-40"
            >
              Submit →
            </button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">Compliance</h1>
            <p className="text-sm text-text-secondary mt-1">
              HISA submission queue — every operational record generates a submission automatically. Review and download JSON payloads for portal upload.
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            onClick={() => buildMut.mutate()}
            disabled={buildMut.isPending}
            className="px-4 py-2 text-sm font-semibold uppercase tracking-widest border border-border text-text-secondary hover:border-accent hover:text-accent transition-colors disabled:opacity-40"
          >
            {buildMut.isPending ? 'Scanning…' : '↺ Sync'}
          </button>
          <span className="text-[10px] text-text-muted font-timing text-right max-w-[160px] leading-tight">
            Scans all records for new submissions not yet in the queue
          </span>
        </div>
      </div>

      {buildMut.data && (
        <p className="text-green-400 text-xs font-timing mb-4">
          ✓ Built {buildMut.data.created} new submission{buildMut.data.created !== 1 ? 's' : ''}
        </p>
      )}

      {/* Urgent action items */}
      {overdue.length > 0 && (
        <div className="border border-red-800 bg-red-950/30 px-4 py-3 mb-4 flex items-start gap-3">
          <span className="text-red-400 text-lg mt-0.5">⚠</span>
          <div>
            <p className="text-red-400 text-sm font-semibold">
              {overdue.length} overdue submission{overdue.length !== 1 ? 's' : ''} — deadline passed
            </p>
            <p className="text-xs text-text-muted font-timing mt-0.5">
              {overdue.map(s => CATEGORY_LABELS[s.rule_category] ?? s.rule_category).join(' · ')}
              {' '}— submit immediately to avoid compliance violation.
            </p>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="flex gap-0 mb-6 border border-border">
        <StatBadge label="Pending" value={pending.length} variant={pending.length > 0 ? 'accent' : 'muted'} />
        <StatBadge label="Overdue" value={overdue.length} variant={overdue.length > 0 ? 'accent' : 'muted'} />
        <StatBadge label="Submitted" value={submitted.length} />
        <StatBadge label="Accepted" value={accepted.length} />
        <StatBadge label="Total" value={allSubs.length} />
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="bg-bg border border-border text-text-primary text-xs px-2 py-1.5 focus:outline-none focus:border-accent"
        >
          <option value="">All statuses</option>
          {['pending', 'submitted', 'accepted', 'rejected', 'needs_correction'].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="bg-bg border border-border text-text-primary text-xs px-2 py-1.5 focus:outline-none focus:border-accent"
        >
          <option value="">All types</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        {(filterStatus || filterCategory) && (
          <button
            onClick={() => { setFilterStatus(''); setFilterCategory('') }}
            className="text-xs font-timing text-text-muted hover:text-accent uppercase tracking-widest"
          >
            Clear
          </button>
        )}
      </div>

      {/* Submissions table */}
      <div className="border border-border bg-surface">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
            Submissions
          </span>
        </div>
        {isLoading ? (
          <p className="px-4 py-6 text-text-muted text-xs font-timing text-center tracking-widest">Loading…</p>
        ) : allSubs.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-text-muted text-sm mb-3">No submissions yet.</p>
            <p className="text-xs text-text-muted font-timing">
              Click <strong className="text-text-primary">↺ Build Missing</strong> to
              scan all operational records and create pending submissions.
            </p>
          </div>
        ) : (
          <DataTable columns={columns} rows={allSubs.map((s) => ({ ...s, id: s.id }))} emptyMessage="" />
        )}
      </div>

      {selectedSub && (
        <PayloadModal
          submission={selectedSub}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
