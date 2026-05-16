export default function SkillTag({ skill, variant = 'neutral', size = 'sm' }) {
  const variants = {
    matched: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    missing: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
    learning: 'bg-sky-500/15 text-sky-400 border-sky-500/30',
    neutral: 'bg-slate-700/60 text-slate-300 border-slate-600/50',
  }

  const sizes = {
    xs: 'text-xs px-2 py-0.5',
    sm: 'text-xs px-2.5 py-1',
    md: 'text-sm px-3 py-1.5',
  }

  const icons = {
    matched: '✓',
    missing: '✗',
    learning: '→',
    neutral: null,
  }

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-lg border font-medium
        ${variants[variant] || variants.neutral}
        ${sizes[size] || sizes.sm}`}
    >
      {icons[variant] && (
        <span className="text-[10px] font-bold">{icons[variant]}</span>
      )}
      {skill}
    </span>
  )
}
