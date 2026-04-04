import { useState } from 'react'
import { useNavigate, Outlet, useLocation } from 'react-router-dom'
import NavLink from './NavLink'
import useRaceStore from '../../store/raceStore'
import LiveDot from '../ui/LiveDot'

export default function Shell() {
  const navigate = useNavigate()
  const location = useLocation()
  const status = useRaceStore((s) => s.status)
  const connected = useRaceStore((s) => s.connected)

  const username = localStorage.getItem('ts_username') ?? ''
  const role = localStorage.getItem('ts_role') ?? ''

  const isSettingsActive = location.pathname.startsWith('/settings') || location.pathname.startsWith('/admin')
  const [settingsOpen, setSettingsOpen] = useState(isSettingsActive)

  function handleLogout() {
    localStorage.removeItem('ts_token')
    localStorage.removeItem('ts_role')
    localStorage.removeItem('ts_username')
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-full min-h-screen bg-bg">
      {/* Sidebar */}
      <aside className="w-52 shrink-0 bg-surface border-r border-border flex flex-col">
        {/* Logo */}
        <div className="px-4 py-5 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="text-accent font-timing font-bold text-lg tracking-tighter">
              TRACK<span className="text-text-primary">SENSE</span>
            </span>
          </div>
          <p className="text-text-muted text-xs mt-1 tracking-widest uppercase">
            v3.0.0
          </p>
        </div>

        {/* Nav items */}
        <nav className="flex flex-col gap-0.5 py-4 flex-1">
          <NavLink to="/live">
            {status === 'running' && <LiveDot />}
            Live Race
          </NavLink>
          <NavLink to="/results">Results</NavLink>
          <NavLink to="/horses">Horses</NavLink>
          <NavLink to="/builder">Race Builder</NavLink>

          <div className="mt-3 border-t border-border pt-3">
            <button
              onClick={() => setSettingsOpen((o) => !o)}
              className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium tracking-wide uppercase transition-colors text-text-muted hover:text-text-primary border-l-2 border-transparent pl-[10px]"
            >
              <span>Settings</span>
              <span className="text-xs opacity-60">{settingsOpen ? '▲' : '▼'}</span>
            </button>
            {settingsOpen && (
              <div className="pl-3">
                <NavLink to="/settings/password">Change Password</NavLink>
                {role === 'admin' && (
                  <NavLink to="/admin/users">User Management</NavLink>
                )}
              </div>
            )}
          </div>
        </nav>

        {/* WS connection indicator */}
        <div className="px-4 py-3 border-t border-border">
          <div className="flex items-center gap-2">
            <span
              className={[
                'w-2 h-2 rounded-full',
                connected ? 'bg-green-500' : 'bg-text-muted',
              ].join(' ')}
            />
            <span className="text-xs text-text-muted font-timing">
              {connected ? 'WS CONNECTED' : 'WS OFFLINE'}
            </span>
          </div>
        </div>

        {/* User info + logout */}
        <div className="px-4 py-3 border-t border-border">
          <p className="text-xs text-text-primary font-timing truncate">{username}</p>
          <span
            className={`text-xs font-timing font-bold uppercase tracking-wide px-1 py-0.5 border ${
              role === 'admin'
                ? 'border-amber-700 text-amber-400'
                : 'border-border text-text-muted'
            }`}
          >
            {role || 'viewer'}
          </span>
          <button
            onClick={handleLogout}
            className="mt-2 w-full text-xs font-timing tracking-widest uppercase text-text-muted border border-border py-1 hover:border-red-700 hover:text-red-400 transition-colors"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}