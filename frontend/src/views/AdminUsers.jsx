import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listUsers, createUser, updateUser, resetPassword, deleteUser } from '../api/auth'

const ROLES = ['admin', 'steward', 'trainer', 'vet', 'viewer']

const ROLE_BADGE = {
  admin:   'border-amber-700 bg-amber-950 text-amber-400',
  steward: 'border-blue-700 bg-blue-950 text-blue-400',
  trainer: 'border-green-700 bg-green-950 text-green-400',
  vet:     'border-purple-700 bg-purple-950 text-purple-400',
  viewer:  'border-border bg-surface text-text-muted',
}

function RoleBadge({ role }) {
  return (
    <span className={`text-xs font-timing font-bold uppercase tracking-wide px-1.5 py-0.5 border ${ROLE_BADGE[role] ?? ROLE_BADGE.viewer}`}>
      {role}
    </span>
  )
}

function StatusBadge({ active }) {
  return active
    ? <span className="text-xs font-timing font-bold uppercase tracking-wide text-green-400">Active</span>
    : <span className="text-xs font-timing font-bold uppercase tracking-wide text-red-400">Inactive</span>
}

function InlineError({ msg }) {
  if (!msg) return null
  return <p className="text-red-400 text-xs font-timing mt-1">{msg}</p>
}

export default function AdminUsers() {
  const role = localStorage.getItem('ts_role')
  const myUsername = localStorage.getItem('ts_username')

  if (role !== 'admin') return <Navigate to="/live" replace />

  const qc = useQueryClient()

  // ── New user form state ──────────────────────────────────────────
  const [showNew, setShowNew] = useState(false)
  const [newForm, setNewForm] = useState({ username: '', full_name: '', password: '', role: 'viewer' })
  const [newError, setNewError] = useState('')

  // ── Per-row inline state: 'edit' | 'reset' | 'delete' | null ────
  const [activeRow, setActiveRow] = useState(null)   // { id, mode }
  const [editForm, setEditForm] = useState({})
  const [resetPw, setResetPw] = useState('')
  const [rowError, setRowError] = useState('')

  const { data: users = [], isLoading, error } = useQuery({
    queryKey: ['admin-users'],
    queryFn: listUsers,
  })

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] })
      setShowNew(false)
      setNewForm({ username: '', full_name: '', password: '', role: 'viewer' })
      setNewError('')
    },
    onError: (err) => setNewError(err.response?.data?.detail ?? 'Failed to create user'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateUser(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] })
      setActiveRow(null)
      setRowError('')
    },
    onError: (err) => setRowError(err.response?.data?.detail ?? 'Update failed'),
  })

  const resetMutation = useMutation({
    mutationFn: ({ id, pw }) => resetPassword(id, pw),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] })
      setActiveRow(null)
      setResetPw('')
      setRowError('')
    },
    onError: (err) => setRowError(err.response?.data?.detail ?? 'Reset failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => deleteUser(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] })
      setActiveRow(null)
      setRowError('')
    },
    onError: (err) => setRowError(err.response?.data?.detail ?? 'Delete failed'),
  })

  function openEdit(user) {
    setActiveRow({ id: user.id, mode: 'edit' })
    setEditForm({ full_name: user.full_name ?? '', role: user.role, active: user.active })
    setRowError('')
  }

  function openReset(user) {
    setActiveRow({ id: user.id, mode: 'reset' })
    setResetPw('')
    setRowError('')
  }

  function openDelete(user) {
    setActiveRow({ id: user.id, mode: 'delete' })
    setRowError('')
  }

  function handleCreateSubmit(e) {
    e.preventDefault()
    setNewError('')
    if (newForm.password.length < 8) {
      setNewError('Password must be at least 8 characters')
      return
    }
    createMutation.mutate(newForm)
  }

  function handleEditSubmit(userId) {
    const updates = {}
    if (editForm.full_name !== undefined) updates.full_name = editForm.full_name || null
    if (editForm.role !== undefined) updates.role = editForm.role
    if (editForm.active !== undefined) updates.active = editForm.active
    updateMutation.mutate({ id: userId, data: updates })
  }

  function handleResetSubmit(userId) {
    if (resetPw.length < 8) {
      setRowError('Password must be at least 8 characters')
      return
    }
    resetMutation.mutate({ id: userId, pw: resetPw })
  }

  if (isLoading) return <div className="p-6 text-text-muted font-timing text-xs">Loading…</div>
  if (error) return <div className="p-6 text-red-400 font-timing text-xs">Failed to load users</div>

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-0">
          <div className="w-1 self-stretch bg-accent mr-4" />
          <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">
            User Management
          </h1>
        </div>
        {!showNew && (
          <button
            onClick={() => { setShowNew(true); setNewError('') }}
            className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-amber-700 text-amber-400 hover:bg-amber-950 transition-colors"
          >
            + New User
          </button>
        )}
      </div>

      {/* New user inline form */}
      {showNew && (
        <form
          onSubmit={handleCreateSubmit}
          className="border border-amber-700 bg-surface mb-6 p-4 flex flex-col gap-3"
        >
          <p className="text-xs font-timing font-bold uppercase tracking-widest text-amber-400">
            New User
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs uppercase tracking-widest text-text-muted font-timing">Username *</label>
              <input
                required
                value={newForm.username}
                onChange={(e) => setNewForm((f) => ({ ...f, username: e.target.value }))}
                className="bg-bg border border-border text-text-primary px-3 py-1.5 text-sm font-timing focus:outline-none focus:border-accent"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs uppercase tracking-widest text-text-muted font-timing">Full Name</label>
              <input
                value={newForm.full_name}
                onChange={(e) => setNewForm((f) => ({ ...f, full_name: e.target.value }))}
                className="bg-bg border border-border text-text-primary px-3 py-1.5 text-sm font-timing focus:outline-none focus:border-accent"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs uppercase tracking-widest text-text-muted font-timing">Password * (min 8)</label>
              <input
                type="password"
                required
                value={newForm.password}
                onChange={(e) => setNewForm((f) => ({ ...f, password: e.target.value }))}
                className="bg-bg border border-border text-text-primary px-3 py-1.5 text-sm font-timing focus:outline-none focus:border-accent"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs uppercase tracking-widest text-text-muted font-timing">Role</label>
              <select
                value={newForm.role}
                onChange={(e) => setNewForm((f) => ({ ...f, role: e.target.value }))}
                className="bg-bg border border-border text-text-primary px-3 py-1.5 text-sm font-timing focus:outline-none focus:border-accent"
              >
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>
          <InlineError msg={newError} />
          <div className="flex gap-2 mt-1">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-1.5 text-xs font-semibold tracking-widest uppercase border border-accent text-accent hover:bg-accent hover:text-bg transition-colors disabled:opacity-40"
            >
              {createMutation.isPending ? 'Creating…' : 'Create User'}
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

      {/* Users table */}
      <div className="border border-border bg-surface">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
            Users — {users.length} total
          </span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-text-muted uppercase tracking-widest font-timing">
              <th className="text-left px-4 py-2">Username</th>
              <th className="text-left px-4 py-2">Full Name</th>
              <th className="text-left px-4 py-2">Role</th>
              <th className="text-left px-4 py-2">Status</th>
              <th className="text-left px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const isMe = user.username === myUsername
              const rowActive = activeRow?.id === user.id
              const mode = rowActive ? activeRow.mode : null

              return (
                <tr
                  key={user.id}
                  className={[
                    'border-b border-border last:border-0',
                    isMe ? 'bg-surface-2' : '',
                  ].join(' ')}
                >
                  <td className="px-4 py-3 font-timing text-text-primary">
                    {user.username}
                    {isMe && (
                      <span className="ml-2 text-xs text-text-muted font-timing">(you)</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {mode === 'edit'
                      ? <input
                          value={editForm.full_name}
                          onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))}
                          className="bg-bg border border-border text-text-primary px-2 py-1 text-xs font-timing focus:outline-none focus:border-accent w-36"
                        />
                      : user.full_name ?? '—'
                    }
                  </td>
                  <td className="px-4 py-3">
                    {mode === 'edit'
                      ? <select
                          value={editForm.role}
                          onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value }))}
                          className="bg-bg border border-border text-text-primary px-2 py-1 text-xs font-timing focus:outline-none focus:border-accent"
                        >
                          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                        </select>
                      : <RoleBadge role={user.role} />
                    }
                  </td>
                  <td className="px-4 py-3">
                    {mode === 'edit'
                      ? <button
                          onClick={() => setEditForm((f) => ({ ...f, active: !f.active }))}
                          className={`text-xs font-timing font-bold uppercase tracking-wide px-2 py-1 border transition-colors ${
                            editForm.active
                              ? 'border-green-700 text-green-400 hover:bg-red-950 hover:border-red-700 hover:text-red-400'
                              : 'border-red-700 text-red-400 hover:bg-green-950 hover:border-green-700 hover:text-green-400'
                          }`}
                        >
                          {editForm.active ? 'Active' : 'Inactive'}
                        </button>
                      : <StatusBadge active={user.active} />
                    }
                  </td>
                  <td className="px-4 py-3">
                    {isMe ? null : (
                      <>
                        {/* Normal action buttons */}
                        {!rowActive && (
                          <div className="flex gap-2">
                            <button
                              onClick={() => openEdit(user)}
                              className="text-xs font-timing uppercase tracking-wide border border-border text-text-muted px-2 py-1 hover:border-accent hover:text-accent transition-colors"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => openReset(user)}
                              className="text-xs font-timing uppercase tracking-wide border border-border text-text-muted px-2 py-1 hover:border-blue-600 hover:text-blue-400 transition-colors"
                            >
                              Reset PW
                            </button>
                            <button
                              onClick={() => openDelete(user)}
                              className="text-xs font-timing uppercase tracking-wide border border-border text-text-muted px-2 py-1 hover:border-red-700 hover:text-red-400 transition-colors"
                            >
                              Delete
                            </button>
                          </div>
                        )}

                        {/* Edit inline actions */}
                        {mode === 'edit' && (
                          <div className="flex flex-col gap-1">
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleEditSubmit(user.id)}
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

                        {/* Reset password inline */}
                        {mode === 'reset' && (
                          <div className="flex flex-col gap-1">
                            <div className="flex gap-2 items-center">
                              <input
                                type="password"
                                placeholder="New password (min 8)"
                                value={resetPw}
                                onChange={(e) => setResetPw(e.target.value)}
                                className="bg-bg border border-border text-text-primary px-2 py-1 text-xs font-timing focus:outline-none focus:border-blue-500 w-44"
                              />
                              <button
                                onClick={() => handleResetSubmit(user.id)}
                                disabled={resetMutation.isPending}
                                className="text-xs font-timing uppercase tracking-wide border border-blue-700 text-blue-400 px-2 py-1 hover:bg-blue-950 transition-colors disabled:opacity-40"
                              >
                                {resetMutation.isPending ? '…' : 'Confirm'}
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

                        {/* Delete confirmation inline */}
                        {mode === 'delete' && (
                          <div className="flex flex-col gap-1">
                            <p className="text-xs text-red-400 font-timing mb-1">
                              Delete <span className="font-bold">{user.username}</span>? This cannot be undone.
                            </p>
                            <div className="flex gap-2">
                              <button
                                onClick={() => deleteMutation.mutate(user.id)}
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
                      </>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
