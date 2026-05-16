// formatDate.js
export const formatDate = (dateStr) => {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export const formatDeadline = (dateStr) => {
  if (!dateStr) return null
  const deadline = new Date(dateStr)
  const now = new Date()
  const diff = Math.ceil((deadline - now) / (1000 * 60 * 60 * 24))
  if (diff < 0) return { label: 'Expired', urgent: true }
  if (diff === 0) return { label: 'Due today', urgent: true }
  if (diff === 1) return { label: '1 day left', urgent: true }
  if (diff <= 7) return { label: `${diff} days left`, urgent: true }
  return { label: `${diff} days left`, urgent: false }
}

export const formatRelativeTime = (dateStr) => {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  if (days > 30) return formatDate(dateStr)
  if (days > 0) return `${days}d ago`
  if (hours > 0) return `${hours}h ago`
  if (minutes > 0) return `${minutes}m ago`
  return 'just now'
}
