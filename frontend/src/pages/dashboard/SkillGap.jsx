import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js'
import { motion } from 'framer-motion'
import { getSkillGap } from '../../api/matching'
import EmptyState from '../../components/ui/EmptyState'
import { Link } from 'react-router-dom'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const SKILL_RESOURCES = {
  Python: { url: 'https://www.coursera.org/learn/python', platform: 'Coursera' },
  React: { url: 'https://react.dev/learn', platform: 'React Docs' },
  'Machine Learning': { url: 'https://www.coursera.org/learn/machine-learning', platform: 'Coursera' },
  SQL: { url: 'https://www.coursera.org/learn/sql-for-data-science', platform: 'Coursera' },
  Docker: { url: 'https://docs.docker.com/get-started/', platform: 'Docker Docs' },
  JavaScript: { url: 'https://javascript.info', platform: 'javascript.info' },
  TypeScript: { url: 'https://www.typescriptlang.org/docs/', platform: 'Official Docs' },
  'Node.js': { url: 'https://nodejs.org/en/learn/getting-started/introduction-to-nodejs', platform: 'Node.js Docs' },
  Django: { url: 'https://www.djangoproject.com/start/', platform: 'Django Docs' },
  TensorFlow: { url: 'https://www.tensorflow.org/learn', platform: 'TensorFlow' },
}

const getResource = (skill) =>
  SKILL_RESOURCES[skill] || {
    url: `https://www.coursera.org/search?query=${encodeURIComponent(skill)}`,
    platform: 'Coursera',
  }

export default function SkillGap() {
  const [learning, setLearning] = useState(() => {
    try { return JSON.parse(localStorage.getItem('learning_skills') || '[]') } catch { return [] }
  })

  const { data: gapData, isLoading, error } = useQuery({
    queryKey: ['skillGap'],
    queryFn: getSkillGap,
  })

  const toggleLearning = (skill) => {
    const updated = learning.includes(skill)
      ? learning.filter((s) => s !== skill)
      : [...learning, skill]
    setLearning(updated)
    localStorage.setItem('learning_skills', JSON.stringify(updated))
  }

  const missingSkills = gapData?.missing_skills?.slice(0, 10) || []
  // Backend only returns missing_skills; profile completeness is estimated from missing count
  const totalMissing = gapData?.missing_skills?.length || 0
  const top20 = Math.max(totalMissing, 20)
  // We estimate skills the user has as complement of missing (max 20 total)
  const userHas = Math.max(0, top20 - totalMissing)

  const barData = {
    labels: missingSkills.map((s) => s.skill_name || s.skill || s.name || s),
    datasets: [
      {
        label: 'Jobs requiring this skill',
        data: missingSkills.map((s) => s.jobs_requiring_it || s.job_count || s.count || 1),
        backgroundColor: 'rgba(14, 165, 233, 0.7)',
        borderColor: '#0ea5e9',
        borderWidth: 1,
        borderRadius: 6,
      },
    ],
  }

  const barOptions = {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1e293b',
        borderColor: '#334155',
        borderWidth: 1,
        titleColor: '#f1f5f9',
        bodyColor: '#94a3b8',
      },
    },
    scales: {
      x: { grid: { color: '#1e293b' }, ticks: { color: '#64748b' } },
      y: { grid: { display: false }, ticks: { color: '#cbd5e1', font: { size: 13 } } },
    },
  }

  if (isLoading) {
    return (
      <div className="py-8 px-4 sm:px-6 max-w-4xl mx-auto space-y-6">
        <div className="skeleton h-8 w-48" />
        <div className="card p-6 skeleton h-72" />
        <div className="grid sm:grid-cols-2 gap-4">
          {Array(6).fill(0).map((_, i) => <div key={i} className="card p-4 skeleton h-32" />)}
        </div>
      </div>
    )
  }

  return (
    <div className="py-8 px-4 sm:px-6 max-w-4xl mx-auto space-y-8 animate-fade-in">
      <div>
        <h1 className="page-title">Skill <span className="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">Gap Analysis</span></h1>
        <p className="text-slate-400 mt-1">Skills the market demands that you should learn next</p>
      </div>

      {error || missingSkills.length === 0 ? (
        <EmptyState
          icon="📄"
          title="Upload your resume first"
          description="We need your resume to analyze which skills you're missing"
          action={<Link to="/resume" className="btn-primary">Upload Resume →</Link>}
        />
      ) : (
        <>
          {/* Progress section */}
          <div className="card p-6">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h2 className="font-display text-lg font-semibold text-white">Profile Completeness</h2>
                <p className="text-slate-400 text-sm mt-1">
                  You have <span className="text-sky-400 font-semibold">{userHas}</span> of the top {top20} most demanded skills
                </p>
              </div>
              <span className="font-display text-3xl font-bold text-sky-400">
                {Math.round((userHas / top20) * 100)}%
              </span>
            </div>
            <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-sky-500 to-blue-500 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${(userHas / top20) * 100}%` }}
                transition={{ duration: 1, ease: 'easeOut', delay: 0.3 }}
              />
            </div>
          </div>

          {/* Bar chart */}
          <div className="card p-6">
            <h2 className="font-display text-lg font-semibold text-white mb-4">
              🎯 Top 10 Missing Skills by Market Demand
            </h2>
            <div style={{ height: 340 }}>
              <Bar data={barData} options={barOptions} />
            </div>
          </div>

          {/* Skill cards */}
          <div>
            <h2 className="font-display text-lg font-semibold text-white mb-4">📚 Learning Roadmap</h2>
            <div className="grid sm:grid-cols-2 gap-4">
              {missingSkills.map((item, idx) => {
                const skill = item.skill_name || item.skill || item.name || item
                const count = item.jobs_requiring_it || item.job_count || item.count || 0
                const resource = getResource(skill)
                const isLearning = learning.includes(skill)
                const trend = idx < 3 ? 'Rising 📈' : idx < 7 ? 'Stable ➡️' : 'Stable ➡️'

                return (
                  <motion.div
                    key={skill}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.06 }}
                    className={`card p-5 transition-all ${isLearning ? 'border-sky-500/40 bg-sky-500/5' : ''}`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="font-display font-semibold text-white">{skill}</h3>
                        {count > 0 && (
                          <p className="text-slate-400 text-sm mt-0.5">{count} internships need this</p>
                        )}
                      </div>
                      <button
                        onClick={() => toggleLearning(skill)}
                        className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all ${
                          isLearning
                            ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                            : 'bg-slate-700 text-slate-300 border border-slate-600 hover:border-sky-500/40 hover:text-sky-400'
                        }`}
                      >
                        {isLearning ? '✓ Learning' : '+ Mark as Learning'}
                      </button>
                    </div>

                    <div className="flex items-center justify-between text-xs text-slate-500 mb-3">
                      <span>Demand: <span className="text-amber-400">{trend}</span></span>
                      <span>via {resource.platform}</span>
                    </div>

                    <a
                      href={resource.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 text-sm text-sky-400 hover:text-sky-300 transition-colors"
                    >
                      🎓 Free course on {resource.platform} →
                    </a>
                  </motion.div>
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
