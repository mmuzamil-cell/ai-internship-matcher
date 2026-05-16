import { useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import { useAuth } from '../../hooks/useAuth'

let _id = 0
const uid = () => `_${++_id}_${Date.now()}`
const blankEdu = () => ({ id: uid(), school: '', degree: '', field: '', start: '', end: '', gpa: '' })
const blankExp = () => ({ id: uid(), company: '', role: '', start: '', end: '', description: '' })
const blankProj = () => ({ id: uid(), name: '', tech: '', description: '', link: '' })

async function downloadPDF(el, filename) {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
    import('html2canvas-pro'), import('jspdf'),
  ])
  const clone = el.cloneNode(true)
  clone.style.width = '794px'
  clone.style.position = 'absolute'
  clone.style.left = '-9999px'
  clone.style.top = '0'
  document.body.appendChild(clone)
  try {
    const canvas = await html2canvas(clone, {
      scale: 2, useCORS: true, backgroundColor: '#ffffff',
      width: 794, windowWidth: 794,
    })
    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF('p', 'mm', 'a4')
    const pW = pdf.internal.pageSize.getWidth()
    const pH = pdf.internal.pageSize.getHeight()
    const imgH = (canvas.height * pW) / canvas.width
    let y = 0
    while (y < imgH) {
      if (y > 0) pdf.addPage()
      pdf.addImage(imgData, 'PNG', 0, -y, pW, imgH)
      y += pH
    }
    pdf.save(filename)
  } finally {
    document.body.removeChild(clone)
  }
}

const TEMPLATES = {
  modern:    { label: 'Modern',    accent: '#0ea5e9', accent2: '#0284c7', headerBg: 'linear-gradient(135deg,#0ea5e9,#0369a1)' },
  classic:   { label: 'Classic',   accent: '#1e293b', accent2: '#334155', headerBg: '#1e293b' },
  elegant:   { label: 'Elegant',   accent: '#7c3aed', accent2: '#6d28d9', headerBg: 'linear-gradient(135deg,#7c3aed,#4f46e5)' },
  minimal:   { label: 'Minimal',   accent: '#059669', accent2: '#047857', headerBg: '#059669' },
  bold:      { label: 'Bold',      accent: '#dc2626', accent2: '#b91c1c', headerBg: 'linear-gradient(135deg,#dc2626,#991b1b)' },
}

const TABS = [
  { key: 'personal', icon: '👤', label: 'Personal' },
  { key: 'education', icon: '🎓', label: 'Education' },
  { key: 'experience', icon: '💼', label: 'Experience' },
  { key: 'skills', icon: '⚡', label: 'Skills' },
  { key: 'projects', icon: '🚀', label: 'Projects' },
  { key: 'extra', icon: '✨', label: 'Extra' },
]

function Input({ label, value, onChange, area, placeholder, ...rest }) {
  return (
    <div>
      <label className="text-xs text-slate-400 font-medium mb-1 block">{label}</label>
      {area ? (
        <textarea rows={3} className="input-field text-sm" placeholder={placeholder} value={value} onChange={onChange} />
      ) : (
        <input className="input-field text-sm" placeholder={placeholder} value={value} onChange={onChange} {...rest} />
      )}
    </div>
  )
}

/* ═══ PREVIEW COMPONENT ═══ */
function CVPreview({ personal, education, experience, skills, projects, certifications, languages, template }) {
  const t = TEMPLATES[template]
  const skillList = skills.split(',').map(s => s.trim()).filter(Boolean)
  const hasContent = personal.name || personal.summary || education.some(e => e.school)

  const SH = ({ text }) => (
    <div style={{ borderBottom: `2px solid ${t.accent}`, marginTop: 16, marginBottom: 8, paddingBottom: 2 }}>
      <span style={{ fontWeight: 700, fontSize: 13, color: t.accent, textTransform: 'uppercase', letterSpacing: 1.5, fontFamily: 'Arial, Helvetica, sans-serif' }}>{text}</span>
    </div>
  )

  if (!hasContent) {
    return (
      <div style={{ textAlign: 'center', color: '#94a3b8', marginTop: 120, fontSize: 14, fontFamily: 'Arial, sans-serif' }}>
        <p style={{ fontSize: 48, marginBottom: 16 }}>&#128221;</p>
        <p>Fill in the form to see your CV preview</p>
      </div>
    )
  }

  return (
    <>
      {/* Header */}
      {template === 'modern' || template === 'elegant' || template === 'bold' ? (
        <div style={{ background: t.headerBg, color: '#fff', padding: '24px 28px', margin: '-28px -28px 20px -28px', borderRadius: '0' }}>
          <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0, letterSpacing: -0.5, fontFamily: 'Arial, Helvetica, sans-serif' }}>
            {personal.name || 'Your Name'}
          </h1>
          <div style={{ fontSize: 11, marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: '4px 14px', opacity: 0.9 }}>
            {personal.email && <span>{personal.email}</span>}
            {personal.phone && <span>{personal.phone}</span>}
            {personal.location && <span>{personal.location}</span>}
            {personal.linkedin && <span>{personal.linkedin}</span>}
            {personal.github && <span>{personal.github}</span>}
            {personal.portfolio && <span>{personal.portfolio}</span>}
          </div>
        </div>
      ) : (
        <div style={{ textAlign: template === 'minimal' ? 'left' : 'center', marginBottom: 14 }}>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: t.accent, margin: 0, letterSpacing: -0.5, fontFamily: 'Arial, Helvetica, sans-serif' }}>
            {personal.name || 'Your Name'}
          </h1>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 6, display: 'flex', flexWrap: 'wrap', justifyContent: template === 'minimal' ? 'flex-start' : 'center', gap: '4px 14px' }}>
            {personal.email && <span>{personal.email}</span>}
            {personal.phone && <span>{personal.phone}</span>}
            {personal.location && <span>{personal.location}</span>}
            {personal.linkedin && <span>{personal.linkedin}</span>}
            {personal.github && <span>{personal.github}</span>}
            {personal.portfolio && <span>{personal.portfolio}</span>}
          </div>
        </div>
      )}

      {personal.summary && <>
        <SH text="Professional Summary" />
        <p style={{ fontSize: 11, color: '#334155', lineHeight: 1.6, margin: 0 }}>{personal.summary}</p>
      </>}

      {education.some(e => e.school) && <>
        <SH text="Education" />
        {education.filter(e => e.school).map(ed => (
          <div key={ed.id} style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <strong style={{ fontSize: 12, fontFamily: 'Arial, sans-serif' }}>{ed.school}</strong>
              <span style={{ fontSize: 10.5, color: '#64748b' }}>{[ed.start, ed.end].filter(Boolean).join(' - ')}</span>
            </div>
            <div style={{ fontSize: 11, color: '#475569' }}>
              {ed.degree}{ed.field ? ` in ${ed.field}` : ''}{ed.gpa ? ` | GPA: ${ed.gpa}` : ''}
            </div>
          </div>
        ))}
      </>}

      {experience.some(e => e.company || e.role) && <>
        <SH text="Experience" />
        {experience.filter(e => e.company || e.role).map(ex => (
          <div key={ex.id} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <strong style={{ fontSize: 12, fontFamily: 'Arial, sans-serif' }}>{ex.role || 'Role'}{ex.company ? ` - ${ex.company}` : ''}</strong>
              <span style={{ fontSize: 10.5, color: '#64748b' }}>{[ex.start, ex.end].filter(Boolean).join(' - ')}</span>
            </div>
            {ex.description && (
              <div style={{ fontSize: 11, color: '#475569', marginTop: 3 }}>
                {ex.description.split('\n').map((line, i) => {
                  const t = line.trim()
                  if (!t) return null
                  if (t.startsWith('•') || t.startsWith('-') || t.startsWith('*'))
                    return <div key={i} style={{ paddingLeft: 12, marginTop: 2 }}>{t}</div>
                  return <div key={i} style={{ marginTop: 2 }}>{t}</div>
                })}
              </div>
            )}
          </div>
        ))}
      </>}

      {skillList.length > 0 && <>
        <SH text="Skills" />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
          {skillList.map(s => (
            <span key={s} style={{
              background: t.accent + '14', color: t.accent, border: `1px solid ${t.accent}30`,
              borderRadius: 5, padding: '2px 10px', fontSize: 10.5, fontWeight: 600, fontFamily: 'Arial, sans-serif'
            }}>{s}</span>
          ))}
        </div>
      </>}

      {projects.some(p => p.name) && <>
        <SH text="Projects" />
        {projects.filter(p => p.name).map(p => (
          <div key={p.id} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: 12, fontFamily: 'Arial, sans-serif' }}>{p.name}</strong>
              {p.link && <span style={{ fontSize: 10, color: t.accent }}>{p.link}</span>}
            </div>
            {p.tech && <div style={{ fontSize: 10.5, color: t.accent, fontWeight: 600 }}>{p.tech}</div>}
            {p.description && <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{p.description}</div>}
          </div>
        ))}
      </>}

      {certifications.trim() && <>
        <SH text="Certifications" />
        {certifications.split('\n').filter(Boolean).map((c, i) => (
          <div key={i} style={{ fontSize: 11, color: '#475569', paddingLeft: 8, marginTop: 2 }}>- {c.trim()}</div>
        ))}
      </>}

      {languages.trim() && <>
        <SH text="Languages" />
        <p style={{ fontSize: 11, color: '#475569', margin: 0 }}>{languages}</p>
      </>}
    </>
  )
}

/* ═══ MAIN COMPONENT ═══ */
export default function CVBuilder() {
  const { user } = useAuth()
  const previewRef = useRef(null)
  const [template, setTemplate] = useState('modern')
  const [tab, setTab] = useState('personal')
  const [downloading, setDownloading] = useState(false)
  const [saving, setSaving] = useState(false)

  const [personal, setPersonal] = useState({
    name: user?.full_name || '', email: user?.email || '', phone: '', location: '',
    linkedin: '', github: '', portfolio: '', summary: '',
  })
  const [education, setEducation] = useState([blankEdu()])
  const [experience, setExperience] = useState([blankExp()])
  const [skills, setSkills] = useState('')
  const [projects, setProjects] = useState([blankProj()])
  const [certifications, setCertifications] = useState('')
  const [languages, setLanguages] = useState('')

  const up = (setter) => (id, field, value) =>
    setter(prev => prev.map(x => (x.id === id ? { ...x, [field]: value } : x)))
  const add = (setter, factory) => () => setter(p => [...p, factory()])
  const remove = (setter) => (id) => setter(p => p.filter(x => x.id !== id))
  const skillList = skills.split(',').map(s => s.trim()).filter(Boolean)

  const handleDownload = useCallback(async () => {
    if (!previewRef.current) return
    setDownloading(true)
    try {
      await downloadPDF(previewRef.current, `${personal.name || 'resume'}_cv.pdf`)
      toast.success('CV downloaded as PDF!')
    } catch (e) {
      console.error(e)
      toast.error('Download failed: ' + e.message)
    } finally { setDownloading(false) }
  }, [personal.name])

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      const { default: api } = await import('../../api/client')
      await api.post('/resume/from-cv', {
        name: personal.name, email: personal.email, phone: personal.phone,
        location: personal.location, linkedin: personal.linkedin, github: personal.github,
        portfolio: personal.portfolio, summary: personal.summary, education, experience,
        skills, projects, certifications, languages,
      })
      toast.success('CV saved & skills extracted for matching!')
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message)
    } finally { setSaving(false) }
  }, [personal, education, experience, skills, projects, certifications, languages])

  const accent = TEMPLATES[template].accent
  const I = Input

  return (
    <div className="py-8 px-4 sm:px-6 max-w-[1500px] mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="page-title">
            CV <span className="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">Builder</span>
          </h1>
          <p className="text-slate-400 mt-1">Create a professional CV and download as PDF</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(TEMPLATES).map(([k, v]) => (
            <button key={k} onClick={() => setTemplate(k)}
              className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition-all ${template === k
                ? 'text-white border-sky-500/40 shadow-lg shadow-sky-500/10'
                : 'bg-white/[0.03] text-slate-400 border-white/[0.06] hover:border-white/[0.15] hover:text-white'}`}
              style={template === k ? { background: v.headerBg || v.accent } : {}}>
              {v.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* LEFT: FORM */}
        <div className="space-y-4">
          {/* Tabs */}
          <div className="flex flex-wrap gap-1.5">
            {TABS.map(t => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`text-xs px-3 py-2 rounded-xl border font-medium transition-all ${tab === t.key
                  ? 'bg-sky-500/15 text-sky-400 border-sky-500/30 shadow-sm shadow-sky-500/10'
                  : 'bg-white/[0.03] text-slate-400 border-white/[0.06] hover:border-white/[0.12] hover:text-white'}`}>
                {t.icon} {t.label}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="card p-5 space-y-4">

              {tab === 'personal' && <>
                <h2 className="font-display text-lg font-semibold text-white">Personal Information</h2>
                <div className="grid sm:grid-cols-2 gap-3">
                  <I label="Full Name" placeholder="John Doe" value={personal.name} onChange={e => setPersonal({ ...personal, name: e.target.value })} />
                  <I label="Email" placeholder="john@email.com" value={personal.email} onChange={e => setPersonal({ ...personal, email: e.target.value })} />
                  <I label="Phone" placeholder="+92 300 1234567" value={personal.phone} onChange={e => setPersonal({ ...personal, phone: e.target.value })} />
                  <I label="Location" placeholder="Lahore, Pakistan" value={personal.location} onChange={e => setPersonal({ ...personal, location: e.target.value })} />
                  <I label="LinkedIn" placeholder="linkedin.com/in/johndoe" value={personal.linkedin} onChange={e => setPersonal({ ...personal, linkedin: e.target.value })} />
                  <I label="GitHub" placeholder="github.com/johndoe" value={personal.github} onChange={e => setPersonal({ ...personal, github: e.target.value })} />
                </div>
                <I label="Portfolio" placeholder="https://johndoe.dev" value={personal.portfolio} onChange={e => setPersonal({ ...personal, portfolio: e.target.value })} />
                <I label="Professional Summary" area placeholder="Passionate software engineer with 2+ years of experience..." value={personal.summary} onChange={e => setPersonal({ ...personal, summary: e.target.value })} />
              </>}

              {tab === 'education' && <>
                <div className="flex items-center justify-between">
                  <h2 className="font-display text-lg font-semibold text-white">Education</h2>
                  <button onClick={add(setEducation, blankEdu)} className="text-xs btn-secondary py-1.5 px-3">+ Add</button>
                </div>
                {education.map((ed, i) => (
                  <div key={ed.id} className="p-3 bg-white/[0.02] rounded-xl border border-white/[0.05] space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-slate-500 font-mono">#{i + 1}</span>
                      {education.length > 1 && <button onClick={() => remove(setEducation)(ed.id)} className="text-xs text-rose-400 hover:text-rose-300">Remove</button>}
                    </div>
                    <div className="grid sm:grid-cols-2 gap-3">
                      <I label="Institution" placeholder="LUMS" value={ed.school} onChange={e => up(setEducation)(ed.id, 'school', e.target.value)} />
                      <I label="Degree" placeholder="BS Computer Science" value={ed.degree} onChange={e => up(setEducation)(ed.id, 'degree', e.target.value)} />
                      <I label="Field of Study" placeholder="Computer Science" value={ed.field} onChange={e => up(setEducation)(ed.id, 'field', e.target.value)} />
                      <I label="GPA" placeholder="3.8/4.0" value={ed.gpa} onChange={e => up(setEducation)(ed.id, 'gpa', e.target.value)} />
                      <I label="Start Date" placeholder="Sep 2020" value={ed.start} onChange={e => up(setEducation)(ed.id, 'start', e.target.value)} />
                      <I label="End Date" placeholder="Jun 2024" value={ed.end} onChange={e => up(setEducation)(ed.id, 'end', e.target.value)} />
                    </div>
                  </div>
                ))}
              </>}

              {tab === 'experience' && <>
                <div className="flex items-center justify-between">
                  <h2 className="font-display text-lg font-semibold text-white">Experience</h2>
                  <button onClick={add(setExperience, blankExp)} className="text-xs btn-secondary py-1.5 px-3">+ Add</button>
                </div>
                {experience.map((ex, i) => (
                  <div key={ex.id} className="p-3 bg-white/[0.02] rounded-xl border border-white/[0.05] space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-slate-500 font-mono">#{i + 1}</span>
                      {experience.length > 1 && <button onClick={() => remove(setExperience)(ex.id)} className="text-xs text-rose-400 hover:text-rose-300">Remove</button>}
                    </div>
                    <div className="grid sm:grid-cols-2 gap-3">
                      <I label="Company" placeholder="Google" value={ex.company} onChange={e => up(setExperience)(ex.id, 'company', e.target.value)} />
                      <I label="Role / Title" placeholder="Software Engineer Intern" value={ex.role} onChange={e => up(setExperience)(ex.id, 'role', e.target.value)} />
                      <I label="Start Date" placeholder="Jun 2023" value={ex.start} onChange={e => up(setExperience)(ex.id, 'start', e.target.value)} />
                      <I label="End Date" placeholder="Aug 2023 or Present" value={ex.end} onChange={e => up(setExperience)(ex.id, 'end', e.target.value)} />
                    </div>
                    <I label="Description (use • for bullets)" area placeholder={"• Developed a REST API using FastAPI\n• Reduced page load time by 40%"} value={ex.description} onChange={e => up(setExperience)(ex.id, 'description', e.target.value)} />
                  </div>
                ))}
              </>}

              {tab === 'skills' && <>
                <h2 className="font-display text-lg font-semibold text-white">Skills</h2>
                <I label="Skills (comma-separated)" area placeholder="Python, React, SQL, Docker, Machine Learning, Git..." value={skills} onChange={e => setSkills(e.target.value)} />
                {skillList.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {skillList.map(s => (
                      <span key={s} className="text-xs bg-sky-500/10 text-sky-400 border border-sky-500/20 rounded-lg px-2.5 py-1 font-medium">{s}</span>
                    ))}
                    <span className="text-xs text-slate-500 self-center ml-1">{skillList.length} skills</span>
                  </div>
                )}
              </>}

              {tab === 'projects' && <>
                <div className="flex items-center justify-between">
                  <h2 className="font-display text-lg font-semibold text-white">Projects</h2>
                  <button onClick={add(setProjects, blankProj)} className="text-xs btn-secondary py-1.5 px-3">+ Add</button>
                </div>
                {projects.map((p, i) => (
                  <div key={p.id} className="p-3 bg-white/[0.02] rounded-xl border border-white/[0.05] space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-slate-500 font-mono">#{i + 1}</span>
                      {projects.length > 1 && <button onClick={() => remove(setProjects)(p.id)} className="text-xs text-rose-400 hover:text-rose-300">Remove</button>}
                    </div>
                    <div className="grid sm:grid-cols-2 gap-3">
                      <I label="Project Name" placeholder="AI Chatbot" value={p.name} onChange={e => up(setProjects)(p.id, 'name', e.target.value)} />
                      <I label="Technologies" placeholder="Python, FastAPI, React" value={p.tech} onChange={e => up(setProjects)(p.id, 'tech', e.target.value)} />
                    </div>
                    <I label="Description" area placeholder="Built a full-stack AI chatbot..." value={p.description} onChange={e => up(setProjects)(p.id, 'description', e.target.value)} />
                    <I label="Link (optional)" placeholder="https://github.com/..." value={p.link} onChange={e => up(setProjects)(p.id, 'link', e.target.value)} />
                  </div>
                ))}
              </>}

              {tab === 'extra' && <>
                <h2 className="font-display text-lg font-semibold text-white">Extra Sections</h2>
                <I label="Certifications (one per line)" area placeholder={"AWS Cloud Practitioner - 2024\nGoogle Data Analytics - 2023"} value={certifications} onChange={e => setCertifications(e.target.value)} />
                <I label="Languages (comma-separated)" placeholder="English (Fluent), Urdu (Native)" value={languages} onChange={e => setLanguages(e.target.value)} />
              </>}

            </motion.div>
          </AnimatePresence>

          {/* Action Buttons */}
          <div className="grid grid-cols-2 gap-3">
            <button onClick={handleDownload} disabled={downloading}
              className="btn-primary py-3 flex items-center justify-center gap-2 text-sm">
              {downloading ? <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : null}
              {downloading ? 'Generating...' : 'Download PDF'}
            </button>
            <button onClick={handleSave} disabled={saving}
              className="btn-secondary py-3 flex items-center justify-center gap-2 text-sm">
              {saving ? <span className="inline-block w-4 h-4 border-2 border-sky-400/30 border-t-sky-400 rounded-full animate-spin" /> : null}
              {saving ? 'Saving...' : 'Save for AI Matching'}
            </button>
          </div>
        </div>

        {/* RIGHT: LIVE PREVIEW */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-sm font-semibold text-slate-400 uppercase tracking-wider">Live Preview</h2>
            <span className="text-xs text-slate-500">A4 Format</span>
          </div>
          <div className="card p-3 overflow-auto max-h-[85vh] sticky top-20" style={{ background: 'rgba(255,255,255,0.02)' }}>
            <div ref={previewRef} style={{
              background: '#fff', color: '#1e293b',
              fontFamily: "'Segoe UI', Arial, Helvetica, sans-serif",
              padding: 28, minHeight: 1000, fontSize: 12, lineHeight: 1.55,
              width: '100%', maxWidth: 794,
            }}>
              <CVPreview personal={personal} education={education} experience={experience}
                skills={skills} projects={projects} certifications={certifications}
                languages={languages} template={template} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
