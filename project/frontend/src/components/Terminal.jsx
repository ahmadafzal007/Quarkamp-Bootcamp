import { useState, useRef, useEffect } from 'react'

const AGENT_COLORS = {
  Orchestrator : '#61afef',
  Planner      : '#c678dd',
  Researcher   : '#e5c07b',
  Writer       : '#98c379',
  Critic       : '#e06c75',
  Memory       : '#56b6c2',
}

const SKILL_HINTS = [
  '/research <topic>',
  '/plan <task>',
  '/critique <your text>',
  '/summarize <topic>',
  '/memory <search query>',
  '/help',
]

function colorizeLogEntry(entry) {
  const match = entry.match(/^\[([^\]]+)\](.*)$/)
  if (!match) return <span className="log-default">{entry}</span>

  const [, agentPart, rest] = match
  const name  = agentPart.split(' ')[0]
  const color = AGENT_COLORS[name] || '#abb2bf'
  return (
    <>
      <span style={{ color, fontWeight: 600 }}>[{agentPart}]</span>
      <span className="log-message">{rest}</span>
    </>
  )
}

export default function Terminal({ onEvent, onComplete }) {
  const [lines, setLines]       = useState([
    { type: 'banner', text: '╔══════════════════════════════════════════════╗' },
    { type: 'banner', text: '║  University Assignment Platform  v1.0.0      ║' },
    { type: 'banner', text: '║  Powered by Claude + LangGraph + ChromaDB    ║' },
    { type: 'banner', text: '╚══════════════════════════════════════════════╝' },
    { type: 'info',   text: 'Type /help to see available skills.' },
    { type: 'info',   text: '' },
  ])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [histIdx, setHistIdx]   = useState(-1)
  const [cmdHistory, setCmdHistory] = useState([])
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const appendLine = (line) => setLines(prev => [...prev, line])

  const submit = async (cmd) => {
    if (!cmd.trim()) return

    setCmdHistory(prev => [cmd, ...prev].slice(0, 50))
    setHistIdx(-1)
    appendLine({ type: 'input', text: `> ${cmd}` })
    setInput('')
    setLoading(true)
    onEvent({ type: 'session_start', question: cmd })

    const encoded = encodeURIComponent(cmd)
    const es = new EventSource(`/stream?input=${encoded}`)
    let finalAnswer = ''
    let skill = ''
    let question = cmd

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        onEvent(event)

        if (event.type === 'session_start') {
          skill    = event.skill
          question = event.question
          appendLine({ type: 'meta', text: `  Skill: /${skill}  →  "${question.slice(0, 60)}${question.length > 60 ? '…' : ''}"` })
          appendLine({ type: 'separator' })
        }

        if (event.type === 'agent_log') {
          appendLine({ type: 'log', text: event.entry })
        }

        if (event.type === 'tool_call') {
          appendLine({ type: 'tool', text: `  [Tool] ${event.tool}(${event.query || ''})` })
        }

        if (event.type === 'token') {
          finalAnswer += event.content
          setLines(prev => {
            const last = prev[prev.length - 1]
            if (last?.type === 'answer') {
              return [...prev.slice(0, -1), { ...last, text: last.text + event.content }]
            }
            return [...prev, { type: 'answer', text: event.content }]
          })
        }

        if (event.type === 'error') {
          appendLine({ type: 'error', text: `  Error: ${event.message}` })
          es.close()
          setLoading(false)
        }

        if (event.type === 'done') {
          appendLine({ type: 'separator' })
          appendLine({
            type: 'meta',
            text: `  Score: ${event.quality_score ?? '—'}/10  |  Time: ${event.duration_s ?? '—'}s`,
          })
          appendLine({ type: 'info', text: '' })
          es.close()
          setLoading(false)
          onComplete({ question, answer: finalAnswer, skill, score: event.quality_score, ts: Date.now() })
        }
      } catch {}
    }

    es.onerror = () => {
      appendLine({ type: 'error', text: '  Connection error. Is the backend running?' })
      es.close()
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !loading) {
      submit(input)
      return
    }
    if (e.key === 'ArrowUp') {
      const idx = Math.min(histIdx + 1, cmdHistory.length - 1)
      setHistIdx(idx)
      setInput(cmdHistory[idx] ?? '')
      e.preventDefault()
    }
    if (e.key === 'ArrowDown') {
      const idx = Math.max(histIdx - 1, -1)
      setHistIdx(idx)
      setInput(idx === -1 ? '' : cmdHistory[idx] ?? '')
      e.preventDefault()
    }
  }

  return (
    <div className="terminal" onClick={() => inputRef.current?.focus()}>
      <div className="terminal-header">
        <span className="dot red" />
        <span className="dot yellow" />
        <span className="dot green" />
        <span className="terminal-title">assignment-platform — bash</span>
      </div>

      <div className="terminal-body">
        {lines.map((line, i) => {
          if (line.type === 'separator') return <div key={i} className="t-separator">{'─'.repeat(54)}</div>
          if (line.type === 'banner')    return <div key={i} className="t-banner">{line.text}</div>
          if (line.type === 'input')     return <div key={i} className="t-input">{line.text}</div>
          if (line.type === 'answer')    return <div key={i} className="t-answer">{line.text}</div>
          if (line.type === 'log')       return <div key={i} className="t-log">{colorizeLogEntry(line.text)}</div>
          if (line.type === 'tool')      return <div key={i} className="t-tool">{line.text}</div>
          if (line.type === 'error')     return <div key={i} className="t-error">{line.text}</div>
          if (line.type === 'meta')      return <div key={i} className="t-meta">{line.text}</div>
          return <div key={i} className="t-info">{line.text}</div>
        })}
        <div ref={bottomRef} />
      </div>

      <div className="terminal-input-row">
        <span className="prompt">{loading ? '⟳' : '❯'}</span>
        <input
          ref={inputRef}
          className="terminal-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder={loading ? 'Processing...' : SKILL_HINTS[Math.floor(Date.now() / 5000) % SKILL_HINTS.length]}
          disabled={loading}
          autoFocus
          spellCheck={false}
        />
      </div>
    </div>
  )
}
