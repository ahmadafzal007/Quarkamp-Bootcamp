import { useEffect, useState } from 'react'
import {
  Database, GitBranch, ListChecks, Search,
  PenTool, ShieldCheck, Save, Award, Clock,
  Cpu,
} from 'lucide-react'

const PIPELINE = [
  { id: 'Memory',       label: 'Memory',       Icon: Database,    color: '#22d3ee', hex: '22d3ee' },
  { id: 'Orchestrator', label: 'Orchestrator',  Icon: GitBranch,   color: '#60a5fa', hex: '60a5fa' },
  { id: 'Planner',      label: 'Planner',       Icon: ListChecks,  color: '#a78bfa', hex: 'a78bfa' },
  { id: 'Researcher',   label: 'Researcher',    Icon: Search,      color: '#fbbf24', hex: 'fbbf24' },
  { id: 'Writer',       label: 'Writer',        Icon: PenTool,     color: '#4ade80', hex: '4ade80' },
  { id: 'Critic',       label: 'Critic',        Icon: ShieldCheck, color: '#f87171', hex: 'f87171' },
  { id: 'Memory Save',  label: 'Memory Save',   Icon: Save,        color: '#22d3ee', hex: '22d3ee' },
]

// Normalise agent name from event to PIPELINE id
function resolveId(raw) {
  if (!raw) return null
  const s = raw.toLowerCase().replace(/\s/g, '')
  return PIPELINE.find(n => n.id.toLowerCase().replace(/\s/g, '') === s)?.id ?? null
}

export default function AgentFlowPanel({ agents, events, stats, isRunning }) {
  const [tick, setTick] = useState(0)

  // Tick every 600ms so the active node shimmers without React state floods
  useEffect(() => {
    if (!isRunning) return
    const id = setInterval(() => setTick(t => t + 1), 600)
    return () => clearInterval(id)
  }, [isRunning])

  const doneCount  = PIPELINE.filter(n => (agents[n.id] || 'idle') === 'done').length
  const progress   = Math.round((doneCount / PIPELINE.length) * 100)
  const activeNode = PIPELINE.find(n => (agents[n.id] || 'idle') === 'active')

  return (
    <div className="fp-root">

      {/* ── Header ────────────────────────────────────────── */}
      <div className="fp-header">
        <div className="fp-header-left">
          <Cpu size={14} className="fp-header-icon" />
          <span className="fp-header-title">
            {isRunning ? 'Pipeline Running' : 'Agent Pipeline'}
          </span>
        </div>
        {isRunning && (
          <span className="fp-header-pct">{progress}%</span>
        )}
      </div>

      {/* ── Progress bar ──────────────────────────────────── */}
      <div className="fp-progress-track">
        <div
          className="fp-progress-fill"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* ── Active agent banner (shown while running) ─────── */}
      {activeNode && (
        <div className="fp-active-banner" style={{ '--ac': activeNode.color }}>
          <div className="fp-active-ring">
            <activeNode.Icon size={16} />
          </div>
          <div className="fp-active-info">
            <span className="fp-active-label">Now running</span>
            <span className="fp-active-name">{activeNode.label}</span>
          </div>
          <div className="fp-active-dots">
            <span /><span /><span />
          </div>
        </div>
      )}

      {/* ── Pipeline nodes ────────────────────────────────── */}
      <div className="fp-nodes">
        {PIPELINE.map((node, idx) => {
          const rawStatus = agents[node.id] || 'idle'
          const isActive  = rawStatus === 'active'
          const isDone    = rawStatus === 'done'

          // Most recent log for this node
          const lastLog = events
            .filter(e => resolveId(e.agent) === node.id)
            .slice(-1)[0]?.entry?.replace(/^\[[^\]]+\]\s*/, '') || null

          const prevDone = idx === 0 || (agents[PIPELINE[idx - 1].id] || 'idle') === 'done'

          return (
            <div key={node.id} className="fp-node-row">
              {/* Vertical timeline rail */}
              <div className="fp-rail">
                <div
                  className={[
                    'fp-dot',
                    isActive ? 'fp-dot-active' : '',
                    isDone   ? 'fp-dot-done'   : '',
                  ].join(' ')}
                  style={isActive || isDone ? { '--nc': node.color } : {}}
                />
                {idx < PIPELINE.length - 1 && (
                  <div className={`fp-line ${isDone ? 'fp-line-done' : ''}`}
                    style={isDone ? { '--nc': node.color } : {}}
                  />
                )}
              </div>

              {/* Node card */}
              <div
                className={[
                  'fp-card',
                  isActive ? 'fp-card-active' : '',
                  isDone   ? 'fp-card-done'   : '',
                ].join(' ')}
                style={isActive ? { '--nc': node.color } : {}}
              >
                <div
                  className="fp-icon"
                  style={{
                    color     : isDone || isActive ? node.color : 'var(--text-dim)',
                    background: isActive ? `#${node.hex}18`
                              : isDone   ? `#${node.hex}10`
                              : 'var(--bg-input)',
                  }}
                >
                  <node.Icon size={14} />
                </div>

                <div className="fp-card-body">
                  <span className="fp-card-name"
                    style={{ color: isActive || isDone ? 'var(--text-bright)' : 'var(--text-dim)' }}
                  >
                    {node.label}
                  </span>
                  {(isActive || isDone) && lastLog && (
                    <span className="fp-card-log">{lastLog}</span>
                  )}
                </div>

                <div className="fp-status">
                  {isActive && <span className="fp-chip fp-chip-active">Active</span>}
                  {isDone   && <span className="fp-chip fp-chip-done">Done</span>}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* ── Stats ─────────────────────────────────────────── */}
      {(stats.score !== null || stats.duration !== null) && (
        <div className="fp-stats">
          <div className="fp-stats-title">
            <Award size={12} />
            Last Run
          </div>
          <div className="fp-stats-row">
            {stats.score !== null && (
              <div className="fp-stat-box">
                <span className="fp-stat-val"
                  style={{ color: stats.score >= 7 ? 'var(--green)' : 'var(--yellow)' }}
                >
                  {stats.score}/10
                </span>
                <span className="fp-stat-lbl">Quality</span>
              </div>
            )}
            {stats.duration !== null && (
              <div className="fp-stat-box">
                <span className="fp-stat-val">{stats.duration}s</span>
                <span className="fp-stat-lbl"><Clock size={9} style={{ marginRight: 2 }} />Duration</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Event log ─────────────────────────────────────── */}
      {events.length > 0 && (
        <div className="fp-log">
          <div className="fp-log-title">Event Log</div>
          <div className="fp-log-list">
            {events.slice(-6).reverse().map((e, i) => {
              const node = PIPELINE.find(n => resolveId(e.agent) === n.id)
              return (
                <div key={i} className="fp-log-row" style={node ? { '--lc': node.color } : {}}>
                  <span className="fp-log-tag" style={{ color: node?.color || 'var(--text-dim)' }}>
                    {e.agent || '?'}
                  </span>
                  <span className="fp-log-msg">
                    {(e.entry || '').replace(/^\[[^\]]+\]\s*/, '')}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
