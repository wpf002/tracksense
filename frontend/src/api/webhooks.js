import client from './client'

export const listWebhooks = () =>
  client.get('/webhooks').then((r) => r.data)

export const createWebhook = (data) =>
  client.post('/webhooks', data).then((r) => r.data)

export const updateWebhook = (id, data) =>
  client.patch(`/webhooks/${id}`, data).then((r) => r.data)

export const deleteWebhook = (id) =>
  client.delete(`/webhooks/${id}`).then((r) => r.data)

export const testWebhook = (id) =>
  client.post(`/webhooks/${id}/test`).then((r) => r.data)
