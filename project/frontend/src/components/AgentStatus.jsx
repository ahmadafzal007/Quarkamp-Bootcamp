import { Database, GitBranch, ListChecks, Search, PenTool, ShieldCheck, Workflow, Clock, Award, ScrollText } from 'lucide-react'

const AGENTS = ['Memory', 'Orchestrator', 'Planner', 'Researcher', 'Writer', 'Critic']

const AGENT_META = {
  Memory      : { desc: 'Retrieves & saves context',  Icon: Database,    color: '#56b6c2' },
  Orchestrator: { desc: 'Routes to the right skill',  Icon: GitBranch,   color: '#61afef' },
  Planner     : { desc: 'Breaks task into subtasks',  Icon: ListChecks,  color: '#c678dd' },
  Researcher  : { desc: 'Gathers information',        Icon: Search,      color: '#e5c07b' },
  Writer      : { desc: 'Drafts the answer',          Icon: PenTool,     color: '#98c379' },
  Critic      : { desc: 'Reviews & scores',           Icon: ShieldCheck, color: '#e06c75' },
}

function StatusBadge({ status }) {
  const map = {
    idle   : { label: 'Idle',    cls: 'badge-idle'    },
    running: { label: 'Active',  cls: 'badge-running' },
    done   : { label: 'Done',    cls: 'badge-done'    },
  }
  const { label, cls } = map[status] || map.idle
  return <span className={`badge ${cls}`}>{label}</span>
}

export default function AgentStatus({ agents, events, stats }) {
  const recentEvents = events.slice(-6)

  return (
    <div className="agent-status">
      <div className="panel-title">
        <Workflow size={14} className="panel-title-icon" />
        Agents
      </div>

      <div className="agent-list">
        {AGENTS.map(name => {
          const status = agents[name] || 'idle'
          const { desc, Icon, color } = AGENT_META[name]
          return (
            <div key={name} className={`agent-row ${status === 'running' ? 'agent-active' : ''}`}>
              <span className="agent-icon-wrap" style={{ color }}>
                <Icon size={16} />
              </span>
              <div className="agent-info">
                <span className="agent-name">{name}</span>
                <span className="agent-desc">{desc}</span>
              </div>
              <StatusBadge status={status} />
            </div>
          )
        })}
      </div>

      {(stats.score !== null || stats.duration !== null) && (
        <div className="stats-box">
          <div className="panel-title">
            <Award size={14} className="panel-title-icon" />
            Last Run
          </div>
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
              <span className="stat-label"><Clock size={11} style={{ marginRight: 4 }} />Duration</span>
              <span className="stat-value">{stats.duration}s</span>
            </div>
          )}
        </div>
      )}

      {recentEvents.length > 0 && (
        <div className="recent-events">
          <div className="panel-title">
            <ScrollText size={14} className="panel-title-icon" />
            Event log
          </div>
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
