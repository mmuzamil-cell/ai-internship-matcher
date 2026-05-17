import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

const getErrorMessage = (error) => {
  const detail = error.response?.data?.detail

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .join('\n')
  }

  if (detail && typeof detail === 'object') {
    return detail.msg || detail.message || JSON.stringify(detail)
  }

  return error.response?.data?.message || error.message || 'An unexpected error occurred'
}

// Request interceptor: attach JWT token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401 and extract error messages
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginRequest = error.config?.url?.includes('/auth/login')
    if (error.response?.status === 401 && !isLoginRequest && window.location.pathname !== '/login') {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
      window.location.href = '/login'
    }
    const message = getErrorMessage(error)
    return Promise.reject(new Error(message))
  }
)

export default client
