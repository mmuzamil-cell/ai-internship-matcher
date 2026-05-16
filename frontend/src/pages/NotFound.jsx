import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

export default function NotFound() {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
      className="min-h-[60vh] flex flex-col items-center justify-center px-4 text-center">
      <span className="text-7xl mb-6">🔍</span>
      <h1 className="font-display text-4xl font-bold text-white mb-3">Page not found</h1>
      <p className="text-slate-400 mb-8 max-w-md">The page you're looking for doesn't exist or has been moved.</p>
      <Link to="/dashboard" className="btn-primary">← Back to Dashboard</Link>
    </motion.div>
  )
}
