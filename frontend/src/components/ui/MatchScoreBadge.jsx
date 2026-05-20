import { getScoreColor, getScoreLabel } from '../../utils/formatScore'


export default function MatchScoreBadge({ score, size = 'md' }) {
  const colors = getScoreColor(score)
  const pct = Math.min(100, Math.max(0, score ?? 0))

  const sizes = {
    sm: { container: 'w-14 h-14', font: 'text-xs', svg: 64, r: 22, strokeW: 4 },
    md: { container: 'w-20 h-20', font: 'text-sm font-bold', svg: 80, r: 28, strokeW: 5 },
    lg: { container: 'w-28 h-28', font: 'text-lg font-bold', svg: 112, r: 40, strokeW: 6 },
  }

  const s = sizes[size] || sizes.md
  const circ = 2 * Math.PI * s.r
  const off = circ - (pct / 100) * circ

  return (
    <div className="flex flex-col items-center gap-1">
      <div className={`relative ${s.container} flex items-center justify-center`}>
        <svg
          width={s.svg}
          height={s.svg}
          className="absolute inset-0 -rotate-90"
        >
          <circle
            cx={s.svg / 2}
            cy={s.svg / 2}
            r={s.r}
            fill="none"
            stroke="currentColor"
            strokeWidth={s.strokeW}
            className="text-slate-700"
          />
          <circle
            cx={s.svg / 2}
            cy={s.svg / 2}
            r={s.r}
            fill="none"
            stroke={colors.hex}
            strokeWidth={s.strokeW}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={off}
            style={{ transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)' }}
          />
        </svg>
        <span className={`relative z-10 ${s.font} ${colors.text}`}>
          {Math.round(pct)}%
        </span>
      </div>
      {size === 'lg' && (
        <span className={`text-xs font-medium ${colors.text}`}>
          {getScoreLabel(score)}
        </span>
      )}
    </div>
  )
}
