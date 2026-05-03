# Day 5 — Full Stack: CLI + React UI + Docker + Monitoring

**Theory link:** Module 4.3–4.4 (Web API Design) + Module 5.1–5.2 (Docker, Monitoring, Deployment)  
**Duration:** 2 hours  
**Goal:** Ship the system. Wrap the Day 4 pipeline in FastAPI, serve it to a React terminal UI, containerise with Docker, and plug in AgentOps monitoring.

---

## 2-Hour Schedule

| Time | Activity |
|------|----------|
| 0:00–0:15 | Recap Day 4 + architecture diagram |
| 0:15–0:35 | Run `concepts/01_fastapi_streaming.py` — SSE streaming |
| 0:35–0:50 | Walk through `concepts/02_docker_explained.md` |
| 0:50–1:05 | Run `concepts/03_agentops_monitoring.py` — live tracing |
| 1:05–1:45 | **Lab:** wire everything together in `project/` |
| 1:45–2:00 | `docker compose up` — demo the full product |

---

## Setup

```bash
# Install remaining packages
conda run -n bootcamp pip install agentops sse-starlette

# Start the project (from Bootcamp root)
cd project
conda run -n bootcamp uvicorn backend.main:app --reload --port 8000

# In another terminal: start the frontend
cd project/frontend
npm install && npm run dev

# Or run everything with Docker:
docker compose up --build
```

---

## Key Concepts

### SSE (Server-Sent Events)
SSE lets the server push updates to the browser without the browser polling.
Perfect for streaming agent thoughts in real time.

```
Browser               FastAPI Server
  |-- GET /stream ------->|
  |<-- data: token1 ------|  (as they arrive)
  |<-- data: token2 ------|
  |<-- data: [DONE] ------|
```

### FastAPI as the Stateless Layer
Agents do the stateful work. FastAPI just:
- Receives requests
- Passes them to the agent pipeline
- Streams results back

Keep FastAPI thin — no business logic in route handlers.

### Docker Compose Architecture
```
docker-compose.yml spins up:
  backend    → FastAPI on :8000
  frontend   → React (Vite) on :3000
  chromadb   → ChromaDB server on :8001
  (optional) → AgentOps collector
```

### AgentOps Monitoring
Every LLM call, tool call, and agent event is traced:
- Cost per session / per agent
- Error rates
- Token usage over time
- Latency per node

---

## Final Deliverable

`docker compose up` from `project/` → open `http://localhost:3000`

The full University Assignment Platform:
- Type `/research quantum entanglement` in the terminal
- Watch agents stream their thoughts live
- See past assignments in the history panel
- Monitor everything in AgentOps dashboard
