import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import { uploadResume, getMyResumes, deleteResume } from '../../api/resume'
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
  const fileInputRef = useRef()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { setSkills } = useAuth()

  const { data: resumes = [], isLoading } = useQuery({
    queryKey: ['resumes'],
    queryFn: getMyResumes,
  })

  const uploadMutation = useMutation({
    mutationFn: (f) => uploadResume(f, (evt) => {
      setProgress(Math.round((evt.loaded / evt.total) * 100))
    }),
    onSuccess: (data) => {
      // Backend returns skills_found (ResumeResponse schema)
      const skills = data.skills_found || data.skills || data.extracted_skills || []
      setUploadedSkills(skills)
      setSkills(skills)
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
      queryClient.invalidateQueries({ queryKey: ['matches'] })
      toast.success('Resume analyzed successfully! 🎉')
      setProgress(0)
      setFile(null)

      // Animate skills in one by one
      setVisibleSkills([])
      skills.forEach((_, i) => {
        setTimeout(() => {
          setVisibleSkills((prev) => [...prev, skills[i]])
        }, i * 120)
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
      setDeleteConfirm(null)
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
    },
    onError: (e) => toast.error(e.message),
  })

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.type === 'application/pdf') setFile(dropped)
    else toast.error('Please upload a PDF file')
  }

  const handleSelect = (e) => {
    const f = e.target.files[0]
    if (f) setFile(f)
  }

  const formatBytes = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="py-8 px-4 sm:px-6 max-w-4xl mx-auto space-y-8 animate-fade-in">
      <div>
        <h1 className="page-title">Resume <span className="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">Upload</span></h1>
        <p className="text-slate-400 mt-1">Upload your resume and let AI extract your skills</p>
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
            <p className="text-slate-500 text-sm">PDF only · Max 10MB</p>
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
              {visibleSkills.map((skill, i) => (
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
              <div key={r.id} className="card p-4 flex items-center gap-4">
                <div className="w-10 h-10 bg-rose-500/15 rounded-xl flex items-center justify-center text-lg shrink-0">
                  📄
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-white text-sm truncate">{r.filename || r.file_name}</p>
                  <p className="text-slate-500 text-xs">
                    {formatDate(r.uploaded_at || r.created_at)} · {r.total_skills ?? r.skills_count ?? r.skills_found?.length ?? 0} skills
                  </p>
                </div>
                <button
                  onClick={() => setDeleteConfirm(r.id)}
                  className="text-slate-500 hover:text-rose-400 transition-colors text-sm px-3 py-1 rounded-lg hover:bg-rose-500/10"
                >
                  Delete
                </button>
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
                  This will permanently remove the resume and its detected skills. This cannot be undone.
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
