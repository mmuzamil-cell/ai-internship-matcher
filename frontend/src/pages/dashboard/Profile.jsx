import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { updateProfile } from '../../api/profile'
import { useAuth } from '../../hooks/useAuth'
import LoadingSpinner from '../../components/ui/LoadingSpinner'
import { getCompanyColor, getInitials } from '../../utils/formatScore'

const MAJORS = [
  'Computer Science', 'Software Engineering', 'Data Science',
  'Information Technology', 'Artificial Intelligence',
  'Cyber Security', 'Computer Engineering', 'Electrical Engineering',
  'Business Administration', 'Other',
]

export default function Profile() {
  const { user, setUser } = useAuth()
  const [form, setForm] = useState({
    full_name: user?.full_name || '',
    university: user?.university || '',
    major: user?.major || '',
  })
  const [saved, setSaved] = useState(false)

  const mutation = useMutation({
    mutationFn: updateProfile,
    onSuccess: (data) => {
      setUser(data)
      setSaved(true)
      toast.success('Profile updated!')
      setTimeout(() => setSaved(false), 3000)
    },
    onError: (e) => toast.error(e.message),
  })

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  return (
    <div className="py-8 px-4 sm:px-6 max-w-2xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Profile <span className="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">Settings</span></h1>
        <p className="text-slate-400 mt-1">Update your personal information</p>
      </div>

      {/* Avatar */}
      <div className="card p-6 flex items-center gap-5">
        <div className={`w-20 h-20 rounded-2xl bg-gradient-to-br ${getCompanyColor(user?.full_name)} 
                        flex items-center justify-center font-display text-2xl font-bold text-white shadow-xl`}>
          {getInitials(user?.full_name)}
        </div>
        <div>
          <p className="font-display text-xl font-semibold text-white">{user?.full_name}</p>
          <p className="text-slate-400">{user?.email}</p>
          {user?.major && <p className="text-slate-500 text-sm mt-1">{user.major} · {user.university}</p>}
        </div>
      </div>

      {/* Form */}
      <div className="card p-6 space-y-5">
        <h2 className="font-display text-lg font-semibold text-white">Edit Information</h2>
        <div>
          <label className="label">Full Name</label>
          <input type="text" value={form.full_name} onChange={set('full_name')} className="input-field" placeholder="Your full name" />
        </div>
        <div>
          <label className="label">University</label>
          <input type="text" value={form.university} onChange={set('university')} className="input-field" placeholder="e.g. LUMS, FAST, NUST" />
        </div>
        <div>
          <label className="label">Major</label>
          <select value={form.major} onChange={set('major')} className="input-field">
            <option value="">Select major…</option>
            {MAJORS.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="pt-2">
          <label className="label">Email Address</label>
          <input type="email" value={user?.email || ''} disabled className="input-field opacity-50 cursor-not-allowed" />
          <p className="text-slate-500 text-xs mt-1">Email cannot be changed</p>
        </div>
        <button onClick={() => mutation.mutate(form)} disabled={mutation.isPending}
          className={`btn-primary flex items-center gap-2 ${saved ? '!bg-gradient-to-r !from-emerald-500 !to-emerald-600 !shadow-emerald-500/20' : ''}`}>
          {mutation.isPending ? <LoadingSpinner size="sm" /> : null}
          {saved ? '✓ Saved!' : mutation.isPending ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </div>
  )
}
