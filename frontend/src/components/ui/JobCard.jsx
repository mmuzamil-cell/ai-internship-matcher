import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { motion } from 'framer-motion'
import MatchScoreBadge from './MatchScoreBadge'
import SkillTag from './SkillTag'
import LoadingSpinner from './LoadingSpinner'
import { applyToJob } from '../../api/applications'
import { formatDeadline } from '../../utils/formatDate'
import { getCompanyColor, getInitials } from '../../utils/formatScore'

export default function JobCard({ job, index = 0 }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { id, title, company, location, is_remote, stipend, deadline, match_score, matched_skills = [], missing_skills = [] } = job
  const deadlineInfo = formatDeadline(deadline)
  const colorClass = getCompanyColor(company)
  const isRemote = is_remote || /remote/i.test(location || '')

  const applyMutation = useMutation({
    mutationFn: () => applyToJob(id),
    onSuccess: () => { toast.success(`Applied to ${title} at ${company}!`); queryClient.invalidateQueries({ queryKey: ['applications'] }) },
    onError: (e) => toast.error(e.message),
  })

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }}
      className="card p-5 hover:border-white/[0.12] transition-all duration-300 hover:shadow-xl
                 hover:shadow-black/30 flex flex-col gap-4 group">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${colorClass} flex items-center justify-center
                          font-display text-sm font-bold text-white shrink-0 shadow-lg group-hover:scale-105 transition-transform`}>
            {getInitials(company)}
          </div>
          <div className="min-w-0">
            <h3 className="font-display font-semibold text-white text-sm leading-tight truncate">{title}</h3>
            <p className="text-slate-400 text-xs truncate mt-0.5">{company}</p>
          </div>
        </div>
        {match_score != null && <MatchScoreBadge score={match_score} size="sm" />}
      </div>
      <div className="flex flex-wrap gap-1.5">
        <span className="text-xs bg-white/[0.04] text-slate-300 rounded-lg px-2 py-1 border border-white/[0.06]">
          📍 {isRemote ? 'Remote' : location || 'On-site'}
        </span>
        {stipend && <span className="text-xs bg-white/[0.04] text-slate-300 rounded-lg px-2 py-1 border border-white/[0.06]">💰 {stipend}</span>}
        {deadlineInfo && (
          <span className={`text-xs rounded-lg px-2 py-1 border ${deadlineInfo.urgent ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-white/[0.04] text-slate-300 border-white/[0.06]'}`}>
            ⏰ {deadlineInfo.label}
          </span>
        )}
      </div>
      <div className="space-y-2">
        {matched_skills.slice(0, 3).length > 0 && (
          <div className="flex flex-wrap gap-1">{matched_skills.slice(0, 3).map(s => <SkillTag key={s} skill={s} variant="matched" />)}</div>
        )}
        {missing_skills.slice(0, 2).length > 0 && (
          <div className="flex flex-wrap gap-1">{missing_skills.slice(0, 2).map(s => <SkillTag key={s} skill={s} variant="missing" />)}</div>
        )}
      </div>
      <div className="flex gap-2 mt-auto pt-1">
        <button onClick={() => navigate(`/jobs/${id}`)} className="flex-1 btn-secondary text-sm py-2 text-center">View Details</button>
        <button onClick={() => applyMutation.mutate()} disabled={applyMutation.isPending}
          className="flex-1 btn-primary text-sm py-2 flex items-center justify-center gap-2">
          {applyMutation.isPending ? <LoadingSpinner size="sm" /> : null}
          Quick Apply
        </button>
      </div>
    </motion.div>
  )
}
