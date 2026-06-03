import client from './client'

export const getTrainingRoster = () =>
  client.get('/training/roster').then((r) => r.data)

export const getOwnerReport = (chip_id, period = 'week') =>
  client.get(`/horses/${chip_id}/owner-report`, { params: { period } }).then((r) => r.data)

export const getVetChecks = (chip_id) =>
  client.get(`/horses/${chip_id}/vet-checks`).then((r) => r.data.vet_checks)

export const addVetCheck = (chip_id, body) =>
  client.post(`/horses/${chip_id}/vet-checks`, body).then((r) => r.data)
