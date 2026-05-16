import client from './client'

export const getJobs = async (params = {}) => {
  const res = await client.get('/jobs', { params })
  return res.data
}

export const getJobById = async (id) => {
  const res = await client.get(`/jobs/${id}`)
  return res.data
}

export const getJobStats = async () => {
  const res = await client.get('/jobs/stats')
  return res.data
}

export const importExternalJobs = async ({ keyword = 'internship', limit = 20 } = {}) => {
  const res = await client.post('/jobs/import-external', null, {
    params: { keyword, limit },
  })
  return res.data
}
