import client from './client'

export const getMyMatches = async (params = {}) => {
  const res = await client.get('/match/my-matches', { params })
  return res.data
}

export const getSkillGap = async () => {
  const res = await client.get('/match/skill-gap')
  return res.data
}
