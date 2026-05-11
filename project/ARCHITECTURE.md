# University Assignment Platform — Architecture & Documentation

This document is the authoritative map of **every major subsystem**, file responsibility, runtime flow, and integration point in the `project/` application. Pair it with the source under `backend/` and `frontend/src/` for implementation detail.

---

## 1. What This System Does

### 1.1 Product goals

- Give students a **web chat UI** where they either use **quick general chat** (single Haiku-backed answers with **multi-turn retention**) or invoke a **slash-command multi-agent pipeline** (`/research`, `/plan`, `/critique`, `/summarize`, plus `/memory` and `/help`).
- Surface **persistent episodic memory** (ChromaDB + embeddings) tied to answered assignments and retrievable before new runs.
- Teach integration patterns bootcamps care about: **SSE streaming**, **LangGraph state machines**, **tool-using LLM loops**, optional **MongoDB-backed UI transcripts**, and **Model Context Protocol (MCP)** as a parallel interface to plugins.

### 1.2 Technology stack (authoritative list)

| Layer | Technology |
| ----- | ----------- |
| API | FastAPI (`backend/main.py`) |
| Streaming | SSE via `sse-starlette` (`EventSourceResponse`), plus fetch-stream parsing for POST chat on the frontend |
| Multi-agent orchestration | LangGraph (`backend/graph.py`) |
| Primary LLMs | Anthropic Claude (Haiku fast path + critic/orchestration; Sonnet planner/researcher/writer) via `anthropic` Python SDK |
| Vector memory | ChromaDB persistent (`data/chroma/`), embeddings from `sentence-transformers` (`all-MiniLM-L6-v2` per `backend/config.py`) |
| Browser UI transcripts (optional server) | MongoDB via PyMongo (`backend/chat_store.py`) |
| MCP | Official Python MCP SDK FastMCP (`backend/mcp_server.py`), stdio + HTTP/SSE mounted on the same FastAPI app |
| Frontend | React 18 + Vite + `react-markdown` / `remark-gfm`; Lucide icons |
| Pipeline tools for the Researcher agent | Declared JSON schemas in `backend/plugins/__init__.py` (`PLUGIN_SCHEMAS`); execution via `execute_plugin()` |

---

## 2. System Context Diagram

```
                                    ┌─────────────────────────────────────────┐
                                    │  Human user (browser)                    │
                                    └─────────────────┬───────────────────────┘
                                                      │ HTTPS (dev proxy)
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ React SPA (localhost:3000)                                                   │
│  ┌───────────────────┐ ┌─────────────────────────┐ ┌───────────────────────┐ │
│  │ AssignmentHistory│ │ Terminal.jsx           │ │ AgentFlowPanel         │ │
│  │ Past completions │ │ Chat • upload • SSE/    │ │ Live pipeline viz      │ │
│  │                  │ │ fetch SSE • Markdown   │ │                        │ │
│  └───────────────────┘ └───────────┬─────────────┘ └───────────────────────┘ │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │ Proxied REST/SSE (/chat,/stream,/upload,...)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FastAPI (default port 9000) — backend/main.py                                │
│  • REST + SSE routes • A2A router • Mongo chat history • MCP SSE mount       │
└───────┬───────────────────────────────┬──────────────────────┬──────────────┘
        │                               │                      │
        ▼                               ▼                      ▼
┌───────────────┐              ┌─────────────────┐     ┌──────────────────────┐
│ Anthropic API │              │ LangGraph app   │     │ Chroma + embedder    │
│ (Claude)      │              │ graph.py        │     │ plugins/memory.py    │
└───────────────┘              └────────┬────────┘     └──────────────────────┘
                                        │
                                ┌───────▼────────┐
                                │ Plugins (DDG,  │
                                │ calc, PDF, …)  │
                                └────────────────┘

Optional: MongoDB Atlas (MONGO_URI) ← chat_store.py (PUT/GET /chat/history/…)

Parallel entry: MCP host (Cursor / Inspector) ← stdio: python -m backend.mcp_server
                                            ← SSE: http://host:9000/mcp/sse
```

---

## 3. Backend — HTTP API Catalog

All routes are defined in `backend/main.py` unless noted. The dev Vite server proxies most paths to port **9000** (see `frontend/vite.config.js`).

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/health` | Liveness; includes version, MCP pointers (`lesson_url`, `sse_relative_path`, `stdio_launch_cmd`, `self_http_base`). |
| GET | `/skills` | JSON list of slash skills from `SKILLS` in `config.py`. |
| GET | `/lesson/mcp` | **Bootcamp JSON** describing MCP concepts, stdio vs SSE usage, external OSS server ideas, and recommended lab flow. |
| GET | `/chat?q=` | Legacy **single-turn** general chat; streams SSE (same normalizer as POST). Prefer POST for history. |
| POST | `/chat` | **Multi-turn** general chat: JSON body `{ "messages": [ { "role": "user"\|"assistant", "content": "..." }, ... ] }`; streams identical SSE event types. |
| GET | `/chat/history/{session_id}` | Load persisted UI message array for a UUID browser session (`persistence`: `enabled` \| `disabled`). |
| PUT | `/chat/history/{session_id}` | Save full transcript snapshot (Mongo only when configured). |
| DELETE | `/chat/history/{session_id}` | **New** — delete session transcript from MongoDB when user removes a session. |
| GET | `/stream?input=` | Multi-agent pipeline or non-pipeline slash responses; SSE. |
| POST | `/upload` | Multipart upload; extracts PDF / DOCX / text (truncated payload in response). |
| POST | `/run` | **Blocking** JSON pipeline run for integrations (`RunRequest` / `RunResponse`). |
| *mount* | `/mcp/` | MCP over **SSE** sub-application (routes include `/mcp/sse`, `/mcp/messages` relative to mount). |

**A2A** (`backend/a2a/server.py`), prefix `/a2a`:

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/a2a/.well-known/agent.json` | Agent card (capabilities). |
| POST | `/a2a/tasks` | Submit `{ skill, question, optional callback_url }`; returns `task_id`. |
| GET | `/a2a/tasks/{task_id}` | Poll `{ status, result? }`; task store is in-memory `_tasks`. |

---

## 4. General Chat vs Assignment Pipeline

### 4.1 General chat (no LangGraph)

- **Frontend** (`frontend/src/components/Terminal.jsx`): If the message does **not** start with `/` (or `/` skill is not a pipeline keyword), builds a **Claude message list** from prior UI bubbles (`transcriptForApi`) and POSTs `{ messages }`.
- **Backend** `_normalize_messages_for_claude` (`main.py`): keeps last ~40 structured turns; merges consecutive same-role blobs; trims length; strips until first `user`.
- Streams **SSE**-shaped JSON lines (same envelope as `/stream`): `session_start`, `token`, `done`, `error`.
- **Stateful model memory** depends entirely on POST including prior turns; GET `/chat?q=` stays **single-shot**.

### 4.2 Assignment pipeline

- Slash commands **`/research`, `/plan`, `/critique`, `/summarize`** parsed by `backend/skills/router.py` → `route_skill()` → **`is_pipeline: True`** unless `/memory`, `/help`, or empty `/help`-like case.
- **Note:** Comments in `router.py` historically mentioned skipping Researcher for `/critique` and `/summarize`; the actual compiled graph (**always** Planner → Researcher → Writer → Critic → …). Treat the **executable graph** as the source of truth; the orchestrator fixes `route`, but nodes are not dynamically skipped today.
- **Non-pipeline** `/memory`: direct Chroma query via `memory_retrieve()`, formatted text returned via SSE tokens.
- Guards: **`before_skill()`** (`hooks/before_skill.py`) before executor thread; **`after_skill()`** (`hooks/after_skill.py`) after completion including optional AgentOps.

### 4.3 `/stream` implementation detail

- `route_skill()` → if not pipeline, stream canned `response` as tokens then `done`.
- Else **`run_pipeline_streaming(question, skill, queue)`** runs in **`run_in_executor`** (thread pool) while asyncio loop drains `queue.Queue` batches into SSE (~100ms sleeps between polls).
- **After** the graph returns, `main.py` **re-streams** `final_answer` in small chunks (`token` events again) plus `done` with `revision_count`, `is_assignment`, `quality_score`. The UI merges tokens into one assistant bubble — expect one logical assistant answer per run.

---

## 5. LangGraph Pipeline — Deep Dive

### 5.1 State schema (`backend/graph.py`)

`AssignmentState` (TypedDict):

| Field | Role |
| ----- | ----- |
| `question`, `skill` | User input slice / explicit slash skill |
| `route` | Orchestrator-selected route keyword |
| `memory_context` | Text snippets from episodic retrieval |
| `subtasks`, `research` | Planner output dict subtask→finding |
| `draft`, `critique`, `final_answer` | Writer/Critic artefacts |
| `quality_score`, `revision_count` | Critic grading and revision bookkeeping |
| `session_id`, `started_at`, `agent_log` | Session id plus **append-only** log list (`Annotated[..., operator.add]`) |

### 5.2 Graph topology

Directed edges:

```
START → memory_retrieve → orchestrator → planner → researcher → writer
     → critic → (conditional) → writer OR memory_save → END
```

Conditional from **critic** (`should_revise`):

- If `quality_score < MIN_SCORE` (default **7**) **and** `revision_count < MAX_REVISIONS` (default **2**), next node is **`writer`**.
- Else go to **`memory_save`** → **END**.

### 5.3 Streaming wrapper

`run_pipeline_streaming()` wraps **each** compiled node function to enqueue:

1. `{ "type": "agent_start", "agent": <DisplayName> }`
2. After node returns `{ "type": "agent_log", "agent": <DisplayName>, "entry": <last log line> }`

Display names (`_DISPLAY_NAMES`) map internal keys (`memory_save`) to labels like **`MemorySave`** which the frontend normalizes (`AgentFlowPanel.jsx` **`resolveId`**) toward fixed pipeline IDs (`Memory`, `Memory Save`, etc.).

### 5.4 Cached graph singleton

`get_graph()` compiles **`_plain_nodes`** once; both blocking `run_pipeline()` and streaming build a **fresh wrapped graph instance** around the same logical node implementations when streaming queue injection is needed.

---

## 6. Agent Modules — File-by-File Behaviour

All under `backend/agents/`.

| File | Model helper | Responsibility |
| ---- | ------------- | ---------------- |
| **orchestrator.py** | `fast_model` (Haiku) | If incoming `skill` is in `SKILLS`, use it as `route`; else classify question into **one word** (`research`|`plan`|`critique`|`summarize`). |
| **planner.py** | `balanced_model` | Produces JSON array of **3–4** subtasks; regex-parsed with safe fallbacks if LLM drift. Consumes shortened `memory_context`. |
| **researcher.py** | `balanced_model_with_tools` | For **each subtask**, up to **4** ReAct-style turns (`for _ in range(4)`), calling tools from **`PLUGIN_SCHEMAS`** only (`web_search`, `calculator`, `read_file`, `memory_retrieve`) via `execute_plugin()`. Accumulates `{ subtask → finding text }`. |
| **writer.py** | `balanced_model` | Formats consolidated research bullets + optional critique on revision rounds; increments `revision_count`. |
| **critic.py** | `fast_model` | Scores draft 1–10, produces critique text, sets **`final_answer`** to accepted draft conceptually aligned with grading (see source for parsing). |

**Models** (`backend/models/`):

| Module | Claude id constant | Roles |
| ------ | ------------------ | ------ |
| `fast.py` | `MODEL_FAST` (`claude-haiku-4-5`) | Cheap routing + critic |
| `balanced.py` | `MODEL_BALANCED` (`claude-sonnet-4-6`) | Planner, researcher (tools), writer |
| `powerful.py` | `MODEL_POWERFUL` (`claude-opus-4-7`) | Available for heavier experiments (not wired in default graph paths unless extended) |

---

## 7. Plugins & Tool Execution

Defined in **`backend/plugins/`** and **`plugins/__init__.py`**.

### 7.1 Runtime registry (`PLUGIN_REGISTRY`)

| Key | Implementing module | Behaviour summary |
| --- | -------------------- | ----------------- |
| `web_search` | `web_search.py` | DuckDuckGo **`duckduckgo_search.DDGS`** (not Brave HTTP in current code despite older docs). Requires `duckduckgo-search`. |
| `calculator` | `calculator.py` | Parsed safe evaluation for student math drills. |
| `read_file` | `pdf_reader.py` | Local path read TXT/PDF (**absolute paths** advised in schema text). |
| `run_code` | `code_runner.py` | Subprocess-bound Python snippets (registry entry exists; **not** listed in Researcher **`PLUGIN_SCHEMAS`** today). |
| `memory_store` | `memory.py` | Chroma upsert Q/A embedding (used inside **`memory_save_node`**, not generally exposed as LLM-facing tool schema). |
| `memory_retrieve` | `memory.py` | Vector query JSON string returned to callers. |

`execute_plugin(name, inputs)` resolves `PLUGIN_REGISTRY`; unknown names return deterministic error strings so the researcher loop never crashes on missing tools.

### 7.2 Episodic memory (`memory.py` + disk)

- Chroma persists on disk under **`project/data/chroma`** (see **`DATA_DIR` / `CHROMA_DIR`** in `backend/config.py`, resolved as `backend`’s parent + `/data/chroma`).
- Lazy `_init()` loads **SentenceTransformer** once (first use cost).
- `memory_retrieve` returns JSON dumps with bounded similarity display and metadata.

---

## 8. Configuration (`backend/config.py`)

Centralizes:

- Paths: **`DATA_DIR`**, **`CHROMA_DIR`** (auto-created).
- API keys / env knobs: **`ANTHROPIC_API_KEY`**, **`AGENTOPS_API_KEY`**, **`BRAVE_API_KEY`** (Brave unused by current DuckDuckGo search path unless you refactor).
- **Mongo**: `MONGO_URI`, **`MONGO_DB`** (default `assignment_ai`), **`MONGO_CHAT_COLL`** (default `chat_sessions`).
- Model ids: **`MODEL_FAST`**, **`MODEL_BALANCED`**, **`MODEL_POWERFUL`**.
- Agent limits: **`MAX_ITERATIONS`**, **`MAX_REVISIONS`**, **`MIN_SCORE`**, **`MEMORY_TOP_K`** (graph currently hardcodes **`n_results=3`** inside `memory_retrieve_node` independently — keep mentally aligned).
- **`SKILLS`**: registry surfaced to UX + router + MCP resources.
- **`PIPELINE_SKILLS`**: set of skills invoking graph (everything except ephemeral commands if extended).
- **A2A**: **`A2A_HOST`**, **`A2A_BASE_URL`**.
- **`PLATFORM_SELF_URL`**: MCP **platform_\*** demo tools call back into **`/health`** and **`/skills`**.

**.env loading:** `dotenv.load_dotenv` against **`project/.env`** resolved from `parents[2]` from `backend/config.py`.

---

## 9. Hooks & Cross-Cutting Concerns

### 9.1 `before_skill` (`hooks/before_skill.py`)

- Max question length (**2000** chars).
- Blocklist patterns for simplistic prompt-injection wording.
- Structured logging (`logger.warning` on block).

### 9.2 `after_skill` (`hooks/after_skill.py`)

- Info log summary (score, revision count, session id).
- **`AGENTOPS_API_KEY`** present → **`agentops.record(ActionEvent(...))`** best-effort (swallowed exceptions logged at debug).

---

## 10. Multi-Session Chat — Architecture & Persistence

### 10.1 Session model

Each **chat session** is an independent conversation with its own ordered message list. Users can maintain several sessions in parallel (e.g. "Physics assignment", "Essay outline", "Quick maths help") and switch between them without losing context.

| Concept | Value |
| ------- | ----- |
| Session identifier | UUID v4, generated in the browser via `crypto.randomUUID()` |
| Messages per session | Up to **500** (server-side trim); localStorage mirrors the full array |
| Memory within a session | Full transcript included in every Claude `POST /chat` call via `transcriptForApi()` |
| Memory across sessions | **Not shared** — each session is fully isolated (by design) |

### 10.2 localStorage keys

| Key | Contents |
| --- | -------- |
| `assignment-ai-sessions-v2` | JSON array of session metadata `[{ id, title, createdAt, updatedAt, preview }]` |
| `assignment-ai-active-session-v2` | UUID of the currently selected session |
| `assignment-ai-msgs-{sessionId}` | JSON array of UI message objects for that session |

**Migration:** on first load, if legacy keys `assignment-ai-chat-v1` / `assignment-ai-chat-session-v1` are present, their data is migrated into the new multi-session structure automatically.

### 10.3 Session lifecycle (`App.jsx`)

`App.jsx` is the **single source of truth** for sessions and messages. `Terminal.jsx` is a stateless UI component that only reads/writes `messages` via props.

| Action | Behaviour |
| ------ | --------- |
| `createSession()` | New UUID session, empty messages, becomes active; switches to chat panel on mobile |
| `switchSession(id)` | Loads new session's messages from localStorage; switches context |
| `deleteSession(id)` | Removes from meta + localStorage + `DELETE /chat/history/{id}` (MongoDB); switches to next session or creates a fresh one |
| `renameSession(id, title)` | Updates title in session metadata array |

### 10.4 Persistence flow (per session)

1. **On mount** — reads `assignment-ai-sessions-v2`; if empty, creates a fresh default session and loads its messages from `assignment-ai-msgs-{id}`.
2. **On every `messages` change** — writes to `assignment-ai-msgs-{id}` in localStorage immediately. Updates session metadata (title derived from first user message, preview from last AI answer, `updatedAt` timestamp).
3. **Debounced Mongo sync (500 ms)** — `PUT /chat/history/{sessionId}` pushes the current message array to MongoDB (no-op if `MONGO_URI` is not configured).
4. **On session delete** — `DELETE /chat/history/{id}` removes the Mongo document; `localStorage.removeItem()` clears the local copy.

### 10.5 Backend session endpoints

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/chat/history/{session_id}` | Load messages for a specific session UUID from MongoDB |
| PUT | `/chat/history/{session_id}` | Upsert full transcript (debounced sync from client) |
| **DELETE** | `/chat/history/{session_id}` | **New** — delete session document from MongoDB |

### 10.6 In-session multi-turn memory

The general chat path (`POST /chat`) builds a **full conversation transcript** for Claude via `transcriptForApi()` in `Terminal.jsx`:

- Filters only `role:user / type:text` and `role:assistant / type:answer` bubbles (skips log groups, upload notices, error bubbles, etc.)
- Passes them as the `messages` array in the Claude API call
- Claude therefore has full multi-turn conversational memory scoped to the current session

Switching sessions resets the context automatically — the new session's message array becomes the transcript.

### 10.7 Session UI features

| Feature | Where |
| ------- | ----- |
| **New Chat button** | Top of left sidebar (`AssignmentHistory.jsx`) |
| **Session list** | Left sidebar, ordered by `updatedAt` descending |
| **Active session highlight** | Gold left border + title color on active card |
| **Auto title** | Derived from first user message (up to 60 chars) |
| **Rename session** | Pencil icon on card → inline input |
| **Delete session** | Trash icon with two-step confirm |
| **Tab: All Sessions** | Lists all sessions; click to switch |
| **Tab: This Chat** | Shows message-level history of the active session with per-message edit/delete |
| **Inline message edit** | Click user bubble in chat → textarea; Save updates in place |
| **Edit & resend** | Edit icon in "This Chat" sidebar tab → loads text into input field |
| **Clear session** | Removes all messages from active session |

Normalization & limits enforced server-side in `chat_store.py`: trim arrays beyond 500 messages / BSON nearing 16 MB ceilings.
---

## 11. Model Context Protocol (MCP) — Integrated Server Deep-Dive

This platform ships a **fully custom, purpose-built MCP server** for the bootcamp.  
It lives in `backend/mcp_server.py` and is powered by the **FastMCP** framework from the official [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk).

> **What is MCP?**  
> Model Context Protocol is an open standard (originally by Anthropic) that lets any AI host (Cursor, Claude Desktop, MCP Inspector) discover and invoke *tools*, read *resources*, and expand *prompts* from a server — without bespoke integration code.  
> Think of it as a "USB-C port" between LLM hosts and capability providers.

---

### 11.1 Server Identity

| Property | Value |
| -------- | ----- |
| Server name | `AssignmentPlatformBootcamp` |
| SDK | `mcp >= 1.2.0` via **`mcp.server.fastmcp.FastMCP`** |
| Module | `backend/mcp_server.py` |
| Mounted path (SSE) | `/mcp/` inside FastAPI (`app.mount("/mcp", mcp.sse_app())`) |
| stdio launch | `cd project && PYTHONPATH=. python -m backend.mcp_server` |

The same Python `FastMCP` object (`mcp`) serves **both transports** — stdio for IDE integration and SSE for web/browser inspection — without duplicating any tool code.

---

### 11.2 Transport layer — how the two transports work

#### stdio transport (Cursor / Claude Desktop wiring)

```
IDE (MCP host)
    │
    │  spawns subprocess
    ▼
python -m backend.mcp_server
    │
    │  JSON-RPC 2.0 over stdin/stdout
    │  (newline-delimited, bidirectional)
    ▼
FastMCP server (this file)
    │  calls Python plugins directly (no HTTP)
    ▼
web_search, calculator, memory, …
```

1. The IDE forks the process and connects its stdin/stdout as a bidirectional pipe.
2. MCP discovery (`tools/list`, `resources/list`, `prompts/list`) happens over the same pipe.
3. When the LLM inside the IDE decides to call `web_search`, it sends a JSON-RPC `tools/call` request; the server executes the Python function and returns the result — all within the same pipe session.
4. **No network port is used** — this is entirely in-process communication via OS pipes.

Cursor config snippet (`.cursor/mcp.json` or Settings → MCP):

```json
{
  "mcpServers": {
    "assignment-bootcamp": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/path/to/project",
      "env": { "PYTHONPATH": "." }
    }
  }
}
```

#### SSE transport (MCP Inspector / browser)

```
Browser / MCP Inspector
    │
    │  GET /mcp/sse          (SSE stream — server → client)
    │  POST /mcp/messages    (HTTP POST — client → server)
    ▼
FastAPI app (port 9000)
    │  app.mount("/mcp", mcp.sse_app())
    ▼
FastMCP SSE sub-application
    │  same tool/resource/prompt registry
    ▼
web_search, calculator, memory, …
```

1. The MCP Inspector (or any SSE-capable host) opens a long-lived GET to `/mcp/sse`.
2. The server sends an initial JSON handshake (`endpoint` URL for the message channel).
3. Subsequent tool calls arrive as HTTP POSTs to `/mcp/messages`.
4. Results stream back over the SSE connection.
5. This transport is identical in **capability** to stdio — the same `mcp` object handles both.

Start the SSE server: `uvicorn backend.main:app --reload --port 9000` (SSE is auto-mounted).

---

### 11.3 MCP surfaces — Tools

Tools are the primary "action" surface.  Each Python function decorated with `@mcp.tool()` becomes callable by any MCP host.

#### Group A — Local plugin tools (direct Python calls)

| Tool name | Plugin module | What it does |
| --------- | ------------- | ------------ |
| `web_search(query, max_results=3)` | `plugins/web_search.py` | Queries **DuckDuckGo** via `duckduckgo_search.DDGS` (no API key required). Returns up to `max_results` formatted snippets. |
| `calculator(expression)` | `plugins/calculator.py` | Evaluates math expressions safely using Python `eval` with a restricted namespace (`sqrt`, `pi`, `log`, `exp`, `abs`, `pow`). |
| `read_file(path)` | `plugins/pdf_reader.py` | Reads `.txt` or `.pdf` files from the server filesystem and returns extracted text. |
| `run_code(code, language="python")` | `plugins/code_runner.py` | Executes Python code in a **sandboxed subprocess** (`tempfile` + `subprocess.run`, 10s timeout). Blocks `import os`, `subprocess`, `open()`, and `__import__` patterns. Returns stdout or stderr (capped at 2000 / 1000 chars). |
| `memory_store(question, answer, subject, score)` | `plugins/memory.py` | Embeds the Q/A pair with **`all-MiniLM-L6-v2`** and upserts into **ChromaDB** (persistent on disk at `data/chroma/`). Returns stored ID + total count. |
| `memory_search(query, n_results=3)` | `plugins/memory.py` | Encodes `query` with the same embedder, queries Chroma, returns JSON with similarity scores and content previews. |
| `memory_chunk_count()` | `plugins/memory.py` | Returns the number of Q/A chunks currently stored in the Chroma collection. |

#### Group B — HTTP façade tools (MCP wrapping REST)

These tools call back into the **running FastAPI app** over HTTP, demonstrating the pattern of using MCP as a proxy layer over existing microservices.

| Tool name | HTTP call | Pedagogical point |
| --------- | --------- | ----------------- |
| `platform_ping_health()` | `GET {PLATFORM_SELF_URL}/health` | Shows MCP can wrap any REST endpoint — even the host's own API. |
| `platform_http_get_skills()` | `GET {PLATFORM_SELF_URL}/skills` | Compares the REST skills catalogue with the MCP tool list — same capabilities, two discovery protocols side-by-side. |

Both use `httpx.get(url, timeout=8.0)` and return graceful error JSON when the FastAPI server is unreachable.

`PLATFORM_SELF_URL` defaults to `http://127.0.0.1:9000` and is configurable via `.env`.

---

### 11.4 MCP surfaces — Resources

Resources are **read-only URI-addressed documents** that MCP hosts can pull into context without invoking a tool.

| URI | Function | Contents |
| --- | -------- | -------- |
| `assignment://bootcamp/mcp-vocabulary` | `resource_mcp_vocabulary()` | Plain-text cheat sheet: Tools vs Resources vs Prompts vs Transports (60-second recap). |
| `assignment://bootcamp/pipeline-outline` | `resource_pipeline_outline()` | High-level LangGraph pipeline flow (START → memory → orchestrator → … → END) — the same steps students see in `/stream` logs. |
| `assignment://config/skills.json` | `resource_skills_json()` | Live JSON dump of `SKILLS` registry from `config.py` — helps students compare REST `/skills` output to the MCP tool list. |

Resources are fetched by the host via `resources/read` RPC; they never execute arbitrary code.

---

### 11.5 MCP surfaces — Prompts

Prompts are **parameterized message templates** that MCP hosts expand into starter chat turns.

| Prompt name | Parameters | Purpose |
| ----------- | ---------- | ------- |
| `assignment_user_prompt(topic, suggested_command="/research")` | `topic: str`, `suggested_command: str` | Generates a multi-turn starter asking the user to list 3 clarifying questions before running the pipeline — mirrors the web Terminal workflow. |
| `reflect_on_run(what_i_tried, observed_score=None)` | `what_i_tried: str`, `observed_score: int \| None` | Post-run metacognition scaffold tying student reflection to the Planner → Researcher → Writer → Critic loop and encouraging iteration. |

Prompts return `list[dict]` (`[{"role": "user", "content": "..."}]`) which the host materializes as pre-filled chat turns.

---

### 11.6 Runtime execution flow — end-to-end example

**Scenario:** Student uses Cursor with stdio MCP wired; types "What does web_search return for quantum computing?"

```
1. Cursor IDE (MCP host)
   └─ Sends JSON-RPC:  tools/call  { "name": "web_search", "arguments": { "query": "quantum computing" } }
        over stdin pipe to backend.mcp_server subprocess

2. FastMCP server (backend/mcp_server.py)
   └─ Dispatches to @mcp.tool() decorated function  web_search("quantum computing")
   └─ Calls plugins/web_search.py → duckduckgo_search.DDGS().text("quantum computing", max_results=3)
   └─ Returns 3 formatted snippets as a string

3. FastMCP serializes result → JSON-RPC response → stdout pipe

4. Cursor IDE receives result
   └─ Injects snippet text into the LLM's context window
   └─ LLM composes a grounded answer for the student
```

---

### 11.7 Memory tool — detailed internal flow

The `memory_store` / `memory_search` tools are the most complex because they involve ML inference.

```
memory_store(question, answer, subject, score)
    │
    ├─ _init() (first call only)
    │   ├─ chromadb.PersistentClient(path="data/chroma/")
    │   └─ SentenceTransformer("all-MiniLM-L6-v2")   ← ~80 MB model, lazy-loaded
    │
    ├─ text = "Q: {question}\nA: {answer}"
    ├─ embedding = embedder.encode(text)               ← 384-dim float vector
    └─ collection.upsert(ids, embeddings, documents, metadatas)
         └─ writes to SQLite + HNSWLIB files under data/chroma/

memory_search(query, n_results=3)
    │
    ├─ q_embed = embedder.encode(query)
    └─ collection.query(query_embeddings=[q_embed], n_results=3)
         ├─ HNSWLIB approximate nearest-neighbour search
         └─ Returns [(document, metadata, distance), …]
              distance is L2 → similarity = 1 - distance
```

The same `_init()` singleton is shared between MCP tool calls and the LangGraph `memory_retrieve_node` / `memory_save_node` — there is only **one Chroma collection** (`assignment_memory`) in the entire process.

---

### 11.8 Teaching companion — `GET /lesson/mcp`

The endpoint `GET /lesson/mcp` (proxied via Vite as `/lesson/mcp`) returns a self-contained JSON bootcamp guide covering:

- MCP mental model (Host / Transport / Server layers)
- Try-it-stdio and SSE steps with exact commands
- Composable OSS server ideas students can wire alongside this repo
- `GET /health` self-reference demonstrating the HTTP façade pattern

This is intentionally a read-only teaching payload — no auth, no side effects — safe to curl from a lecture hall.

---

### 11.9 Quick reference — wiring the MCP server

#### Option A — stdio in Cursor

Add to Cursor MCP settings (JSON):

```json
{
  "mcpServers": {
    "assignment-bootcamp": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/absolute/path/to/project",
      "env": { "PYTHONPATH": ".", "ANTHROPIC_API_KEY": "sk-ant-..." }
    }
  }
}
```

#### Option B — SSE via MCP Inspector

1. Start the FastAPI app: `uvicorn backend.main:app --reload --port 9000`
2. Open [MCP Inspector](https://github.com/modelcontextprotocol/inspector): `npx @modelcontextprotocol/inspector`
3. Set transport to **SSE** and URL to `http://127.0.0.1:9000/mcp/sse`
4. Click **Connect** → browse tools, resources, and prompts in the inspector UI

#### Option C — test standalone stdio

```bash
cd project
PYTHONPATH=. python -m backend.mcp_server
# the server prints a ready message; send JSON-RPC via stdin or use mcp-cli
```
## 12. Frontend — Components & Behaviour

```
frontend/src/
├── main.jsx                   # React root mount
├── App.jsx                    # Tabs / layout orchestration between panels
├── components/
│   ├── Terminal.jsx           # Primary conversational surface (+ fetch-SSE POST /chat logic)
│   ├── AgentFlowPanel.jsx     # GOLD pipeline visualization + timeline logs
│   ├── AssignmentHistory.jsx  # Left rail — multi-session sidebar: session list, new/switch/delete/rename, per-message edit/delete
│   ├── AssignmentCanvas.jsx   # Markdown editing modal for exporting polished assignment text
│   ├── MarkdownBody.jsx       # GFM rendering for assistant answers
│   └── AgentStatus.jsx        # Present **but not wired** into `App.jsx` (example / future use)
├── styles/index.css           # Full theme + responsive + mobile navigation
└── vite.config.js             # Dev proxy prefixes to FastAPI `:9000`
```

### 12.1 `App.jsx` event contract

Owns all **session state** (`sessions`, `activeSessionId`, `messages`) and passes them as props to `Terminal.jsx` and `AssignmentHistory.jsx`. Provides session CRUD handlers (`createSession`, `switchSession`, `deleteSession`, `renameSession`) and message-level handlers (`onDeleteMessage`, `onEditMessage`, `onClearChat`). Passes `loadInputRef` so the sidebar can inject text into Terminal's input field for edit-resend.

Passes **`onEvent`** + **`onComplete`** into `Terminal.jsx` for the agent flow panel.

Central **`handleEvent`** toggles **`agentStates`**, **`agentEvents`**, **`stats`**, **`isRunning`** reacting to streamed JSON event types (**`session_start`**, **`agent_start`**, **`agent_log`**, **`done`**, **`error`**).

Mobile: breakpoint detection toggles **`mobileTab`** between **history/chat/agents**.

### 12.2 `Terminal.jsx` specifics

`Terminal.jsx` is a **pure UI component** — it no longer manages session IDs or localStorage. All persistence is handled by `App.jsx`.

- **`messages` / `setMessages`** — controlled by `App.jsx`; Terminal only appends and mutates through setMessages.
- **`loadInputRef`** — callback ref from App; the sidebar calls it to inject edit text into the input field.
- **Command history (↑/↓)** in input (`cmdHistory`, max ~50 commands).
- **Attachment prepend** merges extracted text capped block into next outbound question (also included in Claude payload for POST /chat branch).
- **Pipeline path** — native **`EventSource`** on `/stream`; **general chat path** uses **`fetch` + `ReadableStream` parser** tolerant of chunked SSE frames.
- **Inline message editing** — click any user bubble to open an in-place textarea; Save updates the message text without resending.
- **`key={activeSessionId}`** on Terminal in App.jsx ensures the component fully resets (input cleared, loading reset) whenever the active session changes.

### 12.3 Styling paradigm

Centralized dark UI tokens in **`styles/index.css`**, typography scale, collapsible triple-column → bottom nav adaptive layout breakpoints.

---

## 13. Streaming Event Schema — Summary Table

Used by BOTH `/chat` streams and `/stream`:

| JSON `type` | Fields | Semantics |
| ----------- | ------ | --------- |
| `session_start` | `skill`, `question` | Session metadata; resets flow UI state on client pseudo-event injection + server echo |
| `agent_start` | `agent` | Node began (assignment mode) |
| `agent_log` | `agent`, `entry` | Node appended log excerpt |
| `token` | `content` | Partial assistant text fragment |
| `done` | `quality_score`, `duration_s`, `is_assignment`, optional **`revision_count`** | Terminalizes streaming spinner |
| `error` | `message` | User-visible failure |

Frontend merges consecutive **`token`** into one **`type: answer`** bubble for assistant role.

---

## 14. Data on Disk / External Services

| Asset | Location / service |
| ----- | ----------------- |
| Chroma embeddings | **`project/data/chroma/`** (auto-created at import/init) |
| Mongo transcripts | Atlas or self-hosted Mongo when **`MONGO_URI`** configured |
| Build output | **`frontend/dist/`** after `npm run build` |

---

## 15. Operational Runbooks

### 15.1 Backend (recommended canonical)

From **`project/`** root for consistent imports:

```bash
cd project
PYTHONPATH=. uvicorn backend.main:app --reload --port 9000
```

Older docs showed `cd backend && uvicorn main:app`; that layout still exists but **prefer** the **`backend.main`** invocation from **`project/`** so package imports mirror CI and MCP instructions.

### 15.2 Frontend dev

```bash
cd project/frontend
npm install   # once
npm run dev   # default :3000 with proxy upstream :9000
```

### 15.3 Environment variables (conceptual completeness)

Populate **`project/.env`** (never commit secrets):

| Variable | Role |
| -------- | ------ |
| `ANTHROPIC_API_KEY` | Required for Claude |
| `MONGO_URI` | Optional transcripts |
| `MONGO_DB`, `MONGO_CHAT_COLL` | Optional Mongo tweaks |
| `AGENTOPS_API_KEY` | Optional observability hooks |
| `PLATFORM_SELF_URL` | MCP demo HTTP reflex (defaults `http://127.0.0.1:9000`) |
| `A2A_BASE_URL` | Agent card public URL embedding |

Legacy **`BRAVE_API_KEY`** retained in config though **unused** unless you wire Brave again.

---

## 16. Dependencies & Packaging

See **`project/requirements.txt`** for authoritative Python pins (FastAPI, LangGraph stack, **`pymongo`**, **`mcp>=1.2.0`**, **`sentence-transformers`**, **`sse-starlette`**, etc.). Heavy ML wheels (embedding model) download on **first episodic-memory** use.

Frontend versions declared in **`frontend/package.json`**.

---

## 17. Logical Directory Tree (Current)

```
project/
├── ARCHITECTURE.md                 # ← This document
├── .env                            # Local secrets (not versioned ideally)
├── requirements.txt
├── data/
│   └── chroma/                     # Persisted embeddings
├── backend/
│   ├── __init__.py
│   ├── main.py                     # Routes, uploads, MCP mount tail
│   ├── graph.py                    # LangGraph compilation + streaming
│   ├── config.py                   # Env + tuning constants
│   ├── chat_store.py               # Mongo transcript persistence helpers
│   ├── mcp_server.py               # FastMCP pedagogical gateway
│   ├── agents/*.py                 # Nodes (orchestrator…critic)
│   ├── models/*.py                 # Anthropic thin clients
│   ├── plugins/*.py                # Capability implementations + registry glue
│   ├── skills/router.py           # Slash command parsing semantics
│   ├── hooks/                      # Lifecycle guard / observability hooks
│   └── a2a/                        # Agent-card + task lifecycle server + client helpers
├── frontend/
│   ├── vite.config.js
│   └── src/…                       # SPA tree (see §12)
```

---

## 18. Evolution / Extension Cheat Sheet

| Goal | Typical touch-points |
| ---- | -------------------- |
| New slash skill | Extend **`SKILLS`**, **`router.py`**, likely orchestrator prompting; conditionally reshape graph routing if semantics differ materially |
| New Researcher-visible tool | Add schema to **`PLUGIN_SCHEMAS`**, function to **`PLUGIN_REGISTRY`**, tighten safety review |
| New REST integration | **`main.py`**, possibly new Pydantic models + optional MCP mirror tool calling same service |
| Change revision policy | **`MIN_SCORE`**, **`MAX_REVISIONS`** (`config.py`) |
| Persist runs server-side historically | Extend beyond ephemeral **`_tasks`** in A2A or add Postgres row per `session_id` |
| Faster cold start embeddings | Warm Chroma/embedder eagerly on startup |

---

## 19. Alignment Notes — Doc vs Reality

Historical drift worth tracking:

| Claim you may still see elsewhere | Reality in this codebase (verify before teaching) |
| ---------------------------------- | ------------------------------------------- |
| `web_search` uses Brave REST | Implemented via **DuckDuckGo** (`duckduckgo-search`). **`BRAVE_API_KEY`** dormant unless you refactor. |
| `/critique` & `/summarize` skip researcher | **Graph always runs Planner → Researcher nodes** unless you refactor graph/router. Comments in **`router.py`** are outdated relative to **`graph.py`**. |

When in doubt, **run the graph** (`graph.py`), not comments.

---

### Document maintenance

When you add routes, transports, persistence, plugins, agents, UI panels, ENV vars, or MCP surfaces, extend **§3**, **§5–§18** first so future bootcamp cohorts inherit an accurate blueprint.
