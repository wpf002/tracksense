import axios from 'axios'

const client = axios.create({
  baseURL: '/',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// Attach Bearer token on every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('ts_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, clear session and redirect to login
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('ts_token')
      localStorage.removeItem('ts_role')
      localStorage.removeItem('ts_username')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client