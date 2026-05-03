import { useState, useCallback } from 'react'
import Terminal from './components/Terminal'
import AgentStatus from './components/AgentStatus'
import AssignmentHistory from './components/AssignmentHistory'

export default function App() {
  const [agentEvents, setAgentEvents]   = useState([])
  const [history, setHistory]           = useState([])
  const [activeAgents, setActiveAgents] = useState({})
  const [stats, setStats]               = useState({ score: null, duration: null, cost: null })

  const handleEvent = useCallback((event) => {
    if (event.type === 'session_start') {
      setAgentEvents([])
      setActiveAgents({})
      setStats({ score: null, duration: null })
    }

    if (event.type === 'agent_log') {
      // Extract agent name from log entry like "[Orchestrator] ..."
      const match = event.entry.match(/\[([^\]]+)\]/)
      if (match) {
        const name = match[1].split(' ')[0]
        setActiveAgents(prev => ({ ...prev, [name]: 'running' }))
      }
      setAgentEvents(prev => [...prev, { ...event, ts: Date.now() }])
    }

    if (event.type === 'done') {
      setStats({
        score   : event.quality_score,
        duration: event.duration_s,
      })
      setActiveAgents(prev => {
        const updated = {}
        Object.keys(prev).forEach(k => { updated[k] = 'done' })
        return updated
      })
    }
  }, [])

  const handleComplete = useCallback((entry) => {
    setHistory(prev => [entry, ...prev].slice(0, 20))
  }, [])

  return (
    <div className="app-layout">
      {/* Left panel — history */}
      <aside className="panel panel-left">
        <AssignmentHistory history={history} />
      </aside>

      {/* Center panel — terminal */}
      <main className="panel panel-center">
        <Terminal onEvent={handleEvent} onComplete={handleComplete} />
      </main>

      {/* Right panel — agent status */}
      <aside className="panel panel-right">
        <AgentStatus agents={activeAgents} events={agentEvents} stats={stats} />
      </aside>
    </div>
  )
}
