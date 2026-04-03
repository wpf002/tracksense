
const SILK_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#14b8a6',
  '#6366f1', '#f43f5e', '#16a34a', '#d97706', '#8b5cf6',
  '#0284c7', '#ea580c', '#059669', '#7c3aed', '#be185d',
]

const W = 800, H = 290
const cx = W / 2, cy = H / 2
// More elongated oval — closer to a real racetrack shape
const OUTER_RX = 355, OUTER_RY = 100
const TRACK_W = 28
const INNER_RX = OUTER_RX - TRACK_W, INNER_RY = OUTER_RY - TRACK_W
const MID_RX   = OUTER_RX - TRACK_W / 2, MID_RY = OUTER_RY - TRACK_W / 2

// Point on oval. progress=0 → bottom, clockwise.
function ovalPt(progress, rx, ry) {
  const a = Math.PI / 2 - progress * 2 * Math.PI
  return { x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a), a }
}

// Outward unit normal at angle `a` on ellipse (rx, ry)
function ovalNormal(a, rx, ry) {
  const nx = Math.cos(a) / rx
  const ny = Math.sin(a) / ry
  const mag = Math.sqrt(nx * nx + ny * ny)
  return { nx: nx / mag, ny: ny / mag }
}

// Interpolate a horse's current distance based on its last known gate event
// and an estimated speed from its recent sectional, extrapolated to currentElapsedMs.
function interpolateDist(horse, currentElapsedMs, totalDistanceM) {
  const events = horse.events ?? []
  if (events.length === 0) return 0

  const last = events[events.length - 1]

  // Finished — freeze at finish line
  if (horse.finish_position != null) return last.distance_m

  // Estimate speed (m/ms) from last completed segment
  let speedMpMs = 0
  if (events.length >= 2) {
    const prev = events[events.length - 2]
    const dt = last.elapsed_ms - prev.elapsed_ms
    if (dt > 0) speedMpMs = (last.distance_m - prev.distance_m) / dt
  } else if (last.elapsed_ms > 0) {
    speedMpMs = last.distance_m / last.elapsed_ms
  } else {
    // At START gate (distance=0, elapsed=0) — use typical early-race speed (~65 km/h)
    speedMpMs = 0.018
  }

  if (speedMpMs <= 0) return last.distance_m

  const extrapolated = last.distance_m + speedMpMs * Math.max(currentElapsedMs - last.elapsed_ms, 0)
  return Math.min(extrapolated, totalDistanceM)
}

export default function TrackMap({ horses = [], totalDistanceM = 1600, gates = [], currentElapsedMs = 0 }) {
  const sortedGates = [...gates].sort((a, b) => a.distance_m - b.distance_m)
  const laneCount = Math.min(horses.length, 6)

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full bg-bg"
      style={{ maxHeight: 290 }}
      aria-label="Live track position map"
    >
      {/* Track band */}
      <ellipse cx={cx} cy={cy} rx={OUTER_RX} ry={OUTER_RY}
               fill="none" stroke="#1c1c1c" strokeWidth={TRACK_W} />

      {/* Infield */}
      <ellipse cx={cx} cy={cy} rx={INNER_RX - 1} ry={INNER_RY - 1} fill="#0f0f0f" />

      {/* Rails */}
      <ellipse cx={cx} cy={cy} rx={OUTER_RX} ry={OUTER_RY}
               fill="none" stroke="#383838" strokeWidth="1.5" />
      <ellipse cx={cx} cy={cy} rx={INNER_RX} ry={INNER_RY}
               fill="none" stroke="#383838" strokeWidth="1.5" />

      {/* Gate markers */}
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

      {/* Start marker */}
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

      {/* Horses — position interpolated continuously from elapsed time */}
      {horses.map((h, idx) => {
        const dist     = interpolateDist(h, currentElapsedMs, totalDistanceM)
        const progress = Math.min(dist / totalDistanceM, 1)
        const { x: bx, y: by, a } = ovalPt(progress, MID_RX, MID_RY)

        // Spread horses across track width using the ellipse outward normal
        const { nx, ny } = ovalNormal(a, MID_RX, MID_RY)
        const clothNum  = parseInt(h.saddle_cloth ?? String(idx + 1)) || (idx + 1)
        const laneIdx   = (clothNum - 1) % Math.max(laneCount, 1)
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