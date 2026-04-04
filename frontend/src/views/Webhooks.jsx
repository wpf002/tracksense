import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listWebhooks, createWebhook, updateWebhook, deleteWebhook, testWebhook } from '../api/webhooks'

function InlineError({ msg }) {
  if (!msg) return null
  return <p className="text-red-400 text-xs font-timing mt-1">{msg}</p>
}

function StatusBadge({ active }) {
  return active
    ? <span className="text-xs font-timing font-bold uppercase tracking-wide text-green-400">Active</span>
    : <span className="text-xs font-timing font-bold uppercase tracking-wide text-text-muted">Inactive</span>
}

export default function Webhooks() {
  const role = localStorage.getItem('ts_role')
  if (role !== 'admin') return <Navigate to="/live" replace />

  const qc = useQueryClient()

  const [showNew, setShowNew] = useState(false)
  const [newForm, setNewForm] = useState({ name: '', url: '', secret: '' })
  const [newError, setNewError] = useState('')

  const [activeRow, setActiveRow] = useState(null)  // { id, mode: 'edit'|'delete' }
  const [editForm, setEditForm] = useState({})
  const [rowError, setRowError] = useState('')
  const [testResults, setTestResults] = useState({})  // id → { ok, msg }

  const { data: webhooks = [], isLoading } = useQuery({
    queryKey: ['webhooks'],
    queryFn: listWebhooks,
  })

  const createMutation = useMutation({
    mutationFn: createWebhook,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['webhooks'] })
      setShowNew(false)
      setNewForm({ name: '', url: '', secret: '' })
      setNewError('')
    },
    onError: (err) => setNewError(err.response?.data?.detail ?? 'Failed to create webhook'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateWebhook(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['webhooks'] })
      setActiveRow(null)
      setRowError('')
    },
    onError: (err) => setRowError(err.response?.data?.detail ?? 'Update failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteWebhook(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['webhooks'] })
      setActiveRow(null)
    },
    onError: (err) => setRowError(err.response?.data?.detail ?? 'Delete failed'),
  })

  const testMutation = useMutation({
    mutationFn: (id) => testWebhook(id),
    onSuccess: (data, id) => {
      setTestResults((r) => ({ ...r, [id]: { ok: true, msg: `✓ Delivered (200)` } }))
      setTimeout(() => setTestResults((r) => { const n = { ...r }; delete n[id]; return n }), 6000)
    },
    onError: (err, id) => {
      const detail = err.response?.data?.detail ?? err.message ?? 'Request failed'
      setTestResults((r) => ({ ...r, [id]: { ok: false, msg: `✗ Failed: ${detail}` } }))
      setTimeout(() => setTestResults((r) => { const n = { ...r }; delete n[id]; return n }), 6000)
    },
  })

  function handleCreateSubmit(e) {
    e.preventDefault()
    setNewError('')
    if (!newForm.url.startsWith('http://') && !newForm.url.startsWith('https://')) {
      setNewError('URL must start with http:// or https://')
      return
    }
    createMutation.mutate(newForm)
  }

  function openEdit(wh) {
    setActiveRow({ id: wh.id, mode: 'edit' })
    setEditForm({ name: wh.name, url: wh.url, secret: '', active: wh.active })
    setRowError('')
  }

  function handleEditSubmit(id) {
    const updates = {}
    if (editForm.name) updates.name = editForm.name
    if (editForm.url) updates.url = editForm.url
    if (editForm.secret) updates.secret = editForm.secret
    if (editForm.active !== undefined) updates.active = editForm.active
    updateMutation.mutate({ id, data: updates })
  }

  if (isLoading) return <div className="p-6 text-text-muted font-timing text-xs">Loading…</div>

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-0">
          <div className="w-1 self-stretch bg-accent mr-4" />
          <div>
            <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">
              Webhook Subscriptions
            </h1>
            <p className="text-text-muted text-xs font-timing mt-1">
              Push race results to external systems when a race finishes.
            </p>
          </div>
        </div>
        {!showNew && (
          <button
            onClick={() => { setShowNew(true); setNewError('') }}
            className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-amber-700 text-amber-400 hover:bg-amber-950 transition-colors"
          >
            + Add Webhook
          </button>
        )}
      </div>

      <div className="mb-6" />

      {/* New webhook inline form */}
      {showNew && (
        <form
          onSubmit={handleCreateSubmit}
          className="border border-amber-700 bg-surface mb-6 p-4 flex flex-col gap-3"
        >
          <p className="text-xs font-timing font-bold uppercase tracking-widest text-amber-400">
            New Webhook
          </p>
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs uppercase tracking-widest text-text-muted font-timing">Name *</label>
              <input
                required
                placeholder="e.g. GateSmart Production"
                value={newForm.name}
                onChange={(e) => setNewForm((f) => ({ ...f, name: e.target.value }))}
                className="bg-bg border border-border text-text-primary px-3 py-1.5 text-sm font-timing focus:outline-none focus:border-accent"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs uppercase tracking-widest text-text-muted font-timing">URL *</label>
              <input
                required
                placeholder="https://example.com/webhook"
                value={newForm.url}
                onChange={(e) => setNewForm((f) => ({ ...f, url: e.target.value }))}
                className="bg-bg border border-border text-text-primary px-3 py-1.5 text-sm font-timing focus:outline-none focus:border-accent"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs uppercase tracking-widest text-text-muted font-timing">Secret *</label>
              <input
                required
                placeholder="Shared signing secret"
                value={newForm.secret}
                onChange={(e) => setNewForm((f) => ({ ...f, secret: e.target.value }))}
                className="bg-bg border border-border text-text-primary px-3 py-1.5 text-sm font-timing focus:outline-none focus:border-accent"
              />
            </div>
          </div>
          <InlineError msg={newError} />
          <div className="flex gap-2 mt-1">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-1.5 text-xs font-semibold tracking-widest uppercase border border-accent text-accent hover:bg-accent hover:text-bg transition-colors disabled:opacity-40"
            >
              {createMutation.isPending ? 'Creating…' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => { setShowNew(false); setNewError('') }}
              className="px-4 py-1.5 text-xs font-semibold tracking-widest uppercase border border-border text-text-muted hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Table */}
      <div className="border border-border bg-surface">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
            Subscribers — {webhooks.length} configured
          </span>
        </div>

        {webhooks.length === 0 ? (
          <p className="px-4 py-8 text-center text-text-muted text-xs font-timing tracking-wide">
            No webhooks configured. Add one to start pushing race results to external systems.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-text-muted uppercase tracking-widest font-timing">
                <th className="text-left px-4 py-2">Name</th>
                <th className="text-left px-4 py-2">URL</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Created</th>
                <th className="text-left px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {webhooks.map((wh) => {
                const rowActive = activeRow?.id === wh.id
                const mode = rowActive ? activeRow.mode : null

                return (
                  <tr key={wh.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 font-timing text-text-primary">
                      {mode === 'edit'
                        ? <input
                            value={editForm.name}
                            onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                            className="bg-bg border border-border text-text-primary px-2 py-1 text-xs font-timing focus:outline-none focus:border-accent w-36"
                          />
                        : wh.name
                      }
                    </td>
                    <td className="px-4 py-3 text-text-muted text-xs font-timing max-w-xs truncate">
                      {mode === 'edit'
                        ? <input
                            value={editForm.url}
                            onChange={(e) => setEditForm((f) => ({ ...f, url: e.target.value }))}
                            className="bg-bg border border-border text-text-primary px-2 py-1 text-xs font-timing focus:outline-none focus:border-accent w-56"
                          />
                        : wh.url
                      }
                    </td>
                    <td className="px-4 py-3">
                      {mode === 'edit'
                        ? <button
                            type="button"
                            onClick={() => setEditForm((f) => ({ ...f, active: !f.active }))}
                            className={`text-xs font-timing font-bold uppercase tracking-wide px-2 py-1 border transition-colors ${
                              editForm.active
                                ? 'border-green-700 text-green-400 hover:bg-red-950 hover:border-red-700 hover:text-red-400'
                                : 'border-border text-text-muted hover:bg-green-950 hover:border-green-700 hover:text-green-400'
                            }`}
                          >
                            {editForm.active ? 'Active' : 'Inactive'}
                          </button>
                        : <StatusBadge active={wh.active} />
                      }
                    </td>
                    <td className="px-4 py-3 text-text-muted text-xs font-timing">
                      {wh.created_at ? new Date(wh.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {!rowActive && (
                        <div className="flex items-center gap-2 flex-wrap">
                          <button
                            onClick={() => testMutation.mutate(wh.id)}
                            disabled={testMutation.isPending}
                            className="text-xs font-timing uppercase tracking-wide border border-border text-text-muted px-2 py-1 hover:border-green-600 hover:text-green-400 transition-colors disabled:opacity-40"
                          >
                            Test
                          </button>
                          {testResults[wh.id] && (
                            <span className={`text-xs font-timing ${testResults[wh.id].ok ? 'text-green-400' : 'text-red-400'}`}>
                              {testResults[wh.id].msg}
                            </span>
                          )}
                          <button
                            onClick={() => openEdit(wh)}
                            className="text-xs font-timing uppercase tracking-wide border border-border text-text-muted px-2 py-1 hover:border-accent hover:text-accent transition-colors"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => { setActiveRow({ id: wh.id, mode: 'delete' }); setRowError('') }}
                            className="text-xs font-timing uppercase tracking-wide border border-border text-text-muted px-2 py-1 hover:border-red-700 hover:text-red-400 transition-colors"
                          >
                            Delete
                          </button>
                        </div>
                      )}

                      {mode === 'edit' && (
                        <div className="flex flex-col gap-1">
                          <div className="flex flex-col gap-1 mb-1">
                            <label className="text-xs text-text-muted font-timing">Secret (leave blank to keep)</label>
                            <input
                              type="password"
                              placeholder="New secret (optional)"
                              value={editForm.secret}
                              onChange={(e) => setEditForm((f) => ({ ...f, secret: e.target.value }))}
                              className="bg-bg border border-border text-text-primary px-2 py-1 text-xs font-timing focus:outline-none focus:border-accent w-44"
                            />
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleEditSubmit(wh.id)}
                              disabled={updateMutation.isPending}
                              className="text-xs font-timing uppercase tracking-wide border border-accent text-accent px-2 py-1 hover:bg-accent hover:text-bg transition-colors disabled:opacity-40"
                            >
                              {updateMutation.isPending ? '…' : 'Save'}
                            </button>
                            <button
                              onClick={() => { setActiveRow(null); setRowError('') }}
                              className="text-xs font-timing uppercase tracking-wide border border-border text-text-muted px-2 py-1 hover:text-text-primary transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                          <InlineError msg={rowError} />
                        </div>
                      )}

                      {mode === 'delete' && (
                        <div className="flex flex-col gap-1">
                          <p className="text-xs text-red-400 font-timing mb-1">
                            Delete <span className="font-bold">{wh.name}</span>? This cannot be undone.
                          </p>
                          <div className="flex gap-2">
                            <button
                              onClick={() => deleteMutation.mutate(wh.id)}
                              disabled={deleteMutation.isPending}
                              className="text-xs font-timing uppercase tracking-wide border border-red-700 text-red-400 px-2 py-1 hover:bg-red-950 transition-colors disabled:opacity-40"
                            >
                              {deleteMutation.isPending ? '…' : 'Delete'}
                            </button>
                            <button
                              onClick={() => { setActiveRow(null); setRowError('') }}
                              className="text-xs font-timing uppercase tracking-wide border border-border text-text-muted px-2 py-1 hover:text-text-primary transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                          <InlineError msg={rowError} />
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
