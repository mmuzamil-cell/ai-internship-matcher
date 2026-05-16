import { NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'

const LINKS = [
  { to: '/dashboard', icon: '⊞', label: 'Overview' },
  { to: '/my-matches', icon: '⚡', label: 'AI Matches' },
  { to: '/scrape', icon: '🌐', label: 'Scrape Jobs' },
  { to: '/applications', icon: '📋', label: 'Applications' },
  { to: '/skill-gap', icon: '📊', label: 'Skill Gap' },
  { to: '/cv-builder', icon: '📝', label: 'CV Builder' },
  { to: '/resume', icon: '📄', label: 'Resume' },
  { to: '/profile', icon: '👤', label: 'Profile' },
]

export default function Sidebar({ isOpen, onClose }) {
  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
      isActive
        ? 'bg-gradient-to-r from-sky-500/15 to-blue-500/10 text-sky-400 border border-sky-500/20 shadow-sm shadow-sky-500/5'
        : 'text-slate-400 hover:text-white hover:bg-white/[0.04] border border-transparent'
    }`

  return (
    <>
      <aside className="hidden md:flex flex-col w-56 shrink-0 border-r border-white/[0.04] min-h-screen py-6 px-3">
        <nav className="space-y-1">
          {LINKS.map(link => (
            <NavLink key={link.to} to={link.to} className={linkClass}>
              <span className="text-base w-5 text-center">{link.icon}</span>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto pt-6 px-3">
          <div className="rounded-xl bg-gradient-to-br from-sky-500/10 to-violet-500/10 border border-white/[0.06] p-4">
            <p className="text-xs font-semibold text-white mb-1">InternIQ Pro</p>
            <p className="text-[10px] text-slate-400 leading-relaxed">AI-Powered Internship Matching Platform</p>
          </div>
        </div>
      </aside>

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={onClose} className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm md:hidden" />
            <motion.aside
              initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="fixed left-0 top-0 bottom-0 z-50 w-64 bg-[#060b1a] border-r border-white/[0.06] py-6 px-3 md:hidden">
              <div className="flex items-center gap-2 px-3 mb-6">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center shadow-lg shadow-sky-500/25">
                  <span className="font-display font-bold text-white text-sm">IQ</span>
                </div>
                <span className="font-display font-bold text-white text-lg">
                  Intern<span className="bg-gradient-to-r from-sky-400 to-blue-400 bg-clip-text text-transparent">IQ</span>
                </span>
              </div>
              <nav className="space-y-1">
                {LINKS.map(link => (
                  <NavLink key={link.to} to={link.to} onClick={onClose} className={linkClass}>
                    <span className="text-base w-5 text-center">{link.icon}</span>
                    {link.label}
                  </NavLink>
                ))}
              </nav>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
