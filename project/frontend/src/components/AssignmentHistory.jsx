import { useState } from 'react'
import MarkdownBody from './MarkdownBody'
import {
  MessageSquarePlus, Trash2, Edit3, Check, X,
  MessageSquare, Clock, ChevronDown, ChevronRight,
  User, MessageSquareText, RotateCcw, History,
} from 'lucide-react'

// ── helpers ───────────────────────────────────────────────────────────────────

function timeAgo(ts) {
  const diff = Date.now() - ts
  const m    = Math.floor(diff / 60000)
  if (m < 1)   return 'just now'
  if (m < 60)  return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24)  return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7)   return `${d}d ago`
  return new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

// ── SessionCard ───────────────────────────────────────────────────────────────

function SessionCard({ session, isActive, onSwitch, onDelete, onRename }) {
  const [editing,        setEditing]        = useState(false)
  const [editTitle,      setEditTitle]      = useState(session.title)
  const [confirmDelete,  setConfirmDelete]  = useState(false)

  function saveRename() {
    if (editTitle.trim()) onRename(session.id, editTitle.trim())
    setEditing(false)
  }

  return (
    <div
      className={`session-card ${isActive ? 'session-card-active' : ''}`}
      onClick={() => !editing && onSwitch(session.id)}
    >
      {/* Title row */}
      <div className="session-card-title-row">
        {editing ? (
          <input
            className="session-rename-input"
            value={editTitle}
            onChange={e => setEditTitle(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter')  saveRename()
              if (e.key === 'Escape') setEditing(false)
            }}
            onClick={e => e.stopPropagation()}
            autoFocus
          />
        ) : (
          <span className="session-card-title" title={session.title}>
            {session.title}
          </span>
        )}

        <div className="session-card-actions" onClick={e => e.stopPropagation()}>
          {editing ? (
            <>
              <button className="sess-icon-btn" onClick={saveRename} title="Save">
                <Check size={11} />
              </button>
              <button className="sess-icon-btn" onClick={() => setEditing(false)} title="Cancel">
                <X size={11} />
              </button>
            </>
          ) : (
            <>
              <button
                className="sess-icon-btn"
                onClick={() => { setEditTitle(session.title); setEditing(true) }}
                title="Rename"
              >
                <Edit3 size={11} />
              </button>
              {confirmDelete ? (
                <>
                  <button
                    className="sess-icon-btn sess-icon-danger"
                    onClick={() => onDelete(session.id)}
                    title="Confirm delete"
                  >
                    <Trash2 size={11} />
                  </button>
                  <button className="sess-icon-btn" onClick={() => setConfirmDelete(false)}>
                    <X size={11} />
                  </button>
                </>
              ) : (
                <button
                  className="sess-icon-btn sess-icon-danger"
                  onClick={() => setConfirmDelete(true)}
                  title="Delete session"
                >
                  <Trash2 size={11} />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Preview + time */}
      {!editing && (
        <div className="session-card-meta">
          {session.preview
            ? <span className="session-preview">{session.preview.slice(0, 60)}{session.preview.length > 60 ? '…' : ''}</span>
            : <span className="session-preview session-preview-empty">No messages yet</span>
          }
          <span className="session-time">
            <Clock size={9} style={{ marginRight: 3, flexShrink: 0 }} />
            {timeAgo(session.updatedAt || session.createdAt)}
          </span>
        </div>
      )}
    </div>
  )
}

// ── MessageCard (mini view of individual messages in active session) ───────────

function MessageCard({ msg, idx, onDelete, onEdit }) {
  const isUser          = msg.role === 'user'
  const [expanded,      setExpanded]     = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const preview = (msg.text || '').slice(0, 70) + ((msg.text || '').length > 70 ? '…' : '')

  return (
    <div className={`sidebar-msg-card ${isUser ? 'sidebar-msg-user' : 'sidebar-msg-assistant'}`}>
      <div className="sidebar-msg-header">
        <div className="sidebar-msg-role">
          {isUser
            ? <User size={11} className="sidebar-role-icon sidebar-role-user" />
            : <MessageSquareText size={11} className="sidebar-role-icon sidebar-role-ai" />
          }
          <span>{isUser ? 'You' : 'AI'}</span>
          {msg.skill && msg.skill !== 'chat' && (
            <span className="sidebar-skill-tag">/{msg.skill}</span>
          )}
        </div>
        <div className="sidebar-msg-actions">
          {isUser && (
            <button className="sidebar-icon-btn" onClick={() => onEdit(idx, msg.text)} title="Edit & resend">
              <Edit3 size={11} />
            </button>
          )}
          {confirmDelete ? (
            <>
              <button className="sidebar-icon-btn sidebar-icon-danger" onClick={() => { onDelete(idx); setConfirmDelete(false) }}>
                <Trash2 size={11} />
              </button>
              <button className="sidebar-icon-btn" onClick={() => setConfirmDelete(false)}><X size={11} /></button>
            </>
          ) : (
            <button className="sidebar-icon-btn sidebar-icon-danger" onClick={() => setConfirmDelete(true)} title="Delete">
              <Trash2 size={11} />
            </button>
          )}
          <button className="sidebar-icon-btn" onClick={() => setExpanded(v => !v)}>
            {expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </button>
        </div>
      </div>

      {expanded ? (
        <div className="sidebar-msg-body expanded">
          {isUser
            ? <p className="sidebar-msg-text">{msg.text}</p>
            : <MarkdownBody>{msg.text}</MarkdownBody>
          }
        </div>
      ) : (
        <div className="sidebar-msg-body preview" onClick={() => setExpanded(true)}>
          {preview || <span className="sidebar-msg-empty">(empty)</span>}
        </div>
      )}
    </div>
  )
}

// ── AssignmentHistory (main export) ──────────────────────────────────────────

export default function AssignmentHistory({
  sessions,
  activeSessionId,
  messages,
  onCreateSession,
  onSwitchSession,
  onDeleteSession,
  onRenameSession,
  onDeleteMessage,
  onEditMessage,
  onClearChat,
}) {
  // "view" toggles between session list and current session's message history
  const [view,         setView]         = useState('sessions') // 'sessions' | 'messages'
  const [confirmClear, setConfirmClear] = useState(false)

  const hasVisibleMessages = messages.some(m =>
    (m.role === 'user' && m.type === 'text') ||
    (m.role === 'assistant' && m.type === 'answer')
  )

  const activeSession = sessions.find(s => s.id === activeSessionId)

  return (
    <div className="history-panel">
      {/* ── Panel header ── */}
      <div className="history-panel-header">
        <div className="panel-title" style={{ padding: '14px 12px 10px', margin: 0, flex: 1 }}>
          <History size={13} className="panel-title-icon" />
          Sessions
        </div>
        <button
          className="new-chat-btn"
          onClick={onCreateSession}
          title="New Chat"
        >
          <MessageSquarePlus size={14} />
          <span>New</span>
        </button>
      </div>

      {/* ── Sub-navigation ── */}
      <div className="history-subnav">
        <button
          className={`history-subnav-tab ${view === 'sessions' ? 'active' : ''}`}
          onClick={() => setView('sessions')}
        >
          <MessageSquare size={12} style={{ marginRight: 4 }} />
          All Sessions
        </button>
        <button
          className={`history-subnav-tab ${view === 'messages' ? 'active' : ''}`}
          onClick={() => setView('messages')}
        >
          <History size={12} style={{ marginRight: 4 }} />
          This Chat
        </button>
      </div>

      {/* ── Sessions list ── */}
      {view === 'sessions' && (
        <div className="history-list">
          {sessions.length === 0 ? (
            <div className="history-empty">
              <MessageSquare size={28} className="empty-icon" />
              <div>No sessions yet</div>
              <div className="history-hint">Click "New" to start a chat</div>
            </div>
          ) : (
            sessions.map(session => (
              <SessionCard
                key={session.id}
                session={session}
                isActive={session.id === activeSessionId}
                onSwitch={onSwitchSession}
                onDelete={onDeleteSession}
                onRename={onRenameSession}
              />
            ))
          )}
        </div>
      )}

      {/* ── Current session messages ── */}
      {view === 'messages' && (
        <>
          {/* Clear button */}
          {hasVisibleMessages && (
            <div className="history-msg-controls">
              <span className="history-msg-session-label">
                {activeSession?.title?.slice(0, 28) || 'Current session'}
              </span>
              {confirmClear ? (
                <div style={{ display: 'flex', gap: 4 }}>
                  <button
                    className="history-action-btn history-action-danger"
                    onClick={() => { onClearChat(); setConfirmClear(false) }}
                  >
                    <Trash2 size={10} /> Yes, clear
                  </button>
                  <button className="history-action-btn" onClick={() => setConfirmClear(false)}>
                    <X size={10} />
                  </button>
                </div>
              ) : (
                <button
                  className="history-action-btn history-action-danger"
                  onClick={() => setConfirmClear(true)}
                  title="Clear all messages"
                >
                  <RotateCcw size={10} /> Clear
                </button>
              )}
            </div>
          )}

          <div className="history-list">
            {!hasVisibleMessages ? (
              <div className="history-empty">
                <MessageSquare size={28} className="empty-icon" />
                <div>No messages yet</div>
                <div className="history-hint">Start chatting to see history here</div>
              </div>
            ) : (
              messages.map((msg, i) => {
                if ((msg.role === 'user' && msg.type === 'text') ||
                    (msg.role === 'assistant' && msg.type === 'answer')) {
                  return (
                    <MessageCard
                      key={i}
                      msg={msg}
                      idx={i}
                      onDelete={onDeleteMessage}
                      onEdit={onEditMessage}
                    />
                  )
                }
                return null
              })
            )}
          </div>
        </>
      )}
    </div>
  )
}
