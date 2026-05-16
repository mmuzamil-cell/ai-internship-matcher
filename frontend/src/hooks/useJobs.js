import { useQuery } from '@tanstack/react-query'
import { getJobs, getJobById, getJobStats } from '../api/jobs'
import { getMyMatches } from '../api/matching'

export const useJobs = (params) =>
  useQuery({ queryKey: ['jobs', params], queryFn: () => getJobs(params) })

export const useJob = (id) =>
  useQuery({ queryKey: ['job', id], queryFn: () => getJobById(id), enabled: !!id })

export const useJobStats = () =>
  useQuery({ queryKey: ['jobStats'], queryFn: getJobStats })

export const useMyMatches = (params) =>
  useQuery({ queryKey: ['matches', params], queryFn: () => getMyMatches(params) })
