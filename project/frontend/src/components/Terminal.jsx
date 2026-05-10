import { useState, useRef, useEffect } from 'react'
import {
  Send,
  User,
  AlertCircle,
  Terminal as TerminalIcon,
  GraduationCap,
  MessageSquareText,
  BookOpen,
  RefreshCw,
  ScrollText,
  Paperclip,
  FileText,
  X,
  PenLine,
} from 'lucide-react'
import AssignmentCanvas from './AssignmentCanvas'
import MarkdownBody from './MarkdownBody'

const PIPELINE_COMMANDS = new Set(['research', 'plan', 'critique', 'summarize', 'memory', 'help'])
const HINTS = [
  'Ask me anything…',
  '/research <topic>',
  '/plan <task>',
  '/critique <your text>',
  '/summarize <topic>',
]

function isCommand(text) {
  if (!text.startsWith('/')) return false
  const cmd = text.slice(1).split(/\s/)[0].toLowerCase()
  return PIPELINE_COMMANDS.has(cmd)
}

export default function Terminal({ onEvent, onComplete }) {
  const [messages,    setMessages]    = useState([])
  const [input,       setInput]       = useState('')
  const [loading,     setLoading]     = useState(false)
  const [histIdx,     setHistIdx]     = useState(-1)
  const [cmdHistory,  setCmdHistory]  = useState([])
  const [attachment,  setAttachment]  = useState(null)   // { name, text }
  const [canvas,      setCanvas]      = useState(null)   // { content, skill, score }
  const bottomRef  = useRef(null)
  const inputRef   = useRef(null)
  const fileRef    = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const addMessage = (msg) => setMessages(prev => [...prev, msg])

  // ── File upload ──────────────────────────────────────────────────────────────

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''

    addMessage({ role: 'user', type: 'upload-pending', name: file.name })

    try {
      const formData = new FormData()
      formData.append('file', file)
      const res  = await fetch('/upload', { method: 'POST', body: formData })
      const data = await res.json()

      if (data.error) {
        addMessage({ role: 'assistant', type: 'error', text: `Upload failed: ${data.error}` })
        return
      }

      setAttachment({ name: data.filename, text: data.text })
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last?.type === 'upload-pending') {
          return [...prev.slice(0, -1), {
            role: 'user', type: 'upload-done',
            name: data.filename,
            length: data.length,
          }]
        }
        return prev
      })
    } catch (err) {
      addMessage({ role: 'assistant', type: 'error', text: 'Upload request failed.' })
    }
  }

  // ── Submit ───────────────────────────────────────────────────────────────────

  const submit = async (cmd) => {
    const raw = cmd.trim()
    if (!raw) return

    setCmdHistory(prev => [raw, ...prev].slice(0, 50))
    setHistIdx(-1)

    // Build the full question, optionally prepending attachment text
    let question = raw
    if (attachment) {
      question = `${raw}\n\n[Attached document: ${attachment.name}]\n${attachment.text.slice(0, 4000)}`
    }

    addMessage({ role: 'user', type: 'text', text: raw, hasAttachment: !!attachment })
    setInput('')
    setAttachment(null)
    setLoading(true)
    onEvent({ type: 'session_start', question })

    const usePipeline = isCommand(raw)
    const endpoint    = usePipeline
      ? `/stream?input=${encodeURIComponent(question)}`
      : `/chat?q=${encodeURIComponent(question)}`

    const es = new EventSource(endpoint)
    let finalAnswer = ''
    let skill       = usePipeline ? raw.slice(1).split(/\s/)[0].toLowerCase() : 'chat'
    let isAssignment = false

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        onEvent(event)

        if (event.type === 'session_start') {
          skill = event.skill || skill
        }

        if (event.type === 'agent_start') {
          // propagated to App for the flow panel
        }

        if (event.type === 'agent_log') {
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last?.type === 'log-group') {
              return [...prev.slice(0, -1), { ...last, logs: [...last.logs, event.entry] }]
            }
            return [...prev, { role: 'assistant', type: 'log-group', logs: [event.entry] }]
          })
        }

        if (event.type === 'token') {
          finalAnswer += event.content
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last?.type === 'answer') {
              return [...prev.slice(0, -1), { ...last, text: last.text + event.content }]
            }
            return [...prev, { role: 'assistant', type: 'answer', text: event.content, skill }]
          })
        }

        if (event.type === 'error') {
          addMessage({ role: 'assistant', type: 'error', text: event.message })
          es.close()
          setLoading(false)
        }

        if (event.type === 'done') {
          isAssignment = !!event.is_assignment
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last?.type === 'answer') {
              return [...prev.slice(0, -1), {
                ...last,
                score      : event.quality_score,
                duration   : event.duration_s,
                isAssignment,
              }]
            }
            return prev
          })
          es.close()
          setLoading(false)
          onComplete({
            question: raw, answer: finalAnswer, skill,
            score: event.quality_score, ts: Date.now(),
          })
        }
      } catch {}
    }

    es.onerror = () => {
      addMessage({ role: 'assistant', type: 'error', text: 'Connection error. Is the backend running on port 9000?' })
      es.close()
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !loading) { submit(input); return }
    if (e.key === 'ArrowUp') {
      const idx = Math.min(histIdx + 1, cmdHistory.length - 1)
      setHistIdx(idx); setInput(cmdHistory[idx] ?? ''); e.preventDefault()
    }
    if (e.key === 'ArrowDown') {
      const idx = Math.max(histIdx - 1, -1)
      setHistIdx(idx); setInput(idx === -1 ? '' : cmdHistory[idx] ?? ''); e.preventDefault()
    }
  }

  const hintPlaceholder = loading
    ? 'Processing…'
    : HINTS[Math.floor(Date.now() / 6000) % HINTS.length]

  return (
    <div className="chat-container" onClick={() => inputRef.current?.focus()}>

      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-left">
          <GraduationCap size={20} className="header-icon" />
          <div>
            <h1 className="chat-title">Assignment AI</h1>
            <span className="chat-subtitle">Multi-Agent Platform</span>
          </div>
        </div>
        <div className="chat-header-right">
          <span className={`status-chip ${loading ? 'status-chip-busy' : 'status-chip-ready'}`}>
            {loading ? 'Processing' : 'Ready'}
          </span>
        </div>
      </div>

      {/* Message list */}
      <div className="chat-body">
        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            msg={msg}
            onOpenCanvas={(content, skill, score) => setCanvas({ content, skill, score })}
          />
        ))}
        {loading && (
          <div className="typing-indicator">
            <ScrollText size={16} className="typing-indicator-icon" />
            <span className="typing-indicator-text">Preparing response…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Attachment chip */}
      {attachment && (
        <div className="attachment-chip">
          <FileText size={13} />
          <span>{attachment.name}</span>
          <button className="attachment-remove" onClick={() => setAttachment(null)}>
            <X size={12} />
          </button>
        </div>
      )}

      {/* Input area */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <button
            className="upload-btn"
            onClick={() => fileRef.current?.click()}
            title="Attach PDF or document"
            disabled={loading}
          >
            <Paperclip size={16} />
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.doc"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />

          <TerminalIcon size={15} className="input-icon" />
          <input
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={hintPlaceholder}
            disabled={loading}
            autoFocus
            spellCheck={false}
          />
          <button
            className="send-btn"
            onClick={() => !loading && submit(input)}
            disabled={loading || !input.trim()}
          >
            {loading ? <RefreshCw size={17} className="spin" /> : <Send size={17} />}
          </button>
        </div>
        <div className="input-hint">
          General chat or use <code>/research</code> <code>/plan</code> <code>/critique</code> <code>/summarize</code> for the full pipeline
        </div>
      </div>

      {/* Assignment canvas modal */}
      {canvas && (
        <AssignmentCanvas
          content={canvas.content}
          skill={canvas.skill}
          score={canvas.score}
          onClose={() => setCanvas(null)}
        />
      )}
    </div>
  )
}

// ── Message bubble renderer ────────────────────────────────────────────────────

function MessageBubble({ msg, onOpenCanvas }) {
  if (msg.type === 'welcome') {
    return (
      <div className="msg msg-assistant">
        <div className="msg-avatar assistant-avatar"><MessageSquareText size={18} /></div>
        <div className="msg-content">
          <div className="msg-bubble assistant-bubble welcome-bubble">
            <BookOpen size={14} className="inline-icon" />
            {msg.text}
          </div>
        </div>
      </div>
    )
  }

  if (msg.type === 'upload-pending') {
    return (
      <div className="msg msg-user">
        <div className="msg-content">
          <div className="msg-bubble user-bubble upload-bubble">
            <RefreshCw size={13} className="spin" style={{ marginRight: 6 }} />
            Uploading {msg.name}…
          </div>
        </div>
        <div className="msg-avatar user-avatar"><User size={18} /></div>
      </div>
    )
  }

  if (msg.type === 'upload-done') {
    return (
      <div className="msg msg-user">
        <div className="msg-content">
          <div className="msg-bubble user-bubble upload-bubble">
            <FileText size={13} style={{ marginRight: 6 }} />
            {msg.name} attached ({(msg.length / 1000).toFixed(1)}k chars)
          </div>
        </div>
        <div className="msg-avatar user-avatar"><User size={18} /></div>
      </div>
    )
  }

  if (msg.role === 'user') {
    return (
      <div className="msg msg-user">
        <div className="msg-content">
          <div className="msg-bubble user-bubble">{msg.text}</div>
          {msg.hasAttachment && (
            <div className="msg-attachment-note">
              <FileText size={11} style={{ marginRight: 4 }} />
              Document attached
            </div>
          )}
        </div>
        <div className="msg-avatar user-avatar"><User size={18} /></div>
      </div>
    )
  }

  if (msg.type === 'log-group') {
    return (
      <div className="msg msg-assistant">
        <div className="msg-avatar assistant-avatar"><MessageSquareText size={18} /></div>
        <div className="msg-content">
          <div className="msg-bubble log-bubble">
            {msg.logs.slice(-5).map((entry, i) => (
              <div key={i} className="log-line">{entry}</div>
            ))}
            {msg.logs.length > 5 && (
              <div className="log-more">+{msg.logs.length - 5} more events</div>
            )}
          </div>
        </div>
      </div>
    )
  }

  if (msg.type === 'answer') {
    return (
      <div className="msg msg-assistant">
        <div className="msg-avatar assistant-avatar"><MessageSquareText size={18} /></div>
        <div className="msg-content">
          <div className="msg-bubble assistant-bubble answer-bubble">
            <MarkdownBody>{msg.text}</MarkdownBody>
            {(msg.score != null || msg.isAssignment) && (
              <div className="answer-meta">
                {msg.score != null && (
                  <span className={`score-badge ${msg.score >= 7 ? 'score-good' : 'score-warn'}`}>
                    Score {msg.score}/10
                  </span>
                )}
                {msg.duration != null && (
                  <span className="duration-badge">{msg.duration}s</span>
                )}
                {msg.isAssignment && (
                  <button
                    className="canvas-open-btn"
                    onClick={() => onOpenCanvas(msg.text, msg.skill, msg.score)}
                  >
                    <PenLine size={13} style={{ marginRight: 5 }} />
                    Edit in Canvas
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  if (msg.type === 'error') {
    return (
      <div className="msg msg-assistant">
        <div className="msg-avatar assistant-avatar error-avatar"><AlertCircle size={18} /></div>
        <div className="msg-content">
          <div className="msg-bubble error-bubble">{msg.text}</div>
        </div>
      </div>
    )
  }

  return null
}
