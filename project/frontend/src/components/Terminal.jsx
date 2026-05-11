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
  Search,
  ListChecks,
  ShieldCheck,
  BookMarked,
  Database,
  HelpCircle,
  Check,
  Zap,
} from 'lucide-react'
import AssignmentCanvas from './AssignmentCanvas'
import MarkdownBody from './MarkdownBody'

const PIPELINE_COMMANDS = new Set(['research', 'plan', 'critique', 'summarize', 'memory', 'help'])

const SLASH_COMMANDS = [
  { cmd: '/research',  label: 'Research a topic in depth',            Icon: Search },
  { cmd: '/plan',      label: 'Break a task into a structured plan',  Icon: ListChecks },
  { cmd: '/critique',  label: 'Review and improve a piece of writing', Icon: ShieldCheck },
  { cmd: '/summarize', label: 'Summarise a topic or document',        Icon: BookMarked },
  { cmd: '/memory',    label: 'Search your past answers',             Icon: Database },
  { cmd: '/help',      label: 'List available skills',                Icon: HelpCircle },
]

function transcriptForApi(messages) {
  const out = []
  for (const msg of messages) {
    if (msg.role === 'user' && msg.type === 'text' && typeof msg.text === 'string') {
      out.push({ role: 'user', content: msg.text })
    } else if (msg.role === 'assistant' && msg.type === 'answer' && typeof msg.text === 'string') {
      out.push({ role: 'assistant', content: msg.text })
    }
  }
  return out
}

function isCommand(text) {
  if (!text.startsWith('/')) return false
  const cmd = text.slice(1).split(/\s/)[0].toLowerCase()
  return PIPELINE_COMMANDS.has(cmd)
}

async function consumeFetchSSE(response, onData) {
  const reader = response.body?.getReader()
  if (!reader) { onData({ type: 'error', message: 'No response body' }); return }
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (value) buffer += decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')
      let sep
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        for (const line of block.split('\n')) {
          if (line.startsWith('data:')) {
            const payload = line.slice(5).trimStart()
            if (!payload) continue
            try { onData(JSON.parse(payload)) } catch { /* skip malformed */ }
          }
        }
      }
      if (done) break
    }
  } catch (err) {
    onData({ type: 'error', message: err?.message || 'Stream read error' })
  }
}

// ── Terminal component ────────────────────────────────────────────────────────
// App.jsx owns session selection, localStorage, and MongoDB sync.
// Terminal is purely the chat UI + submit logic.

export default function Terminal({ sessionId, messages, setMessages, loadInputRef, onEvent, onComplete }) {
  const [input,       setInput]       = useState('')
  const [loading,     setLoading]     = useState(false)
  const [histIdx,     setHistIdx]     = useState(-1)
  const [cmdHistory,  setCmdHistory]  = useState([])
  const [attachment,  setAttachment]  = useState(null)
  const [canvas,      setCanvas]      = useState(null)
  const [slashFilter, setSlashFilter] = useState(null)
  const [slashIdx,    setSlashIdx]    = useState(0)
  const [editingIdx,  setEditingIdx]  = useState(null)
  const [editText,    setEditText]    = useState('')

  const bottomRef = useRef(null)
  const inputRef  = useRef(null)
  const fileRef   = useRef(null)

  // Expose "load text into input" to App for sidebar edit-resend
  useEffect(() => {
    if (loadInputRef) {
      loadInputRef.current = (text) => {
        setInput(text)
        setTimeout(() => inputRef.current?.focus(), 50)
      }
    }
  }, [loadInputRef])

  // Auto-scroll to bottom when messages change
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const addMessage = (msg) => setMessages(prev => [...prev, msg])

  // ── Slash autocomplete ─────────────────────────────────────────────────────

  const filteredSlash = slashFilter !== null
    ? SLASH_COMMANDS.filter(c => c.cmd.startsWith('/' + slashFilter))
    : []

  function handleInputChange(e) {
    const val = e.target.value
    setInput(val)
    if (val.startsWith('/') && !val.includes(' ')) {
      setSlashFilter(val.slice(1).toLowerCase())
      setSlashIdx(0)
    } else {
      setSlashFilter(null)
    }
  }

  function pickSlashCommand(cmd) {
    setInput(cmd + ' ')
    setSlashFilter(null)
    inputRef.current?.focus()
  }

  // ── File upload ────────────────────────────────────────────────────────────

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
            name: data.filename, length: data.length,
          }]
        }
        return prev
      })
    } catch {
      addMessage({ role: 'assistant', type: 'error', text: 'Upload request failed.' })
    }
  }

  // ── Inline message edit (saves in-place, does NOT resend) ─────────────────

  function startEditMessage(idx) {
    setEditingIdx(idx)
    setEditText(messages[idx]?.text || '')
  }

  function saveEditMessage() {
    if (editingIdx == null) return
    setMessages(prev => prev.map((m, i) =>
      i === editingIdx ? { ...m, text: editText } : m
    ))
    setEditingIdx(null)
    setEditText('')
  }

  function cancelEdit() {
    setEditingIdx(null)
    setEditText('')
  }

  // ── Submit ─────────────────────────────────────────────────────────────────

  const submit = async (cmd) => {
    const raw = cmd.trim()
    if (!raw || loading) return

    setSlashFilter(null)
    setCmdHistory(prev => [raw, ...prev].slice(0, 50))
    setHistIdx(-1)

    let question = raw
    if (attachment) {
      question = `${raw}\n\n[Attached document: ${attachment.name}]\n${attachment.text.slice(0, 4000)}`
    }

    const usePipeline    = isCommand(raw)
    // Include full conversation history for multi-turn memory
    const priorTranscript = usePipeline ? [] : transcriptForApi(messages)
    const apiMessages     = usePipeline ? [] : [...priorTranscript, { role: 'user', content: question }]

    addMessage({ role: 'user', type: 'text', text: raw, hasAttachment: !!attachment })
    setInput('')
    setAttachment(null)
    setLoading(true)
    onEvent({ type: 'session_start', question })

    let finalAnswer = ''
    let skill       = usePipeline ? raw.slice(1).split(/\s/)[0].toLowerCase() : 'chat'
    let gotDone     = false

    const handleStreamEvent = (event) => {
      try {
        onEvent(event)
        if (event.type === 'session_start') skill = event.skill || skill

        // Backend auto-detected pipeline intent — show a routing notice bubble
        if (event.type === 'route_detected') {
          addMessage({
            role : 'assistant',
            type : 'route-notice',
            skill: event.skill,
            text : `Auto-routing to **/${event.skill}** agents based on your request…`,
          })
          return
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
          setLoading(false)
          gotDone = true
        }

        if (event.type === 'done') {
          gotDone = true
          const isAssignment = !!event.is_assignment
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last?.type === 'answer') {
              return [...prev.slice(0, -1), {
                ...last,
                score     : event.quality_score,
                duration  : event.duration_s,
                isAssignment,
              }]
            }
            return prev
          })
          setLoading(false)
          onComplete({ question: raw, answer: finalAnswer, skill, score: event.quality_score, ts: Date.now() })
        }
      } catch { /* ignore malformed events */ }
    }

    const onStreamError = () => {
      if (!gotDone) {
        addMessage({ role: 'assistant', type: 'error', text: 'Connection error. Is the backend running on port 9000?' })
      }
      setLoading(false)
    }

    // Pipeline commands use EventSource (GET /stream)
    if (usePipeline) {
      const es = new EventSource(`/stream?input=${encodeURIComponent(question)}`)
      es.onmessage = (e) => {
        try {
          handleStreamEvent(JSON.parse(e.data))
          if (gotDone) es.close()
        } catch {
          onStreamError()
          es.close()
        }
      }
      es.onerror = () => { onStreamError(); es.close() }
      return
    }

    // General chat uses fetch + SSE parser (POST /chat)
    try {
      const res = await fetch('/chat', {
        method : 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body   : JSON.stringify({ messages: apiMessages }),
      })
      if (!res.ok) {
        addMessage({ role: 'assistant', type: 'error', text: `Chat request failed (${res.status}).` })
        setLoading(false)
        return
      }
      await consumeFetchSSE(res, handleStreamEvent)
    } catch {
      onStreamError()
    } finally {
      if (!gotDone) setLoading(false)
    }
  }

  // ── Keyboard handling ──────────────────────────────────────────────────────

  const handleKey = (e) => {
    if (slashFilter !== null && filteredSlash.length > 0) {
      if (e.key === 'ArrowDown')  { e.preventDefault(); setSlashIdx(i => (i + 1) % filteredSlash.length); return }
      if (e.key === 'ArrowUp')    { e.preventDefault(); setSlashIdx(i => (i - 1 + filteredSlash.length) % filteredSlash.length); return }
      if (e.key === 'Tab' || e.key === 'Enter') {
        if (filteredSlash[slashIdx]) { e.preventDefault(); pickSlashCommand(filteredSlash[slashIdx].cmd); return }
      }
      if (e.key === 'Escape') { e.preventDefault(); setSlashFilter(null); return }
    }

    if (e.key === 'Enter' && !e.shiftKey && !loading) { submit(input); return }
    if (e.key === 'ArrowUp' && slashFilter === null) {
      const idx = Math.min(histIdx + 1, cmdHistory.length - 1)
      setHistIdx(idx); setInput(cmdHistory[idx] ?? ''); e.preventDefault()
    }
    if (e.key === 'ArrowDown' && slashFilter === null) {
      const idx = Math.max(histIdx - 1, -1)
      setHistIdx(idx); setInput(idx === -1 ? '' : cmdHistory[idx] ?? ''); e.preventDefault()
    }
  }

  const hintPlaceholder = loading
    ? 'Processing…'
    : 'Ask me anything… or type / for commands'

  // ── Render ─────────────────────────────────────────────────────────────────

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
        {messages.length === 0 && (
          <div className="chat-welcome">
            <BookOpen size={32} className="welcome-icon" />
            <p className="welcome-heading">Start a new conversation</p>
            <p className="welcome-sub">
              Ask anything, or type <code>/</code> to use an agent command like{' '}
              <code>/research</code>, <code>/plan</code>, <code>/critique</code>.
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            msg={msg}
            msgIdx={i}
            editingIdx={editingIdx}
            editText={editText}
            onEditText={setEditText}
            onStartEdit={startEditMessage}
            onSaveEdit={saveEditMessage}
            onCancelEdit={cancelEdit}
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
        {/* Slash command popup */}
        {slashFilter !== null && filteredSlash.length > 0 && (
          <div className="slash-popup">
            {filteredSlash.map((item, i) => (
              <button
                key={item.cmd}
                className={`slash-popup-item ${i === slashIdx ? 'slash-popup-item-active' : ''}`}
                onMouseDown={(e) => { e.preventDefault(); pickSlashCommand(item.cmd) }}
              >
                <item.Icon size={15} className="slash-popup-icon" />
                <span className="slash-popup-cmd">{item.cmd}</span>
                <span className="slash-popup-label">{item.label}</span>
              </button>
            ))}
          </div>
        )}

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
            onChange={handleInputChange}
            onKeyDown={handleKey}
            onBlur={() => setTimeout(() => setSlashFilter(null), 150)}
            placeholder={hintPlaceholder}
            disabled={loading}
            autoFocus
            spellCheck={false}
          />
          <button
            className="send-btn"
            onClick={() => submit(input)}
            disabled={loading || !input.trim()}
          >
            {loading ? <RefreshCw size={17} className="spin" /> : <Send size={17} />}
          </button>
        </div>
        <div className="input-hint">
          General chat or type <code>/</code> for agent commands
        </div>
      </div>

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

function MessageBubble({ msg, msgIdx, editingIdx, editText, onEditText, onStartEdit, onSaveEdit, onCancelEdit, onOpenCanvas }) {
  const isEditing = editingIdx === msgIdx

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
          {isEditing ? (
            <div className="msg-edit-wrapper">
              <textarea
                className="msg-edit-input"
                value={editText}
                onChange={e => onEditText(e.target.value)}
                autoFocus
                rows={3}
              />
              <div className="msg-edit-actions">
                <button className="msg-edit-btn msg-edit-save" onClick={onSaveEdit}>
                  <Check size={13} style={{ marginRight: 4 }} />Save
                </button>
                <button className="msg-edit-btn msg-edit-cancel" onClick={onCancelEdit}>
                  <X size={13} style={{ marginRight: 4 }} />Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="msg-bubble user-bubble msg-bubble-editable" onClick={() => onStartEdit(msgIdx)}>
                {msg.text}
                <PenLine size={11} className="bubble-edit-hint" />
              </div>
              {msg.hasAttachment && (
                <div className="msg-attachment-note">
                  <FileText size={11} style={{ marginRight: 4 }} />
                  Document attached
                </div>
              )}
            </>
          )}
        </div>
        <div className="msg-avatar user-avatar"><User size={18} /></div>
      </div>
    )
  }

  if (msg.type === 'route-notice') {
    return (
      <div className="msg msg-assistant">
        <div className="msg-avatar assistant-avatar route-avatar"><Zap size={15} /></div>
        <div className="msg-content">
          <div className="msg-bubble route-notice-bubble">
            <Zap size={12} style={{ marginRight: 6, color: 'var(--gold)', flexShrink: 0 }} />
            <span>
              Assignment intent detected — routing to{' '}
              <strong style={{ color: 'var(--gold)' }}>/{msg.skill}</strong> agents
            </span>
          </div>
        </div>
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
    // Show "Edit in Canvas" for pipeline answers OR any response longer than ~300 chars
    const isLong = (msg.text || '').length > 300
    const showMeta = msg.score != null || msg.isAssignment || isLong

    return (
      <div className="msg msg-assistant">
        <div className="msg-avatar assistant-avatar"><MessageSquareText size={18} /></div>
        <div className="msg-content">
          <div className="msg-bubble assistant-bubble answer-bubble">
            <MarkdownBody>{msg.text}</MarkdownBody>
            {showMeta && (
              <div className="answer-meta">
                {msg.score != null && (
                  <span className={`score-badge ${msg.score >= 7 ? 'score-good' : 'score-warn'}`}>
                    Score {msg.score}/10
                  </span>
                )}
                {msg.duration != null && <span className="duration-badge">{msg.duration}s</span>}
                {(msg.isAssignment || isLong) && (
                  <button className="canvas-open-btn" onClick={() => onOpenCanvas(msg.text, msg.skill, msg.score)}>
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
