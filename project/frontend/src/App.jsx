import { useState, useCallback, useEffect, useRef } from 'react'
import Terminal from './components/Terminal'
import AgentFlowPanel from './components/AgentFlowPanel'
import AssignmentHistory from './components/AssignmentHistory'
import { History, MessageSquare, Workflow } from 'lucide-react'

// ── Storage keys ──────────────────────────────────────────────────────────────
const SESSIONS_META_KEY   = 'assignment-ai-sessions-v2'
const ACTIVE_SESSION_KEY  = 'assignment-ai-active-session-v2'
const SESSION_MSGS_PREFIX = 'assignment-ai-msgs-'

// Old single-session keys (for one-time migration)
const OLD_MSGS_KEY     = 'assignment-ai-chat-v1'
const OLD_SESSION_KEY  = 'assignment-ai-chat-session-v1'

// ── localStorage helpers ──────────────────────────────────────────────────────

function loadSessionsMeta() {
  try {
    const raw = localStorage.getItem(SESSIONS_META_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
    // One-time migration from old single-session storage
    const oldMsgs    = localStorage.getItem(OLD_MSGS_KEY)
    const oldId      = localStorage.getItem(OLD_SESSION_KEY)
    if (oldMsgs) {
      try {
        const msgs = JSON.parse(oldMsgs)
        if (Array.isArray(msgs) && msgs.length > 0) {
          const firstUser = msgs.find(m => m.role === 'user' && m.type === 'text')
          const id        = oldId || crypto.randomUUID()
          const session   = {
            id,
            title    : firstUser?.text?.slice(0, 50) || 'Previous Chat',
            createdAt: Date.now(),
            updatedAt: Date.now(),
            preview  : '',
          }
          localStorage.setItem(`${SESSION_MSGS_PREFIX}${id}`, oldMsgs)
          localStorage.setItem(SESSIONS_META_KEY, JSON.stringify([session]))
          localStorage.setItem(ACTIVE_SESSION_KEY, id)
          return [session]
        }
      } catch { /* ignore */ }
    }
    return []
  } catch {
    return []
  }
}

function saveSessionsMeta(sessions) {
  try { localStorage.setItem(SESSIONS_META_KEY, JSON.stringify(sessions)) } catch {}
}

function loadActiveId(sessions) {
  try {
    const stored = localStorage.getItem(ACTIVE_SESSION_KEY)
    if (stored && sessions.some(s => s.id === stored)) return stored
  } catch { /* ignore */ }
  return sessions[0]?.id ?? null
}

function saveActiveId(id) {
  try { localStorage.setItem(ACTIVE_SESSION_KEY, id) } catch {}
}

function loadSessionMessages(sessionId) {
  if (!sessionId) return []
  try {
    const raw = localStorage.getItem(`${SESSION_MSGS_PREFIX}${sessionId}`)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch { return [] }
}

function saveSessionMessages(sessionId, messages) {
  if (!sessionId) return
  try { localStorage.setItem(`${SESSION_MSGS_PREFIX}${sessionId}`, JSON.stringify(messages)) } catch {}
}

function deleteSessionMessages(sessionId) {
  try { localStorage.removeItem(`${SESSION_MSGS_PREFIX}${sessionId}`) } catch {}
}

/** Derive a display title + preview from a message array */
function deriveSessionMeta(messages) {
  const firstUser = messages.find(m => m.role === 'user' && m.type === 'text')
  const lastAi    = [...messages].reverse().find(m => m.role === 'assistant' && m.type === 'answer')
  return {
    title  : firstUser?.text?.slice(0, 60) || 'New Chat',
    preview: lastAi?.text?.slice(0, 90)    || '',
  }
}

function makeNewSession() {
  return {
    id       : crypto.randomUUID(),
    title    : 'New Chat',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    preview  : '',
  }
}

// ── App component ─────────────────────────────────────────────────────────────

export default function App() {
  // ── Session state ────────────────────────────────────────────────────────
  const [sessions, setSessions] = useState(() => {
    const loaded = loadSessionsMeta()
    if (loaded.length > 0) return loaded
    const fresh = makeNewSession()
    saveSessionsMeta([fresh])
    saveActiveId(fresh.id)
    return [fresh]
  })

  const [activeSessionId, setActiveSessionId] = useState(() => {
    const loaded = loadSessionsMeta()
    return loadActiveId(loaded.length > 0 ? loaded : [])
  })

  const [messages, setMessages] = useState(() => {
    const loaded = loadSessionsMeta()
    const aid    = loadActiveId(loaded)
    return loadSessionMessages(aid)
  })

  // ── Agent flow (right panel) ──────────────────────────────────────────────
  const [agentStates,   setAgentStates]   = useState({})
  const [agentEvents,   setAgentEvents]   = useState([])
  const [stats,         setStats]         = useState({ score: null, duration: null })
  const [isRunning,     setIsRunning]     = useState(false)
  const [currentSkill,  setCurrentSkill]  = useState('chat')
  const [autoRouted,    setAutoRouted]    = useState(false)

  // ── Mobile layout ────────────────────────────────────────────────────────
  const [mobileTab, setMobileTab] = useState('chat')
  const [isMobile,  setIsMobile]  = useState(() =>
    typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches
  )

  // ── Ref so sidebar can inject text into Terminal's input ─────────────────
  const loadInputRef = useRef(null)

  // ── Persist messages whenever they change ────────────────────────────────
  const messagesRef = useRef(messages)
  messagesRef.current = messages

  useEffect(() => {
    if (!activeSessionId) return
    saveSessionMessages(activeSessionId, messages)
    // Update session metadata (title from first user msg, preview from last AI msg)
    const { title, preview } = deriveSessionMeta(messages)
    setSessions(prev => {
      const updated = prev.map(s =>
        s.id === activeSessionId
          ? { ...s, title, preview, updatedAt: Date.now() }
          : s
      )
      saveSessionsMeta(updated)
      return updated
    })
  }, [messages, activeSessionId])

  // ── Debounced MongoDB sync ───────────────────────────────────────────────
  useEffect(() => {
    if (!activeSessionId) return
    const t = setTimeout(() => {
      fetch(`/chat/history/${activeSessionId}`, {
        method : 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body   : JSON.stringify({ messages: messagesRef.current }),
      }).catch(() => {})
    }, 500)
    return () => clearTimeout(t)
  }, [messages, activeSessionId])

  // ── Mobile viewport listener ─────────────────────────────────────────────
  useEffect(() => {
    const mq       = window.matchMedia('(max-width: 768px)')
    const onChange = () => setIsMobile(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  // ── Agent event handler (feeds right panel) ──────────────────────────────
  const handleEvent = useCallback((event) => {
    if (event.type === 'session_start') {
      setAgentStates({})
      setAgentEvents([])
      setStats({ score: null, duration: null })
      setIsRunning(true)
      setCurrentSkill(event.skill || 'chat')
      setAutoRouted(event.auto_routed || false)
    }
    if (event.type === 'agent_start') {
      const name = event.agent
      setAgentStates(prev => {
        const upd = { ...prev }
        Object.keys(upd).forEach(k => { if (upd[k] === 'active') upd[k] = 'done' })
        upd[name] = 'active'
        return upd
      })
    }
    if (event.type === 'agent_log') {
      const name = event.agent
      if (name) setAgentStates(prev => ({ ...prev, [name]: 'done' }))
      setAgentEvents(prev => [...prev, { agent: name || '?', entry: event.entry || '', ts: Date.now() }])
    }
    if (event.type === 'done') {
      setStats({ score: event.quality_score ?? null, duration: event.duration_s ?? null })
      setAgentStates(prev => {
        const upd = {}
        Object.keys(prev).forEach(k => { upd[k] = 'done' })
        return upd
      })
      setIsRunning(false)
    }
    if (event.type === 'error') setIsRunning(false)
  }, [])

  const handleComplete = useCallback(() => { /* sessions auto-update via messages effect */ }, [])

  // ── Session CRUD ─────────────────────────────────────────────────────────

  const createSession = useCallback(() => {
    const session = makeNewSession()
    setSessions(prev => {
      const updated = [session, ...prev]
      saveSessionsMeta(updated)
      return updated
    })
    setActiveSessionId(session.id)
    saveActiveId(session.id)
    setMessages([])
    if (isMobile) setMobileTab('chat')
  }, [isMobile])

  const switchSession = useCallback((id) => {
    if (id === activeSessionId) return
    setActiveSessionId(id)
    saveActiveId(id)
    setMessages(loadSessionMessages(id))
    if (isMobile) setMobileTab('chat')
  }, [activeSessionId, isMobile])

  const deleteSession = useCallback((id) => {
    deleteSessionMessages(id)
    // Remove from Mongo (best-effort)
    fetch(`/chat/history/${id}`, { method: 'DELETE' }).catch(() => {})

    setSessions(prev => {
      const remaining = prev.filter(s => s.id !== id)
      saveSessionsMeta(remaining)
      // If we deleted the active session, switch to another
      if (id === activeSessionId) {
        if (remaining.length > 0) {
          const next = remaining[0]
          setActiveSessionId(next.id)
          saveActiveId(next.id)
          setMessages(loadSessionMessages(next.id))
        } else {
          // No sessions left — create a fresh one
          const fresh = makeNewSession()
          const withFresh = [fresh]
          saveSessionsMeta(withFresh)
          saveActiveId(fresh.id)
          setActiveSessionId(fresh.id)
          setMessages([])
          return withFresh
        }
      }
      return remaining
    })
  }, [activeSessionId])

  const renameSession = useCallback((id, newTitle) => {
    setSessions(prev => {
      const updated = prev.map(s => s.id === id ? { ...s, title: newTitle } : s)
      saveSessionsMeta(updated)
      return updated
    })
  }, [])

  // ── Sidebar message-level operations (for inline edit/delete) ────────────

  const handleDeleteMessage = useCallback((idx) => {
    setMessages(prev => prev.filter((_, i) => i !== idx))
  }, [])

  const handleEditMessage = useCallback((idx, text) => {
    if (loadInputRef.current) loadInputRef.current(text)
    if (isMobile) setMobileTab('chat')
  }, [isMobile])

  const handleClearChat = useCallback(() => {
    setMessages([])
  }, [])

  // ── Layout ───────────────────────────────────────────────────────────────
  const showHistory = !isMobile || mobileTab === 'history'
  const showChat    = !isMobile || mobileTab === 'chat'
  const showAgents  = !isMobile || mobileTab === 'agents'

  return (
    <div className="app-root">
      <div className="app-layout">
        {/* Left sidebar — session list */}
        <aside className={`panel panel-left ${showHistory ? 'panel-visible' : ''}`}>
          <AssignmentHistory
            sessions={sessions}
            activeSessionId={activeSessionId}
            messages={messages}
            onCreateSession={createSession}
            onSwitchSession={switchSession}
            onDeleteSession={deleteSession}
            onRenameSession={renameSession}
            onDeleteMessage={handleDeleteMessage}
            onEditMessage={handleEditMessage}
            onClearChat={handleClearChat}
          />
        </aside>

        {/* Center — chat */}
        <main className={`panel panel-center ${showChat ? 'panel-visible' : ''}`}>
          <Terminal
            key={activeSessionId}
            sessionId={activeSessionId}
            messages={messages}
            setMessages={setMessages}
            loadInputRef={loadInputRef}
            onEvent={handleEvent}
            onComplete={handleComplete}
          />
        </main>

        {/* Right — agent flow */}
        <aside className={`panel panel-right ${showAgents ? 'panel-visible' : ''}`}>
          <AgentFlowPanel
            agents={agentStates}
            events={agentEvents}
            stats={stats}
            isRunning={isRunning}
            currentSkill={currentSkill}
            autoRouted={autoRouted}
          />
        </aside>
      </div>

      {isMobile && (
        <nav className="app-mobile-nav" aria-label="Workspace sections">
          <button
            type="button"
            className={`app-mobile-nav-btn ${mobileTab === 'history' ? 'is-active' : ''}`}
            onClick={() => setMobileTab('history')}
          >
            <History size={18} strokeWidth={2} />
            <span>Sessions</span>
          </button>
          <button
            type="button"
            className={`app-mobile-nav-btn ${mobileTab === 'chat' ? 'is-active' : ''}`}
            onClick={() => setMobileTab('chat')}
          >
            <MessageSquare size={18} strokeWidth={2} />
            <span>Chat</span>
          </button>
          <button
            type="button"
            className={`app-mobile-nav-btn ${mobileTab === 'agents' ? 'is-active' : ''}`}
            onClick={() => setMobileTab('agents')}
          >
            <Workflow size={18} strokeWidth={2} />
            <span>Agents</span>
          </button>
        </nav>
      )}
    </div>
  )
}
