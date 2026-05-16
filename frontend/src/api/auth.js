import client from './client'

export const register = async (data) => {
  const res = await client.post('/auth/register', data)
  return res.data
}

export const login = async ({ email, password }) => {
  const formData = new URLSearchParams()
  formData.append('username', email)
  formData.append('password', password)
  const res = await client.post('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return res.data // { access_token, token_type }
}

export const getMe = async () => {
  const res = await client.get('/auth/me')
  return res.data
}

export const updateProfile = async (data) => {
  const res = await client.put('/auth/me', data)
  return res.data
}
