import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { Link } from 'react-router-dom'
import { getJobs, importExternalJobs } from '../../api/jobs'
import { getMyMatches } from '../../api/matching'
import JobCard from '../../components/ui/JobCard'
import EmptyState from '../../components/ui/EmptyState'

const SORT_OPTIONS = [
  { value: 'score', label: 'Best Match' },
  { value: 'recent', label: 'Most Recent' },
  { value: 'deadline', label: 'Deadline Soon' },
  { value: 'stipend', label: 'Highest Stipend' },
]

const SkeletonJobCard = () => (
  <div className="card p-5 space-y-4">
    <div className="flex items-center gap-3">
      <div className="skeleton w-11 h-11 rounded-xl" />
      <div className="flex-1 space-y-2">
        <div className="skeleton h-4 w-36" />
        <div className="skeleton h-3 w-24" />
      </div>
    </div>
    <div className="flex gap-2">
      <div className="skeleton h-6 w-20 rounded-lg" />
      <div className="skeleton h-6 w-16 rounded-lg" />
    </div>
    <div className="flex gap-2">
      <div className="skeleton h-9 flex-1 rounded-xl" />
      <div className="skeleton h-9 flex-1 rounded-xl" />
    </div>
  </div>
)

const parseStipend = (value) => parseInt(String(value || '').replace(/[^\d]/g, ''), 10) || 0

export default function MyMatches() {
  const queryClient = useQueryClient()
  const [sort, setSort] = useState('score')
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [minScore, setMinScore] = useState(0)
  const [city, setCity] = useState('')
  const [keyword, setKeyword] = useState('internship')

  const flattenMatch = (match) => ({
    ...match.internship,
    is_remote: /remote/i.test(match.internship?.location || ''),
    match_score: match.score_percent,
    matched_skills: match.matching_skills || [],
    missing_skills: match.missing_skills || [],
  })

  const normalizeJob = (job) => ({
    ...job,
    is_remote: /remote/i.test(job.location || ''),
    match_score: null,
    matched_skills: job.required_skills || [],
    missing_skills: [],
  })

  const { data: rawMatches = [], isLoading: matchesLoading, error } = useQuery({
    queryKey: ['matches'],
    queryFn: () => getMyMatches(),
  })

  const { data: rawJobs = [], isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs', 'browse'],
    queryFn: () => getJobs({ limit: 100 }),
  })

  const importMutation = useMutation({
    mutationFn: () => importExternalJobs({ keyword, limit: 20 }),
    onSuccess: (data) => {
      toast.success(`Fetched ${data.imported} new internships`)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['jobStats'] })
      queryClient.invalidateQueries({ queryKey: ['matches'] })
    },
    onError: (e) => toast.error(e.message),
  })

  const matches = useMemo(() => rawMatches.map(flattenMatch), [rawMatches])
  const browseJobs = useMemo(() => rawJobs.map(normalizeJob), [rawJobs])
  const displayJobs = matches.length > 0 ? matches : browseJobs
  const isBrowseMode = matches.length === 0
  const isLoading = matchesLoading || jobsLoading

  const filtered = useMemo(() => {
    let list = [...displayJobs]
    if (remoteOnly) list = list.filter((job) => job.is_remote || /remote/i.test(job.location || ''))
    if (city) list = list.filter((job) => job.location?.toLowerCase().includes(city.toLowerCase()))
    if (minScore > 0) list = list.filter((job) => (job.match_score || 0) >= minScore)

    switch (sort) {
      case 'score':
        list.sort((a, b) => (b.match_score || 0) - (a.match_score || 0))
        break
      case 'recent':
        list.sort((a, b) => new Date(b.scraped_at || 0) - new Date(a.scraped_at || 0))
        break
      case 'deadline':
        list.sort((a, b) => new Date(a.deadline || '9999') - new Date(b.deadline || '9999'))
        break
      case 'stipend':
        list.sort((a, b) => parseStipend(b.stipend) - parseStipend(a.stipend))
        break
    }
    return list
  }, [displayJobs, sort, remoteOnly, minScore, city])

  return (
    <div className="py-8 px-4 sm:px-6 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <h1 className="page-title">Intern<span className="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">ships</span></h1>
          <p className="text-slate-400 mt-1">
            {isLoading
              ? 'Loading internships...'
              : isBrowseMode
                ? `${filtered.length} internships available to browse`
                : `${filtered.length} opportunities matched to your profile`}
          </p>
        </div>

        <div className="card p-3 flex flex-col sm:flex-row gap-2 sm:items-center">
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="python internship"
            className="input-field py-2 text-sm sm:w-52 bg-white/[0.03]"
          />
          <button
            onClick={() => importMutation.mutate()}
            disabled={importMutation.isPending || keyword.trim().length < 2}
            className="btn-primary text-sm py-2 whitespace-nowrap"
          >
            {importMutation.isPending ? 'Fetching...' : 'Fetch internships'}
          </button>
        </div>
      </div>

      <div className="card p-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-400 whitespace-nowrap">Sort by</label>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="input-field py-2 text-sm w-auto"
          >
            {SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </div>

        <input
          type="text"
          placeholder="Filter by city..."
          value={city}
          onChange={(e) => setCity(e.target.value)}
          className="input-field py-2 text-sm w-40"
        />

        <label className="flex items-center gap-2 cursor-pointer">
          <div
            onClick={() => setRemoteOnly(!remoteOnly)}
            className={`w-9 h-5 rounded-full transition-colors relative cursor-pointer ${remoteOnly ? 'bg-sky-500' : 'bg-white/[0.1]'}`}
          >
            <div
              className="w-3.5 h-3.5 bg-white rounded-full absolute top-0.75 transition-transform"
              style={{ top: 3, left: remoteOnly ? 18 : 2 }}
            />
          </div>
          <span className="text-sm text-slate-300">Remote only</span>
        </label>

        {!isBrowseMode && (
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <span className="text-sm text-slate-400 whitespace-nowrap">Min score</span>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="flex-1 accent-sky-500"
            />
            <span className="text-sm text-sky-400 font-mono w-10 text-right">{minScore}%</span>
          </div>
        )}

        {(remoteOnly || minScore > 0 || city) && (
          <button
            onClick={() => { setRemoteOnly(false); setMinScore(0); setCity('') }}
            className="text-sm text-slate-400 hover:text-white transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array(6).fill(0).map((_, i) => <SkeletonJobCard key={i} />)}
        </div>
      ) : error && !isBrowseMode ? (
        <EmptyState
          icon="!"
          title="Failed to load matches"
          description={error.message}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="F"
          title="No internships yet"
          description="Fetch internships from external platforms, or upload your resume for AI-ranked matches."
          action={
            <div className="flex flex-wrap gap-2 justify-center">
              <button onClick={() => importMutation.mutate()} className="btn-primary">Fetch internships</button>
              <Link to="/resume" className="btn-secondary">Upload Resume</Link>
            </div>
          }
        />
      ) : (
        <motion.div layout className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((job, index) => (
            <JobCard key={job.id} job={job} index={index} />
          ))}
        </motion.div>
      )}
    </div>
  )
}
