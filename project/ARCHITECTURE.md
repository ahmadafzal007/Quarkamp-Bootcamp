# University Assignment Platform — Architecture & Flow

## Overview

A full-stack multi-agent AI platform for university students. The system combines a
**FastAPI + LangGraph** backend with a **React** frontend and uses **Claude** (via the
Anthropic API) to power all agents.

```
┌──────────────────────────────────────────────────────────────┐
│                        React Frontend                        │
│  ┌──────────────┐  ┌─────────────────────┐  ┌────────────┐  │
│  │  History     │  │       Chat          │  │  Agent     │  │
│  │  Panel       │  │  (Terminal.jsx)     │  │  Flow      │  │
│  │              │  │                     │  │  Panel     │  │
│  │ Past runs    │  │ • Chat mode         │  │            │  │
│  │ with scores  │  │ • Pipeline mode     │  │ Live       │  │
│  │              │  │ • File upload       │  │ pipeline   │  │
│  │              │  │ • Assignment canvas │  │ status     │  │
│  └──────────────┘  └─────────────────────┘  └────────────┘  │
└────────────────────────────┬─────────────────────────────────┘
                             │ SSE / HTTP
┌────────────────────────────▼─────────────────────────────────┐
│                       FastAPI Backend (port 9000)            │
│                                                              │
│   GET /chat    →  Direct LLM (no pipeline, fast)            │
│   GET /stream  →  Full multi-agent pipeline (SSE)           │
│   POST /upload →  PDF / DOCX text extraction                 │
│   POST /run    →  Blocking pipeline run (for integrations)   │
│   GET /health  →  Health check                               │
└────────────────────────────┬─────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────┐
│                     LangGraph Pipeline                       │
│                                                              │
│  Memory Retrieve → Orchestrator → Planner → Researcher      │
│                                                     ↓        │
│          Memory Save ← Critic ←──────────── Writer          │
│          (END)            ↑                    ↑             │
│                       (REVISE if score < 7) ───┘             │
└──────────────────────────────────────────────────────────────┘
```

---

## Request Flow

### 1. General Chat (Fast Path)

```
User types a question  →  Frontend detects no "/" prefix
       ↓
GET /chat?q=<question>   (EventSource)
       ↓
FastAPI calls Claude Haiku (single LLM call, max 1024 tokens)
       ↓
Tokens streamed back via SSE  →  Frontend renders chat bubble
       ↓
done event  →  no canvas, no score  →  ready for next message
```

### 2. Assignment Pipeline (Full Multi-Agent)

```
User types /research, /plan, /critique, or /summarize
       ↓
Frontend detects "/" prefix  →  GET /stream?input=<command>
       ↓
FastAPI: route_skill() parses command  →  before_skill() guard check
       ↓
run_pipeline_streaming() launched in thread pool
  real-time events pushed to a queue.Queue
       ↓
SSE generator polls queue:
  agent_start  →  sent to frontend (flow panel highlights node)
  agent_log    →  sent to frontend (flow panel marks node done + logs)
       ↓
After pipeline completes:
  final answer streamed token-by-token
  done { is_assignment: true, quality_score, duration_s }
       ↓
Frontend:
  • Right panel shows each agent as active → done in real time
  • "Edit in Canvas" button appears on the answer bubble
  • Entry saved to history panel
```

### 3. Document Upload Flow

```
User clicks paperclip → selects PDF / DOCX / TXT
       ↓
POST /upload  (multipart/form-data)
       ↓
Backend: pdfminer.six (PDF) | python-docx (DOCX) | utf-8 decode (TXT)
Text capped at 12 000 chars
       ↓
Frontend receives { filename, text, length }
  → attachment chip shown in input area
  → on next submit, document text prepended to the question
```

---

## Agent Pipeline — Node Details

| Node | Model | Reads | Writes | Role |
|------|-------|-------|--------|------|
| **Memory Retrieve** | — (ChromaDB) | question | memory_context | Fetches top-3 semantically similar past answers |
| **Orchestrator** | Claude Haiku | question, skill | route | Classifies route (research / plan / critique / summarize) |
| **Planner** | Claude Sonnet | question, memory_context | subtasks | Generates 3-4 research subtasks as JSON array |
| **Researcher** | Claude Sonnet + tools | subtasks | research | ReAct loop (max 4 iterations) per subtask; uses web_search, calculator, pdf_reader, memory_retrieve |
| **Writer** | Claude Sonnet | question, research, critique | draft | Writes the structured academic answer |
| **Critic** | Claude Haiku | question, draft | critique, quality_score, final_answer | Scores 1-10; if score < 7 and revisions < 2 → routes back to Writer |
| **Memory Save** | — (ChromaDB) | final_answer | — | Embeds the answer for future retrieval |

### Revision Loop

```
Writer → Critic
           │
           ├─ score >= 7 OR revisions >= 2  ──→  Memory Save → END
           │
           └─ score < 7 AND revisions < 2   ──→  Writer (with critique feedback)
```

---

## Streaming Protocol (SSE Events)

All real-time communication uses Server-Sent Events. The frontend opens an
`EventSource` connection and processes these event types:

| Event | Fields | When |
|-------|--------|------|
| `session_start` | `skill`, `question` | First event on any request |
| `agent_start` | `agent` | Agent node begins executing |
| `agent_log` | `agent`, `entry` | Agent node completes (includes log text) |
| `token` | `content` | One chunk of the final streamed answer |
| `done` | `quality_score`, `duration_s`, `is_assignment` | Pipeline finished |
| `error` | `message` | Any error occurred |

---

## Frontend Component Tree

```
App.jsx
├── AssignmentHistory.jsx   (left panel — past runs)
├── Terminal.jsx            (center — chat + upload + canvas)
│   └── AssignmentCanvas.jsx  (modal — editable assignment output)
└── AgentFlowPanel.jsx      (right panel — live pipeline visualization)
```

### State flow (App.jsx → children)

```
handleEvent(event)
  session_start  →  reset agentStates, agentEvents, stats, isRunning=true
  agent_start    →  agentStates[name] = 'active'
  agent_log      →  agentStates[name] = 'done', push to agentEvents
  done           →  stats updated, isRunning=false

Props passed to AgentFlowPanel: agents, events, stats, isRunning
Props passed to Terminal:        onEvent, onComplete
```

---

## Directory Structure

```
project/
├── backend/
│   ├── main.py              # FastAPI app + all endpoints
│   ├── graph.py             # LangGraph pipeline + streaming wrapper
│   ├── config.py            # Constants, model names, skill registry
│   ├── agents/
│   │   ├── orchestrator.py  # Routing agent
│   │   ├── planner.py       # Subtask planner
│   │   ├── researcher.py    # ReAct researcher
│   │   ├── writer.py        # Academic writer
│   │   └── critic.py        # Scoring critic
│   ├── models/
│   │   ├── fast.py          # claude-haiku-4-5
│   │   ├── balanced.py      # claude-sonnet-4-6
│   │   └── powerful.py      # claude-opus-4-7
│   ├── plugins/
│   │   ├── web_search.py    # Brave Search API
│   │   ├── calculator.py    # Safe math eval
│   │   ├── pdf_reader.py    # Local PDF extraction
│   │   ├── code_runner.py   # Sandboxed Python exec
│   │   └── memory.py        # ChromaDB interface
│   ├── skills/
│   │   └── router.py        # Slash-command parser
│   ├── hooks/
│   │   ├── before_skill.py  # Input validation / guardrails
│   │   └── after_skill.py   # Logging / analytics
│   └── a2a/
│       ├── server.py        # A2A task endpoints
│       └── client.py        # A2A client
│
├── frontend/
│   └── src/
│       ├── App.jsx                  # Root: state management
│       ├── components/
│       │   ├── Terminal.jsx         # Chat UI + upload
│       │   ├── AgentFlowPanel.jsx   # Live pipeline visualization
│       │   ├── AssignmentCanvas.jsx # Editable output canvas
│       │   └── AssignmentHistory.jsx
│       └── styles/index.css
│
├── data/
│   └── chroma/              # ChromaDB vector store (auto-created)
│
└── ARCHITECTURE.md          # This file
```

---

## Running Locally

```bash
# Backend
cd project/backend
conda activate bootcamp
uvicorn main:app --reload --port 9000

# Frontend
cd project/frontend
npm run dev          # runs on http://localhost:3000
```

### Environment Variables (project/.env)

```
ANTHROPIC_API_KEY=sk-ant-...
BRAVE_API_KEY=BSA...          # optional — for web_search plugin
A2A_BASE_URL=http://localhost:9000
```

### Optional PDF/DOCX dependencies

```bash
pip install pdfminer.six   # for PDF upload extraction
pip install python-docx    # for DOCX upload extraction
```
