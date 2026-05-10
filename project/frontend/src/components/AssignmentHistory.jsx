import { useState } from 'react'
import MarkdownBody from './MarkdownBody'
import { History, Clock, X, BookOpen, FileText, MessageSquare } from 'lucide-react'

const SKILL_COLORS = {
  research : '#61afef',
  plan     : '#c678dd',
  critique : '#e06c75',
  summarize: '#e5c07b',
  memory   : '#56b6c2',
  help     : '#abb2bf',
}

const SKILL_ICONS = {
  research : BookOpen,
  plan     : FileText,
  critique : MessageSquare,
  summarize: FileText,
  memory   : History,
  help     : MessageSquare,
}

function ScorePill({ score }) {
  if (score == null) return null
  const color = score >= 8 ? '#98c379' : score >= 6 ? '#e5c07b' : '#e06c75'
  return <span className="score-pill" style={{ color }}>{score}/10</span>
}

function HistoryItem({ item, onSelect }) {
  const color = SKILL_COLORS[item.skill] || '#abb2bf'
  const Icon = SKILL_ICONS[item.skill] || MessageSquare
  const time  = new Date(item.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  return (
    <button className="history-item" onClick={() => onSelect(item)}>
      <div className="history-item-header">
        <span className="history-skill" style={{ color }}>
          <Icon size={12} style={{ marginRight: 4 }} />
          /{item.skill}
        </span>
        <span className="history-time"><Clock size={10} style={{ marginRight: 3 }} />{time}</span>
      </div>
      <div className="history-question">{item.question.slice(0, 60)}{item.question.length > 60 ? '…' : ''}</div>
      <ScorePill score={item.score} />
    </button>
  )
}

function AnswerModal({ item, onClose }) {
  if (!item) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span>/{item.skill} — {item.question.slice(0, 50)}</span>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body">
          <MarkdownBody>{item.answer}</MarkdownBody>
        </div>
      </div>
    </div>
  )
}

export default function AssignmentHistory({ history }) {
  const [selected, setSelected] = useState(null)

  return (
    <div className="history-panel">
      <div className="panel-title">
        <History size={14} className="panel-title-icon" />
        History
      </div>

      {history.length === 0 ? (
        <div className="history-empty">
          <MessageSquare size={32} className="empty-icon" />
          <div>No conversations yet</div>
          <div className="history-hint">Ask a question to get started</div>
        </div>
      ) : (
        <div className="history-list">
          {history.map((item, i) => (
            <HistoryItem key={i} item={item} onSelect={setSelected} />
          ))}
        </div>
      )}

      {selected && <AnswerModal item={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
