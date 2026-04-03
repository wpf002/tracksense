import client from './client'

export const getRaceStatus = () =>
  client.get('/race/status').then((r) => r.data)

export const getRaceState = () =>
  client.get('/race/state').then((r) => r.data)

export const getFinishOrder = () =>
  client.get('/race/finish-order').then((r) => r.data)

export const registerHorses = (body) =>
  client.post('/race/register', body).then((r) => r.data)

export const armRace = () =>
  client.post('/race/arm').then((r) => r.data)

export const resetRace = () =>
  client.post('/race/reset').then((r) => r.data)

export const simulateRace = () =>
  client.post('/race/simulate').then((r) => r.data)

export const listRaces = () =>
  client.get('/races').then((r) => r.data.races)

export const createRace = (body) =>
  client.post('/races', body).then((r) => r.data)

export const getRace = (id) =>
  client.get(`/races/${id}`).then((r) => r.data)

export const persistRace = (id) =>
  client.post(`/races/${id}/persist`).then((r) => r.data)

export const pauseSimulation = () =>
  client.post('/race/simulate/pause').then((r) => r.data)

export const resumeSimulation = () =>
  client.post('/race/simulate/resume').then((r) => r.data)