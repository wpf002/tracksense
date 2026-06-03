import client from './client'

export const listRaces = () =>
  client.get('/races').then((r) => r.data.races)

export const getRace = (id) =>
  client.get(`/races/${id}`).then((r) => r.data)

export const getRaceEntries = (id) =>
  client.get(`/races/${id}/entries`).then((r) => r.data)

export const addEntry = (raceId, body) =>
  client.post(`/races/${raceId}/entries`, body).then((r) => r.data)

export const updateEntry = (raceId, chipId, body) =>
  client.patch(`/races/${raceId}/entries/${chipId}`, body).then((r) => r.data)

export const scratchHorse = (raceId, chipId, body) =>
  client.post(`/races/${raceId}/scratch/${chipId}`, body).then((r) => r.data)

export const ingestResults = (raceId, results) =>
  client.post(`/races/${raceId}/results/ingest`, { results }).then((r) => r.data)

export const updateRaceStatus = (raceId, status) =>
  client.patch(`/races/${raceId}/status`, { status }).then((r) => r.data)
