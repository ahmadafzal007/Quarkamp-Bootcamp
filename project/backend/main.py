"""
FastAPI Application — University Assignment Platform
=====================================================
Routes:
  GET  /health                     health check
  GET  /skills                     list available skills
  POST /run                        run pipeline (blocking, returns JSON)
  GET  /stream                     run pipeline (streaming SSE)
  GET  /a2a/.well-known/agent.json A2A agent card
  POST /a2a/tasks                  A2A task submission
  GET  /a2a/tasks/{id}             A2A task result

Run:
    conda run -n bootcamp uvicorn project.backend.main:app --reload --port 8000
"""

import os
import json
import time
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from .config import SKILLS, ANTHROPIC_API_KEY
from .skills.router import route_skill
from .graph import run_pipeline
from .hooks import before_skill, after_skill
from .a2a.server import a2a_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("main")

app = FastAPI(
    title      = "University Assignment Platform",
    description= "Multi-agent AI system for university assignments",
    version    = "1.0.0",
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
    logger.info("University Assignment Platform started")


# ── Request / Response models ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    input: str        # raw user input e.g. "/research What is DNA?"


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
    return {"status": "ok", "version": "1.0.0"}


@app.get("/skills")
async def list_skills():
    return {"skills": [{"name": k, "description": v} for k, v in SKILLS.items()]}


# ── Blocking run ──────────────────────────────────────────────────────────────

@app.post("/run", response_model=RunResponse)
async def run_endpoint(request: RunRequest):
    routed = route_skill(request.input)

    if not routed["is_pipeline"]:
        return RunResponse(
            skill        = routed["skill"],
            question     = routed["question"],
            final_answer = routed["response"],
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


# ── Streaming SSE run ─────────────────────────────────────────────────────────

@app.get("/stream")
async def stream_endpoint(input: str = "/help"):
    """
    SSE endpoint. Connect with EventSource in React.
    Events: session_start, agent_start, tool_call, token, done, error
    """
    routed = route_skill(input)

    async def generate():
        yield json.dumps({"type": "session_start", "skill": routed["skill"], "question": routed["question"]})

        if not routed["is_pipeline"]:
            yield json.dumps({"type": "token", "content": routed["response"]})
            yield json.dumps({"type": "done", "quality_score": 0, "duration_s": 0})
            return

        guard = before_skill(routed["question"], routed["skill"])
        if not guard["ok"]:
            yield json.dumps({"type": "error", "message": guard["reason"]})
            return

        # Run pipeline in thread and stream events
        t_start = time.time()
        loop    = asyncio.get_event_loop()

        # Stream agent log events via a queue
        import queue
        event_queue: queue.Queue = queue.Queue()

        def patched_run():
            result = run_pipeline(routed["question"], routed["skill"])
            event_queue.put(("done", result))
            return result

        future = loop.run_in_executor(None, patched_run)

        # Stream log entries from the pipeline (polled)
        last_log_idx = 0
        while not future.done():
            await asyncio.sleep(0.3)
            try:
                msg_type, payload = event_queue.get_nowait()
            except Exception:
                pass

        result   = await future
        duration = time.time() - t_start
        after_skill(result, routed["skill"], duration)

        # Stream the agent log entries
        for entry in result.get("agent_log", []):
            yield json.dumps({"type": "agent_log", "entry": entry})
            await asyncio.sleep(0.05)

        # Stream the final answer token by token
        answer = result.get("final_answer", "")
        chunk_size = 4
        for i in range(0, len(answer), chunk_size):
            yield json.dumps({"type": "token", "content": answer[i:i+chunk_size]})
            await asyncio.sleep(0.01)

        yield json.dumps({
            "type"         : "done",
            "quality_score": result.get("quality_score", 0),
            "duration_s"   : round(duration, 2),
            "revision_count": result.get("revision_count", 0),
        })

    return EventSourceResponse(generate())
