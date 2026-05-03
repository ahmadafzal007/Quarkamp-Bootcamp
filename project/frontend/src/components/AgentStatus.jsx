const AGENTS = ['Memory', 'Orchestrator', 'Planner', 'Researcher', 'Writer', 'Critic']

const AGENT_DESCRIPTIONS = {
  Memory      : 'Retrieves & saves context',
  Orchestrator: 'Routes to the right skill',
  Planner     : 'Breaks task into subtasks',
  Researcher  : 'Gathers information',
  Writer      : 'Drafts the answer',
  Critic      : 'Reviews & scores',
}

const AGENT_ICONS = {
  Memory      : '🗄',
  Orchestrator: '🔀',
  Planner     : '📋',
  Researcher  : '🔍',
  Writer      : '✍',
  Critic      : '⚖',
}

function StatusBadge({ status }) {
  const map = {
    idle   : { label: 'idle',    cls: 'badge-idle'    },
    running: { label: '● running', cls: 'badge-running' },
    done   : { label: '✓ done',  cls: 'badge-done'    },
  }
  const { label, cls } = map[status] || map.idle
  return <span className={`badge ${cls}`}>{label}</span>
}

export default function AgentStatus({ agents, events, stats }) {
  const recentEvents = events.slice(-6)

  return (
    <div className="agent-status">
      <div className="panel-title">Agents</div>

      <div className="agent-list">
        {AGENTS.map(name => {
          const status = agents[name] || 'idle'
          return (
            <div key={name} className={`agent-row ${status === 'running' ? 'agent-active' : ''}`}>
              <span className="agent-icon">{AGENT_ICONS[name]}</span>
              <div className="agent-info">
                <span className="agent-name">{name}</span>
                <span className="agent-desc">{AGENT_DESCRIPTIONS[name]}</span>
              </div>
              <StatusBadge status={status} />
            </div>
          )
        })}
      </div>

      {/* Stats */}
      {(stats.score !== null || stats.duration !== null) && (
        <div className="stats-box">
          <div className="panel-title" style={{ marginTop: '1rem' }}>Last Run</div>
          {stats.score !== null && (
            <div className="stat-row">
              <span className="stat-label">Quality</span>
              <span className={`stat-value ${stats.score >= 7 ? 'stat-good' : 'stat-warn'}`}>
                {stats.score}/10
              </span>
            </div>
          )}
          {stats.duration !== null && (
            <div className="stat-row">
              <span className="stat-label">Duration</span>
              <span className="stat-value">{stats.duration}s</span>
            </div>
          )}
        </div>
      )}

      {/* Recent log events */}
      {recentEvents.length > 0 && (
        <div className="recent-events">
          <div className="panel-title" style={{ marginTop: '1rem' }}>Activity</div>
          {recentEvents.map((e, i) => (
            <div key={i} className="event-entry">
              {e.entry?.replace(/^\[\d{2}:\d{2}:\d{2}\]\s*/, '')}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
