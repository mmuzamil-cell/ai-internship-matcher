import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import { sendMessage } from '../api/chatbot'
import { useAuth } from '../hooks/useAuth'

const STARTERS = [
  'Which skill should I learn first?',
  'How can I improve my match score?',
  'Help me write a cover letter',
  'How to prepare for interviews?',
]

const CHAT_KEY = 'chatbot_history'

/** Render markdown-like text with bold, bullets, headers, and line breaks */
function RenderMessage({ text }) {
  if (!text) return null
  
  const lines = text.split('\n')
  
  return (
    <div className="space-y-1.5">
      {lines.map((line, i) => {
        // Skip empty lines but add spacing
        if (!line.trim()) return <div key={i} className="h-1" />
        
        // Headers (## or **Header:**)
        if (line.startsWith('## ') || line.startsWith('### ')) {
          const headerText = line.replace(/^#{2,3}\s/, '')
          return <p key={i} className="font-semibold text-white text-sm mt-2">{renderInline(headerText)}</p>
        }
        
        // Bullet points
        if (line.trim().startsWith('• ') || line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
          const bulletText = line.trim().replace(/^[•\-\*]\s/, '')
          return (
            <div key={i} className="flex gap-1.5 pl-1">
              <span className="text-sky-400 shrink-0">•</span>
              <span>{renderInline(bulletText)}</span>
            </div>
          )
        }
        
        // Numbered items
        const numMatch = line.trim().match(/^(\d+)\.\s(.+)/)
        if (numMatch) {
          return (
            <div key={i} className="flex gap-1.5 pl-1">
              <span className="text-sky-400 shrink-0 font-mono text-xs mt-0.5">{numMatch[1]}.</span>
              <span>{renderInline(numMatch[2])}</span>
            </div>
          )
        }
        
        return <p key={i}>{renderInline(line)}</p>
      })}
    </div>
  )
}

/** Render inline markdown: **bold**, `code`, emoji */
function renderInline(text) {
  if (!text) return text
  
  const parts = []
  let remaining = text
  let key = 0
  
  while (remaining.length > 0) {
    // Bold **text**
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/)
    // Code `text`
    const codeMatch = remaining.match(/`(.+?)`/)
    
    // Find the earliest match
    let earliestMatch = null
    let matchType = null
    
    if (boldMatch && (!earliestMatch || boldMatch.index < earliestMatch.index)) {
      earliestMatch = boldMatch
      matchType = 'bold'
    }
    if (codeMatch && (!earliestMatch || codeMatch.index < earliestMatch.index)) {
      earliestMatch = codeMatch
      matchType = 'code'
    }
    
    if (!earliestMatch) {
      parts.push(remaining)
      break
    }
    
    // Add text before match
    if (earliestMatch.index > 0) {
      parts.push(remaining.substring(0, earliestMatch.index))
    }
    
    // Add formatted match
    if (matchType === 'bold') {
      parts.push(<strong key={key++} className="text-white font-semibold">{earliestMatch[1]}</strong>)
    } else if (matchType === 'code') {
      parts.push(
        <code key={key++} className="bg-slate-600/50 text-sky-300 px-1 py-0.5 rounded text-xs">
          {earliestMatch[1]}
        </code>
      )
    }
    
    remaining = remaining.substring(earliestMatch.index + earliestMatch[0].length)
  }
  
  return parts.length === 1 && typeof parts[0] === 'string' ? parts[0] : parts
}

export default function Chatbot() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState(() => {
    try { return JSON.parse(localStorage.getItem(CHAT_KEY) || '[]') } catch { return [] }
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef()
  const { skills } = useAuth()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, open])

  useEffect(() => {
    localStorage.setItem(CHAT_KEY, JSON.stringify(messages.slice(-30)))
  }, [messages])

  const send = async (text) => {
    const content = text || input.trim()
    if (!content || loading) return
    setInput('')

    const userMsg = { role: 'user', content }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setLoading(true)

    try {
      const apiMessages = newMessages.map((m) => ({ role: m.role, content: m.content }))
      const reply = await sendMessage(apiMessages, skills)
      setMessages((prev) => [...prev, { role: 'assistant', content: reply.content }])
    } catch (e) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: "I'm having trouble connecting right now. Here are some quick tips:\n\n• **Upload your resume** to get AI-powered skill matching\n• **Check the Scrape Jobs page** for new opportunities\n• **Visit the Skill Gap page** for personalized learning suggestions\n\nPlease try again in a moment!",
      }])
    } finally {
      setLoading(false)
    }
  }

  const clearChat = () => {
    setMessages([])
    localStorage.removeItem(CHAT_KEY)
    toast.success('Chat cleared')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <>
      {/* Floating button */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setOpen(!open)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-500 to-blue-600
                   flex items-center justify-center shadow-xl shadow-sky-500/30 text-white text-2xl
                   hover:shadow-2xl hover:shadow-sky-500/40 transition-shadow"
        aria-label="Open AI Career Advisor"
      >
        {open ? '✕' : '🤖'}
      </motion.button>

      {/* Chat Panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="fixed bottom-24 right-6 z-50 w-[400px] h-[560px] flex flex-col card
                       border border-slate-600/60 shadow-2xl shadow-black/60 overflow-hidden"
            style={{ maxWidth: 'calc(100vw - 24px)' }}
          >
            {/* Header */}
            <div className="flex items-center gap-3 p-4 border-b border-slate-700/60 bg-slate-800/80">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center text-sm">
                🤖
              </div>
              <div className="flex-1">
                <p className="font-display font-semibold text-white text-sm">AI Career Advisor</p>
                <p className="text-emerald-400 text-xs flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
                  Online — Ready to help
                </p>
              </div>
              <div className="flex items-center gap-1">
                {messages.length > 0 && (
                  <button
                    onClick={clearChat}
                    className="text-slate-500 hover:text-rose-400 transition-colors text-xs px-2 py-1 rounded-lg hover:bg-slate-700/60"
                    title="Clear chat"
                  >
                    🗑️
                  </button>
                )}
                <button
                  onClick={() => setOpen(false)}
                  className="text-slate-500 hover:text-white transition-colors px-2"
                >
                  ─
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.length === 0 && (
                <div className="space-y-4">
                  <div className="flex gap-2.5">
                    <div className="w-7 h-7 rounded-lg bg-sky-500/20 flex items-center justify-center text-xs shrink-0 mt-0.5">
                      🤖
                    </div>
                    <div className="bg-slate-700/60 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-slate-200 max-w-[85%]">
                      <RenderMessage text={"Hey! 👋 I'm your **AI Career Advisor**. I can help with:\n\n• **Skill recommendations** — what to learn next\n• **Resume & cover letter** tips\n• **Interview preparation** strategies\n• **Match score** improvement\n• **Company targeting** advice\n\nWhat would you like help with?"} />
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 pl-9">
                    {STARTERS.map((s) => (
                      <button
                        key={s}
                        onClick={() => send(s)}
                        className="text-xs bg-slate-700/60 hover:bg-slate-600/60 border border-slate-600/50 
                                   text-slate-300 hover:text-white rounded-xl px-3 py-1.5 transition-all"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="w-7 h-7 rounded-lg bg-sky-500/20 flex items-center justify-center text-xs shrink-0 mt-0.5">
                      🤖
                    </div>
                  )}
                  <div
                    className={`px-4 py-3 rounded-2xl text-sm max-w-[85%] leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-sky-500/20 text-sky-100 rounded-tr-sm ml-auto'
                        : 'bg-slate-700/60 text-slate-200 rounded-tl-sm'
                    }`}
                  >
                    {msg.role === 'assistant' ? (
                      <RenderMessage text={msg.content} />
                    ) : (
                      msg.content
                    )}
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {loading && (
                <div className="flex gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-sky-500/20 flex items-center justify-center text-xs shrink-0">
                    🤖
                  </div>
                  <div className="bg-slate-700/60 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="p-3 border-t border-slate-700/60 flex gap-2">
              <input
                type="text"
                placeholder="Ask me anything about your career…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                className="flex-1 bg-slate-700/60 border border-slate-600/50 rounded-xl px-3 py-2.5
                           text-sm text-slate-100 placeholder-slate-500 focus:outline-none
                           focus:ring-2 focus:ring-sky-500/50 focus:border-sky-500"
                disabled={loading}
              />
              <button
                onClick={() => send()}
                disabled={!input.trim() || loading}
                className="w-10 h-10 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-40
                           flex items-center justify-center transition-all active:scale-95"
              >
                ↑
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
