import { Outlet } from 'react-router-dom'
import NavLink from './NavLink'
import useRaceStore from '../../store/raceStore'
import LiveDot from '../ui/LiveDot'

export default function Shell() {
  const status = useRaceStore((s) => s.status)
  const connected = useRaceStore((s) => s.connected)

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
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}