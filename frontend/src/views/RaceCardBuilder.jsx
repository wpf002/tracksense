import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listVenues, createVenue, getVenue, addGate } from '../api/venues'
import { getHorse, listHorses } from '../api/horses'
import { registerHorses } from '../api/races'

// ──────────────────────────────────────────────
// Step indicator
// ──────────────────────────────────────────────
function StepHeader({ step, current }) {
  const active = step === current
  const done = step < current
  return (
    <div
      className={[
        'flex items-center gap-2 px-4 py-2 border-b border-border',
        active ? 'bg-surface-2' : 'bg-surface',
      ].join(' ')}
    >
      <span
        className={[
          'w-6 h-6 flex items-center justify-center text-xs font-bold border',
          active
            ? 'border-accent text-accent'
            : done
            ? 'border-green-700 text-green-400'
            : 'border-border text-text-muted',
        ].join(' ')}
      >
        {done ? '✓' : step}
      </span>
      <span
        className={[
          'text-xs font-semibold uppercase tracking-widest',
          active ? 'text-text-primary' : 'text-text-muted',
        ].join(' ')}
      >
        {step === 1 ? 'Venue & Gates' : step === 2 ? 'Field' : 'Register & Arm'}
      </span>
    </div>
  )
}

// ──────────────────────────────────────────────
// Step 1 — Venue selection & gate management
// ──────────────────────────────────────────────
function StepVenue({ onSelect, selectedVenueId }) {
  const qc = useQueryClient()
  const [newVenueId, setNewVenueId] = useState('')
  const [newVenueName, setNewVenueName] = useState('')
  const [newVenueDist, setNewVenueDist] = useState('')
  const [createError, setCreateError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  // Gate form
  const [gateReaderId, setGateReaderId] = useState('')
  const [gateName, setGateName] = useState('')
  const [gateDist, setGateDist] = useState('')
  const [gateIsFinish, setGateIsFinish] = useState(false)
  const [gateError, setGateError] = useState(null)
  const [gateSuccess, setGateSuccess] = useState(null)

  const { data: venues = [], isLoading } = useQuery({
    queryKey: ['venues'],
    queryFn: listVenues,
  })

  const { data: venueDetail } = useQuery({
    queryKey: ['venue', selectedVenueId],
    queryFn: () => getVenue(selectedVenueId),
    enabled: !!selectedVenueId,
  })

  const createVenueMut = useMutation({
    mutationFn: createVenue,
    onSuccess: (data) => {
      setCreateError(null)
      setShowCreate(false)
      setNewVenueId('')
      setNewVenueName('')
      setNewVenueDist('')
      qc.invalidateQueries({ queryKey: ['venues'] })
      onSelect(data.venue_id ?? newVenueId.toUpperCase())
    },
    onError: (err) => setCreateError(err.response?.data?.detail ?? 'Create failed'),
  })

  const addGateMut = useMutation({
    mutationFn: (body) => addGate(selectedVenueId, body),
    onSuccess: () => {
      setGateError(null)
      setGateSuccess('Gate added.')
      setGateReaderId('')
      setGateName('')
      setGateDist('')
      setGateIsFinish(false)
      qc.invalidateQueries({ queryKey: ['venue', selectedVenueId] })
    },
    onError: (err) => {
      setGateError(err.response?.data?.detail ?? 'Add gate failed')
      setGateSuccess(null)
    },
  })

  const gates = venueDetail?.gates ?? []

  return (
    <div className="p-4">
      {isLoading ? (
        <p className="text-text-muted text-xs font-timing">Loading venues...</p>
      ) : (
        <>
          {/* Venue list */}
          <table className="w-full text-sm border-collapse mb-3">
            <thead>
              <tr className="border-b border-border">
                {['ID', 'Name', 'Distance', ''].map((h) => (
                  <th key={h} className="px-3 py-1.5 text-left text-xs text-text-muted uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {venues.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-4 text-text-muted text-xs text-center font-timing">
                    No venues — create one below
                  </td>
                </tr>
              ) : (
                venues.map((v) => (
                  <tr
                    key={v.venue_id}
                    className={[
                      'border-b border-border cursor-pointer',
                      selectedVenueId === v.venue_id
                        ? 'bg-amber-950'
                        : 'bg-bg hover:bg-surface-2',
                    ].join(' ')}
                    onClick={() => onSelect(v.venue_id)}
                  >
                    <td className="px-3 py-2 font-timing text-accent text-xs">{v.venue_id}</td>
                    <td className="px-3 py-2 text-text-primary">{v.name}</td>
                    <td className="px-3 py-2 font-timing text-text-muted">{v.total_distance_m}m</td>
                    <td className="px-3 py-2">
                      {selectedVenueId === v.venue_id && (
                        <span className="text-xs text-accent font-timing">SELECTED</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Create venue toggle */}
          <button
            onClick={() => setShowCreate((s) => !s)}
            className="text-xs text-text-muted hover:text-accent font-timing uppercase tracking-widest mb-3"
          >
            {showCreate ? '− Cancel' : '+ Create New Venue'}
          </button>

          {showCreate && (
            <div className="flex gap-2 flex-wrap mb-3">
              <input
                type="text"
                placeholder="ID (e.g. FLEMINGTON)"
                value={newVenueId}
                onChange={(e) => setNewVenueId(e.target.value.toUpperCase())}
                className="bg-bg border border-border text-text-primary px-2 py-1.5 text-sm font-timing focus:outline-none focus:border-accent w-44"
              />
              <input
                type="text"
                placeholder="Name"
                value={newVenueName}
                onChange={(e) => setNewVenueName(e.target.value)}
                className="bg-bg border border-border text-text-primary px-2 py-1.5 text-sm focus:outline-none focus:border-accent flex-1 min-w-36"
              />
              <input
                type="number"
                placeholder="Distance (m)"
                value={newVenueDist}
                onChange={(e) => setNewVenueDist(e.target.value)}
                className="bg-bg border border-border text-text-primary px-2 py-1.5 text-sm font-timing focus:outline-none focus:border-accent w-32"
              />
              <button
                onClick={() =>
                  createVenueMut.mutate({
                    venue_id: newVenueId.trim(),
                    name: newVenueName.trim(),
                    total_distance_m: parseFloat(newVenueDist),
                  })
                }
                disabled={!newVenueId || !newVenueName || !newVenueDist || createVenueMut.isPending}
                className="px-3 py-1.5 text-sm font-semibold uppercase tracking-widest border border-accent text-accent hover:bg-amber-950 transition-colors disabled:opacity-40"
              >
                Create
              </button>
            </div>
          )}
          {createError && <p className="text-red-400 text-xs font-timing mb-2">{createError}</p>}

          {/* Gate management */}
          {selectedVenueId && (
            <div className="mt-4 border-t border-border pt-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-text-muted mb-3">
                Gates — {selectedVenueId}
              </p>

              {gates.length === 0 ? (
                <p className="text-text-muted text-xs font-timing mb-3">No gates configured yet.</p>
              ) : (
                <table className="w-full text-sm border-collapse mb-3">
                  <thead>
                    <tr className="border-b border-border">
                      {['Reader ID', 'Name', 'Distance', 'Finish'].map((h) => (
                        <th key={h} className="px-3 py-1.5 text-left text-xs text-text-muted uppercase tracking-wider">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...gates]
                      .sort((a, b) => a.distance_m - b.distance_m)
                      .map((g) => (
                        <tr key={g.reader_id} className="border-b border-border bg-bg">
                          <td className="px-3 py-2 font-timing text-xs text-accent">{g.reader_id}</td>
                          <td className="px-3 py-2 text-text-primary">{g.name}</td>
                          <td className="px-3 py-2 font-timing text-text-muted">{g.distance_m}m</td>
                          <td className="px-3 py-2">
                            {g.is_finish && (
                              <span className="text-xs font-timing font-bold text-accent">✓</span>
                            )}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              )}

              {/* Add gate form */}
              <div className="flex gap-2 flex-wrap items-center">
                <input
                  type="text"
                  placeholder="Reader ID"
                  value={gateReaderId}
                  onChange={(e) => setGateReaderId(e.target.value.toUpperCase())}
                  className="bg-bg border border-border text-text-primary px-2 py-1.5 text-sm font-timing focus:outline-none focus:border-accent w-36"
                />
                <input
                  type="text"
                  placeholder="Gate name"
                  value={gateName}
                  onChange={(e) => setGateName(e.target.value)}
                  className="bg-bg border border-border text-text-primary px-2 py-1.5 text-sm focus:outline-none focus:border-accent w-36"
                />
                <input
                  type="number"
                  placeholder="Distance (m)"
                  value={gateDist}
                  onChange={(e) => setGateDist(e.target.value)}
                  className="bg-bg border border-border text-text-primary px-2 py-1.5 text-sm font-timing focus:outline-none focus:border-accent w-28"
                />
                <label className="flex items-center gap-1.5 text-xs text-text-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={gateIsFinish}
                    onChange={(e) => setGateIsFinish(e.target.checked)}
                    className="accent-amber-500"
                  />
                  Finish
                </label>
                <button
                  onClick={() =>
                    addGateMut.mutate({
                      reader_id: gateReaderId.trim(),
                      name: gateName.trim(),
                      distance_m: parseFloat(gateDist),
                      is_finish: gateIsFinish,
                    })
                  }
                  disabled={!gateReaderId || !gateName || !gateDist || addGateMut.isPending}
                  className="px-3 py-1.5 text-sm font-semibold uppercase tracking-widest border border-border text-text-muted hover:border-accent hover:text-accent transition-colors disabled:opacity-40"
                >
                  Add Gate
                </button>
              </div>
              {gateError && <p className="text-red-400 text-xs font-timing mt-1">{gateError}</p>}
              {gateSuccess && <p className="text-green-400 text-xs font-timing mt-1">{gateSuccess}</p>}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ──────────────────────────────────────────────
// Step 2 — Field management
// ──────────────────────────────────────────────
function StepField({ field, setField }) {
  const [epcInput, setEpcInput] = useState('')
  const [nameInput, setNameInput] = useState('')
  const [clothInput, setClothInput] = useState('')
  const [lookupLoading, setLookupLoading] = useState(false)
  const [addError, setAddError] = useState(null)

  const { data: allHorses, isLoading: horsesLoading } = useQuery({
    queryKey: ['horses'],
    queryFn: listHorses,
  })

  // Auto-populate from DB when the field is empty and horses have loaded
  useEffect(() => {
    if (field.length === 0 && allHorses && allHorses.length > 0) {
      setField(
        allHorses.map((h, i) => ({
          horse_id: h.epc,
          display_name: h.name,
          saddle_cloth: String(i + 1),
        }))
      )
    }
  }, [allHorses]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleReload = () => {
    if (!allHorses) return
    setField(
      allHorses.map((h, i) => ({
        horse_id: h.epc,
        display_name: h.name,
        saddle_cloth: String(i + 1),
      }))
    )
  }

  const handleEpcBlur = async () => {
    const epc = epcInput.trim().toUpperCase()
    if (!epc) return
    setLookupLoading(true)
    try {
      const horse = await getHorse(epc)
      setNameInput(horse.name ?? '')
    } catch (_) {
      // horse not in DB — manual name entry
    } finally {
      setLookupLoading(false)
    }
  }

  const handleAdd = () => {
    const epc = epcInput.trim().toUpperCase()
    const name = nameInput.trim()
    const cloth = clothInput.trim()
    if (!epc || !name || !cloth) {
      setAddError('EPC, name, and saddle cloth are required.')
      return
    }
    if (field.some((h) => h.horse_id === epc)) {
      setAddError(`${epc} already in field.`)
      return
    }
    setField([...field, { horse_id: epc, display_name: name, saddle_cloth: cloth }])
    setEpcInput('')
    setNameInput('')
    setClothInput('')
    setAddError(null)
  }

  const handleRemove = (epc) => {
    setField(field.filter((h) => h.horse_id !== epc))
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-text-muted font-timing uppercase tracking-widest">
          {horsesLoading ? 'Loading horses…' : `${field.length} runner${field.length !== 1 ? 's' : ''}`}
        </span>
        <button
          onClick={handleReload}
          disabled={horsesLoading || !allHorses}
          className="text-xs text-text-muted hover:text-accent font-timing uppercase tracking-widest disabled:opacity-40"
        >
          ↺ Reload All from Registry
        </button>
      </div>

      {field.length > 0 && (
        <table className="w-full text-sm border-collapse mb-4">
          <thead>
            <tr className="border-b border-border">
              {['EPC', 'Name', 'Cloth', ''].map((h) => (
                <th key={h} className="px-3 py-1.5 text-left text-xs text-text-muted uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {field.map((h) => (
              <tr key={h.horse_id} className="border-b border-border bg-bg">
                <td className="px-3 py-2 font-timing text-xs text-accent">{h.horse_id}</td>
                <td className="px-3 py-2 text-text-primary">{h.display_name}</td>
                <td className="px-3 py-2 font-timing text-text-muted">{h.saddle_cloth}</td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => handleRemove(h.horse_id)}
                    className="text-xs text-red-500 hover:text-red-400 font-timing"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Add horse form */}
      <div className="flex gap-2 flex-wrap items-start">
        <div className="flex flex-col gap-0.5">
          <input
            type="text"
            placeholder="EPC"
            value={epcInput}
            onChange={(e) => setEpcInput(e.target.value.toUpperCase())}
            onBlur={handleEpcBlur}
            className="bg-bg border border-border text-text-primary px-2 py-1.5 text-sm font-timing focus:outline-none focus:border-accent w-40"
          />
          {lookupLoading && (
            <span className="text-xs text-text-muted font-timing">Looking up...</span>
          )}
        </div>
        <input
          type="text"
          placeholder="Display name"
          value={nameInput}
          onChange={(e) => setNameInput(e.target.value)}
          className="bg-bg border border-border text-text-primary px-2 py-1.5 text-sm focus:outline-none focus:border-accent flex-1 min-w-36"
        />
        <input
          type="text"
          placeholder="Cloth #"
          value={clothInput}
          onChange={(e) => setClothInput(e.target.value)}
          className="bg-bg border border-border text-text-primary px-2 py-1.5 text-sm font-timing focus:outline-none focus:border-accent w-20"
        />
        <button
          onClick={handleAdd}
          className="px-3 py-1.5 text-sm font-semibold uppercase tracking-widest border border-border text-text-muted hover:border-accent hover:text-accent transition-colors"
        >
          Add
        </button>
      </div>
      {addError && <p className="text-red-400 text-xs font-timing mt-2">{addError}</p>}
    </div>
  )
}

// ──────────────────────────────────────────────
// Step 3 — Register & Arm
// ──────────────────────────────────────────────
function StepRegister({ venueId, field }) {
  const navigate = useNavigate()
  const [registerResult, setRegisterResult] = useState(null)
  const [registerError, setRegisterError] = useState(null)

  const registerMut = useMutation({
    mutationFn: () =>
      registerHorses({ venue_id: venueId, horses: field }),
    onSuccess: (data) => {
      setRegisterResult(data)
      setRegisterError(null)
    },
    onError: (err) => {
      setRegisterError(err.response?.data?.detail ?? 'Registration failed')
      setRegisterResult(null)
    },
  })

  return (
    <div className="p-4">
      <div className="mb-4 text-sm text-text-muted">
        <p>Venue: <span className="text-text-primary font-timing">{venueId ?? '—'}</span></p>
        <p>Runners: <span className="text-text-primary font-timing">{field.length}</span></p>
      </div>

      {!registerResult ? (
        <button
          onClick={() => registerMut.mutate()}
          disabled={!venueId || field.length === 0 || registerMut.isPending}
          className="px-6 py-2 text-sm font-bold uppercase tracking-widest border border-accent text-accent hover:bg-amber-950 transition-colors disabled:opacity-40"
        >
          {registerMut.isPending ? 'Registering…' : 'Register Field'}
        </button>
      ) : (
        <div>
          <p className="text-green-400 text-sm font-timing mb-4">
            ✓ Field registered — {registerResult.registered ?? field.length} horses ready
          </p>
          <button
            onClick={() => navigate('/live')}
            className="px-6 py-2 text-sm font-bold uppercase tracking-widest bg-accent text-bg hover:bg-accent-dim transition-colors"
          >
            Go to Live View →
          </button>
        </div>
      )}

      {registerError && (
        <p className="text-red-400 text-xs font-timing mt-2">{registerError}</p>
      )}
    </div>
  )
}

// ──────────────────────────────────────────────
// Main RaceCardBuilder
// ──────────────────────────────────────────────
export default function RaceCardBuilder() {
  const [step, setStep] = useState(1)
  const [selectedVenueId, setSelectedVenueId] = useState(null)
  const [field, setField] = useState([])

  const handleSelectVenue = (id) => {
    setSelectedVenueId(id)
  }

  const canAdvance1 = !!selectedVenueId
  const canAdvance2 = field.length > 0

  return (
    <div className="p-6">
      <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase mb-6">
        Race Builder
      </h1>

      <div className="border border-border bg-surface">
        {/* Step 1 */}
        <StepHeader step={1} current={step} />
        {step === 1 && (
          <>
            <StepVenue onSelect={handleSelectVenue} selectedVenueId={selectedVenueId} />
            <div className="px-4 pb-4">
              <button
                onClick={() => setStep(2)}
                disabled={!canAdvance1}
                className="px-5 py-1.5 text-sm font-semibold uppercase tracking-widest border border-accent text-accent hover:bg-amber-950 transition-colors disabled:opacity-40"
              >
                Next: Build Field →
              </button>
            </div>
          </>
        )}

        {/* Step 2 */}
        <StepHeader step={2} current={step} />
        {step === 2 && (
          <>
            <StepField field={field} setField={setField} />
            <div className="px-4 pb-4 flex gap-3">
              <button
                onClick={() => setStep(1)}
                className="px-4 py-1.5 text-sm uppercase tracking-widest border border-border text-text-muted hover:border-accent hover:text-accent transition-colors"
              >
                ← Back
              </button>
              <button
                onClick={() => setStep(3)}
                disabled={!canAdvance2}
                className="px-5 py-1.5 text-sm font-semibold uppercase tracking-widest border border-accent text-accent hover:bg-amber-950 transition-colors disabled:opacity-40"
              >
                Next: Register →
              </button>
            </div>
          </>
        )}

        {/* Step 3 */}
        <StepHeader step={3} current={step} />
        {step === 3 && (
          <>
            <StepRegister venueId={selectedVenueId} field={field} />
            <div className="px-4 pb-4">
              <button
                onClick={() => setStep(2)}
                className="px-4 py-1.5 text-sm uppercase tracking-widest border border-border text-text-muted hover:border-accent hover:text-accent transition-colors"
              >
                ← Back
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}