
const SILK_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#14b8a6',
  '#6366f1', '#f43f5e', '#16a34a', '#d97706', '#8b5cf6',
  '#0284c7', '#ea580c', '#059669', '#7c3aed', '#be185d',
]

const W = 800, H = 310
const cx = W / 2, cy = H / 2
const OUTER_RX = 300, OUTER_RY = 118
const TRACK_W = 26
const INNER_RX = OUTER_RX - TRACK_W, INNER_RY = OUTER_RY - TRACK_W
const MID_RX   = OUTER_RX - TRACK_W / 2, MID_RY = OUTER_RY - TRACK_W / 2

// ─── Arc-length parameterization ─────────────────────────────────────────────
// Precompute once at module load. Maps progress (0–1) to an angle on the oval
// so that equal progress increments equal equal arc-length increments — giving
// evenly-spaced gate markers even on a non-circular ellipse.
const ARC_STEPS = 720
const _arcTable = (() => {
  const table = [{ angle: 0, arc: 0 }]
  let total = 0
  const da = (2 * Math.PI) / ARC_STEPS
  for (let i = 1; i <= ARC_STEPS; i++) {
    const mid = (i - 0.5) * da
    // ds = sqrt((rx·sin(a))² + (ry·cos(a))²) · da  (ellipse arc element)
    total += Math.sqrt((MID_RX * Math.sin(mid)) ** 2 + (MID_RY * Math.cos(mid)) ** 2) * da
    table.push({ angle: i * da, arc: total })
  }
  return { table, total }
})()

// Convert progress (0=bottom, clockwise) to the SVG angle used in ovalPt
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
  return Math.PI / 2 - arcAngle   // clockwise from bottom
}

// Point on oval at given progress
function ovalPt(progress, rx, ry) {
  const a = progressToAngle(progress)
  return { x: cx + rx * Math.cos(a), y: cy + ry * Math.sin(a), a }
}

// Outward unit normal at angle `a` on ellipse (rx, ry)
function ovalNormal(a, rx, ry) {
  const nx = Math.cos(a) / rx
  const ny = Math.sin(a) / ry
  const mag = Math.sqrt(nx * nx + ny * ny)
  return { nx: nx / mag, ny: ny / mag }
}

// Interpolate a horse's current distance from its gate events + elapsed time
function interpolateDist(horse, currentElapsedMs, totalDistanceM) {
  const events = horse.events ?? []

  if (events.length === 0) {
    // No events yet but race is running — extrapolate from gun at default speed
    return currentElapsedMs > 0
      ? Math.min(0.018 * currentElapsedMs, totalDistanceM)
      : 0
  }

  const last = events[events.length - 1]

  // Finished — freeze at finish
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
    // At START gate (elapsed=0, dist=0) — use default early-race speed (~65 km/h)
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
      style={{ maxHeight: 310 }}
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

      {/* Gate markers — arc-length positioned so equal distance = equal spacing */}
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

      {/* Horses */}
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