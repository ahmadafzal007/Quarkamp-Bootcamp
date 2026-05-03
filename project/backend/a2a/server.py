"""
A2A (Agent-to-Agent) Server
============================
Exposes our agent pipeline to external AI agents using a
simplified version of Google's A2A protocol.

Endpoints:
  GET  /a2a/.well-known/agent.json   → AgentCard (capabilities)
  POST /a2a/tasks                    → Submit a task
  GET  /a2a/tasks/{task_id}          → Get task result

External agents discover us via the agent.json endpoint,
then submit tasks and poll for results.
"""

import uuid
import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from ..config import A2A_BASE_URL, SKILLS

a2a_router = APIRouter(prefix="/a2a", tags=["A2A"])

# In-memory task store (Day 5: replace with Redis or DB for production)
_tasks: dict[str, dict] = {}


# ── Agent Card ────────────────────────────────────────────────────────────────

AGENT_CARD = {
    "name"       : "UniversityAssignmentPlatform",
    "description": (
        "An AI agent that helps university students research, plan, "
        "write, and critique academic assignments."
    ),
    "version"    : "1.0.0",
    "url"        : A2A_BASE_URL,
    "provider"   : {"name": "Bootcamp", "url": A2A_BASE_URL},
    "skills"     : [
        {"id": skill, "name": skill.capitalize(), "description": desc}
        for skill, desc in SKILLS.items()
        if skill != "help"
    ],
    "defaultInputModes" : ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "authentication"    : {"schemes": ["none"]},
}


@a2a_router.get("/.well-known/agent.json")
async def get_agent_card():
    """Returns the agent's capabilities. External agents read this to discover us."""
    return AGENT_CARD


# ── Task submission ───────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    skill   : str = "research"
    question: str
    callback_url: str | None = None  # optional webhook for async notification


@a2a_router.post("/tasks")
async def create_task(request: TaskRequest):
    """
    Submit a task to our agent pipeline.
    Returns a task_id — poll GET /a2a/tasks/{task_id} for the result.
    """
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "id"        : task_id,
        "status"    : "submitted",
        "skill"     : request.skill,
        "question"  : request.question,
        "result"    : None,
        "created_at": datetime.datetime.now().isoformat(),
    }

    # Run pipeline asynchronously in background
    import asyncio
    asyncio.create_task(_run_task(task_id, request.skill, request.question))

    return {"task_id": task_id, "status": "submitted", "poll_url": f"{A2A_BASE_URL}/a2a/tasks/{task_id}"}


@a2a_router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get the status and result of a submitted task."""
    task = _tasks.get(task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}
    return task


# ── Background task runner ────────────────────────────────────────────────────

async def _run_task(task_id: str, skill: str, question: str) -> None:
    import asyncio
    _tasks[task_id]["status"] = "running"
    try:
        loop   = asyncio.get_event_loop()
        from ..graph import run_pipeline
        result = await loop.run_in_executor(None, run_pipeline, question, skill)
        _tasks[task_id].update({
            "status"      : "completed",
            "result"      : result.get("final_answer", ""),
            "quality_score": result.get("quality_score", 0),
            "completed_at": datetime.datetime.now().isoformat(),
        })
    except Exception as e:
        _tasks[task_id].update({
            "status": "failed",
            "error" : str(e),
        })
