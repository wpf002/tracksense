import { useState } from 'react'
import { changePassword } from '../api/auth'

export default function ChangePassword() {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess(false)

    if (form.new_password.length < 8) {
      setError('New password must be at least 8 characters')
      return
    }
    if (form.new_password !== form.confirm_password) {
      setError('New passwords do not match')
      return
    }

    setLoading(true)
    try {
      await changePassword(form.current_password, form.new_password)
      setSuccess(true)
      setForm({ current_password: '', new_password: '', confirm_password: '' })
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to change password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-sm">
      {/* Header */}
      <div className="flex items-center gap-0 mb-6">
        <div className="w-1 self-stretch bg-accent mr-4" />
        <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">
          Change Password
        </h1>
      </div>

      <div className="border border-border bg-surface">
        <div className="px-6 py-4 border-b border-border">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold font-timing">
            Update your password
          </span>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-6 flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs uppercase tracking-widest text-text-muted font-timing">
              Current Password
            </label>
            <input
              type="password"
              required
              value={form.current_password}
              onChange={(e) => setForm((f) => ({ ...f, current_password: e.target.value }))}
              className="bg-bg border border-border text-text-primary px-3 py-2 text-sm font-timing focus:outline-none focus:border-accent"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs uppercase tracking-widest text-text-muted font-timing">
              New Password (min 8)
            </label>
            <input
              type="password"
              required
              value={form.new_password}
              onChange={(e) => setForm((f) => ({ ...f, new_password: e.target.value }))}
              className="bg-bg border border-border text-text-primary px-3 py-2 text-sm font-timing focus:outline-none focus:border-accent"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs uppercase tracking-widest text-text-muted font-timing">
              Confirm New Password
            </label>
            <input
              type="password"
              required
              value={form.confirm_password}
              onChange={(e) => setForm((f) => ({ ...f, confirm_password: e.target.value }))}
              className="bg-bg border border-border text-text-primary px-3 py-2 text-sm font-timing focus:outline-none focus:border-accent"
            />
          </div>

          {error && (
            <p className="text-red-400 text-xs font-timing tracking-wide">{error}</p>
          )}
          {success && (
            <p className="text-green-400 text-xs font-timing tracking-wide">
              Password changed successfully
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-2 px-4 py-2 text-sm font-semibold tracking-widest uppercase border border-accent text-accent hover:bg-accent hover:text-bg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? 'Updating…' : 'Change Password'}
          </button>
        </form>
      </div>
    </div>
  )
}
