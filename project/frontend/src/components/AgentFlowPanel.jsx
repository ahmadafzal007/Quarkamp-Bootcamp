import {
  Database, GitBranch, ListChecks, Search,
  PenTool, ShieldCheck, Save, Award, Clock,
  Cpu, MessageSquareText, Zap, BookOpen,
  Info,
} from 'lucide-react'

/* Pipeline agent definitions */
const PIPELINE = [
  { id: 'Memory',       label: 'Memory',      Icon: Database,    color: '#c9a962', hex: 'c9a962' },
  { id: 'Orchestrator', label: 'Orchestrator', Icon: GitBranch,   color: '#d4af37', hex: 'd4af37' },
  { id: 'Planner',      label: 'Planner',      Icon: ListChecks,  color: '#b8972e', hex: 'b8972e' },
  { id: 'Researcher',   label: 'Researcher',   Icon: Search,      color: '#e8c547', hex: 'e8c547' },
  { id: 'Writer',       label: 'Writer',       Icon: PenTool,     color: '#a68b28', hex: 'a68b28' },
  { id: 'Critic',       label: 'Critic',       Icon: ShieldCheck, color: '#8a7530', hex: '8a7530' },
  { id: 'Memory Save',  label: 'Memory Save',  Icon: Save,        color: '#c9a962', hex: 'c9a962' },
]

const SKILL_META = {
  research : { label: 'Research',   color: '#e8c547', desc: 'Deep topic research via web + memory' },
  plan     : { label: 'Plan',       color: '#b8972e', desc: 'Structured outline & breakdown' },
  critique : { label: 'Critique',   color: '#8a7530', desc: 'Review & quality evaluation' },
  summarize: { label: 'Summarize',  color: '#c9a962', desc: 'Condense & extract key points' },
  chat     : { label: 'Chat',       color: '#737373', desc: 'Direct Claude response' },
  memory   : { label: 'Memory',     color: '#c9a962', desc: 'Vector search past answers' },
  help     : { label: 'Help',       color: '#737373', desc: 'Skill directory' },
}

function resolveId(raw) {
  if (!raw) return null
  const s = raw.toLowerCase().replace(/\s/g, '')
  return PIPELINE.find(n => n.id.toLowerCase().replace(/\s/g, '') === s)?.id ?? null
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SkillBadge({ skill, autoRouted }) {
  const meta  = SKILL_META[skill] || SKILL_META.chat
  return (
    <div className="fp-skill-badge" style={{ '--sc': meta.color }}>
      {autoRouted && (
        <span className="fp-auto-tag" title="Auto-detected from your message">
          <Zap size={9} style={{ marginRight: 2 }} />auto
        </span>
      )}
      <span className="fp-skill-name" style={{ color: meta.color }}>/{meta.label}</span>
      <span className="fp-skill-desc">{meta.desc}</span>
    </div>
  )
}

function ChatModeView({ isRunning }) {
  return (
    <div className="fp-chat-mode">
      <div className="fp-chat-icon">
        <MessageSquareText size={22} />
      </div>
      <div className="fp-chat-label">
        {isRunning ? 'Claude is responding…' : 'Chat Mode'}
      </div>
      <div className="fp-chat-sub">
        {isRunning
          ? 'Direct response — no pipeline needed'
          : 'General questions answered directly by Claude'
        }
      </div>
      {isRunning && (
        <div className="fp-chat-dots">
          <span /><span /><span />
        </div>
      )}
    </div>
  )
}

function IdleCapabilities() {
  const caps = [
    { Icon: Search,      label: '/research',  desc: 'Deep topic research' },
    { Icon: ListChecks,  label: '/plan',      desc: 'Structured outline' },
    { Icon: PenTool,     label: '/critique',  desc: 'Writing review' },
    { Icon: BookOpen,    label: '/summarize', desc: 'Key point extraction' },
    { Icon: Database,    label: '/memory',    desc: 'Past answer retrieval' },
  ]
  return (
    <div className="fp-idle">
      <div className="fp-idle-title">
        <Info size={12} style={{ marginRight: 5 }} />
        Available Agents
      </div>
      {caps.map(({ Icon, label, desc }) => (
        <div key={label} className="fp-idle-row">
          <Icon size={12} className="fp-idle-icon" />
          <span className="fp-idle-cmd">{label}</span>
          <span className="fp-idle-desc">{desc}</span>
        </div>
      ))}
      <div className="fp-idle-hint">
        Type a command or describe your task — the backend auto-detects when to route to agents.
      </div>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function AgentFlowPanel({ agents, events, stats, isRunning, currentSkill, autoRouted }) {
  const doneCount       = PIPELINE.filter(n => (agents[n.id] || 'idle') === 'done').length
  const progress        = Math.round((doneCount / PIPELINE.length) * 100)
  const activeNode      = PIPELINE.find(n => (agents[n.id] || 'idle') === 'active')
  const hasPipelineWork = Object.keys(agents).length > 0
  const isChatMode      = !hasPipelineWork                 // no pipeline agents triggered
  const skill           = currentSkill || 'chat'

  return (
    <div className="fp-root">

      {/* ── Header ─────────────────────────────────────── */}
      <div className="fp-header">
        <div className="fp-header-left">
          <Cpu size={14} className="fp-header-icon" />
          <span className="fp-header-title">
            {isRunning
              ? (isChatMode ? 'Chat Processing' : 'Pipeline Running')
              : 'Agent Pipeline'
            }
          </span>
        </div>
        {isRunning && !isChatMode && (
          <span className="fp-header-pct">{progress}%</span>
        )}
      </div>

      {/* ── Current skill badge ─────────────────────────── */}
      {(isRunning || hasPipelineWork) && (
        <SkillBadge skill={skill} autoRouted={autoRouted} />
      )}

      {/* ── Progress bar (pipeline only) ───────────────── */}
      {!isChatMode && (
        <div className="fp-progress-track">
          <div className="fp-progress-fill" style={{ width: `${progress}%` }} />
        </div>
      )}

      {/* ── Active agent banner ─────────────────────────── */}
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

      {/* ── Chat mode view ──────────────────────────────── */}
      {isChatMode && isRunning && (
        <ChatModeView isRunning={true} />
      )}

      {/* ── Pipeline nodes ──────────────────────────────── */}
      {!isChatMode && (
        <div className="fp-nodes">
          {PIPELINE.map((node, idx) => {
            const rawStatus = agents[node.id] || 'idle'
            const isActive  = rawStatus === 'active'
            const isDone    = rawStatus === 'done'

            const lastLog = events
              .filter(e => resolveId(e.agent) === node.id)
              .slice(-1)[0]?.entry?.replace(/^\[[^\]]+\]\s*/, '') || null

            return (
              <div key={node.id} className="fp-node-row">
                <div className="fp-rail">
                  <div
                    className={['fp-dot', isActive ? 'fp-dot-active' : '', isDone ? 'fp-dot-done' : ''].join(' ')}
                    style={isActive || isDone ? { '--nc': node.color } : {}}
                  />
                  {idx < PIPELINE.length - 1 && (
                    <div className={`fp-line ${isDone ? 'fp-line-done' : ''}`}
                      style={isDone ? { '--nc': node.color } : {}}
                    />
                  )}
                </div>

                <div
                  className={['fp-card', isActive ? 'fp-card-active' : '', isDone ? 'fp-card-done' : ''].join(' ')}
                  style={isActive ? { '--nc': node.color } : {}}
                >
                  <div
                    className="fp-icon"
                    style={{
                      color     : isDone || isActive ? node.color : 'var(--text-dim)',
                      background: isActive ? `#${node.hex}18` : isDone ? `#${node.hex}10` : 'var(--bg-input)',
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
      )}

      {/* ── Idle state — show capability info ──────────── */}
      {!isRunning && !hasPipelineWork && <IdleCapabilities />}

      {/* ── Stats ──────────────────────────────────────── */}
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
                  style={{ color: stats.score >= 7 ? 'var(--gold)' : 'var(--gold-muted)' }}
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

      {/* ── Event log ──────────────────────────────────── */}
      {events.length > 0 && (
        <div className="fp-log">
          <div className="fp-log-title">Event Log</div>
          <div className="fp-log-list">
            {events.slice(-8).reverse().map((e, i) => {
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
