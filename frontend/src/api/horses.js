import client from './client'

export const listHorses = () =>
  client.get('/horses').then((r) => r.data.horses)

export const getHorse = (chip_id) =>
  client.get(`/horses/${chip_id}`).then((r) => r.data)

export const getHorseSummary = (chip_id) =>
  client.get(`/horses/${chip_id}/summary`).then((r) => r.data)

export const createHorse = (body) =>
  client.post('/horses', body).then((r) => r.data)

export const getHorseCareer = (chip_id) =>
  client.get(`/horses/${chip_id}/career`).then((r) => r.data.career)

export const getHorseForm = (chip_id) =>
  client.get(`/horses/${chip_id}/form`).then((r) => r.data.form)

export const getHorseVet = (chip_id) =>
  client.get(`/horses/${chip_id}/vet`).then((r) => r.data.vet_records)

export const addVetRecord = (chip_id, body) =>
  client.post(`/horses/${chip_id}/vet`, body).then((r) => r.data)

export const compareHorses = (chip_id1, chip_id2) =>
  client.get(`/horses/compare/${chip_id1}/vs/${chip_id2}`).then((r) => r.data)

export const getHorseWorkouts = (chip_id) =>
  client.get(`/horses/${chip_id}/workouts`).then((r) => r.data.workouts)

export const addWorkout = (chip_id, body) =>
  client.post(`/horses/${chip_id}/workouts`, body).then((r) => r.data)

export const getHorseCheckins = (chip_id) =>
  client.get(`/horses/${chip_id}/checkins`).then((r) => r.data.checkins)

export const getHorseTestBarn = (chip_id) =>
  client.get(`/horses/${chip_id}/testbarn`).then((r) => r.data.test_barn_records)

export const getHorseBiosensor = (chip_id, limit = 200) =>
  client.get(`/horses/${chip_id}/biosensor`, { params: { limit } }).then((r) => r.data.readings)

export const getHorseTemperatureHistory = (chip_id) =>
  client.get(`/horses/${chip_id}/temperature-history`).then((r) => r.data.readings)

export const getHorseTemperatureAlerts = (chip_id) =>
  client.get(`/horses/${chip_id}/temperature-alerts`).then((r) => r.data)