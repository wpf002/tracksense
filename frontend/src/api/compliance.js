import client from './client'

// HISA Submissions
export const listSubmissions = (params = {}) =>
  client.get('/hisa/submissions', { params }).then((r) => r.data.submissions)

export const getSubmission = (id) =>
  client.get(`/hisa/submissions/${id}`).then((r) => r.data)

export const submitHISA = (id) =>
  client.post(`/hisa/submit/${id}`).then((r) => r.data)

export const buildAllSubmissions = () =>
  client.post('/hisa/build-all').then((r) => r.data)

// Stewards' rulings
export const createStewardsRuling = (body) =>
  client.post('/stewards/rulings', body).then((r) => r.data)

export const listStewardsRulings = (params = {}) =>
  client.get('/stewards/rulings', { params }).then((r) => r.data.rulings)

// Surface conditions
export const addSurfaceCondition = (venueId, body) =>
  client.post(`/venues/${venueId}/surface-conditions`, body).then((r) => r.data)

export const getSurfaceConditions = (venueId) =>
  client.get(`/venues/${venueId}/surface-conditions`).then((r) => r.data.logs)
