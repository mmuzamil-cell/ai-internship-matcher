import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import { Link } from 'react-router-dom'
import { getScraperSources, scrapeInternships, getScraperStatus } from '../../api/scraper'
import { applyToJob } from '../../api/applications'
import SkillTag from '../../components/ui/SkillTag'
import EmptyState from '../../components/ui/EmptyState'

const SUGGESTED_KEYWORDS = [
  'software engineer intern',
  'data science internship',
  'web developer',
  'python developer',
  'react developer',
  'machine learning',
  'ui ux design',
  'cybersecurity',
  'mobile developer',
  'devops',
  'business analyst',
  'cloud engineer',
]

function ScrapedJobCard({ job, onApply }) {
  const [expanded, setExpanded] = useState(false)

  const {
    id,
    title,
    company,
    location,
    description,
    required_skills = [],
    stipend,
    source_url,
    source_site,
    scraped_at,
  } = job

  const isRemote = /remote/i.test(location || '')

  // Format description for display
  const descriptionLines = (description || 'No description available.').split('\n').filter(Boolean)
  const shortDesc = descriptionLines.slice(0, 3).join('\n')
  const hasMore = descriptionLines.length > 3

  const applyMutation = useMutation({
    mutationFn: () => applyToJob(id),
    onSuccess: () => toast.success(`Applied to ${title}!`),
    onError: (e) => toast.error(e.message),
  })

  // Generate company initials
  const initials = (company || '?')
    .split(/[\s&]+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()

  const colors = [
    'from-violet-500 to-purple-600',
    'from-sky-500 to-blue-600',
    'from-emerald-500 to-teal-600',
    'from-amber-500 to-orange-600',
    'from-rose-500 to-pink-600',
    'from-indigo-500 to-blue-600',
    'from-cyan-500 to-teal-600',
  ]
  const colorIdx = (company || '').split('').reduce((a, c) => a + c.charCodeAt(0), 0) % colors.length

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="card p-0 overflow-hidden hover:border-slate-600/80 transition-all duration-200 hover:shadow-xl hover:shadow-black/20"
    >
      {/* Header */}
      <div className="p-5 pb-3">
        <div className="flex items-start gap-3">
          <div
            className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colors[colorIdx]} flex items-center justify-center font-display text-sm font-bold text-white shrink-0 shadow-lg`}
          >
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-display font-semibold text-white text-base leading-tight">
              {title}
            </h3>
            <p className="text-slate-400 text-sm mt-0.5">{company}</p>
          </div>
          {source_site && (
            <span className="text-xs bg-slate-800/80 text-slate-400 rounded-lg px-2 py-1 border border-slate-700/40 shrink-0">
              {source_site}
            </span>
          )}
        </div>

        {/* Info Chips */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          <span className="text-xs bg-slate-700/60 text-slate-300 rounded-lg px-2 py-1 border border-slate-600/40">
            📍 {isRemote ? 'Remote' : location || 'On-site'}
          </span>
          {stipend && (
            <span className="text-xs bg-emerald-500/10 text-emerald-400 rounded-lg px-2 py-1 border border-emerald-500/20">
              💰 {stipend}
            </span>
          )}
          {scraped_at && (
            <span className="text-xs bg-slate-700/60 text-slate-400 rounded-lg px-2 py-1 border border-slate-600/40">
              🕐 {new Date(scraped_at).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>

      {/* Description Section */}
      <div className="px-5 pb-3">
        <div className="border-t border-slate-700/40 pt-3">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            📋 Description
          </h4>
          <div className="text-slate-300 text-sm leading-relaxed whitespace-pre-line">
            {expanded ? descriptionLines.join('\n') : shortDesc}
          </div>
          {hasMore && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-sky-400 text-xs mt-2 hover:text-sky-300 transition-colors font-medium"
            >
              {expanded ? '▲ Show less' : `▼ Show more (${descriptionLines.length - 3} more lines)`}
            </button>
          )}
        </div>
      </div>

      {/* Skills */}
      {required_skills.length > 0 && (
        <div className="px-5 pb-3">
          <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
            🛠 Skills
          </h4>
          <div className="flex flex-wrap gap-1">
            {required_skills.slice(0, 8).map((s) => (
              <SkillTag key={s} skill={s} variant="neutral" size="sm" />
            ))}
            {required_skills.length > 8 && (
              <span className="text-xs text-slate-500 px-1.5 py-0.5">
                +{required_skills.length - 8} more
              </span>
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="px-5 py-3 bg-slate-800/30 border-t border-slate-700/30 flex flex-wrap gap-2">
        <Link
          to={`/jobs/${id}`}
          className="flex-1 btn-secondary text-sm py-2 text-center rounded-xl"
        >
          📄 Full Details
        </Link>
        {source_url && (
          <a
            href={source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 text-sm py-2 text-center rounded-xl font-medium transition-all
                       bg-gradient-to-r from-sky-500/15 to-blue-500/15 text-sky-300 border border-sky-500/30
                       hover:from-sky-500/25 hover:to-blue-500/25 hover:shadow-lg hover:shadow-sky-500/5"
          >
            🔗 Apply on {source_site || 'Source'}
          </a>
        )}
        <button
          onClick={() => applyMutation.mutate()}
          disabled={applyMutation.isPending}
          className="flex-1 btn-primary text-sm py-2 flex items-center justify-center gap-2 rounded-xl"
        >
          {applyMutation.isPending ? (
            <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : null}
          {applyMutation.isPending ? 'Applying...' : '🚀 Quick Apply'}
        </button>
      </div>
    </motion.div>
  )
}

export default function ScrapeInternships() {
  const queryClient = useQueryClient()
  const [keyword, setKeyword] = useState('software engineer intern')
  const [selectedSources, setSelectedSources] = useState(new Set(['all']))
  const [limit, setLimit] = useState(15)
  const [scrapedJobs, setScrapedJobs] = useState([])
  const [scrapeLog, setScrapeLog] = useState([])

  // Fetch available sources
  const { data: sources = {} } = useQuery({
    queryKey: ['scraperSources'],
    queryFn: getScraperSources,
  })

  // Fetch scraper status
  const { data: status } = useQuery({
    queryKey: ['scraperStatus'],
    queryFn: getScraperStatus,
  })

  // Toggle source selection
  const toggleSource = (key) => {
    setSelectedSources((prev) => {
      const next = new Set(prev)
      if (key === 'all') {
        return new Set(['all'])
      }
      next.delete('all')
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      if (next.size === 0) return new Set(['all'])
      return next
    })
  }

  // Scrape mutation
  const scrapeMutation = useMutation({
    mutationFn: () => {
      const sourcesStr = selectedSources.has('all') ? 'all' : [...selectedSources].join(',')
      return scrapeInternships({ keyword, sources: sourcesStr, limit })
    },
    onMutate: () => {
      setScrapeLog((prev) => [
        ...prev,
        { time: new Date().toLocaleTimeString(), message: `🚀 Starting scrape for "${keyword}"...`, type: 'info' },
      ])
    },
    onSuccess: (data) => {
      const newJobs = (data.internships || []).map((job) => ({
        ...job,
        is_remote: /remote/i.test(job.location || ''),
        match_score: null,
        matched_skills: job.required_skills || [],
        missing_skills: [],
      }))
      setScrapedJobs((prev) => [...newJobs, ...prev])

      setScrapeLog((prev) => [
        ...prev,
        {
          time: new Date().toLocaleTimeString(),
          message: `✅ Found ${data.imported} new internships from ${data.sources.join(', ')}${data.skipped ? ` (${data.skipped} duplicates skipped)` : ''}`,
          type: 'success',
        },
      ])

      toast.success(`Scraped ${data.imported} internships!`)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['jobStats'] })
      queryClient.invalidateQueries({ queryKey: ['matches'] })
      queryClient.invalidateQueries({ queryKey: ['scraperStatus'] })
    },
    onError: (err) => {
      setScrapeLog((prev) => [
        ...prev,
        { time: new Date().toLocaleTimeString(), message: `❌ ${err.message}`, type: 'error' },
      ])
      toast.error(err.message)
    },
  })

  return (
    <div className="py-8 px-4 sm:px-6 max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <h1 className="page-title">
            Scrape <span className="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">Internships</span>
          </h1>
          <p className="text-slate-400 mt-1">
            Fetch real internship listings from multiple job platforms automatically
          </p>
        </div>

        {/* Stats Badge */}
        {status && (
          <div className="card p-3 flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-slate-300">
                <span className="font-semibold text-white">{status.total_internships}</span> in database
              </span>
            </div>
            <div className="text-slate-500">|</div>
            <div className="text-slate-400">
              <span className="text-emerald-400 font-semibold">{status.active_internships}</span> active
            </div>
            {status.last_scraped_at && (
              <>
                <div className="text-slate-500">|</div>
                <div className="text-slate-400 text-xs">
                  Last: {new Date(status.last_scraped_at).toLocaleDateString()}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Scrape Controls */}
      <div className="card p-6 space-y-5">
        <h2 className="font-display text-lg font-semibold text-white flex items-center gap-2">
          🔧 Scrape Configuration
        </h2>

        {/* Keyword Input */}
        <div className="space-y-2">
          <label className="text-sm text-slate-400 font-medium">Search Keyword</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="e.g., python developer internship"
              className="input-field flex-1"
            />
            <button
              onClick={() => scrapeMutation.mutate()}
              disabled={scrapeMutation.isPending || keyword.trim().length < 2}
              className="btn-primary px-6 flex items-center gap-2 whitespace-nowrap"
            >
              {scrapeMutation.isPending ? (
                <>
                  <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Scraping...
                </>
              ) : (
                <>🚀 Start Scraping</>
              )}
            </button>
          </div>

          {/* Suggested Keywords */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {SUGGESTED_KEYWORDS.map((kw) => (
              <button
                key={kw}
                onClick={() => setKeyword(kw)}
                className={`text-xs px-2.5 py-1 rounded-lg border transition-all ${
                  keyword === kw
                    ? 'bg-sky-500/15 text-sky-400 border-sky-500/30'
                    : 'bg-slate-800/60 text-slate-400 border-slate-700/50 hover:border-slate-600 hover:text-slate-300'
                }`}
              >
                {kw}
              </button>
            ))}
          </div>
        </div>

        {/* Source Selection */}
        <div className="space-y-2">
          <label className="text-sm text-slate-400 font-medium">Select Sources</label>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {/* All sources button */}
            <button
              onClick={() => toggleSource('all')}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium transition-all border ${
                selectedSources.has('all')
                  ? 'bg-gradient-to-r from-sky-500/20 to-blue-500/20 text-sky-300 border-sky-500/40 shadow-lg shadow-sky-500/10'
                  : 'bg-slate-800/60 text-slate-400 border-slate-700/50 hover:border-slate-600'
              }`}
            >
              <span>🌐</span>
              <span>All Sources</span>
              {selectedSources.has('all') && <span className="ml-auto text-sky-400">✓</span>}
            </button>

            {/* Individual sources */}
            {Object.entries(sources).map(([key, source]) => (
              <button
                key={key}
                onClick={() => toggleSource(key)}
                className={`flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium transition-all border ${
                  selectedSources.has(key) || selectedSources.has('all')
                    ? 'bg-gradient-to-r from-emerald-500/15 to-teal-500/15 text-emerald-300 border-emerald-500/30'
                    : 'bg-slate-800/60 text-slate-400 border-slate-700/50 hover:border-slate-600'
                }`}
              >
                <span>{source.icon}</span>
                <div className="text-left min-w-0">
                  <div className="truncate">{source.name}</div>
                </div>
                {(selectedSources.has(key) || selectedSources.has('all')) && (
                  <span className="ml-auto text-emerald-400">✓</span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Limit Slider */}
        <div className="flex items-center gap-4">
          <label className="text-sm text-slate-400 font-medium whitespace-nowrap">Results per source:</label>
          <input
            type="range"
            min="5"
            max="50"
            step="5"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="flex-1 accent-sky-500"
          />
          <span className="text-sm text-sky-400 font-mono w-8 text-right">{limit}</span>
        </div>
      </div>

      {/* Scrape Progress / Log */}
      {scrapeLog.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="card p-4 space-y-2"
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-display text-sm font-semibold text-white flex items-center gap-2">
              📋 Scraping Log
              {scrapeMutation.isPending && (
                <span className="inline-block w-3 h-3 border-2 border-sky-500/30 border-t-sky-400 rounded-full animate-spin" />
              )}
            </h3>
            <button
              onClick={() => setScrapeLog([])}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              Clear
            </button>
          </div>
          <div className="max-h-40 overflow-y-auto space-y-1 font-mono text-xs">
            {scrapeLog.map((log, i) => (
              <div
                key={i}
                className={`flex gap-2 px-2 py-1 rounded ${
                  log.type === 'success'
                    ? 'bg-emerald-500/5 text-emerald-400'
                    : log.type === 'error'
                    ? 'bg-rose-500/5 text-rose-400'
                    : 'bg-slate-800/30 text-slate-400'
                }`}
              >
                <span className="text-slate-600 shrink-0">[{log.time}]</span>
                <span>{log.message}</span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Source Stats (from database) */}
      {status?.by_source && Object.keys(status.by_source).length > 0 && (
        <div className="card p-5">
          <h3 className="font-display text-sm font-semibold text-white mb-3">📊 Internships by Source</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {Object.entries(status.by_source)
              .sort(([, a], [, b]) => b - a)
              .map(([source, count]) => (
                <div key={source} className="bg-slate-800/50 rounded-xl p-3 text-center border border-slate-700/30">
                  <p className="font-display text-xl font-bold text-white">{count}</p>
                  <p className="text-xs text-slate-400 mt-0.5 truncate">{source}</p>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Scraped Results */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg font-semibold text-white">
            {scrapedJobs.length > 0
              ? `🆕 Recently Scraped (${scrapedJobs.length})`
              : '📂 Scraped Internships'}
          </h2>
          {scrapedJobs.length > 0 && (
            <Link to="/my-matches" className="text-sky-400 text-sm hover:text-sky-300 transition-colors">
              View all internships →
            </Link>
          )}
        </div>

        {scrapeMutation.isPending ? (
          <div className="card p-12 flex flex-col items-center justify-center gap-4">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-slate-700 rounded-full" />
              <div className="w-16 h-16 border-4 border-transparent border-t-sky-500 rounded-full absolute inset-0 animate-spin" />
              <div className="w-16 h-16 border-4 border-transparent border-t-emerald-500 rounded-full absolute inset-0 animate-spin" style={{ animationDuration: '1.5s', animationDirection: 'reverse' }} />
            </div>
            <div className="text-center">
              <p className="text-white font-display font-semibold">Scraping in progress...</p>
              <p className="text-slate-400 text-sm mt-1">
                Fetching internships from {selectedSources.has('all') ? 'all sources' : [...selectedSources].join(', ')}
              </p>
            </div>
          </div>
        ) : scrapedJobs.length > 0 ? (
          <div className="grid lg:grid-cols-2 gap-4">
            <AnimatePresence>
              {scrapedJobs.map((job) => (
                <ScrapedJobCard key={`scraped-${job.id}`} job={job} />
              ))}
            </AnimatePresence>
          </div>
        ) : (
          <EmptyState
            icon="🌐"
            title="No internships scraped yet"
            description="Configure your search above and hit 'Start Scraping' to fetch real internships from job platforms."
            action={
              <button
                onClick={() => scrapeMutation.mutate()}
                disabled={scrapeMutation.isPending}
                className="btn-primary"
              >
                🚀 Start Scraping
              </button>
            }
          />
        )}
      </div>
    </div>
  )
}
