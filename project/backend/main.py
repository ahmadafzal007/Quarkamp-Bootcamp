"""
FastAPI Application — University Assignment Platform
=====================================================
Routes:
  GET  /health                       health check
  GET  /skills                       list available skills
  GET  /chat                         general AI chat (fast, no pipeline) — SSE
  GET  /stream                       full multi-agent pipeline — SSE
  POST /upload                       extract text from PDF / DOCX / TXT
  POST /run                          run pipeline (blocking, returns JSON)
  GET  /a2a/.well-known/agent.json   A2A agent card
  POST /a2a/tasks                    A2A task submission
  GET  /a2a/tasks/{id}               A2A task result

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
import json
import time
import queue
import asyncio
import logging
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.config import SKILLS, ANTHROPIC_API_KEY, MODEL_FAST
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


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/skills")
async def list_skills():
    return {"skills": [{"name": k, "description": v} for k, v in SKILLS.items()]}


# ── General chat (fast path, no pipeline) ────────────────────────────────────

@app.get("/chat")
async def chat_endpoint(q: str = ""):
    """
    Fast general-chat endpoint.  Uses a single LLM call — no multi-agent pipeline.
    Streams tokens via SSE.
    """
    import anthropic

    async def generate():
        yield json.dumps({"type": "session_start", "skill": "chat", "question": q})

        if not q.strip():
            yield json.dumps({"type": "error", "message": "Please enter a question."})
            return

        try:
            client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            t_start = time.time()

            response = client.messages.create(
                model      = MODEL_FAST,
                max_tokens = 1024,
                system     = (
                    "You are a helpful AI assistant for university students. "
                    "Answer clearly and concisely. "
                    "If the user is asking to research, write, plan, or critique an assignment in depth, "
                    "suggest they use commands like /research, /plan, /summarize, or /critique."
                ),
                messages   = [{"role": "user", "content": q}],
            )
            answer = response.content[0].text

            for i in range(0, len(answer), 8):
                yield json.dumps({"type": "token", "content": answer[i:i + 8]})
                await asyncio.sleep(0.005)

            yield json.dumps({
                "type"        : "done",
                "quality_score": 0,
                "duration_s"  : round(time.time() - t_start, 2),
                "is_assignment": False,
            })
        except Exception as exc:
            logger.error("chat error: %s", exc)
            yield json.dumps({"type": "error", "message": str(exc)})

    return EventSourceResponse(generate())


# ── Multi-agent pipeline — streaming SSE ──────────────────────────────────────

@app.get("/stream")
async def stream_endpoint(input: str = "/help"):
    """
    Full multi-agent pipeline.  Emits real-time events while agents run:
      agent_start, agent_log, token, done, error
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

        guard = before_skill(routed["question"], routed["skill"])
        if not guard["ok"]:
            yield json.dumps({"type": "error", "message": guard["reason"]})
            return

        event_q = queue.Queue()
        t_start  = time.time()
        loop     = asyncio.get_event_loop()

        # Run pipeline in thread pool; it pushes events to event_q
        future = loop.run_in_executor(
            None,
            run_pipeline_streaming,
            routed["question"],
            routed["skill"],
            event_q,
        )

        # Forward events while pipeline runs
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
        after_skill(result, routed["skill"], duration)

        # Stream final answer token-by-token
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
