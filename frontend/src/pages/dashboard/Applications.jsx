import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  closestCorners,
} from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { getMyApplications, updateApplicationStatus } from '../../api/applications'
import { formatDate } from '../../utils/formatDate'
import EmptyState from '../../components/ui/EmptyState'
import { Link } from 'react-router-dom'

const COLUMNS = [
  { id: 'applied', label: 'Applied', icon: '📨', color: 'sky' },
  { id: 'reviewing', label: 'Under Review', icon: '🔍', color: 'amber' },
  { id: 'accepted', label: 'Accepted', icon: '✅', color: 'emerald' },
  { id: 'rejected', label: 'Rejected', icon: '❌', color: 'rose' },
]

const STATUS_COLORS = {
  applied: 'border-sky-500/20 bg-sky-500/5',
  reviewing: 'border-amber-500/20 bg-amber-500/5',
  accepted: 'border-emerald-500/20 bg-emerald-500/5',
  rejected: 'border-rose-500/20 bg-rose-500/5',
}

function AppCard({ app, isOverlay = false }) {
  const [expanded, setExpanded] = useState(false)
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: app.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  if (isOverlay) {
    return (
      <div className="card p-4 rotate-2 scale-105 shadow-2xl border border-sky-500/40 cursor-grabbing">
        <p className="font-semibold text-white text-sm">{app.internship?.title || app.job_title || '—'}</p>
        <p className="text-slate-400 text-xs">{app.internship?.company || app.company || '—'}</p>
      </div>
    )
  }

  return (
    <div ref={setNodeRef} style={style}>
      <div
        className={`card p-4 cursor-pointer hover:border-slate-500/60 transition-all ${expanded ? 'border-slate-500/60' : ''}`}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          <div
            {...attributes}
            {...listeners}
            className="mt-0.5 text-slate-600 hover:text-slate-400 cursor-grab active:cursor-grabbing touch-none"
            onClick={(e) => e.stopPropagation()}
          >
            ⠿
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-white text-sm leading-snug">{app.internship?.title || app.job_title || '—'}</p>
            <p className="text-slate-400 text-xs mt-0.5">{app.internship?.company || app.company || '—'}</p>
            <p className="text-slate-500 text-xs mt-1">{formatDate(app.applied_at || app.created_at)}</p>
          </div>
        </div>

        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mt-3 pt-3 border-t border-slate-700/50"
          >
            <textarea
              className="input-field text-xs py-2 resize-none"
              rows={3}
              placeholder="Add notes…"
              defaultValue={app.notes || ''}
              onClick={(e) => e.stopPropagation()}
            />
            {app.status === 'accepted' && (
              <p className="text-emerald-400 text-xs mt-2 font-medium">🎉 Congratulations! You were accepted.</p>
            )}
            {app.status === 'rejected' && (
              <p className="text-rose-400 text-xs mt-2">❌ Not selected this time. Keep going!</p>
            )}
          </motion.div>
        )}
      </div>
    </div>
  )
}

function KanbanColumn({ column, apps }) {
  const { setNodeRef, isOver } = useDroppable({ id: `column-${column.id}` })

  const colorMap = {
    sky: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    violet: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    rose: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  }

  return (
    <div className="flex flex-col gap-3 min-w-0">
      <div className={`flex items-center gap-2 rounded-xl px-3 py-2 border ${colorMap[column.color]}`}>
        <span>{column.icon}</span>
        <span className="font-display font-semibold text-sm">{column.label}</span>
        <span className="ml-auto text-xs bg-black/20 rounded-md px-1.5 py-0.5">{apps.length}</span>
      </div>

      <SortableContext items={apps.map((a) => a.id)} strategy={verticalListSortingStrategy}>
        <div
          ref={setNodeRef}
          className={`space-y-2 min-h-[120px] rounded-xl transition-colors ${isOver ? 'bg-slate-800/60' : ''}`}
        >
          {apps.map((app) => (
            <AppCard key={app.id} app={app} />
          ))}
          {apps.length === 0 && (
            <div className="border-2 border-dashed border-slate-700/50 rounded-xl p-6 text-center">
              <p className="text-slate-600 text-xs">No applications here</p>
            </div>
          )}
        </div>
      </SortableContext>
    </div>
  )
}

export default function Applications() {
  const [activeId, setActiveId] = useState(null)
  const queryClient = useQueryClient()

  const { data: applications = [], isLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: getMyApplications,
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, status }) => updateApplicationStatus(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['applications'] }),
    onError: (e) => toast.error(e.message),
  })

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  const getColumnApps = (colId) => applications.filter((a) => a.status === colId)

  const handleDragEnd = ({ active, over }) => {
    setActiveId(null)
    if (!over || active.id === over.id) return
    const overId = String(over.id)
    if (overId.startsWith('column-')) {
      updateMutation.mutate({ id: active.id, status: overId.replace('column-', '') })
      return
    }
    const targetCol = COLUMNS.find((c) => {
      const colApps = getColumnApps(c.id)
      return colApps.some((a) => a.id === over.id)
    })
    if (targetCol) {
      updateMutation.mutate({ id: active.id, status: targetCol.id })
    }
  }

  const activeApp = applications.find((a) => a.id === activeId)

  const totalApps = applications.length
  const responded = applications.filter((a) => ['accepted', 'rejected'].includes(a.status)).length
  const responseRate = totalApps > 0 ? Math.round((responded / totalApps) * 100) : 0

  if (isLoading) {
    return (
      <div className="py-8 px-4 sm:px-6 max-w-7xl mx-auto">
        <div className="skeleton h-8 w-48 mb-6" />
        <div className="grid grid-cols-4 gap-4">
          {Array(4).fill(0).map((_, i) => <div key={i} className="skeleton h-64 rounded-2xl" />)}
        </div>
      </div>
    )
  }

  return (
    <div className="py-8 px-4 sm:px-6 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Application <span className="bg-gradient-to-r from-sky-400 to-violet-400 bg-clip-text text-transparent">Tracker</span></h1>
        <p className="text-slate-400 mt-1">Drag cards between columns to update status</p>
      </div>

      {/* Stats bar */}
      <div className="flex flex-wrap gap-4">
        {[
          { label: 'Total Applied', value: totalApps, color: 'text-white' },
          { label: 'Response Rate', value: `${responseRate}%`, color: 'text-sky-400' },
          { label: 'Under Review', value: getColumnApps('reviewing').length, color: 'text-amber-400' },
          { label: 'Accepted', value: applications.filter((a) => a.status === 'accepted').length, color: 'text-emerald-400' },
        ].map((s) => (
          <div key={s.label} className="card px-5 py-3 flex items-center gap-3">
            <span className={`font-display text-2xl font-bold ${s.color}`}>{s.value}</span>
            <span className="text-slate-400 text-sm">{s.label}</span>
          </div>
        ))}
      </div>

      {applications.length === 0 ? (
        <EmptyState
          icon="📋"
          title="No applications yet"
          description="Start applying to internships and track your progress here"
          action={<Link to="/my-matches" className="btn-primary">Find Internships →</Link>}
        />
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={({ active }) => setActiveId(active.id)}
          onDragEnd={handleDragEnd}
        >
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {COLUMNS.map((col) => (
              <KanbanColumn key={col.id} column={col} apps={getColumnApps(col.id)} />
            ))}
          </div>
          <DragOverlay>
            {activeApp ? <AppCard app={activeApp} isOverlay /> : null}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  )
}
