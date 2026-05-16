import { motion } from 'framer-motion'

export default function EmptyState({ icon = '🔍', title, description, action }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-20 px-6 text-center"
    >
      <div className="text-5xl mb-4">{icon}</div>
      <h3 className="font-display text-xl font-semibold text-white mb-2">{title}</h3>
      {description && <p className="text-slate-400 max-w-sm mb-6">{description}</p>}
      {action && action}
    </motion.div>
  )
}
