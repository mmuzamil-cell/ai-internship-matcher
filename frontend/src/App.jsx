import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { AnimatePresence, motion } from 'framer-motion'

import { useAuth } from './hooks/useAuth'
import Navbar from './components/layout/Navbar'
import Sidebar from './components/layout/Sidebar'
import Footer from './components/layout/Footer'
import Chatbot from './pages/Chatbot'

import Login from './pages/auth/Login'
import Register from './pages/auth/Register'
import Dashboard from './pages/dashboard/Dashboard'
import MyMatches from './pages/dashboard/MyMatches'
import JobDetail from './pages/dashboard/JobDetail'
import ResumeUpload from './pages/dashboard/ResumeUpload'
import Applications from './pages/dashboard/Applications'
import SkillGap from './pages/dashboard/SkillGap'
import Profile from './pages/dashboard/Profile'
import ScrapeInternships from './pages/dashboard/ScrapeInternships'
import CVBuilder from './pages/dashboard/CVBuilder'
import NotFound from './pages/NotFound'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2,
      retry: 1,
    },
  },
})

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function PublicRoute({ children, redirectTo = '/dashboard' }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <Navigate to={redirectTo} replace /> : children
}

const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
}

function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  const isAuthPage = ['/login', '/register'].includes(location.pathname)

  return (
    <div className="min-h-screen flex flex-col bg-[#060b1a]">
      <Navbar onSidebarToggle={() => setSidebarOpen(!sidebarOpen)} />

      <div className="flex flex-1">
        {isAuthenticated && !isAuthPage && (
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        )}

        <main className="flex-1 min-w-0">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.25 }}
            >
              <Routes location={location}>
                {/* Public routes */}
                <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
                <Route path="/register" element={<PublicRoute redirectTo="/resume"><Register /></PublicRoute>} />

                {/* Protected routes */}
                <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                <Route path="/my-matches" element={<ProtectedRoute><MyMatches /></ProtectedRoute>} />
                <Route path="/jobs/:id" element={<ProtectedRoute><JobDetail /></ProtectedRoute>} />
                <Route path="/resume" element={<ProtectedRoute><ResumeUpload /></ProtectedRoute>} />
                <Route path="/applications" element={<ProtectedRoute><Applications /></ProtectedRoute>} />
                <Route path="/skill-gap" element={<ProtectedRoute><SkillGap /></ProtectedRoute>} />
                <Route path="/scrape" element={<ProtectedRoute><ScrapeInternships /></ProtectedRoute>} />
                <Route path="/cv-builder" element={<ProtectedRoute><CVBuilder /></ProtectedRoute>} />
                <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />

                {/* Redirects */}
                <Route path="/" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {!isAuthPage && <Footer />}

      {/* Floating chatbot */}
      {isAuthenticated && !isAuthPage && <Chatbot />}

      {/* Toast notifications */}
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#1e293b',
            color: '#f1f5f9',
            border: '1px solid #334155',
            borderRadius: '12px',
            fontFamily: 'DM Sans, sans-serif',
          },
          success: { iconTheme: { primary: '#10b981', secondary: '#1e293b' } },
          error: { iconTheme: { primary: '#f43f5e', secondary: '#1e293b' } },
        }}
      />
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppLayout />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
