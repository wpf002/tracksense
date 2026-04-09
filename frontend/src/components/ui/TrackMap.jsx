
import { useEffect, useRef, useState, useCallback } from 'react'

const SILK_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#14b8a6',
  '#6366f1', '#f43f5e', '#16a34a', '#d97706', '#8b5cf6',
  '#0284c7', '#ea580c', '#059669', '#7c3aed', '#be185d',
]

// ─── Oval constants (mirrors backend arc-length parameterisation) ─────────────
const W = 800, H = 310
const cx = W / 2, cy = H / 2
const OUTER_RX = 300, OUTER_RY = 118
const TRACK_W = 26
const INNER_RX = OUTER_RX - TRACK_W, INNER_RY = OUTER_RY - TRACK_W
const MID_RX   = OUTER_RX - TRACK_W / 2, MID_RY = OUTER_RY - TRACK_W / 2

// Arc-length LUT — built once at module load
const ARC_STEPS = 720
const _arcTable = (() => {
  const t = [{ angle: 0, arc: 0 }]
  let total = 0
  const da = (2 * Math.PI) / ARC_STEPS
  for (let i = 1; i <= ARC_STEPS; i++) {
    const mid = (i - 0.5) * da
    total += Math.sqrt((MID_RX * Math.cos(mid)) ** 2 + (MID_RY * Math.sin(mid)) ** 2) * da
    t.push({ angle: i * da, arc: total })
  }
  return { table: t, total }
})()

function progressToAngle(p) {
  const target = (p % 1) * _arcTable.total
  let lo = 0, hi = _arcTable.table.length - 1
  while (lo < hi - 1) {
    const m = (lo + hi) >> 1
    if (_arcTable.table[m].arc <= target) lo = m; else hi = m
  }
  const t0 = _arcTable.table[lo], t1 = _arcTable.table[hi]
  const f = t0.arc === t1.arc ? 0 : (target - t0.arc) / (t1.arc - t0.arc)
  return Math.PI / 2 - (t0.angle + f * (t1.angle - t0.angle))
}

function ovalPt(p, rx, ry) {
  const a = progressToAngle(p)
  return { x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a), a }
}

function ovalNormal(a, rx, ry) {
  const nx = Math.cos(a) / rx, ny = Math.sin(a) / ry
  const mag = Math.sqrt(nx * nx + ny * ny)
  return { nx: nx / mag, ny: ny / mag }
}

// ─── Distance interpolation ───────────────────────────────────────────────────
function interpolateDist(horse, nowMs, totalM) {
  const events = horse.events ?? []
  if (events.length === 0) return nowMs > 0 ? Math.min(0.018 * nowMs, totalM) : 0
  const last = events[events.length - 1]
  if (horse.finish_position != null) return last.distance_m
  let speed = 0
  if (events.length >= 2) {
    const prev = events[events.length - 2]
    const dt = last.elapsed_ms - prev.elapsed_ms
    if (dt > 0) speed = (last.distance_m - prev.distance_m) / dt
  } else if (last.elapsed_ms > 0 && last.distance_m > 0) {
    speed = last.distance_m / last.elapsed_ms
  } else {
    speed = 0.018
  }
  if (speed <= 0) return last.distance_m
  return Math.min(last.distance_m + speed * Math.max(nowMs - last.elapsed_ms, 0), totalM)
}

// ─── Oval SVG canvas renderer ─────────────────────────────────────────────────
// Renders directly to a <canvas> via rAF for smooth 60fps animation.
function OvalCanvas({ horses, totalDistanceM, gates, currentElapsedMs, trackPath, fullscreen }) {
  const canvasRef = useRef(null)
  const rafRef = useRef(null)
  const [hovered, setHovered] = useState(null)

  // Build sorted gates
  const sortedGates = [...gates].sort((a, b) => a.distance_m - b.distance_m)
  const laneCount = Math.min(horses.length, 6)

  // Canvas device-pixel scaling
  const scale = fullscreen ? 1.5 : 1

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const sw = W * scale, sh = H * scale
    canvas.width  = sw * dpr
    canvas.height = sh * dpr
    canvas.style.width  = `${sw}px`
    canvas.style.height = `${sh}px`
    ctx.scale(dpr * scale, dpr * scale)

    // Background
    ctx.fillStyle = '#0a0a0a'
    ctx.fillRect(0, 0, W, H)

    // ── Track surface ──
    ctx.lineWidth = TRACK_W
    ctx.strokeStyle = '#1c1c1c'
    ctx.beginPath()
    ctx.ellipse(cx, cy, OUTER_RX, OUTER_RY, 0, 0, 2 * Math.PI)
    ctx.stroke()

    // Inner fill
    ctx.fillStyle = '#0f0f0f'
    ctx.beginPath()
    ctx.ellipse(cx, cy, INNER_RX - 1, INNER_RY - 1, 0, 0, 2 * Math.PI)
    ctx.fill()

    // ── Track path overlay (if available) ──
    if (trackPath && trackPath.length >= 3) {
      ctx.strokeStyle = 'rgba(255,255,255,0.04)'
      ctx.lineWidth = TRACK_W + 2
      ctx.beginPath()
      const first = trackPath[0]
      ctx.moveTo(first.x * W, first.y * H)
      for (let i = 1; i < trackPath.length; i++) {
        ctx.lineTo(trackPath[i].x * W, trackPath[i].y * H)
      }
      ctx.closePath()
      ctx.stroke()
    }

    // Outer rail
    ctx.strokeStyle = '#383838'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.ellipse(cx, cy, OUTER_RX, OUTER_RY, 0, 0, 2 * Math.PI)
    ctx.stroke()

    // Inner rail
    ctx.beginPath()
    ctx.ellipse(cx, cy, INNER_RX, INNER_RY, 0, 0, 2 * Math.PI)
    ctx.stroke()

    // ── Gate markers ──
    sortedGates.forEach(gate => {
      const p = gate.distance_m / totalDistanceM
      const outer = ovalPt(p, OUTER_RX + 6, OUTER_RY + 6)
      const inner = ovalPt(p, INNER_RX - 6, INNER_RY - 6)
      const lbl   = ovalPt(p, OUTER_RX + 20, OUTER_RY + 20)
      const abbr  = gate.is_finish ? 'FIN'
        : gate.name.replace(/Furlong\s*/i, 'F').replace(/Start/i, 'S')
      const color = gate.is_finish ? '#f59e0b' : '#555'

      ctx.strokeStyle = color
      ctx.lineWidth = gate.is_finish ? 2.5 : 1
      if (gate.is_finish) {
        ctx.setLineDash([5, 3])
      }
      ctx.beginPath()
      ctx.moveTo(outer.x, outer.y)
      ctx.lineTo(inner.x, inner.y)
      ctx.stroke()
      ctx.setLineDash([])

      ctx.fillStyle = gate.is_finish ? '#f59e0b' : '#555'
      ctx.font = '7px monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(abbr, lbl.x, lbl.y)

      // Hover tooltip
      if (hovered === gate.reader_id) {
        ctx.fillStyle = 'rgba(0,0,0,0.85)'
        const tw = ctx.measureText(gate.name).width + 10
        ctx.fillRect(lbl.x - tw / 2, lbl.y - 18, tw, 14)
        ctx.fillStyle = '#f5f5f5'
        ctx.font = '8px monospace'
        ctx.fillText(gate.name, lbl.x, lbl.y - 11)
      }
    })

    // Start gate marker
    const sOuter = ovalPt(0, OUTER_RX + 6, OUTER_RY + 6)
    const sInner = ovalPt(0, INNER_RX - 6, INNER_RY - 6)
    const sLbl   = ovalPt(0, OUTER_RX + 20, OUTER_RY + 20)
    ctx.strokeStyle = '#555'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(sOuter.x, sOuter.y)
    ctx.lineTo(sInner.x, sInner.y)
    ctx.stroke()
    ctx.fillStyle = '#555'
    ctx.font = '7px monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('S', sLbl.x, sLbl.y)

    // ── Horse dots ──
    horses.forEach((h, idx) => {
      const dist = interpolateDist(h, currentElapsedMs, totalDistanceM)
      const progress = Math.min(dist / totalDistanceM, 1)
      const { x: bx, y: by, a } = ovalPt(progress, MID_RX, MID_RY)
      const { nx, ny } = ovalNormal(a, MID_RX, MID_RY)

      const clothNum = parseInt(h.saddle_cloth ?? String(idx + 1)) || (idx + 1)
      const laneIdx  = (clothNum - 1) % Math.max(laneCount, 1)
      const laneOff  = laneCount > 1 ? (laneIdx / (laneCount - 1) - 0.5) * (TRACK_W - 10) : 0

      const hx = bx + nx * laneOff
      const hy = by + ny * laneOff
      const color = SILK_COLORS[(clothNum - 1) % SILK_COLORS.length]

      // Shadow
      ctx.shadowColor = 'rgba(0,0,0,0.6)'
      ctx.shadowBlur = 4

      ctx.fillStyle = color
      ctx.strokeStyle = 'rgba(255,255,255,0.8)'
      ctx.lineWidth = 1.2
      ctx.beginPath()
      ctx.roundRect(hx - 9, hy - 9, 18, 18, 2)
      ctx.fill()
      ctx.stroke()

      ctx.shadowBlur = 0
      ctx.fillStyle = 'white'
      ctx.font = 'bold 8px monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(String(h.saddle_cloth ?? clothNum), hx, hy + 0.5)
    })
  }, [horses, totalDistanceM, gates, currentElapsedMs, trackPath, hovered, sortedGates, laneCount, fullscreen])

  // rAF loop
  useEffect(() => {
    let running = true
    function loop() {
      if (!running) return
      draw()
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => {
      running = false
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [draw])

  // Gate hover hit-testing
  const handleMouseMove = useCallback((e) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const mx = (e.clientX - rect.left) / scale
    const my = (e.clientY - rect.top) / scale
    let found = null
    for (const gate of sortedGates) {
      const p = gate.distance_m / totalDistanceM
      const lbl = ovalPt(p, OUTER_RX + 20, OUTER_RY + 20)
      if (Math.abs(lbl.x - mx) < 18 && Math.abs(lbl.y - my) < 10) {
        found = gate.reader_id
        break
      }
    }
    setHovered(found)
  }, [sortedGates, totalDistanceM, scale])

  return (
    <canvas
      ref={canvasRef}
      style={{ display: 'block', maxWidth: '100%' }}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => setHovered(null)}
      aria-label="Live track position map"
    />
  )
}

// ─── Public component ─────────────────────────────────────────────────────────
export default function TrackMap({
  horses = [],
  totalDistanceM = 1600,
  gates = [],
  currentElapsedMs = 0,
  venueId = null,
}) {
  const [trackPath, setTrackPath] = useState(null)
  const [fullscreen, setFullscreen] = useState(false)
  const containerRef = useRef(null)

  // Fetch track path for this venue
  useEffect(() => {
    if (!venueId) return
    let cancelled = false
    fetch(`/venues/${venueId}/track-path`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!cancelled && data?.points?.length >= 3) setTrackPath(data.points)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [venueId])

  // Fullscreen: F key or Escape
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'f' || e.key === 'F') setFullscreen(fs => !fs)
      if (e.key === 'Escape') setFullscreen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const mapContent = (
    <OvalCanvas
      horses={horses}
      totalDistanceM={totalDistanceM}
      gates={gates}
      currentElapsedMs={currentElapsedMs}
      trackPath={trackPath}
      fullscreen={fullscreen}
    />
  )

  if (fullscreen) {
    return (
      <div
        className="fixed inset-0 z-50 bg-black flex flex-col"
        ref={containerRef}
      >
        <div className="flex items-center justify-between px-4 py-2 border-b border-border">
          <span className="text-xs text-text-muted font-timing tracking-widest uppercase">
            TrackMap — Full Screen
          </span>
          <button
            onClick={() => setFullscreen(false)}
            className="text-xs font-timing text-text-muted hover:text-accent tracking-widest uppercase"
          >
            ESC / F to close
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center overflow-hidden p-4">
          {mapContent}
        </div>
        {/* Timing strip */}
        <div className="px-4 py-2 border-t border-border bg-surface flex gap-6 overflow-x-auto">
          {[...horses]
            .sort((a, b) => (a.finish_position ?? 999) - (b.finish_position ?? 999))
            .slice(0, 10)
            .map((h) => {
              const last = h.events?.[h.events.length - 1]
              const ms = last?.elapsed_ms ?? 0
              const mins = Math.floor(ms / 60000)
              const secs = ((ms % 60000) / 1000).toFixed(2).padStart(5, '0')
              const timeStr = ms ? `${mins}:${secs}` : '—'
              const color = SILK_COLORS[((parseInt(h.saddle_cloth) || 1) - 1) % SILK_COLORS.length]
              return (
                <div key={h.horse_id} className="flex items-center gap-1.5 shrink-0">
                  <span
                    className="inline-block w-3 h-3 rounded-sm"
                    style={{ background: color }}
                  />
                  <span className="text-xs font-timing text-text-muted">
                    #{h.saddle_cloth}
                  </span>
                  <span className="text-xs font-timing text-accent">{timeStr}</span>
                </div>
              )
            })}
        </div>
      </div>
    )
  }

  return (
    <div className="relative">
      {mapContent}
      <button
        onClick={() => setFullscreen(true)}
        title="Full screen (F)"
        className="absolute top-2 right-2 text-xs font-timing text-text-muted hover:text-accent border border-border px-2 py-0.5 bg-surface opacity-70 hover:opacity-100 transition-opacity"
      >
        ⛶
      </button>
    </div>
  )
}
