import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../../hooks/useAuth'
import { getInitials, getCompanyColor } from '../../utils/formatScore'

const NAV_LINKS = [
  { to: '/dashboard', label: 'Overview', icon: '⊞' },
  { to: '/my-matches', label: 'Matches', icon: '⚡' },
  { to: '/applications', label: 'Applications', icon: '📋' },
  { to: '/skill-gap', label: 'Skill Gap', icon: '📊' },
]

export default function Navbar({ onSidebarToggle }) {
  const { user, logout, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  const handleLogout = () => { logout(); navigate('/login'); setMenuOpen(false) }

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#060b1a]/80 backdrop-blur-2xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        <Link to="/dashboard" className="flex items-center gap-2.5 shrink-0 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center shadow-lg shadow-sky-500/25 group-hover:shadow-sky-500/40 transition-shadow">
            <span className="font-display font-bold text-white text-sm">IQ</span>
          </div>
          <span className="font-display font-bold text-white text-lg hidden sm:block">
            Intern<span className="bg-gradient-to-r from-sky-400 to-blue-400 bg-clip-text text-transparent">IQ</span>
          </span>
        </Link>

        {isAuthenticated && (
          <nav className="hidden md:flex items-center gap-0.5">
            {NAV_LINKS.map(link => (
              <Link key={link.to} to={link.to}
                className={`px-3.5 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
                  location.pathname === link.to
                    ? 'bg-white/[0.08] text-white shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
                }`}>
                {link.label}
              </Link>
            ))}
          </nav>
        )}

        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <>
              <Link to="/resume" className="hidden sm:flex btn-ghost text-sm items-center gap-2">
                <span>📄</span> Resume
              </Link>
              <div className="relative">
                <button onClick={() => setMenuOpen(!menuOpen)}
                  className={`w-9 h-9 rounded-xl bg-gradient-to-br ${getCompanyColor(user?.full_name)} 
                    flex items-center justify-center font-display text-sm font-bold text-white
                    hover:scale-105 transition-all duration-200 shadow-lg`}>
                  {getInitials(user?.full_name)}
                </button>
                <AnimatePresence>
                  {menuOpen && (
                    <>
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
                      <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: -8 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: -8 }}
                        transition={{ duration: 0.15 }}
                        className="absolute right-0 top-12 w-60 z-50 bg-[#0c1222] border border-white/[0.08] rounded-2xl shadow-2xl shadow-black/60 py-1 overflow-hidden">
                        <div className="px-4 py-3 border-b border-white/[0.06]">
                          <p className="font-semibold text-white text-sm">{user?.full_name}</p>
                          <p className="text-slate-500 text-xs truncate">{user?.email}</p>
                        </div>
                        <Link to="/profile" onClick={() => setMenuOpen(false)}
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-slate-300 hover:text-white hover:bg-white/[0.04] transition-colors">
                          👤 Profile Settings
                        </Link>
                        <Link to="/cv-builder" onClick={() => setMenuOpen(false)}
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-slate-300 hover:text-white hover:bg-white/[0.04] transition-colors">
                          📝 CV Builder
                        </Link>
                        <Link to="/resume" onClick={() => setMenuOpen(false)}
                          className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-slate-300 hover:text-white hover:bg-white/[0.04] transition-colors">
                          📄 My Resumes
                        </Link>
                        <div className="border-t border-white/[0.06] mt-1" />
                        <button onClick={handleLogout}
                          className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-rose-400 hover:text-rose-300 hover:bg-rose-500/[0.06] transition-colors">
                          🚪 Sign Out
                        </button>
                      </motion.div>
                    </>
                  )}
                </AnimatePresence>
              </div>
              <button onClick={onSidebarToggle} className="md:hidden btn-ghost p-2" aria-label="Toggle sidebar">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Link to="/login" className="btn-ghost text-sm">Login</Link>
              <Link to="/register" className="btn-primary text-sm">Get Started</Link>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
