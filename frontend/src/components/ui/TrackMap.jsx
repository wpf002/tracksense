
import { useEffect, useState } from 'react'

const SILK_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#14b8a6',
  '#6366f1', '#f43f5e', '#16a34a', '#d97706', '#8b5cf6',
  '#0284c7', '#ea580c', '#059669', '#7c3aed', '#be185d',
]

// ─── Oval mode constants ──────────────────────────────────────────────────────
const W_OVAL = 800, H_OVAL = 310
const cx = W_OVAL / 2, cy = H_OVAL / 2
const OUTER_RX = 300, OUTER_RY = 118
const TRACK_W = 26
const INNER_RX = OUTER_RX - TRACK_W, INNER_RY = OUTER_RY - TRACK_W
const MID_RX   = OUTER_RX - TRACK_W / 2, MID_RY = OUTER_RY - TRACK_W / 2

// ─── Arc-length parameterization (oval mode) ─────────────────────────────────
const ARC_STEPS = 720
const _arcTable = (() => {
  const table = [{ angle: 0, arc: 0 }]
  let total = 0
  const da = (2 * Math.PI) / ARC_STEPS
  for (let i = 1; i <= ARC_STEPS; i++) {
    const mid = (i - 0.5) * da
    total += Math.sqrt((MID_RX * Math.cos(mid)) ** 2 + (MID_RY * Math.sin(mid)) ** 2) * da
    table.push({ angle: i * da, arc: total })
  }
  return { table, total }
})()

function progressToAngle(progress) {
  const target = (progress % 1) * _arcTable.total
  let lo = 0, hi = _arcTable.table.length - 1
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1
    if (_arcTable.table[mid].arc <= target) lo = mid; else hi = mid
  }
  const t0 = _arcTable.table[lo], t1 = _arcTable.table[hi]
  const f = t0.arc === t1.arc ? 0 : (target - t0.arc) / (t1.arc - t0.arc)
  const arcAngle = t0.angle + f * (t1.angle - t0.angle)
  return Math.PI / 2 - arcAngle
}

function ovalPt(progress, rx, ry) {
  const a = progressToAngle(progress)
  return { x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a), a }
}

function ovalNormal(a, rx, ry) {
  const nx = Math.cos(a) / rx
  const ny = Math.sin(a) / ry
  const mag = Math.sqrt(nx * nx + ny * ny)
  return { nx: nx / mag, ny: ny / mag }
}

function interpolateDist(horse, currentElapsedMs, totalDistanceM) {
  const events = horse.events ?? []
  if (events.length === 0) {
    return currentElapsedMs > 0 ? Math.min(0.018 * currentElapsedMs, totalDistanceM) : 0
  }
  const last = events[events.length - 1]
  if (horse.finish_position != null) return last.distance_m
  let speedMpMs = 0
  if (events.length >= 2) {
    const prev = events[events.length - 2]
    const dt = last.elapsed_ms - prev.elapsed_ms
    if (dt > 0) speedMpMs = (last.distance_m - prev.distance_m) / dt
  } else if (last.elapsed_ms > 0 && last.distance_m > 0) {
    speedMpMs = last.distance_m / last.elapsed_ms
  } else {
    speedMpMs = 0.018
  }
  if (speedMpMs <= 0) return last.distance_m
  const extrapolated = last.distance_m + speedMpMs * Math.max(currentElapsedMs - last.elapsed_ms, 0)
  return Math.min(extrapolated, totalDistanceM)
}

// ─── Coordinate mode constants ───────────────────────────────────────────────
const GW = 600, GH = 400

/**
 * Interpolate a horse's (x,y) position in coordinate mode.
 * Uses the last two gate events to determine which segment it's in.
 */
function interpolatePosition(horse, currentElapsedMs, gatePositions) {
  const events = horse.events ?? []
  if (events.length === 0) return null

  const last = events[events.length - 1]
  const lastPos = gatePositions[last.reader_id]
  if (!lastPos) return null

  // Finished — freeze at finish gate
  if (horse.finish_position != null) return lastPos

  if (events.length >= 2) {
    const prev = events[events.length - 2]
    const prevPos = gatePositions[prev.reader_id]
    if (!prevPos) return lastPos

    const segMs = last.elapsed_ms - prev.elapsed_ms
    if (segMs <= 0) return lastPos

    // Estimate when horse will reach next gate (same duration as this segment)
    const extraMs = Math.max(currentElapsedMs - last.elapsed_ms, 0)
    const segDist = last.distance_m - prev.distance_m
    if (segDist <= 0) return lastPos

    const speed = segDist / segMs   // m/ms
    const extraDist = extraMs * speed

    // Find next gate position by distance
    const nextDist = last.distance_m + extraDist
    // Clamp progress between last and next known gate
    const tRaw = extraDist / segDist
    const t = Math.min(tRaw, 1.5)   // allow up to 150% interpolation before stopping
    return {
      x: lastPos.x + (lastPos.x - prevPos.x) * t,
      y: lastPos.y + (lastPos.y - prevPos.y) * t,
    }
  }

  return lastPos
}

// ─── Geometry fetch ───────────────────────────────────────────────────────────
async function fetchGeometry(venueId) {
  try {
    const res = await fetch(`/venues/${venueId}/geometry`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

// ─── Oval mode renderer ───────────────────────────────────────────────────────
function OvalTrackMap({ horses, totalDistanceM, gates, currentElapsedMs }) {
  const sortedGates = [...gates].sort((a, b) => a.distance_m - b.distance_m)
  const laneCount = Math.min(horses.length, 6)

  return (
    <svg
      viewBox={`0 0 ${W_OVAL} ${H_OVAL}`}
      className="w-full bg-bg"
      style={{ maxHeight: 310 }}
      aria-label="Live track position map"
    >
      <ellipse cx={cx} cy={cy} rx={OUTER_RX} ry={OUTER_RY}
               fill="none" stroke="#1c1c1c" strokeWidth={TRACK_W} />
      <ellipse cx={cx} cy={cy} rx={INNER_RX - 1} ry={INNER_RY - 1} fill="#0f0f0f" />
      <ellipse cx={cx} cy={cy} rx={OUTER_RX} ry={OUTER_RY}
               fill="none" stroke="#383838" strokeWidth="1.5" />
      <ellipse cx={cx} cy={cy} rx={INNER_RX} ry={INNER_RY}
               fill="none" stroke="#383838" strokeWidth="1.5" />

      {sortedGates.map(gate => {
        const p = gate.distance_m / totalDistanceM
        const outer = ovalPt(p, OUTER_RX + 6, OUTER_RY + 6)
        const inner = ovalPt(p, INNER_RX - 6, INNER_RY - 6)
        const lbl   = ovalPt(p, OUTER_RX + 20, OUTER_RY + 20)
        const abbr  = gate.is_finish
          ? 'FIN'
          : gate.name.replace(/Furlong\s*/i, 'F').replace(/Start/i, 'S')
        return (
          <g key={gate.reader_id}>
            <line x1={outer.x} y1={outer.y} x2={inner.x} y2={inner.y}
                  stroke={gate.is_finish ? '#f59e0b' : '#444'}
                  strokeWidth={gate.is_finish ? 2.5 : 1}
                  strokeDasharray={gate.is_finish ? '5 3' : undefined} />
            <text x={lbl.x} y={lbl.y} textAnchor="middle" dominantBaseline="middle"
                  fill={gate.is_finish ? '#f59e0b' : '#555'}
                  fontSize="7" fontFamily="monospace">
              {abbr}
            </text>
          </g>
        )
      })}

      {(() => {
        const outer = ovalPt(0, OUTER_RX + 6, OUTER_RY + 6)
        const inner = ovalPt(0, INNER_RX - 6, INNER_RY - 6)
        const lbl   = ovalPt(0, OUTER_RX + 20, OUTER_RY + 20)
        return (
          <g>
            <line x1={outer.x} y1={outer.y} x2={inner.x} y2={inner.y}
                  stroke="#555" strokeWidth="1" />
            <text x={lbl.x} y={lbl.y} textAnchor="middle" dominantBaseline="middle"
                  fill="#555" fontSize="7" fontFamily="monospace">S</text>
          </g>
        )
      })()}

      {horses.map((h, idx) => {
        const dist     = interpolateDist(h, currentElapsedMs, totalDistanceM)
        const progress = Math.min(dist / totalDistanceM, 1)
        const { x: bx, y: by, a } = ovalPt(progress, MID_RX, MID_RY)

        const { nx, ny } = ovalNormal(a, MID_RX, MID_RY)
        const clothNum   = parseInt(h.saddle_cloth ?? String(idx + 1)) || (idx + 1)
        const laneIdx    = (clothNum - 1) % Math.max(laneCount, 1)
        const laneOffset = laneCount > 1
          ? (laneIdx / (laneCount - 1) - 0.5) * (TRACK_W - 10)
          : 0

        const hx    = (bx + nx * laneOffset).toFixed(2)
        const hy    = (by + ny * laneOffset).toFixed(2)
        const color = SILK_COLORS[(clothNum - 1) % SILK_COLORS.length]

        return (
          <g key={h.horse_id} transform={`translate(${hx}, ${hy})`}>
            <rect x={-9} y={-9} width={18} height={18} rx={2}
                  fill={color} stroke="rgba(255,255,255,0.75)" strokeWidth="1.2" />
            <text x={0} y={4} textAnchor="middle" fill="white"
                  fontSize="8" fontWeight="bold" fontFamily="monospace"
                  style={{ userSelect: 'none', pointerEvents: 'none' }}>
              {h.saddle_cloth}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

// ─── Coordinate mode renderer ─────────────────────────────────────────────────
function CoordTrackMap({ horses, geometry, currentElapsedMs }) {
  // Build a lookup: reader_id -> { x, y } in pixel space
  const gatePositions = {}
  const positionedGates = geometry.gates.filter(g => g.position_x != null && g.position_y != null)
  for (const g of positionedGates) {
    gatePositions[g.reader_id] = { x: g.position_x * GW, y: g.position_y * GH }
  }

  // Draw connecting lines between consecutive gates (by distance order)
  const sortedGates = [...positionedGates].sort((a, b) => a.distance_m - b.distance_m)

  return (
    <svg
      viewBox={`0 0 ${GW} ${GH}`}
      className="w-full bg-bg"
      style={{ maxHeight: GH }}
      aria-label="Live track position map (coordinate mode)"
    >
      {/* Track outline — connect gates in order */}
      {sortedGates.length > 1 && sortedGates.map((gate, i) => {
        if (i === sortedGates.length - 1) return null
        const a = gatePositions[gate.reader_id]
        const b = gatePositions[sortedGates[i + 1].reader_id]
        if (!a || !b) return null
        return (
          <line key={`seg-${i}`}
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke="#333" strokeWidth="18" strokeLinecap="round" />
        )
      })}

      {/* Gate markers */}
      {positionedGates.map(gate => {
        const pos = gatePositions[gate.reader_id]
        if (!pos) return null
        const abbr = gate.is_finish
          ? 'FIN'
          : gate.name.replace(/Furlong\s*/i, 'F').replace(/Start/i, 'S')
        return (
          <g key={gate.reader_id}>
            <circle cx={pos.x} cy={pos.y} r={8}
                    fill={gate.is_finish ? '#f59e0b' : '#555'}
                    stroke="#222" strokeWidth="1.5" />
            <text x={pos.x} y={pos.y - 12} textAnchor="middle"
                  fill={gate.is_finish ? '#f59e0b' : '#888'}
                  fontSize="9" fontFamily="monospace">
              {abbr}
            </text>
          </g>
        )
      })}

      {/* Horses */}
      {horses.map((h, idx) => {
        const pos = interpolatePosition(h, currentElapsedMs, gatePositions)
        if (!pos) return null

        const clothNum = parseInt(h.saddle_cloth ?? String(idx + 1)) || (idx + 1)
        const color = SILK_COLORS[(clothNum - 1) % SILK_COLORS.length]

        return (
          <g key={h.horse_id} transform={`translate(${pos.x.toFixed(1)}, ${pos.y.toFixed(1)})`}>
            <rect x={-9} y={-9} width={18} height={18} rx={2}
                  fill={color} stroke="rgba(255,255,255,0.75)" strokeWidth="1.2" />
            <text x={0} y={4} textAnchor="middle" fill="white"
                  fontSize="8" fontWeight="bold" fontFamily="monospace"
                  style={{ userSelect: 'none', pointerEvents: 'none' }}>
              {h.saddle_cloth}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

// ─── Public component ─────────────────────────────────────────────────────────
export default function TrackMap({
  horses = [],
  totalDistanceM = 1600,
  gates = [],
  currentElapsedMs = 0,
  venueId = null,    // optional: if provided, fetches geometry for coordinate mode
}) {
  const [geometry, setGeometry] = useState(null)

  useEffect(() => {
    if (!venueId) return
    let cancelled = false
    fetchGeometry(venueId).then(geo => {
      if (!cancelled) setGeometry(geo)
    })
    return () => { cancelled = true }
  }, [venueId])

  // Coordinate mode: venue geometry fetched and at least one gate has position data
  const hasPositions = geometry?.gates?.some(g => g.position_x != null && g.position_y != null)

  if (hasPositions) {
    return (
      <CoordTrackMap
        horses={horses}
        geometry={geometry}
        currentElapsedMs={currentElapsedMs}
      />
    )
  }

  // Fallback: oval mode (always works, even with no geometry data)
  return (
    <OvalTrackMap
      horses={horses}
      totalDistanceM={totalDistanceM}
      gates={gates}
      currentElapsedMs={currentElapsedMs}
    />
  )
}
