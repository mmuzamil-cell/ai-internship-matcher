export const formatScore = (score) => {
  if (score == null) return '—'
  return `${Math.round(score)}%`
}

export const getScoreColor = (score) => {
  if (score >= 70) return { bg: 'bg-emerald-500', text: 'text-emerald-400', ring: 'ring-emerald-500/30', hex: '#10b981' }
  if (score >= 40) return { bg: 'bg-amber-500', text: 'text-amber-400', ring: 'ring-amber-500/30', hex: '#f59e0b' }
  return { bg: 'bg-rose-500', text: 'text-rose-400', ring: 'ring-rose-500/30', hex: '#f43f5e' }
}

export const getScoreLabel = (score) => {
  if (score >= 70) return 'Strong Match'
  if (score >= 40) return 'Moderate Match'
  return 'Weak Match'
}

export const getInitials = (name) => {
  if (!name) return '?'
  return name
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

export const COMPANY_COLORS = [
  'from-violet-500 to-purple-700',
  'from-sky-500 to-blue-700',
  'from-emerald-500 to-teal-700',
  'from-rose-500 to-pink-700',
  'from-amber-500 to-orange-700',
  'from-cyan-500 to-sky-700',
]

export const getCompanyColor = (name) => {
  if (!name) return COMPANY_COLORS[0]
  const idx = name.charCodeAt(0) % COMPANY_COLORS.length
  return COMPANY_COLORS[idx]
}
