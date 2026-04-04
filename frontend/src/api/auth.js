import client from './client'

export const login = (username, password) =>
  client.post('/auth/login', { username, password }).then((r) => r.data)

export const getMe = () =>
  client.get('/auth/me').then((r) => r.data)

export const listUsers = () =>
  client.get('/admin/users').then((r) => r.data)

export const createUser = (data) =>
  client.post('/auth/register', data).then((r) => r.data)

export const updateUser = (id, data) =>
  client.patch(`/admin/users/${id}`, data).then((r) => r.data)

export const resetPassword = (id, new_password) =>
  client.post(`/admin/users/${id}/reset-password`, { new_password }).then((r) => r.data)

export const deleteUser = (id) =>
  client.delete(`/admin/users/${id}`).then((r) => r.data)

export const changePassword = (current_password, new_password) =>
  client.post('/auth/change-password', { current_password, new_password }).then((r) => r.data)