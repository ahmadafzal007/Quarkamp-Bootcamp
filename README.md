# Agentic AI Bootcamp

5-day hands-on lab course for university students. Each 2-hour daily session builds one layer of a production-grade multi-agent system. By Day 5, students have a running, monitored, Dockerised AI platform they can show in their portfolio.

**Instructor:** add your API key, run `verify_setup.py`, and you're ready to teach.

---

## Quick Start (for the instructor)

```bash
# 1. Clone / copy this folder to your machine
# 2. Create the .env file
cp setup/.env.example .env
#    Open .env and paste your ANTHROPIC_API_KEY

# 3. Verify everything works
conda run -n bootcamp python setup/verify_setup.py

# 4. Run the capstone project (Day 5 end-state)
cd project
cp .env.example .env          # same key as above
docker compose up --build
# → backend on http://localhost:8000
# → frontend on http://localhost:3000
```

---

## What This Is

Students build a **University Assignment Platform** — an AI system that accepts slash commands like `/research` or `/critique`, runs them through a 5-agent pipeline, and streams the reasoning process live to a terminal-style React UI.

```
Student types:   /research causes of World War 1

Platform does:
  [Memory]        Retrieves 2 similar past answers from ChromaDB
  [Orchestrator]  Routes → research pipeline
  [Planner]       Breaks into 3 subtasks
  [Researcher]    Calls web_search, reads results
  [Writer]        Drafts a structured answer
  [Critic]        Scores it 8/10 → PASS
  [Memory]        Saves to ChromaDB for next time

Browser shows:   Live streaming output, agent activity badges, history panel
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Conda | any | env named `bootcamp` already created |
| Python | 3.12 | inside `bootcamp` env |
| Node.js | 18+ | for Day 5 frontend |
| Docker | 20+ | for Day 5 deployment |
| Anthropic API key | — | required from Day 1 |
| AgentOps key | — | optional, Day 5 monitoring |

All Python packages are installed when you run:
```bash
conda run -n bootcamp pip install -r project/requirements.txt
```

---

## Repository Structure

```
Bootcamp/
│
├── setup/                        Pre-flight tools
│   ├── environment.yml           Conda env definition (recreate with conda env create)
│   ├── .env.example              API key template
│   └── verify_setup.py           Checks packages, .env, and live API call
│
├── day1/                         Single Reasoning Agent
│   ├── README.md                 2-hour schedule + key concepts
│   ├── concepts/
│   │   ├── 01_pparm_framework.py     PPARM: Perception, Planning, Action, Reflection, Memory
│   │   ├── 02_system_prompts.py      Role + Goal + Constraints + Format comparison
│   │   └── 03_chain_of_thought.py    Direct vs CoT vs Structured CoT
│   └── lab/
│       └── assignment_agent_v1.py    ← student deliverable: PPARM CLI agent
│
├── day2/                         Tool-Using ReAct Agent
│   ├── README.md
│   ├── concepts/
│   │   ├── 01_react_pattern.py       Thought → Action → Observation loop
│   │   ├── 02_function_calling.py    Claude tool_use API, schemas, tool_choice
│   │   └── 03_tool_schemas.py        Execution cycle, error handling
│   └── lab/
│       └── react_agent.py            ← student deliverable: agent + web search + calculator + PDF
│
├── day3/                         Multi-Agent System (LangGraph)
│   ├── README.md
│   ├── concepts/
│   │   ├── 01_langgraph_basics.py    StateGraph, nodes, edges
│   │   ├── 02_state_machines.py      Conditional edges, loops, routing
│   │   └── 03_agent_handoffs.py      State passing, context preservation
│   └── lab/
│       └── multi_agent_graph.py      ← student deliverable: 5-agent LangGraph pipeline
│
├── day4/                         RAG Memory + MCP + A2A
│   ├── README.md
│   ├── concepts/
│   │   ├── 01_rag_memory.py          Embed → Store → Retrieve → Inject cycle
│   │   ├── 02_vector_stores.py       ChromaDB: collections, filtering, similarity
│   │   └── 03_mcp_protocol.py        MCP vs direct tools, A2A protocol explained
│   └── lab/
│       ├── rag_agent.py              ← student deliverable: Day 3 graph + ChromaDB memory
│       └── mcp_server.py             ← student deliverable: MCP server with all plugins
│
├── day5/                         Full Stack Deployment
│   ├── README.md
│   ├── concepts/
│   │   ├── 01_fastapi_streaming.py   SSE streaming endpoint (runnable demo server)
│   │   ├── 02_docker_explained.md    Docker & Compose explained with our project
│   │   └── 03_agentops_monitoring.py AgentOps integration + metrics walkthrough
│   └── lab/                          (students wire project/ together)
│
└── project/                      Capstone — University Assignment Platform
    ├── backend/
    │   ├── main.py               FastAPI app: /run, /stream (SSE), /health, /skills
    │   ├── config.py             All constants, paths, model names
    │   ├── graph.py              LangGraph pipeline (the full state machine)
    │   ├── mcp_server.py         MCP server exposing all plugins via FastMCP
    │   │
    │   ├── agents/               One file per agent node
    │   │   ├── orchestrator.py   Routes question to the right pipeline path
    │   │   ├── planner.py        Breaks question into 3-4 research subtasks
    │   │   ├── researcher.py     Executes subtasks using plugins (ReAct loop)
    │   │   ├── writer.py         Synthesises research into a structured answer
    │   │   └── critic.py         Scores the draft; triggers revision if < 7/10
    │   │
    │   ├── skills/               Slash-command routing layer
    │   │   └── router.py         Parses /research, /plan, /critique, /summarize, /memory, /help
    │   │
    │   ├── models/               Named LLM configurations
    │   │   ├── fast.py           claude-haiku-4-5   — Orchestrator, Critic
    │   │   ├── balanced.py       claude-sonnet-4-6  — Planner, Researcher, Writer
    │   │   └── powerful.py       claude-opus-4-7    — optional /powerful flag
    │   │
    │   ├── plugins/              Tool implementations (called by Researcher + MCP server)
    │   │   ├── web_search.py     DuckDuckGo search
    │   │   ├── calculator.py     Safe Python eval (math expressions)
    │   │   ├── pdf_reader.py     .txt and .pdf file reader
    │   │   ├── code_runner.py    Sandboxed Python subprocess runner
    │   │   └── memory.py         ChromaDB read/write wrapper
    │   │
    │   ├── hooks/                Lifecycle hooks (run before/after every skill)
    │   │   ├── before_skill.py   Input validation, length check, prompt injection guard
    │   │   └── after_skill.py    Result logging, AgentOps event recording
    │   │
    │   └── a2a/                  Agent-to-Agent protocol
    │       ├── server.py         Exposes agent card + task endpoints (/a2a/...)
    │       └── client.py         Calls external A2A agents (other students' platforms)
    │
    ├── frontend/                 React terminal UI
    │   └── src/
    │       ├── App.jsx           3-panel layout (history | terminal | agent status)
    │       ├── components/
    │       │   ├── Terminal.jsx          Streaming terminal with slash-command input
    │       │   ├── AgentStatus.jsx       Live agent activity badges + last-run stats
    │       │   └── AssignmentHistory.jsx Saved past Q&As with click-to-expand modal
    │       └── styles/index.css          Dark terminal theme (One Dark)
    │
    ├── docker-compose.yml        Spins up backend + frontend + ChromaDB
    ├── Dockerfile.backend        Python 3.12 slim + pip install
    ├── Dockerfile.frontend       Node build → nginx serve
    ├── nginx.conf                SSE-safe reverse proxy config
    └── requirements.txt          All Python dependencies
```

---

## The Agent Pipeline

```
User input  →  Skills Router  →  before_skill hook
                                       ↓
                               ┌───────────────┐
                               │  Orchestrator │  classify + route
                               └───────┬───────┘
                                       ↓
                               ┌───────────────┐
                               │    Planner    │  break into subtasks
                               └───────┬───────┘
                                       ↓
                               ┌───────────────┐
                               │  Researcher   │  ReAct loop + plugins
                               └───────┬───────┘
                                       ↓
                               ┌───────────────┐
                               │    Writer     │  synthesise answer
                               └───────┬───────┘
                                       ↓
                               ┌───────────────┐
                               │    Critic     │  score (1-10)
                               └───────┬───────┘
                                       │
                          score ≥ 7 ───┼─── score < 7 (max 2 revisions)
                               ↓              ↓
                         memory_save     back to Writer
                               ↓
                         after_skill hook  →  AgentOps
                               ↓
                        SSE stream to browser
```

---

## Skills Reference

| Command | What it does | Pipeline path |
|---|---|---|
| `/research <topic>` | Research a topic in depth | Full pipeline |
| `/plan <task>` | Break a task into a structured plan | Full pipeline |
| `/critique <text>` | Review and improve a piece of writing | Full pipeline |
| `/summarize <topic>` | Summarise a topic or document | Full pipeline |
| `/memory <query>` | Search past answers in ChromaDB | Direct DB query |
| `/help` | List all skills | Immediate response |

---

## Models

| Name | Model ID | Used by | Cost |
|---|---|---|---|
| `fast` | `claude-haiku-4-5` | Orchestrator, Critic, hooks | Cheapest |
| `balanced` | `claude-sonnet-4-6` | Planner, Researcher, Writer | Default |
| `powerful` | `claude-opus-4-7` | Optional `/powerful` flag | Most capable |

---

## Plugins (Tools)

| Plugin | What it does | Needs |
|---|---|---|
| `web_search` | DuckDuckGo search (top N results) | `duckduckgo-search` |
| `calculator` | Safe eval of math expressions | built-in |
| `read_file` | Read .txt or .pdf files | `PyPDF2` |
| `run_code` | Sandboxed Python subprocess | built-in |
| `memory_store` | Save Q&A to ChromaDB | `chromadb` |
| `memory_retrieve` | Similarity search in ChromaDB | `chromadb` |

All plugins are also exposed as an **MCP server** (`project/backend/mcp_server.py`) — any external agent can call them via the MCP protocol.

---

## A2A Endpoints

The platform exposes a simplified [Google A2A protocol](https://google.github.io/A2A/) interface:

```
GET  /a2a/.well-known/agent.json   →  agent capabilities card
POST /a2a/tasks                    →  submit a task (returns task_id)
GET  /a2a/tasks/{task_id}          →  poll for result
```

Students can connect their platforms to each other — the Researcher on one machine can delegate to the Researcher on another.

---

## Running Each Day

All commands run from the `Bootcamp/` root:

```bash
# Day 1
conda run -n bootcamp python day1/concepts/01_pparm_framework.py
conda run -n bootcamp python day1/concepts/02_system_prompts.py
conda run -n bootcamp python day1/concepts/03_chain_of_thought.py
conda run -n bootcamp python day1/lab/assignment_agent_v1.py

# Day 2
conda run -n bootcamp python day2/concepts/01_react_pattern.py
conda run -n bootcamp python day2/concepts/02_function_calling.py
conda run -n bootcamp python day2/concepts/03_tool_schemas.py
conda run -n bootcamp python day2/lab/react_agent.py

# Day 3
conda run -n bootcamp python day3/concepts/01_langgraph_basics.py
conda run -n bootcamp python day3/concepts/02_state_machines.py
conda run -n bootcamp python day3/concepts/03_agent_handoffs.py
conda run -n bootcamp python day3/lab/multi_agent_graph.py

# Day 4  (two terminals)
conda run -n bootcamp python day4/lab/mcp_server.py    # terminal 1
conda run -n bootcamp python day4/lab/rag_agent.py     # terminal 2

# Day 5  (from project/)
cd project
conda run -n bootcamp uvicorn backend.main:app --reload --port 8000   # terminal 1
cd frontend && npm install && npm run dev                              # terminal 2
# OR: docker compose up --build
```

---

## Environment Variables

Copy `setup/.env.example` to `.env` at the repo root, and copy `project/.env.example` to `project/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...   # required — get from console.anthropic.com
AGENTOPS_API_KEY=              # optional — get from agentops.ai (free tier)
BRAVE_API_KEY=                 # optional — better web search (brave.com/search/api)
```

---

## Day-by-Day Learning Arc

| Day | Core concept | What students add to the project |
|---|---|---|
| 1 | PPARM, CoT, system prompts | Orchestrator agent + `/ask` endpoint |
| 2 | ReAct loop, tool use | Plugins (web_search, calculator, pdf_reader) |
| 3 | LangGraph, state machines, handoffs | Full 5-agent graph + SSE streaming |
| 4 | RAG, vector stores, MCP, A2A | ChromaDB memory + MCP server + A2A endpoints |
| 5 | FastAPI, Docker, monitoring | React UI + Docker Compose + AgentOps |

---

## Instructor Tips

- **Start each session** with a 5-min live demo of the day's end-state — students build faster when they can see the target.
- **Day 3 is the hardest.** Spend 5 extra minutes on the whiteboard drawing the state dict flowing through each node before touching code. The concept files have good diagrams in their output.
- **Day 4 MCP:** run the MCP server first, then show students the tool list it exposes — makes the "why" click before they write the code.
- **Day 5:** have your own `.env` with all keys pre-configured as a fallback in case students hit rate limits.
- **Portfolio push:** encourage students to add a personal "killer feature" on Day 5 (e.g. a Critic Agent that loops more aggressively, a PDF upload endpoint, a `/compare` skill). This differentiates their repos.
- Each `day*/README.md` has the full 2-hour schedule broken down to the minute — use it as a run sheet.
