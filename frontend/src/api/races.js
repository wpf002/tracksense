import client from './client'

// Race-day ops state is DB-backed. The in-memory gate-timing engine was
// removed in the Phase 1 pivot, so there are no live-timing / simulate calls.

export const listRaces = () =>
  client.get('/races').then((r) => r.data.races)

export const createRace = (body) =>
  client.post('/races', body).then((r) => r.data)

export const getRace = (id) =>
  client.get(`/races/${id}`).then((r) => r.data)

export const getRaceResults = (id) =>
  client.get(`/races/${id}/results`).then((r) => r.data)
