import client from './client'

export const listHorses = () =>
  client.get('/horses').then((r) => r.data.horses)

export const getHorse = (epc) =>
  client.get(`/horses/${epc}`).then((r) => r.data)

export const createHorse = (body) =>
  client.post('/horses', body).then((r) => r.data)

export const getHorseCareer = (epc) =>
  client.get(`/horses/${epc}/career`).then((r) => r.data.career)

export const getHorseForm = (epc) =>
  client.get(`/horses/${epc}/form`).then((r) => r.data.form)

export const getHorseSectionals = (epc) =>
  client.get(`/horses/${epc}/sectionals`).then((r) => r.data.sectional_averages)

export const getHorseVet = (epc) =>
  client.get(`/horses/${epc}/vet`).then((r) => r.data.vet_records)

export const addVetRecord = (epc, body) =>
  client.post(`/horses/${epc}/vet`, body).then((r) => r.data)

export const compareHorses = (epc1, epc2) =>
  client.get(`/horses/compare/${epc1}/vs/${epc2}`).then((r) => r.data)

export const getHorseWorkouts = (epc) =>
  client.get(`/horses/${epc}/workouts`).then((r) => r.data.workouts)

export const getHorseCheckins = (epc) =>
  client.get(`/horses/${epc}/checkins`).then((r) => r.data.checkins)

export const getHorseTestBarn = (epc) =>
  client.get(`/horses/${epc}/testbarn`).then((r) => r.data.test_barn_records)

export const getHorseBiosensor = (epc, limit = 200) =>
  client.get(`/horses/${epc}/biosensor`, { params: { limit } }).then((r) => r.data.readings)

export const getHorseTemperatureHistory = (epc) =>
  client.get(`/horses/${epc}/temperature-history`).then((r) => r.data.readings)

export const getHorseTemperatureAlerts = (epc) =>
  client.get(`/horses/${epc}/temperature-alerts`).then((r) => r.data)