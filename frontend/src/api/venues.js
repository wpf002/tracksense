import client from './client'

export const listVenues = () =>
  client.get('/venues').then((r) => r.data.venues)

export const createVenue = (body) =>
  client.post('/venues', body).then((r) => r.data)

export const getVenue = (venueId) =>
  client.get(`/venues/${venueId}`).then((r) => r.data)

export const addGate = (venueId, body) =>
  client.post(`/venues/${venueId}/gates`, body).then((r) => r.data)