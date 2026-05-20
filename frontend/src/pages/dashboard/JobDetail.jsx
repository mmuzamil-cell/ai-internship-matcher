import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { getJobById } from '../../api/jobs'
import { applyToJob } from '../../api/applications'
import { getMyMatches } from '../../api/matching'
import MatchScoreBadge from '../../components/ui/MatchScoreBadge'
import SkillTag from '../../components/ui/SkillTag'
import JobCard from '../../components/ui/JobCard'
import LoadingSpinner from '../../components/ui/LoadingSpinner'
import { formatDate, formatDeadline } from '../../utils/formatDate'
import { getCompanyColor, getInitials } from '../../utils/formatScore'

const COURSE_LINKS = {
  'React': 'https://www.coursera.org/learn/react-basics',
  'Python': 'https://www.coursera.org/learn/python',
  'Machine Learning': 'https://www.coursera.org/learn/machine-learning',
  'SQL': 'https://www.coursera.org/learn/sql-for-data-science',
  'Docker': 'https://www.coursera.org/learn/docker-for-developers',
  'default': 'https://www.coursera.org/search?query=',
}

export default function JobDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [saved, setSaved] = useState(() => {
    try { return JSON.parse(localStorage.getItem('saved_jobs') || '[]').includes(id) } catch { return false }
  })

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => getJobById(id),
  })

  const { data: allMatches = [] } = useQuery({
    queryKey: ['matches'],
    queryFn: () => getMyMatches({ limit: 20 }),
  })

  // Flatten match result: backend returns { internship, score_percent, matching_skills, missing_skills }
  const rawMatchData = allMatches.find((m) => String(m.internship?.id) === String(id))
  const matchData = rawMatchData ? {
    match_score: rawMatchData.score_percent,
    matched_skills: rawMatchData.matching_skills || [],
    missing_skills: rawMatchData.missing_skills || [],
  } : null

  const applyMutation = useMutation({
    mutationFn: () => applyToJob(id),
    onSuccess: () => {
      toast.success('Application submitted! 🎉')
      queryClient.invalidateQueries({ queryKey: ['applications'] })
    },
    onError: (e) => toast.error(e.message),
  })

  const toggleSave = () => {
    const saved_jobs = JSON.parse(localStorage.getItem('saved_jobs') || '[]')
    const newList = saved_jobs.includes(id)
      ? saved_jobs.filter((j) => j !== id)
      : [...saved_jobs, id]
    localStorage.setItem('saved_jobs', JSON.stringify(newList))
    setSaved(!saved)
    toast.success(saved ? 'Removed from saved' : 'Saved for later!')
  }

  const copyUrl = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      toast.success('Link copied!')
    } catch {
      toast.error('Could not copy link')
    }
  }

  if (isLoading) {
    return (
      <div className="py-8 px-4 sm:px-6 max-w-7xl mx-auto">
        <div className="skeleton h-8 w-32 mb-6" />
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <div className="card p-8 space-y-4">
              <div className="skeleton h-8 w-64" />
              <div className="skeleton h-5 w-40" />
              <div className="flex gap-2">
                {Array(3).fill(0).map((_, i) => <div key={i} className="skeleton h-7 w-24 rounded-lg" />)}
              </div>
              <div className="skeleton h-40 w-full mt-4" />
            </div>
          </div>
          <div className="skeleton h-64 rounded-2xl" />
        </div>
      </div>
    )
  }

  if (!job) return null

  const deadline = formatDeadline(job.deadline)
  const colorClass = getCompanyColor(job.company)
  const isRemote = job.is_remote || /remote/i.test(job.location || '')
  const similar = allMatches
    .filter((m) => m.internship?.id !== Number(id) && m.internship?.company !== job.company)
    .slice(0, 3)
    .map((m) => ({
      ...m.internship,
      is_remote: /remote/i.test(m.internship?.location || ''),
      match_score: m.score_percent,
      matched_skills: m.matching_skills || [],
      missing_skills: m.missing_skills || [],
    }))

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="py-8 px-4 sm:px-6 max-w-7xl mx-auto space-y-6"
    >
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors btn-ghost"
      >
        ← Back
      </button>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Header card */}
          <div className="card p-8">
            <div className="flex items-start gap-5">
              <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${colorClass} flex items-center justify-center font-display text-xl font-bold text-white shrink-0 shadow-xl`}>
                {getInitials(job.company)}
              </div>
              <div className="flex-1 min-w-0">
                <h1 className="font-display text-2xl sm:text-3xl font-bold text-white mb-1">{job.title}</h1>
                <p className="text-slate-400 text-lg mb-4">{job.company}</p>
                <div className="flex flex-wrap gap-2">
                  <span className="text-sm bg-slate-700/60 text-slate-300 rounded-lg px-3 py-1.5 border border-slate-600/40">
                    📍 {isRemote ? 'Remote' : job.location || 'On-site'}
                  </span>
                  {job.stipend && (
                    <span className="text-sm bg-slate-700/60 text-slate-300 rounded-lg px-3 py-1.5 border border-slate-600/40">
                      💰 {job.stipend}
                    </span>
                  )}
                  {deadline && (
                    <span className={`text-sm rounded-lg px-3 py-1.5 border ${deadline.urgent ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-slate-700/60 text-slate-300 border-slate-600/40'}`}>
                      ⏰ {deadline.label}
                    </span>
                  )}
                  {job.deadline && (
                    <span className="text-sm bg-slate-700/60 text-slate-300 rounded-lg px-3 py-1.5 border border-slate-600/40">
                      📅 {formatDate(job.deadline)}
                    </span>
                  )}
                </div>
              </div>
              {matchData?.match_score != null && (
                <MatchScoreBadge score={matchData.match_score} size="lg" />
              )}
            </div>
          </div>

          {/* Description */}
          <div className="card p-6">
            <h2 className="font-display text-lg font-semibold text-white mb-4">📋 Job Description</h2>
            <div className="text-slate-300 text-sm leading-relaxed space-y-2">
              {(job.description || 'No description available.').split('\n').filter(Boolean).map((p, i) => {
                const trimmed = p.trim()
                if (!trimmed) return null
                // Render bullet-like items
                if (trimmed.startsWith('•') || trimmed.startsWith('-') || trimmed.startsWith('*')) {
                  return (
                    <div key={i} className="flex gap-2 pl-2">
                      <span className="text-sky-400 shrink-0">•</span>
                      <span>{trimmed.replace(/^[•\-\*]\s?/, '')}</span>
                    </div>
                  )
                }
                // Render section headers (lines ending with ':')
                if (trimmed.endsWith(':') && trimmed.length < 60) {
                  return <p key={i} className="font-semibold text-white mt-3">{trimmed}</p>
                }
                // Render key-value lines (e.g. "Location: Remote")
                if (/^(Location|Compensation|Job Type|Posted|Category|Salary):/.test(trimmed)) {
                  const [label, ...rest] = trimmed.split(':')
                  return (
                    <div key={i} className="flex gap-2">
                      <span className="text-slate-400 font-medium shrink-0">{label}:</span>
                      <span>{rest.join(':').trim()}</span>
                    </div>
                  )
                }
                return <p key={i}>{trimmed}</p>
              })}
            </div>
            {job.source_url && (
              <a
                href={job.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 mt-4 text-sm text-sky-400 hover:text-sky-300 transition-colors
                           bg-sky-500/10 px-4 py-2 rounded-xl border border-sky-500/20 hover:bg-sky-500/15"
              >
                🔗 View & apply on {job.source_site || 'source'} →
              </a>
            )}
          </div>

          {/* Skills sections */}
          <div className="card p-6 space-y-6">
            <div>
              <h2 className="font-display text-lg font-semibold text-white mb-3">🛠 Required Skills</h2>
              <div className="flex flex-wrap gap-2">
                {(job.required_skills || []).map((s) => (
                  <SkillTag key={s} skill={s} variant="neutral" size="md" />
                ))}
                {!job.required_skills?.length && <p className="text-slate-500 text-sm">Not specified</p>}
              </div>
            </div>

            {matchData?.matched_skills?.length > 0 && (
              <div>
                <h2 className="font-display text-lg font-semibold text-white mb-3">✅ Why You Match</h2>
                <div className="flex flex-wrap gap-2">
                  {matchData.matched_skills.map((s) => (
                    <SkillTag key={s} skill={s} variant="matched" size="md" />
                  ))}
                </div>
              </div>
            )}

            {matchData?.missing_skills?.length > 0 && (
              <div>
                <h2 className="font-display text-lg font-semibold text-white mb-3">📚 Skills to Learn</h2>
                <div className="flex flex-wrap gap-2">
                  {matchData.missing_skills.map((s) => {
                    const link = COURSE_LINKS[s] || `${COURSE_LINKS.default}${encodeURIComponent(s)}`
                    return (
                      <a key={s} href={link} target="_blank" rel="noopener noreferrer">
                        <SkillTag skill={s} variant="missing" size="md" />
                      </a>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sticky Action Card */}
        <div className="space-y-4">
          <div className="card p-6 space-y-3 lg:sticky lg:top-24">
            <button
              onClick={() => applyMutation.mutate()}
              disabled={applyMutation.isPending}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 text-base"
            >
              {applyMutation.isPending ? <LoadingSpinner size="sm" /> : '🚀'}
              {applyMutation.isPending ? 'Submitting…' : 'Apply Now'}
            </button>

            {job.source_url && (
              <a
                href={job.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-3 rounded-xl font-medium transition-all text-sm text-center block
                           bg-gradient-to-r from-sky-500/15 to-blue-500/15 text-sky-300 border border-sky-500/30
                           hover:from-sky-500/25 hover:to-blue-500/25 hover:shadow-lg hover:shadow-sky-500/5"
              >
                🔗 Apply on {job.source_site || 'Source'}
              </a>
            )}

            <button
              onClick={toggleSave}
              className={`w-full py-3 rounded-xl font-medium transition-all text-sm ${
                saved
                  ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30 hover:bg-amber-500/25'
                  : 'btn-secondary'
              }`}
            >
              {saved ? '⭐ Saved for Later' : '🔖 Save for Later'}
            </button>

            <button onClick={copyUrl} className="w-full btn-ghost py-2.5 text-sm">
              🔗 Copy Link
            </button>

            {job.company_url && (
              <a
                href={job.company_url}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full flex items-center justify-center gap-2 btn-ghost py-2.5 text-sm"
              >
                🌐 Company Website
              </a>
            )}

            {matchData?.match_score != null && (
              <div className="pt-3 border-t border-slate-700/50">
                <p className="text-slate-400 text-xs text-center mb-2">Your match score</p>
                <div className="flex justify-center">
                  <MatchScoreBadge score={matchData.match_score} size="md" />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Similar Internships */}
      {similar.length > 0 && (
        <div className="space-y-4">
          <h2 className="font-display text-xl font-semibold text-white">Similar Internships</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {similar.map((job, i) => <JobCard key={job.id} job={job} index={i} />)}
          </div>
        </div>
      )}
    </motion.div>
  )
}
