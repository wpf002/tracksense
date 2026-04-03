import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/auth'

export default function Login() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(username, password)
      localStorage.setItem('ts_token', data.access_token)
      localStorage.setItem('ts_role', data.role)
      localStorage.setItem('ts_username', data.username)
      navigate('/live', { replace: true })
    } catch {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <div className="w-full max-w-sm">
        {/* Wordmark */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-1">
            <span className="text-accent font-timing font-bold text-2xl tracking-tighter">
              TRACK<span className="text-text-primary">SENSE</span>
            </span>
          </div>
          <p className="text-text-muted text-xs mt-1 tracking-widest uppercase">
            v3.0.0
          </p>
        </div>

        {/* Panel */}
        <div className="border border-border bg-surface">
          <div className="px-6 py-4 border-b border-border">
            <h1 className="text-xs font-semibold uppercase tracking-widest text-text-muted">
              System Login
            </h1>
          </div>

          <form onSubmit={handleSubmit} className="px-6 py-6 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs uppercase tracking-widest text-text-muted font-timing">
                Username
              </label>
              <input
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="bg-bg border border-border text-text-primary px-3 py-2 text-sm font-timing focus:outline-none focus:border-accent"
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs uppercase tracking-widest text-text-muted font-timing">
                Password
              </label>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="bg-bg border border-border text-text-primary px-3 py-2 text-sm font-timing focus:outline-none focus:border-accent"
                required
              />
            </div>

            {error && (
              <p className="text-red-400 text-xs font-timing tracking-wide">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-2 px-4 py-2 text-sm font-semibold tracking-widest uppercase border border-accent text-accent hover:bg-accent hover:text-bg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}