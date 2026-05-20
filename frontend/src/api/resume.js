import client from './client'

export const uploadResume = async (file, onUploadProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  const res = await client.post('/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
  })
  return res.data
}

export const getMyResumes = async () => {
  const res = await client.get('/resume/my-resumes')
  return res.data
}

export const deleteResume = async (id) => {
  const res = await client.delete(`/resume/${id}`)
  return res.data
}

/**
 * Save CV Builder data as a resume record for AI matching.
 * @param {Object} cvData - Full CV form data
 */
export const saveCVAsResume = async (cvData) => {
  const res = await client.post('/resume/from-cv', cvData)
  return res.data
}

/**
 * Fetch detailed ATS analysis feedback for a resume.
 * @param {number} id - Resume ID
 */
export const getResumeFeedback = async (id) => {
  const res = await client.get(`/resume/${id}/feedback`)
  return res.data
}

