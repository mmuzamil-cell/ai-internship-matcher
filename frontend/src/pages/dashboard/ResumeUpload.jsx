import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import { uploadResume, getMyResumes, deleteResume, getResumeFeedback } from '../../api/resume'
import { useAuth } from '../../hooks/useAuth'
import { formatDate } from '../../utils/formatDate'
import LoadingSpinner from '../../components/ui/LoadingSpinner'
import SkillTag from '../../components/ui/SkillTag'

export default function ResumeUpload() {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState(null)
  const [progress, setProgress] = useState(0)
  const [uploadedSkills, setUploadedSkills] = useState([])
  const [visibleSkills, setVisibleSkills] = useState([])
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  
  // ATS Critique State
  const [selectedResumeId, setSelectedResumeId] = useState(null)
  const [expandedCategories, setExpandedCategories] = useState({
    "Contact Information": true,
    "Impact & Metrics": false,
    "Action Verbs": false,
    "Formatting & Structure": false
  })
  const [copiedIndex, setCopiedIndex] = useState(null)
  
  const fileInputRef = useRef()
  const critiqueRef = useRef()
  const skillTimersRef = useRef([])
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { setSkills } = useAuth()

  const { data: resumes = [], isLoading } = useQuery({
    queryKey: ['resumes'],
    queryFn: getMyResumes,
  })

  // Fetch feedback for selected resume
  const { data: feedbackData, isLoading: isFeedbackLoading, error: feedbackError } = useQuery({
    queryKey: ['resume-feedback', selectedResumeId],
    queryFn: () => getResumeFeedback(selectedResumeId),
    enabled: !!selectedResumeId,
    retry: false
  })

  useEffect(() => {
    return () => skillTimersRef.current.forEach(clearTimeout)
  }, [])

  useEffect(() => {
    if (selectedResumeId && critiqueRef.current) {
      critiqueRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [selectedResumeId])

  const uploadMutation = useMutation({
    mutationFn: (f) => uploadResume(f, (evt) => {
      setProgress(Math.round((evt.loaded / evt.total) * 100))
    }),
    onSuccess: (data) => {
      const skills = data.skills_found || data.skills || data.extracted_skills || []
      setUploadedSkills(skills)
      setSkills(skills)
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
      queryClient.invalidateQueries({ queryKey: ['matches'] })
      toast.success('Resume analyzed successfully! 🎉')
      setProgress(0)
      setFile(null)

      // Open critique for the newly uploaded resume
      if (data.id) {
        setSelectedResumeId(data.id)
      }

      // Clear any previous timers
      skillTimersRef.current.forEach(clearTimeout)
      skillTimersRef.current = []

      // Animate skills in one by one
      setVisibleSkills([])
      skills.forEach((_, i) => {
        const timerId = setTimeout(() => {
          setVisibleSkills((prev) => [...prev, skills[i]])
        }, i * 120)
        skillTimersRef.current.push(timerId)
      })
    },
    onError: (e) => {
      toast.error(e.message)
      setProgress(0)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteResume,
    onSuccess: () => {
      toast.success('Resume deleted')
      if (selectedResumeId === deleteConfirm) {
        setSelectedResumeId(null)
      }
      setDeleteConfirm(null)
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
    },
    onError: (e) => toast.error(e.message),
  })

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    const isPdf = dropped?.type === 'application/pdf' || dropped?.type === 'application/x-pdf' || dropped?.name?.toLowerCase().endsWith('.pdf')
    if (!isPdf) {
      toast.error('Please upload a PDF file')
      return
    }
    if (dropped.size > 5 * 1024 * 1024) {
      toast.error('File too large. Maximum size is 5MB.')
      return
    }
    setFile(dropped)
  }

  const handleSelect = (e) => {
    const f = e.target.files[0]
    if (f) {
      const isPdf = f.type === 'application/pdf' || f.type === 'application/x-pdf' || f.name?.toLowerCase().endsWith('.pdf')
      if (!isPdf) {
        toast.error('Please select a PDF file')
        return
      }
      if (f.size > 5 * 1024 * 1024) {
        toast.error('File too large. Maximum size is 5MB.')
        return
      }
      setFile(f)
    }
  }

  const formatBytes = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const toggleCategory = (name) => {
    setExpandedCategories(prev => ({
      ...prev,
      [name]: !prev[name]
    }))
  }

  const handleCopy = (text, index) => {
    navigator.clipboard.writeText(text)
    setCopiedIndex(index)
    toast.success('Suggestion copied to clipboard!')
    setTimeout(() => setCopiedIndex(null), 2000)
  }

  return (
    <div className="py-8 px-4 sm:px-6 max-w-4xl mx-auto space-y-8 animate-fade-in">
      <div>
        <h1 className="page-title">Resume <span className="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">Upload & Critique</span></h1>
        <p className="text-slate-400 mt-1">Upload your resume, extract skills, and get real-time ATS optimization feedback</p>
      </div>

      {/* Drop Zone */}
      <div
        onDragEnter={() => setDragging(true)}
        onDragLeave={() => setDragging(false)}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => !file && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 cursor-pointer
          ${dragging ? 'border-sky-400 bg-sky-500/10' : 'border-white/[0.08] hover:border-white/[0.15] hover:bg-white/[0.02]'}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleSelect}
          className="hidden"
        />

        {!file ? (
          <div className="space-y-3">
            <div className="text-5xl">📂</div>
            <h3 className="font-display text-xl font-semibold text-white">
              Drop your PDF resume here
            </h3>
            <p className="text-slate-400">or click to browse files</p>
            <p className="text-slate-500 text-sm">PDF only · Max 5MB</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-center gap-4">
              <div className="w-12 h-12 bg-rose-500/15 rounded-xl flex items-center justify-center text-2xl">
                📄
              </div>
              <div className="text-left">
                <p className="font-semibold text-white">{file.name}</p>
                <p className="text-slate-400 text-sm">{formatBytes(file.size)}</p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setFile(null) }}
                className="text-slate-500 hover:text-rose-400 ml-2 transition-colors"
              >✕</button>
            </div>

            {/* Progress bar */}
            {uploadMutation.isPending && (
              <div>
                <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-sky-500 to-blue-500 rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
                <p className="text-sky-400 text-sm mt-2">{progress}% uploaded</p>
              </div>
            )}

            {!uploadMutation.isPending && (
              <button
                onClick={(e) => { e.stopPropagation(); uploadMutation.mutate(file) }}
                className="btn-primary flex items-center gap-2 mx-auto"
              >
                🚀 Analyze Resume
              </button>
            )}
          </div>
        )}
      </div>

      {/* Skills Result */}
      <AnimatePresence>
        {uploadedSkills.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="card p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-lg font-semibold text-white">
                🎉 {uploadedSkills.length} Skills Detected!
              </h2>
              <button
                onClick={() => navigate('/my-matches')}
                className="btn-primary text-sm"
              >
                Analyze My Matches →
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {visibleSkills.map((skill) => (
                <motion.span
                  key={skill}
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                >
                  <SkillTag skill={skill} variant="matched" size="md" />
                </motion.span>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ATS Critique & Feedback Section */}
      <AnimatePresence>
        {selectedResumeId && (
          <motion.div
            ref={critiqueRef}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 30 }}
            className="card p-6 border-white/[0.08] relative overflow-hidden"
          >
            {/* Top decorative glow */}
            <div className="absolute top-0 right-0 w-48 h-48 bg-sky-500/5 rounded-full blur-3xl pointer-events-none" />

            <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/[0.06]">
              <div>
                <h2 className="font-display text-lg font-bold text-white flex items-center gap-2">
                  📝 ATS Resume Critique
                </h2>
                <p className="text-xs text-slate-400">Heuristical scan on formatting, keywords, and metrics</p>
              </div>
              <button
                onClick={() => setSelectedResumeId(null)}
                className="text-slate-500 hover:text-white transition-colors text-sm px-2.5 py-1 rounded-lg hover:bg-white/[0.04]"
              >
                ✕ Close
              </button>
            </div>

            {isFeedbackLoading ? (
              <div className="py-12 flex flex-col items-center justify-center gap-3">
                <LoadingSpinner size="lg" />
                <p className="text-slate-400 text-sm animate-pulse">Running ATS scanners and AI advisors…</p>
              </div>
            ) : feedbackError ? (
              <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-sm">
                Could not fetch feedback for this resume. Please try again.
              </div>
            ) : feedbackData ? (
              <div className="space-y-8">
                {/* Score & General Summary */}
                <div className="flex flex-col md:flex-row items-center gap-6 p-4 rounded-xl bg-white/[0.01] border border-white/[0.03]">
                  {/* Glowing Animated Progress Ring */}
                  <div className="relative w-28 h-28 flex items-center justify-center shrink-0">
                    <svg className="w-full h-full transform -rotate-90">
                      <circle
                        cx="56"
                        cy="56"
                        r="48"
                        className="stroke-slate-800"
                        strokeWidth="8"
                        fill="transparent"
                      />
                      <motion.circle
                        cx="56"
                        cy="56"
                        r="48"
                        className={`${
                          feedbackData.score >= 80 ? 'stroke-emerald-500' :
                          feedbackData.score >= 60 ? 'stroke-amber-500' : 'stroke-rose-500'
                        }`}
                        strokeWidth="8"
                        fill="transparent"
                        strokeDasharray={2 * Math.PI * 48}
                        initial={{ strokeDashoffset: 2 * Math.PI * 48 }}
                        animate={{ strokeDashoffset: 2 * Math.PI * 48 * (1 - feedbackData.score / 100) }}
                        transition={{ duration: 1, ease: "easeOut" }}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute text-center">
                      <span className="text-3xl font-extrabold font-display text-white">{feedbackData.grade}</span>
                      <p className="text-[10px] text-slate-400 font-mono mt-0.5">{feedbackData.score}/100</p>
                    </div>
                  </div>

                  {/* Summary text */}
                  <div className="flex-1 text-center md:text-left space-y-1.5">
                    <h3 className="font-display font-semibold text-white text-base">
                      {feedbackData.score >= 85 ? '🌟 Excellent Work!' : (feedbackData.score >= 70 ? '📈 Good foundation, slight tweaks needed' : '🔧 High-priority fixes required')}
                    </h3>
                    <p className="text-slate-300 text-sm leading-relaxed">
                      {feedbackData.summary}
                    </p>
                  </div>
                </div>

                {/* Checklist Categories */}
                <div className="grid md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <h3 className="font-display font-semibold text-slate-200 text-sm">
                      📊 ATS Parameters Breakdown
                    </h3>
                    <div className="space-y-4 bg-white/[0.01] border border-white/[0.03] p-4 rounded-xl">
                      {feedbackData.categories.map((cat) => {
                        const isExpanded = expandedCategories[cat.name];
                        const barColor = cat.status === 'success' ? 'bg-emerald-500' : (cat.status === 'warning' ? 'bg-amber-500' : 'bg-rose-500');
                        const textColor = cat.status === 'success' ? 'text-emerald-400' : (cat.status === 'warning' ? 'text-amber-400' : 'text-rose-400');
                        
                        return (
                          <div key={cat.name} className="border-b border-white/[0.04] pb-4 last:border-0 last:pb-0">
                            <div 
                              onClick={() => toggleCategory(cat.name)}
                              className="flex items-center justify-between cursor-pointer group"
                            >
                              <div className="flex-1 pr-4">
                                <div className="flex items-center justify-between mb-1.5">
                                  <span className="font-semibold text-xs text-slate-300 group-hover:text-white transition-colors">{cat.name}</span>
                                  <span className={`text-xs font-mono font-bold ${textColor}`}>{cat.score}%</span>
                                </div>
                                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-full">
                                  <motion.div 
                                    className={`h-full ${barColor}`} 
                                    initial={{ width: 0 }}
                                    animate={{ width: `${cat.score}%` }}
                                    transition={{ duration: 0.8 }}
                                  />
                                </div>
                              </div>
                              <span className="text-slate-500 group-hover:text-slate-300 text-xs transition-colors shrink-0">
                                {isExpanded ? '▲' : '▼'}
                              </span>
                            </div>
                            <AnimatePresence>
                              {isExpanded && (
                                <motion.div
                                  initial={{ height: 0, opacity: 0 }}
                                  animate={{ height: 'auto', opacity: 1 }}
                                  exit={{ height: 0, opacity: 0 }}
                                  className="overflow-hidden mt-3 pl-1 space-y-2"
                                >
                                  {cat.feedback.map((fb, idx) => (
                                    <div key={idx} className="text-xs text-slate-400 flex items-start gap-2 leading-relaxed">
                                      <span className="shrink-0 mt-0.5">
                                        {fb.startsWith('✅') ? '✅' : (fb.startsWith('❌') ? '❌' : (fb.startsWith('⚠️') ? '⚠️' : (fb.startsWith('💡') ? '💡' : '•')))}
                                      </span>
                                      <span>
                                        {fb.replace(/^[✅❌⚠️💡]\s*/, '')}
                                      </span>
                                    </div>
                                  ))}
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  {/* AI Rewrite Assistant */}
                  <div className="space-y-4">
                    <h3 className="font-display font-semibold text-slate-200 text-sm flex items-center gap-2">
                      💡 Resume Bullet Optimization
                    </h3>
                    <div className="space-y-3 overflow-y-auto max-h-[340px] pr-1">
                      {feedbackData.bullet_suggestions.map((sug, i) => (
                        <div key={i} className="bg-[#0e1326] border border-white/[0.04] p-3.5 rounded-xl flex flex-col gap-2.5">
                          <div className="space-y-1.5">
                            <div className="text-[10px] text-slate-500 font-semibold tracking-wider uppercase">Original phrasing</div>
                            <p className="text-xs text-slate-400 font-mono italic break-words">"{sug.original}"</p>
                          </div>
                          
                          <div className="h-px bg-white/[0.03]" />
                          
                          <div className="space-y-1.5 relative">
                            <div className="text-[10px] text-sky-400 font-semibold tracking-wider uppercase">Suggested rewrite</div>
                            <p className="text-xs text-slate-200 font-mono break-words">"{sug.suggestion}"</p>
                          </div>

                          <button
                            onClick={() => handleCopy(sug.suggestion, i)}
                            className="btn-secondary text-[11px] py-1.5 px-3 flex items-center justify-center gap-1.5 self-end"
                          >
                            {copiedIndex === i ? '✅ Copied!' : '📋 Copy Text'}
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Previous Resumes */}
      <div>
        <h2 className="font-display text-lg font-semibold text-white mb-4">📁 Uploaded Resumes</h2>
        {isLoading ? (
          <div className="space-y-3">
            {Array(2).fill(0).map((_, i) => <div key={i} className="card p-4 skeleton h-16" />)}
          </div>
        ) : resumes.length === 0 ? (
          <p className="text-slate-500 text-sm py-4 text-center">No resumes uploaded yet</p>
        ) : (
          <div className="space-y-3">
            {resumes.map((r) => (
              <div key={r.id} className="card p-4 flex items-center gap-4 hover:bg-white/[0.01] transition-all">
                <div className="w-10 h-10 bg-rose-500/15 rounded-xl flex items-center justify-center text-lg shrink-0">
                  📄
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-white text-sm truncate">{r.filename || r.file_name}</p>
                  <p className="text-slate-500 text-xs">
                    {formatDate(r.uploaded_at || r.created_at)} · {r.total_skills ?? r.skills_count ?? r.skills_found?.length ?? 0} skills
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setSelectedResumeId(r.id)}
                    className={`text-xs px-3 py-1.5 rounded-lg transition-colors border
                      ${selectedResumeId === r.id 
                        ? 'bg-sky-500/10 text-sky-400 border-sky-500/30' 
                        : 'bg-white/[0.04] text-slate-300 border-white/[0.08] hover:bg-white/[0.08] hover:text-white'}`}
                  >
                    ATS Critique
                  </button>
                  <button
                    onClick={() => setDeleteConfirm(r.id)}
                    className="text-slate-500 hover:text-rose-400 transition-colors text-xs px-3 py-1.5 rounded-lg hover:bg-rose-500/10"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteConfirm && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDeleteConfirm(null)}
              className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4"
            >
              <div className="card p-6 max-w-sm w-full border border-rose-500/30">
                <h3 className="font-display font-semibold text-white text-lg mb-2">Delete Resume?</h3>
                <p className="text-slate-400 text-sm mb-5">
                  This will permanently remove the resume, its detected skills, and matching history. This cannot be undone.
                </p>
                <div className="flex gap-3">
                  <button onClick={() => setDeleteConfirm(null)} className="flex-1 btn-secondary">Cancel</button>
                  <button
                    onClick={() => deleteMutation.mutate(deleteConfirm)}
                    disabled={deleteMutation.isPending}
                    className="flex-1 bg-rose-500 hover:bg-rose-400 text-white font-semibold px-4 py-2.5 rounded-xl transition-colors flex items-center justify-center gap-2"
                  >
                    {deleteMutation.isPending ? <LoadingSpinner size="sm" /> : null}
                    Delete
                  </button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

