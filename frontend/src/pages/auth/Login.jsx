import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { login, getMe } from '../../api/auth'
import { useAuth } from '../../hooks/useAuth'
import LoadingSpinner from '../../components/ui/LoadingSpinner'

export default function Login() {
  const [form, setForm] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuth()
  const navigate = useNavigate()

  const validate = () => {
    const e = {}
    if (!form.email) e.email = 'Email is required'
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Invalid email format'
    if (!form.password) e.password = 'Password is required'
    return e
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }
    setLoading(true)
    try {
      const { access_token } = await login(form)
      localStorage.setItem('auth_token', access_token)
      const user = await getMe()
      setAuth(access_token, user)
      toast.success(`Welcome back, ${user.full_name?.split(' ')[0]}!`)
      navigate('/dashboard')
    } catch (err) {
      toast.error(err.message)
      setErrors({ server: err.message })
    } finally { setLoading(false) }
  }

  const set = (field) => (e) => {
    setForm({ ...form, [field]: e.target.value })
    if (errors[field]) setErrors({ ...errors, [field]: null })
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-16 relative">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[700px] h-[700px] bg-sky-500/[0.05] rounded-full blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-violet-500/[0.04] rounded-full blur-[100px]" />
      </div>

      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
        className="w-full max-w-md relative">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center mx-auto mb-5 shadow-2xl shadow-sky-500/30">
            <span className="font-display font-bold text-white text-2xl">IQ</span>
          </div>
          <h1 className="font-display text-3xl font-bold text-white">Welcome back</h1>
          <p className="text-slate-400 mt-2">Sign in to find your perfect internship</p>
        </div>

        <div className="card p-8">
          {errors.server && (
            <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-3 mb-5 text-rose-400 text-sm">{errors.server}</div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email address</label>
              <input type="email" placeholder="you@university.edu" value={form.email}
                onChange={set('email')} className="input-field" autoComplete="email" />
              {errors.email && <p className="text-rose-400 text-xs mt-1">{errors.email}</p>}
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="label mb-0">Password</label>
                <span className="text-xs text-slate-500 cursor-not-allowed" title="Coming soon">Forgot password?</span>
              </div>
              <input type="password" placeholder="••••••••" value={form.password}
                onChange={set('password')} className="input-field" autoComplete="current-password" />
              {errors.password && <p className="text-rose-400 text-xs mt-1">{errors.password}</p>}
            </div>
            <button type="submit" disabled={loading}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 mt-2">
              {loading ? <LoadingSpinner size="sm" /> : null}
              {loading ? 'Signing in…' : 'Sign in →'}
            </button>
          </form>
          <p className="text-center text-slate-400 text-sm mt-6">
            No account?{' '}
            <Link to="/register" className="text-sky-400 hover:text-sky-300 font-medium transition-colors">Create one free →</Link>
          </p>
        </div>
      </motion.div>
    </div>
  )
}
