"""
FastAPI Application — University Assignment Platform
=====================================================
Routes:
  GET  /health                       health check
  GET  /skills                       list available skills
  GET  /chat                         general AI chat (SSE) — single question via ?q=
  POST /chat                         same SSE stream, JSON body `{ "messages": [...] }` for history
  GET  /chat/history/{session_id}     load persisted chat UI (MongoDB when MONGO_URI set)
  PUT  /chat/history/{session_id}     save chat UI transcript
  GET  /stream                       full multi-agent pipeline — SSE
  POST /upload                       extract text from PDF / DOCX / TXT
  POST /run                          run pipeline (blocking, returns JSON)
  GET  /a2a/.well-known/agent.json   A2A agent card
  POST /a2a/tasks                    A2A task submission
  GET  /a2a/tasks/{id}               A2A task result
  GET  /lesson/mcp                   JSON bootcamp guide: MCP concepts & lab steps
  (mount) /mcp/*                     MCP over HTTP+SSE (same FastMCP app as stdio module)

Run:
    From backend/: uvicorn main:app --reload --port 9000
    From project/: uvicorn backend.main:app --reload --port 9000
"""

import sys
from pathlib import Path

_project_dir = Path(__file__).resolve().parent.parent
if str(_project_dir) not in sys.path:
    sys.path.insert(0, str(_project_dir))

import os
import io
import re
import json
import time
import queue
import asyncio
import logging
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.config import SKILLS, ANTHROPIC_API_KEY, MODEL_FAST, PLATFORM_SELF_URL
from backend import chat_store
from backend import mcp_server as _assignment_mcp
from backend.skills.router import route_skill
from backend.graph import run_pipeline, run_pipeline_streaming
from backend.hooks import before_skill, after_skill
from backend.a2a.server import a2a_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("main")

app = FastAPI(
    title      = "University Assignment Platform",
    description= "Multi-agent AI system for university assignments",
    version    = "2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins    = ["*"],
    allow_methods    = ["*"],
    allow_headers    = ["*"],
)

app.include_router(a2a_router)


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — LLM calls will fail")
    else:
        logger.info("ANTHROPIC_API_KEY loaded OK")
    if chat_store.is_configured():
        if chat_store.ping_ok():
            logger.info("Chat history persistence: MongoDB connected")
        else:
            logger.warning("MONGO_URI set but MongoDB ping failed — chat will not persist server-side")
    else:
        logger.info("MONGO_URI not set — chat history only in the browser (localStorage)")
    logger.info(
        "MCP SSE app mounted under /mcp when import succeeds "
        "(GET /lesson/mcp for labs; stdio: python -m backend.mcp_server)"
    )
    logger.info("University Assignment Platform v2.0 started")


# ── Request / Response models ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    input: str


class RunResponse(BaseModel):
    skill        : str
    question     : str
    final_answer : str
    quality_score: int
    agent_log    : list[str]
    duration_s   : float


class ChatTurn(BaseModel):
    role   : Literal["user", "assistant"]
    content: str = Field(default="", max_length=48_000)


class ChatRequest(BaseModel):
    messages: list[ChatTurn] = Field(..., min_length=1, max_length=80)


class ChatHistoryUpsert(BaseModel):
    """Chat bubble payloads from the React client (BSON document)."""

    messages: list[dict] = Field(default_factory=list, max_length=500)


# ── Smart intent detection — routes general chat to the pipeline when needed ──

# Each tuple: (compiled regex, skill)
_INTENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Essay / assignment writing
    (re.compile(r'\b(write|draft|compose|create|generate)\b.{0,40}\b(essay|report|paper|assignment|article|thesis|dissertation|paragraph|story|letter)\b', re.I), 'plan'),
    (re.compile(r'\b(write\s+me|help\s+me\s+write|i\s+need\s+to\s+write)\b', re.I), 'plan'),
    (re.compile(r'\b(write|draft|compose)\b.{0,20}\b(about|on|regarding|for)\b', re.I), 'plan'),
    # Research in depth
    (re.compile(r'\b(research|investigate|explore)\b.{0,30}\b(topic|subject|concept|theme|area|issue)\b', re.I), 'research'),
    (re.compile(r'\b(comprehensive|in.depth|detailed|thorough)\b.{0,30}\b(analysis|overview|study|research|explanation)\b', re.I), 'research'),
    (re.compile(r'\b(explain|discuss|describe)\b.{0,30}\b(in\s+detail|thoroughly|comprehensively|in\s+depth)\b', re.I), 'research'),
    # Structured plan / outline
    (re.compile(r'\b(create|make|build|give\s+me|develop)\b.{0,30}\b(plan|outline|structure|roadmap|framework|strategy)\b', re.I), 'plan'),
    (re.compile(r'\b(plan|outline|structure|organize)\b.{0,20}\b(my|the|an?)\b.{0,20}\b(essay|paper|assignment|report|project|presentation)\b', re.I), 'plan'),
    (re.compile(r'\bhow\s+(should|do|can)\s+i\s+(structure|organize|approach|plan)\b.{0,30}\b(assignment|essay|paper|project)\b', re.I), 'plan'),
    # Critique / review
    (re.compile(r'\b(review|critique|proofread|give\s+feedback|check)\b.{0,20}\b(my|this|the)\b.{0,30}\b(essay|writing|text|assignment|draft|paper)\b', re.I), 'critique'),
    (re.compile(r'\b(improve|evaluate|assess|analyze)\b.{0,20}\b(my|this)\b.{0,20}\b(writing|essay|assignment|draft)\b', re.I), 'critique'),
    # Summarize
    (re.compile(r'\b(summarize|summarise|provide\s+(a\s+)?summary|condense|key\s+points|main\s+points|brief\s+overview)\b', re.I), 'summarize'),
    (re.compile(r'\btldr\b', re.I), 'summarize'),
]

_MIN_PIPELINE_LEN = 20  # skip routing for very short messages


def _detect_pipeline_intent(question: str) -> tuple[bool, str]:
    """
    Heuristic classifier: returns (should_use_pipeline, skill).

    Checks the user's question against assignment-related patterns without
    requiring an extra LLM call (latency-free).  The skill returned determines
    which agent chain handles the request.
    """
    q = question.strip()
    if len(q) < _MIN_PIPELINE_LEN:
        return False, 'chat'
    for pattern, skill in _INTENT_PATTERNS:
        if pattern.search(q):
            return True, skill
    return False, 'chat'


async def _stream_pipeline_events(question: str, skill: str):
    """
    Async generator: run the LangGraph pipeline for *question/skill* and yield
    SSE-JSON strings in the same envelope as the /stream endpoint.

    Used both by GET /stream and by POST /chat when auto-routing is triggered.
    """
    guard = before_skill(question, skill)
    if not guard["ok"]:
        yield json.dumps({"type": "error", "message": guard["reason"]})
        return

    event_q = queue.Queue()
    t_start  = time.time()
    loop     = asyncio.get_event_loop()

    future = loop.run_in_executor(
        None, run_pipeline_streaming, question, skill, event_q,
    )

    while not future.done() or not event_q.empty():
        drained = 0
        while drained < 20:
            try:
                ev = event_q.get_nowait()
                yield json.dumps(ev)
                drained += 1
            except queue.Empty:
                break
        if not future.done():
            await asyncio.sleep(0.1)

    result   = await future
    duration = time.time() - t_start
    after_skill(result, skill, duration)

    answer = result.get("final_answer", "")
    for i in range(0, len(answer), 8):
        yield json.dumps({"type": "token", "content": answer[i:i + 8]})
        await asyncio.sleep(0.005)

    yield json.dumps({
        "type"          : "done",
        "quality_score" : result.get("quality_score", 0),
        "duration_s"    : round(duration, 2),
        "revision_count": result.get("revision_count", 0),
        "is_assignment" : True,
    })


def _normalize_messages_for_claude(turns: list[dict]) -> list[dict]:
    """Clamp history, merge consecutive same-role turns, ensure leading user message."""
    out: list[dict] = []
    for t in turns[-40:]:
        role = t.get("role")
        content = (t.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if len(content) > 24_000:
            content = content[:24_000]
        if out and out[-1]["role"] == role:
            out[-1]["content"] = out[-1]["content"] + "\n\n" + content
        else:
            out.append({"role": role, "content": content})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def _call_claude_sync(claude_messages: list[dict]) -> str:
    """Blocking Anthropic call — must run in a thread pool, never on the event loop."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model      = MODEL_FAST,
        max_tokens = 1024,
        system     = (
            "You are a helpful AI assistant for university students. "
            "Answer clearly and concisely. "
            "Use the prior conversation when the user refers to earlier messages. "
            "You are backed by a multi-agent platform; complex assignment requests are "
            "automatically routed to specialized research, planning, writing, and critique agents."
        ),
        messages   = claude_messages,
    )
    return response.content[0].text


async def _stream_chat_events(claude_messages: list[dict]):
    """
    Shared SSE generator for general chat (POST /chat).

    If the latest user message is detected as an assignment-type request
    (write / research / plan / critique / summarize), we silently redirect to
    the full multi-agent pipeline and stream pipeline events instead.
    The frontend receives a `route_detected` event first so it can show an
    informative notice.
    """
    if not claude_messages:
        yield json.dumps({"type": "session_start", "skill": "chat", "question": ""})
        yield json.dumps({"type": "error", "message": "Please enter a question."})
        return

    # Pull the most recent user message
    last_user = ""
    for m in reversed(claude_messages):
        if m["role"] == "user":
            last_user = m["content"][:600]
            break

    # ── Intent detection ───────────────────────────────────────────────────
    should_pipeline, detected_skill = _detect_pipeline_intent(last_user)

    if should_pipeline:
        logger.info("Auto-routing to pipeline: skill=%s  question=%.80s", detected_skill, last_user)
        # Notify the frontend that we are redirecting to agents
        yield json.dumps({
            "type"       : "route_detected",
            "skill"      : detected_skill,
            "question"   : last_user,
            "auto_routed": True,
        })
        yield json.dumps({
            "type"       : "session_start",
            "skill"      : detected_skill,
            "question"   : last_user,
            "auto_routed": True,
        })
        async for ev in _stream_pipeline_events(last_user, detected_skill):
            yield ev
        return

    # ── Regular chat path ──────────────────────────────────────────────────
    yield json.dumps({"type": "session_start", "skill": "chat", "question": last_user})

    try:
        t_start = time.time()
        loop    = asyncio.get_event_loop()
        answer  = await loop.run_in_executor(None, _call_claude_sync, claude_messages)

        for i in range(0, len(answer), 8):
            yield json.dumps({"type": "token", "content": answer[i:i + 8]})
            await asyncio.sleep(0.005)

        yield json.dumps({
            "type"         : "done",
            "quality_score": 0,
            "duration_s"   : round(time.time() - t_start, 2),
            "is_assignment": False,
        })
    except Exception as exc:
        logger.error("chat error: %s", exc)
        yield json.dumps({"type": "error", "message": str(exc)})


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status" : "ok",
        "version": "2.0.0",
        "mcp"    : {
            "lesson_url"       : "/lesson/mcp",
            "stdio_launch_cmd" : "PYTHONPATH=. python -m backend.mcp_server",
            "sse_relative_path": "/mcp/sse",
            "self_http_base"   : PLATFORM_SELF_URL,
            "tool_count_notice": "nine tools expose plugins + REST bridges — see MCP host",
        },
    }


@app.get("/skills")
async def list_skills():
    return {"skills": [{"name": k, "description": v} for k, v in SKILLS.items()]}


@app.get("/lesson/mcp")
async def lesson_model_context_protocol():
    """
    Bootcamp reading — no secrets — safe to curl from the lecture hall.

    Describes Model Context Protocol, how students wire hosts, plus composable OSS servers.
    """
    base_hint = PLATFORM_SELF_URL.rstrip("/")
    return {
        "title"           : "Model Context Protocol lab — Assignment Platform edition",
        "what_is_mcp"     : (
            "A small JSON-RPC-ish contract (tools, optional resources/prompts) so any "
            "AI host can discover and call helpers without rebuilding bespoke integrations "
            "for each product."
        ),
        "mental_model"    : [
            {"layer": "Host", "examples": ["Cursor", "Claude Desktop", "MCP Inspector CLI"]},
            {"layer": "Transport", "note": "stdio pipes for local binaries; HTTP+SSE for remote workshops"},
            {"layer": "Server", "this_repo": "`backend/mcp_server.py` via FastMCP"},
        ],
        "try_it_stdio"    : {
            "command"           : "cd project && PYTHONPATH=. python -m backend.mcp_server",
            "cursor_config_hint": (
                '"mcpServers": {"assignment-bootcamp": {"command": "python", '
                '"args": ["-m","backend.mcp_server"], '
                '"cwd": "/ABS/PATH/project", "env": {"PYTHONPATH": "."}}}'
            ),
        },
        "try_it_sse": {
            "step_1"        : "Start API: PYTHONPATH=. uvicorn backend.main:app --reload --port 9000",
            "sse_listen_url": f"{base_hint}/mcp/sse",
            "note"          : (
                "Point MCP Inspector (or compatible clients) directly at localhost:9000 — "
                "avoid localhost:3000 Vite proxies for SSE; they may buffer long streams oddly."
            ),
        },
        "this_server_surfaces": {
            "tools"    : (
                "web_search,calculator,read_file,run_code,memory_*,memory_chunk_count,"
                "platform_ping_health (GET /health), platform_http_get_skills (GET /skills)"
            ),
            "resources": [
                "assignment://bootcamp/mcp-vocabulary",
                "assignment://bootcamp/pipeline-outline",
                "assignment://config/skills.json",
            ],
            "prompts": ["assignment_user_prompt", "reflect_on_run"],
        },
        "opensource_mcp_you_can_compose": {
            "curated_registry": "https://github.com/modelcontextprotocol/servers",
            "ideas"           : [
                {
                    "name"      : "@modelcontextprotocol/server-filesystem",
                    "lesson"    : "Compare URI resources vs MCP tool calls for bounded file IO.",
                    "transport" : "stdio (Node package via npx)",
                },
                {
                    "name"      : "@modelcontextprotocol/server-everything",
                    "lesson"    : "Reference server for MCP tool/resource/prompt matrix testing.",
                    "transport" : "stdio",
                },
                {
                    "name"      : "sqlite / git / puppeteer MCP variants in the servers monorepo",
                    "lesson"    : "Each server is intentionally single-purpose → compose many.",
                    "transport" : "stdio typical",
                },
            ],
            "comparison_to_this_lab": (
                "This repo keeps plugins in Python LangGraph/FastAPI; MCP simply re-exports them "
                "plus HTTP bridges (`platform_*`) so students observe cross-layer composition."
            ),
        },
        "env_knob"           : {"PLATFORM_SELF_URL": "Overrides http://127.0.0.1:9000 for platform_* tools"},
        "recommended_flow" : [
            "1. Curl /lesson/mcp (what you just did programmatically)",
            "2. Launch uvicorn → open MCP Inspector SSE on /mcp/sse",
            "3. Spawn stdio server module + attach Cursor MCP config",
            "4. Add an external MCP (filesystem) beside this one inside the IDE",
            "5. Contrast MCP tool JSON vs REST /run JSON payloads in write-ups",
        ],
    }


# ── General chat (fast path, no pipeline) ────────────────────────────────────

@app.get("/chat")
async def chat_endpoint(q: str = ""):
    """
    Fast general-chat endpoint (single-turn).  Prefer POST /chat for conversation history.
    Streams tokens via SSE.
    """
    msgs = _normalize_messages_for_claude([{"role": "user", "content": q}])
    return EventSourceResponse(_stream_chat_events(msgs))


@app.post("/chat")
async def chat_endpoint_with_history(body: ChatRequest):
    """
    General chat with full message history — same SSE event shape as GET /chat.
    """
    raw  = [t.model_dump() for t in body.messages]
    msgs = _normalize_messages_for_claude(raw)
    return EventSourceResponse(_stream_chat_events(msgs))


@app.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """Load saved chat UI messages for this browser session."""
    if not chat_store.valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id (expected UUID).")
    if not chat_store.is_configured():
        return {"messages": [], "persistence": "disabled"}
    return {
        "messages"    : chat_store.load_messages(session_id),
        "persistence" : "enabled",
    }


@app.put("/chat/history/{session_id}")
async def put_chat_history(session_id: str, body: ChatHistoryUpsert):
    """Persist full chat transcript (debounced snapshots from the client)."""
    if not chat_store.valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id (expected UUID).")
    if not chat_store.is_configured():
        raise HTTPException(status_code=503, detail="MongoDB not configured (set MONGO_URI).")
    if not chat_store.save_messages(session_id, body.messages):
        raise HTTPException(status_code=503, detail="Could not save chat history to MongoDB.")
    return {"ok": True}


@app.delete("/chat/history/{session_id}")
async def delete_chat_history(session_id: str):
    """Delete a session transcript from MongoDB (called when user deletes a session)."""
    if not chat_store.valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id (expected UUID).")
    if not chat_store.is_configured():
        return {"ok": True, "note": "MongoDB not configured — nothing to delete server-side."}
    chat_store.delete_messages(session_id)
    return {"ok": True}


# ── Multi-agent pipeline — streaming SSE ──────────────────────────────────────

@app.get("/stream")
async def stream_endpoint(input: str = "/help"):
    """
    Full multi-agent pipeline — triggered by /slash commands from the UI.
    Emits real-time SSE events: session_start, agent_start, agent_log, token, done, error.
    """
    routed = route_skill(input)

    async def generate():
        yield json.dumps({
            "type"    : "session_start",
            "skill"   : routed["skill"],
            "question": routed["question"],
        })

        # Non-pipeline skills (memory lookup, help)
        if not routed["is_pipeline"]:
            response_text = routed.get("response") or ""
            for i in range(0, len(response_text), 8):
                yield json.dumps({"type": "token", "content": response_text[i:i + 8]})
                await asyncio.sleep(0.005)
            yield json.dumps({"type": "done", "quality_score": 0, "duration_s": 0, "is_assignment": False})
            return

        # Full pipeline — delegate to shared helper
        async for ev in _stream_pipeline_events(routed["question"], routed["skill"]):
            yield ev

    return EventSourceResponse(generate())


# ── Document upload ───────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Accept a PDF, DOCX, or plain-text file and return the extracted text.
    The caller can prepend this text as context for a pipeline run.
    """
    raw      = await file.read()
    filename = (file.filename or "").lower()
    text     = ""

    try:
        if filename.endswith(".pdf"):
            text = _extract_pdf(raw)
        elif filename.endswith(".docx"):
            text = _extract_docx(raw)
        else:
            text = raw.decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.error("Upload extraction error: %s", exc)
        return {"error": str(exc), "text": "", "filename": file.filename}

    return {
        "filename": file.filename,
        "text"    : text[:12000],
        "length"  : len(text),
    }


def _extract_pdf(content: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams
        output = io.StringIO()
        extract_text_to_fp(io.BytesIO(content), output, laparams=LAParams())
        return output.getvalue()
    except ImportError:
        pass
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        return "[PDF extraction requires pdfminer.six or PyPDF2 — run: pip install pdfminer.six]"


def _extract_docx(content: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        return "[DOCX extraction requires python-docx — run: pip install python-docx]"


# ── Blocking run (for integrations) ──────────────────────────────────────────

@app.post("/run", response_model=RunResponse)
async def run_endpoint(request: RunRequest):
    routed = route_skill(request.input)

    if not routed["is_pipeline"]:
        return RunResponse(
            skill        = routed["skill"],
            question     = routed["question"],
            final_answer = routed.get("response") or "",
            quality_score= 0,
            agent_log    = [],
            duration_s   = 0.0,
        )

    guard = before_skill(routed["question"], routed["skill"])
    if not guard["ok"]:
        raise HTTPException(status_code=400, detail=guard["reason"])

    loop    = asyncio.get_event_loop()
    t_start = time.time()
    result  = await loop.run_in_executor(
        None, run_pipeline, routed["question"], routed["skill"]
    )
    duration = time.time() - t_start
    after_skill(result, routed["skill"], duration)

    return RunResponse(
        skill        = routed["skill"],
        question     = routed["question"],
        final_answer = result.get("final_answer", ""),
        quality_score= result.get("quality_score", 0),
        agent_log    = result.get("agent_log", []),
        duration_s   = round(duration, 2),
    )


# ── MCP over HTTP (SSE); stdio counterpart: python -m backend.mcp_server ───────

app.mount("/mcp", _assignment_mcp.mcp.sse_app())
