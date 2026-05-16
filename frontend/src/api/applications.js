import client from './client'

// BUG FIX: backend POST /applications expects { internship_id }, not { job_id }
export const applyToJob = async (internshipId, data = {}) => {
  const res = await client.post('/applications', { internship_id: internshipId, ...data })
  return res.data
}

// BUG FIX: backend GET /applications (not /applications/my-applications)
export const getMyApplications = async () => {
  const res = await client.get('/applications')
  return res.data
}

export const updateApplicationStatus = async (id, data) => {
  const res = await client.put(`/applications/${id}`, data)
  return res.data
}
