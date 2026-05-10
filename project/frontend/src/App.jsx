import { useState, useCallback } from 'react'
import Terminal from './components/Terminal'
import AgentFlowPanel from './components/AgentFlowPanel'
import AssignmentHistory from './components/AssignmentHistory'

export default function App() {
  const [history,      setHistory]      = useState([])
  const [agentStates,  setAgentStates]  = useState({})   // { agentName: 'idle' | 'active' | 'done' }
  const [agentEvents,  setAgentEvents]  = useState([])   // { agent, entry }
  const [stats,        setStats]        = useState({ score: null, duration: null })
  const [isRunning,    setIsRunning]    = useState(false)

  const handleEvent = useCallback((event) => {
    if (event.type === 'session_start') {
      setAgentStates({})
      setAgentEvents([])
      setStats({ score: null, duration: null })
      setIsRunning(true)
    }

    // Real-time: agent node started
    if (event.type === 'agent_start') {
      const name = event.agent
      setAgentStates(prev => {
        const updated = { ...prev }
        // Mark any previously active agent as done
        Object.keys(updated).forEach(k => {
          if (updated[k] === 'active') updated[k] = 'done'
        })
        updated[name] = 'active'
        return updated
      })
    }

    // Real-time: agent node finished
    if (event.type === 'agent_log') {
      const name = event.agent
      if (name) {
        setAgentStates(prev => ({ ...prev, [name]: 'done' }))
      }
      setAgentEvents(prev => [...prev, { agent: name || '?', entry: event.entry || '', ts: Date.now() }])
    }

    if (event.type === 'done') {
      setStats({
        score   : event.quality_score ?? null,
        duration: event.duration_s    ?? null,
      })
      setAgentStates(prev => {
        const updated = {}
        Object.keys(prev).forEach(k => { updated[k] = 'done' })
        return updated
      })
      setIsRunning(false)
    }

    if (event.type === 'error') {
      setIsRunning(false)
    }
  }, [])

  const handleComplete = useCallback((entry) => {
    setHistory(prev => [entry, ...prev].slice(0, 20))
  }, [])

  return (
    <div className="app-layout">
      {/* Left — conversation history */}
      <aside className="panel panel-left">
        <AssignmentHistory history={history} />
      </aside>

      {/* Center — chat */}
      <main className="panel panel-center">
        <Terminal onEvent={handleEvent} onComplete={handleComplete} />
      </main>

      {/* Right — live agent pipeline visualization */}
      <aside className="panel panel-right">
        <AgentFlowPanel
          agents={agentStates}
          events={agentEvents}
          stats={stats}
          isRunning={isRunning}
        />
      </aside>
    </div>
  )
}
