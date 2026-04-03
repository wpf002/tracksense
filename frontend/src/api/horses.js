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