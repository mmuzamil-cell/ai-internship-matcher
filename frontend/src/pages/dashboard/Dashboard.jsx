import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Doughnut } from 'react-chartjs-2'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { useAuth } from '../../hooks/useAuth'
import { getJobStats } from '../../api/jobs'
import { getMyMatches } from '../../api/matching'
import { getMyApplications } from '../../api/applications'
import JobCard from '../../components/ui/JobCard'
import EmptyState from '../../components/ui/EmptyState'
import { formatRelativeTime } from '../../utils/formatDate'

ChartJS.register(ArcElement, Tooltip, Legend)

const StatCard = ({ icon, label, value, sub, accent, delay }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay }}
    className="card p-6 hover:border-white/[0.1] transition-all duration-300 group"
  >
    <div className="flex items-start justify-between">
      <div>
        <p className="text-slate-400 text-sm mb-1">{label}</p>
        <p className={`font-display text-3xl font-bold ${accent || 'text-white'}`}>{value}</p>
        {sub && <p className="text-slate-500 text-xs mt-1">{sub}</p>}
      </div>
      <span className="text-2xl group-hover:scale-110 transition-transform duration-300">{icon}</span>
    </div>
  </motion.div>
)

const SkeletonCard = () => (
  <div className="card p-6">
    <div className="skeleton h-4 w-24 mb-3" />
    <div className="skeleton h-8 w-16 mb-2" />
    <div className="skeleton h-3 w-32" />
  </div>
)

export default function Dashboard() {
  const { user } = useAuth()

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['jobStats'],
    queryFn: getJobStats,
  })

  const { data: matches, isLoading: matchesLoading } = useQuery({
    queryKey: ['matches'],
    queryFn: () => getMyMatches({ limit: 5 }),
  })

  const { data: applications, isLoading: appsLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: getMyApplications,
  })

  const flatMatches = matches?.map((m) => ({
    ...m.internship,
    is_remote: /remote/i.test(m.internship?.location || ''),
    match_score: m.score_percent,
    matched_skills: m.matching_skills || [],
    missing_skills: m.missing_skills || [],
  })) || []

  const avgScore = flatMatches.length
    ? Math.round(flatMatches.slice(0, 5).reduce((a, m) => a + (m.match_score || 0), 0) / Math.min(5, flatMatches.length))
    : null

  const allMatchedSkills = new Set()
  const allMissingSkills = new Set()
  flatMatches.forEach((m) => {
    ;(m.matched_skills || []).forEach((s) => allMatchedSkills.add(s))
    ;(m.missing_skills || []).forEach((s) => allMissingSkills.add(s))
  })
  const skillsMatched = allMatchedSkills.size
  const skillsMissing = allMissingSkills.size

  const donutData = {
    labels: ['Matched', 'Missing'],
    datasets: [{
      data: [skillsMatched || 1, skillsMissing || 1],
      backgroundColor: ['#10b981', '#f43f5e'],
      borderColor: ['transparent', 'transparent'],
      borderWidth: 0,
    }],
  }

  const donutOptions = {
    cutout: '72%',
    plugins: { legend: { display: false }, tooltip: { enabled: true } },
    animation: { duration: 1200 },
  }

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  const statCards = [
    { icon: '💼', label: 'Internships Available', value: statsLoading ? '—' : (stats?.total_active?.toLocaleString() || '0'), sub: 'Updated today', accent: 'text-white' },
    { icon: '⚡', label: 'My Match Score', value: avgScore != null ? `${avgScore}%` : '—', sub: 'Average of top 5', accent: avgScore >= 70 ? 'text-emerald-400' : avgScore >= 40 ? 'text-amber-400' : 'text-white' },
    { icon: '📨', label: 'Applications Sent', value: appsLoading ? '—' : (applications?.length || 0), sub: 'Total submitted', accent: 'text-sky-400' },
    { icon: '🧠', label: 'Skills Detected', value: matchesLoading ? '—' : skillsMatched, sub: 'From your resume', accent: 'text-violet-400' },
  ]

  return (
    <div className="py-8 px-4 sm:px-6 max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="page-title">
          {greeting},{' '}
          <span className="bg-gradient-to-r from-sky-400 to-blue-400 bg-clip-text text-transparent">
            {user?.full_name?.split(' ')[0] || 'there'}
          </span> 👋
        </h1>
        <p className="text-slate-400 mt-1">Here's your internship overview for today</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statsLoading
          ? Array(4).fill(0).map((_, i) => <SkeletonCard key={i} />)
          : statCards.map((s, i) => <StatCard key={s.label} {...s} delay={i * 0.08} />)
        }
      </div>

      {/* Main content grid */}
      <div className="grid lg:grid-cols-5 gap-6">
        {/* Top Matches */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-semibold text-white">⚡ Top Matches</h2>
            <Link to="/my-matches" className="text-sky-400 text-sm hover:text-sky-300 transition-colors">
              View all →
            </Link>
          </div>

          {matchesLoading ? (
            <div className="space-y-3">
              {Array(3).fill(0).map((_, i) => (
                <div key={i} className="card p-5 space-y-3">
                  <div className="skeleton h-4 w-48" />
                  <div className="skeleton h-3 w-32" />
                  <div className="skeleton h-8 w-full" />
                </div>
              ))}
            </div>
          ) : flatMatches?.length ? (
            <div className="space-y-3">
              {flatMatches.slice(0, 5).map((job, i) => (
                <JobCard key={job.id} job={job} index={i} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon="📄"
              title="No matches yet"
              description="Upload your resume to get AI-powered internship recommendations"
              action={<Link to="/resume" className="btn-primary">Upload Resume →</Link>}
            />
          )}
        </div>

        {/* Right column */}
        <div className="lg:col-span-2 space-y-5">
          {/* Skills Donut */}
          <div className="card p-6">
            <h2 className="font-display text-lg font-semibold text-white mb-4">🎯 Skills Breakdown</h2>
            {matchesLoading ? (
              <div className="skeleton h-48 w-48 rounded-full mx-auto" />
            ) : skillsMatched + skillsMissing > 0 ? (
              <>
                <div className="relative mx-auto" style={{ maxWidth: 180 }}>
                  <Doughnut data={donutData} options={donutOptions} />
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="font-display text-2xl font-bold text-white">{skillsMatched}</span>
                    <span className="text-slate-400 text-xs">matched</span>
                  </div>
                </div>
                <div className="flex justify-center gap-6 mt-4">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                    <span className="text-xs text-slate-400">{skillsMatched} Matched</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                    <span className="text-xs text-slate-400">{skillsMissing} Missing</span>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-slate-500 text-sm text-center py-8">Upload a resume to see skill breakdown</p>
            )}
          </div>

          {/* Quick Actions */}
          <div className="card p-6">
            <h2 className="font-display text-lg font-semibold text-white mb-4">🚀 Quick Actions</h2>
            <div className="space-y-2">
              {[
                { to: '/cv-builder', icon: '📝', label: 'Build CV', desc: 'Create professional resume' },
                { to: '/scrape', icon: '🌐', label: 'Scrape Jobs', desc: 'Fetch new internships' },
                { to: '/resume', icon: '📄', label: 'Upload Resume', desc: 'AI skill extraction' },
              ].map(item => (
                <Link key={item.to} to={item.to}
                  className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/[0.04] transition-all duration-200 group">
                  <span className="text-xl group-hover:scale-110 transition-transform">{item.icon}</span>
                  <div>
                    <p className="text-sm font-medium text-white">{item.label}</p>
                    <p className="text-xs text-slate-500">{item.desc}</p>
                  </div>
                  <span className="ml-auto text-slate-600 group-hover:text-slate-400 transition-colors">→</span>
                </Link>
              ))}
            </div>
          </div>

          {/* Recent Activity */}
          <div className="card p-6">
            <h2 className="font-display text-lg font-semibold text-white mb-4">📋 Recent Activity</h2>
            {appsLoading ? (
              <div className="space-y-3">
                {Array(4).fill(0).map((_, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="skeleton w-8 h-8 rounded-lg shrink-0" />
                    <div className="flex-1 space-y-1.5">
                      <div className="skeleton h-3 w-36" />
                      <div className="skeleton h-3 w-20" />
                    </div>
                  </div>
                ))}
              </div>
            ) : applications?.length ? (
              <div className="space-y-3">
                {applications.slice(0, 5).map((app) => (
                  <div key={app.id} className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center text-sm shrink-0">
                      {app.status === 'accepted' ? '✅' : app.status === 'rejected' ? '❌' : app.status === 'reviewing' ? '🔍' : '📨'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white truncate">{app.internship?.title || app.job_title || '—'}</p>
                      <p className="text-xs text-slate-500">{formatRelativeTime(app.applied_at || app.updated_at || app.created_at)}</p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-md font-medium ${
                      app.status === 'accepted' ? 'bg-emerald-500/15 text-emerald-400' :
                      app.status === 'rejected' ? 'bg-rose-500/15 text-rose-400' :
                      app.status === 'reviewing' ? 'bg-amber-500/15 text-amber-400' :
                      'bg-sky-500/15 text-sky-400'
                    }`}>
                      {app.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500 text-sm text-center py-4">No applications yet</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
