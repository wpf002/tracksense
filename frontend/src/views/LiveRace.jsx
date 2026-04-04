import { useEffect, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import useRaceStore from '../store/raceStore'
import { getRaceStatus, getRaceState, armRace, resetRace, simulateRace, pauseSimulation, resumeSimulation } from '../api/races'
import { getVenue } from '../api/venues'
import DataTable from '../components/ui/DataTable'
import TimingDisplay, { formatMs } from '../components/ui/TimingDisplay'
import StatBadge from '../components/ui/StatBadge'
import LiveDot from '../components/ui/LiveDot'
import TrackMap from '../components/ui/TrackMap'

const STATUS_COLORS = {
  idle: 'text-text-muted',
  armed: 'text-yellow-400',
  running: 'text-green-400',
  paused: 'text-blue-400',
  finished: 'text-accent',
}

function StatusBadge({ status }) {
  return (
    <span
      className={[
        'text-xs font-timing font-bold tracking-widest uppercase px-2 py-0.5 border',
        status === 'running'
          ? 'border-green-700 bg-green-950 text-green-400'
          : status === 'armed'
          ? 'border-yellow-700 bg-yellow-950 text-yellow-400'
          : status === 'paused'
          ? 'border-blue-700 bg-blue-950 text-blue-400'
          : status === 'finished'
          ? 'border-amber-700 bg-amber-950 text-accent'
          : 'border-border bg-surface text-text-muted',
      ].join(' ')}
    >
      {status}
    </span>
  )
}

export default function LiveRace() {
  const qc = useQueryClient()
  const { status, horses, lastEventTime, connected, setStatus, setHorses, setLastEvent, setConnected } =
    useRaceStore()

  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const reconnectDelay = useRef(1000)
  const clientRaceStartAt = useRef(null)
  const [highlightedHorseId, setHighlightedHorseId] = useState(null)
  const [elapsedMs, setElapsedMs] = useState(null)
  const [elapsedSince, setElapsedSince] = useState(null)
  const [armError, setArmError] = useState(null)
  const [resetError, setResetError] = useState(null)
  const [simulateError, setSimulateError] = useState(null)
  const [pauseError, setPauseError] = useState(null)
  const [venueId, setVenueId] = useState(null)

  // Poll /race/status every 2s
  useQuery({
    queryKey: ['race-status'],
    queryFn: async () => {
      const data = await getRaceStatus()
      setStatus(data.status)
      if (data.status === 'running' && data.elapsed_ms != null) {
        clientRaceStartAt.current = Date.now() - data.elapsed_ms
        setElapsedMs(data.elapsed_ms)
        setElapsedSince(Date.now())
      } else if (data.status === 'paused') {
        // Freeze display: null the live anchor, store backend's frozen elapsed
        clientRaceStartAt.current = null
        setElapsedMs(data.elapsed_ms)
        setElapsedSince(null)
      } else if (data.status === 'finished') {
        clientRaceStartAt.current = null
        setElapsedMs((prev) => prev ?? data.elapsed_ms ?? null)
        setElapsedSince(null)
      } else if (data.status === 'idle') {
        clientRaceStartAt.current = null
        setElapsedMs(null)
        setElapsedSince(null)
      }
      // Do NOT reset elapsed on 'armed' — race threads may already be running
      return data
    },
    refetchInterval: 2000,
  })

  // Poll /race/state every 3s for horse positions
  useQuery({
    queryKey: ['race-state'],
    queryFn: async () => {
      const data = await getRaceState()
      if (data.horses) setHorses(data.horses)
      if (data.venue_id) setVenueId(data.venue_id)
      return data
    },
    refetchInterval: 3000,
  })

  const { data: venueData } = useQuery({
    queryKey: ['venue', venueId],
    queryFn: () => getVenue(venueId),
    enabled: !!venueId,
  })

  // Live elapsed timer when running
  useEffect(() => {
    if (status !== 'running' || elapsedMs == null || elapsedSince == null) return
    const interval = setInterval(() => {
      // no-op: re-render triggers via the interval below
    }, 100)
    return () => clearInterval(interval)
  }, [status, elapsedMs, elapsedSince])

  // Compute displayed elapsed — ref-based so it's immune to React batching
  // and doesn't reset when status briefly passes through 'armed'.
  const displayedElapsed = clientRaceStartAt.current != null
    ? Date.now() - clientRaceStartAt.current
    : (elapsedMs != null && elapsedSince != null
        ? elapsedMs + (Date.now() - elapsedSince)
        : elapsedMs)

  // Force re-render every 100ms when running
  const [, setTick] = useState(0)
  useEffect(() => {
    if (status !== 'running') return
    const id = setInterval(() => setTick((t) => t + 1), 100)
    return () => clearInterval(id)
  }, [status])

  // WebSocket with exponential backoff reconnect
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(`ws://${window.location.host}/ws/race`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      reconnectDelay.current = 1000
    }

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        if (msg.type === 'gate_event') {
          const data = msg.data
          setLastEvent(data)
          setHighlightedHorseId(data.tag_id)
          setTimeout(() => setHighlightedHorseId(null), 2000)
          if (!data.race_finished) {
            setStatus('running')
            // Anchor the client clock once from the first gate event so all
            // horses animate from t=0 rather than jumping to this event's time.
            if (clientRaceStartAt.current == null && data.elapsed_ms != null) {
              clientRaceStartAt.current = Date.now() - data.elapsed_ms
            }
          }
          // Refresh horse positions after each event
          qc.invalidateQueries({ queryKey: ['race-state'] })
          if (data.race_finished) {
            setStatus('finished')
            clientRaceStartAt.current = null
            setElapsedMs(data.elapsed_ms ?? null)
            setElapsedSince(null)
            qc.invalidateQueries({ queryKey: ['race-status'] })
          }
        }
      } catch (_) {
        // ignore parse errors
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      reconnectTimer.current = setTimeout(() => {
        connect()
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
      }, reconnectDelay.current)
    }
  }, [qc, setConnected, setLastEvent, setStatus])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const armMutation = useMutation({
    mutationFn: armRace,
    onSuccess: () => {
      setArmError(null)
      qc.invalidateQueries({ queryKey: ['race-status'] })
    },
    onError: (err) => setArmError(err.response?.data?.detail ?? 'Arm failed'),
  })

  const resetMutation = useMutation({
    mutationFn: resetRace,
    onSuccess: () => {
      setResetError(null)
      clientRaceStartAt.current = null
      setElapsedMs(null)
      setElapsedSince(null)
      setHorses([])
      setStatus('idle')
      qc.invalidateQueries({ queryKey: ['race-status'] })
      qc.invalidateQueries({ queryKey: ['race-state'] })
    },
    onError: (err) => setResetError(err.response?.data?.detail ?? 'Reset failed'),
  })

  const simulateMutation = useMutation({
    mutationFn: simulateRace,
    onSuccess: () => {
      setSimulateError(null)
      // Clear the old clock so it re-anchors on the first incoming gate event
      clientRaceStartAt.current = null
      setElapsedMs(null)
      setElapsedSince(null)
      qc.invalidateQueries({ queryKey: ['race-status'] })
    },
    onError: (err) => setSimulateError(err.response?.data?.detail ?? 'Simulate failed'),
  })

  const pauseMutation = useMutation({
    mutationFn: pauseSimulation,
    onSuccess: () => {
      setPauseError(null)
      clientRaceStartAt.current = null
      setElapsedSince(null)
      setStatus('paused')
      qc.invalidateQueries({ queryKey: ['race-status'] })
    },
    onError: (err) => setPauseError(err.response?.data?.detail ?? 'Pause failed'),
  })

  const resumeMutation = useMutation({
    mutationFn: resumeSimulation,
    onSuccess: () => {
      setPauseError(null)
      if (elapsedMs != null) {
        clientRaceStartAt.current = Date.now() - elapsedMs
        setElapsedSince(Date.now())
      }
      setStatus('running')
      qc.invalidateQueries({ queryKey: ['race-status'] })
    },
    onError: (err) => setPauseError(err.response?.data?.detail ?? 'Resume failed'),
  })

  // Sort horses: finished first (by position), then by gates_passed desc
  const sortedHorses = [...horses].sort((a, b) => {
    if (a.finish_position != null && b.finish_position != null)
      return a.finish_position - b.finish_position
    if (a.finish_position != null) return -1
    if (b.finish_position != null) return 1
    return (b.gates_passed ?? 0) - (a.gates_passed ?? 0)
  })

  const columns = [
    {
      key: 'rank',
      label: 'Rank',
      className: 'w-14',
      render: (row, i) => (
        <span className="font-timing font-bold text-accent">
          {row.finish_position ?? '—'}
        </span>
      ),
    },
    {
      key: 'saddle_cloth',
      label: '#',
      className: 'w-12',
      render: (row) => (
        <span className="font-timing font-bold text-text-primary">
          {row.saddle_cloth}
        </span>
      ),
    },
    {
      key: 'display_name',
      label: 'Horse',
      render: (row) => (
        <span className="font-medium">{row.display_name}</span>
      ),
    },
    {
      key: 'current_gate',
      label: 'Last Gate',
      render: (row) => (
        <span className="text-text-muted text-xs font-timing">
          {row.current_gate ?? '—'}
        </span>
      ),
    },
    {
      key: 'elapsed',
      label: 'Elapsed',
      render: (row) => {
        const lastEvent = row.events?.[row.events.length - 1]
        return <TimingDisplay ms={lastEvent?.elapsed_ms} />
      },
    },
    {
      key: 'gates_passed',
      label: 'Gates',
      className: 'w-16 text-right',
      render: (row) => (
        <span className="font-timing text-text-muted">
          {row.gates_passed ?? 0}
        </span>
      ),
    },
  ]

  // Map horses to include id for highlight tracking
  const tableRows = sortedHorses.map((h) => ({ ...h, id: h.horse_id }))

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">
            Live Race
          </h1>
          <StatusBadge status={status} />
          {status === 'running' && <LiveDot />}
        </div>

        <div className="flex items-center gap-3">
          {status === 'finished' && (
            <Link
              to="/results"
              className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase bg-accent text-bg hover:bg-accent-dim transition-colors"
            >
              View Results →
            </Link>
          )}
          <button
            onClick={() => simulateMutation.mutate()}
            disabled={simulateMutation.isPending || status === 'running' || status === 'paused' || status === 'finished'}
            className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-green-700 text-green-400 hover:bg-green-950 transition-colors disabled:opacity-40"
          >
            {simulateMutation.isPending ? 'Starting…' : 'SIMULATE'}
          </button>
          {(status === 'running' || status === 'paused') && (
            <button
              onClick={() => status === 'paused' ? resumeMutation.mutate() : pauseMutation.mutate()}
              disabled={pauseMutation.isPending || resumeMutation.isPending}
              className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-blue-700 text-blue-400 hover:bg-blue-950 transition-colors disabled:opacity-40"
            >
              {pauseMutation.isPending || resumeMutation.isPending
                ? '…'
                : status === 'paused'
                ? 'RESUME'
                : 'PAUSE'}
            </button>
          )}
          <button
            onClick={() => armMutation.mutate()}
            disabled={armMutation.isPending}
            className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-yellow-700 text-yellow-400 hover:bg-yellow-950 transition-colors disabled:opacity-40"
          >
            ARM
          </button>
          <button
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
            className="px-4 py-1.5 text-sm font-semibold tracking-widest uppercase border border-border text-text-muted hover:border-red-700 hover:text-red-400 transition-colors disabled:opacity-40"
          >
            RESET
          </button>
        </div>
      </div>

      {/* Errors */}
      {simulateError && (
        <p className="text-red-400 text-xs mb-3 font-timing">{simulateError}</p>
      )}
      {pauseError && (
        <p className="text-red-400 text-xs mb-3 font-timing">{pauseError}</p>
      )}
      {armError && (
        <p className="text-red-400 text-xs mb-3 font-timing">{armError}</p>
      )}
      {resetError && (
        <p className="text-red-400 text-xs mb-3 font-timing">{resetError}</p>
      )}

      {/* Stats bar */}
      <div className="flex gap-0 mb-6 border border-border">
        <StatBadge
          label="Status"
          value={status?.toUpperCase()}
          variant={status === 'running' ? 'accent' : 'muted'}
        />
        <StatBadge
          label="Elapsed"
          value={
            <TimingDisplay
              ms={displayedElapsed}
              className="text-base"
            />
          }
        />
        <StatBadge label="Runners" value={horses.length} />
        <StatBadge
          label="Finished"
          value={horses.filter((h) => h.finish_position != null).length}
        />
        <StatBadge
          label="Remaining"
          value={horses.filter((h) => h.finish_position == null).length}
        />
      </div>

      {/* Track map */}
      {horses.length > 0 && venueData && (
        <div className="border border-border mb-6">
          <div className="px-4 py-2 border-b border-border bg-surface">
            <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
              Track — {venueData.name}
            </span>
          </div>
          <TrackMap
            horses={horses}
            totalDistanceM={venueData.total_distance_m}
            gates={venueData.gates ?? []}
            currentElapsedMs={displayedElapsed ?? 0}
          />
        </div>
      )}

      {/* Race table */}
      <div className="border border-border bg-surface">
        <div className="px-4 py-2 border-b border-border">
          <span className="text-xs text-text-muted uppercase tracking-widest font-semibold">
            Field
          </span>
        </div>
        <DataTable
          columns={columns}
          rows={tableRows}
          highlightedRowId={highlightedHorseId}
          emptyMessage="No race registered — use Race Builder to set up a field"
        />
      </div>

      {/* Idle hint */}
      {status === 'idle' && horses.length === 0 && (
        <p className="mt-4 text-text-muted text-xs font-timing text-center tracking-widest">
          NO ACTIVE RACE — GO TO{' '}
          <Link to="/builder" className="text-accent hover:underline">
            RACE BUILDER
          </Link>{' '}
          TO REGISTER A FIELD
        </p>
      )}
    </div>
  )
}