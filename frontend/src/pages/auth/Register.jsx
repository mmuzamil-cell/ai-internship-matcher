import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { register, login, getMe } from '../../api/auth'
import { useAuth } from '../../hooks/useAuth'
import LoadingSpinner from '../../components/ui/LoadingSpinner'

const MAJORS = [
  'Computer Science', 'Software Engineering', 'Data Science',
  'Information Technology', 'Artificial Intelligence', 'Cyber Security',
  'Computer Engineering', 'Electrical Engineering', 'Business Administration', 'Other',
]

export default function Register() {
  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirm_password: '', university: '', major: '' })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuth()
  const navigate = useNavigate()

  const validate = () => {
    const e = {}
    if (!form.full_name.trim()) e.full_name = 'Full name is required'
    if (!form.email) e.email = 'Email is required'
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Invalid email format'
    if (!form.password) e.password = 'Password is required'
    else if (form.password.length < 8) e.password = 'Password must be at least 8 characters'
    if (form.password !== form.confirm_password) e.confirm_password = 'Passwords do not match'
    if (!form.university.trim()) e.university = 'University is required'
    if (!form.major) e.major = 'Please select your major'
    return e
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }
    setLoading(true)
    try {
      const { full_name, email, password, university, major } = form
      await register({ full_name, email, password, university, major })
      const { access_token } = await login({ email, password })
      localStorage.setItem('auth_token', access_token)
      const user = await getMe()
      setAuth(access_token, user)
      toast.success(`Welcome to InternIQ, ${full_name.split(' ')[0]}! 🎉`)
      navigate('/resume')
    } catch (err) {
      toast.error(err.message)
      setErrors({ server: err.message })
    } finally { setLoading(false) }
  }

  const set = (field) => (e) => { setForm({ ...form, [field]: e.target.value }); if (errors[field]) setErrors({ ...errors, [field]: null }) }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-16 relative">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 right-1/4 w-[500px] h-[500px] bg-violet-500/[0.05] rounded-full blur-[120px]" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-sky-600/[0.05] rounded-full blur-[100px]" />
      </div>

      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-lg relative">
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center mx-auto mb-5 shadow-2xl shadow-sky-500/30">
            <span className="font-display font-bold text-white text-2xl">IQ</span>
          </div>
          <h1 className="font-display text-3xl font-bold text-white">Join InternIQ</h1>
          <p className="text-slate-400 mt-2">Find AI-matched internships in minutes</p>
        </div>

        <div className="card p-8">
          {errors.server && (
            <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-3 mb-5 text-rose-400 text-sm">{errors.server}</div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            {[
              { id: 'full_name', label: 'Full Name', type: 'text', placeholder: 'Ahmed Khan', autoComplete: 'name' },
              { id: 'email', label: 'Email Address', type: 'email', placeholder: 'ahmed@university.edu', autoComplete: 'email' },
              { id: 'university', label: 'University', type: 'text', placeholder: 'LUMS, FAST, NUST…', autoComplete: 'organization' },
            ].map(f => (
              <div key={f.id}>
                <label className="label">{f.label}</label>
                <input type={f.type} placeholder={f.placeholder} value={form[f.id]}
                  onChange={set(f.id)} className="input-field" autoComplete={f.autoComplete} />
                {errors[f.id] && <p className="text-rose-400 text-xs mt-1">{errors[f.id]}</p>}
              </div>
            ))}

            <div>
              <label className="label">Major / Field of Study</label>
              <select value={form.major} onChange={set('major')} className="input-field">
                <option value="">Select your major…</option>
                {MAJORS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              {errors.major && <p className="text-rose-400 text-xs mt-1">{errors.major}</p>}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Password</label>
                <input type="password" placeholder="Min 8 chars" value={form.password}
                  onChange={set('password')} className="input-field" autoComplete="new-password" />
                {errors.password && <p className="text-rose-400 text-xs mt-1">{errors.password}</p>}
              </div>
              <div>
                <label className="label">Confirm Password</label>
                <input type="password" placeholder="Repeat password" value={form.confirm_password}
                  onChange={set('confirm_password')} className="input-field" autoComplete="new-password" />
                {errors.confirm_password && <p className="text-rose-400 text-xs mt-1">{errors.confirm_password}</p>}
              </div>
            </div>

            <button type="submit" disabled={loading}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 mt-2">
              {loading ? <LoadingSpinner size="sm" /> : null}
              {loading ? 'Creating account…' : 'Create Account →'}
            </button>
          </form>
          <p className="text-center text-slate-400 text-sm mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-sky-400 hover:text-sky-300 font-medium transition-colors">Sign in</Link>
          </p>
        </div>
      </motion.div>
    </div>
  )
}
