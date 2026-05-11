"""
Model Context Protocol (MCP) — bootcamp-facing server for this Assignment Platform.

What students should take away:
  Host (Cursor, Claude Desktop, MCP Inspector): starts the client workflow and consumes tools.
  Server (this file): declares tools/resources/prompts the host discovers over the wire.

Transports demonstrated here:
  * stdio  — subprocess pipes; Cursor/IDE configs usually launch:
        cd project && PYTHONPATH=. python -m backend.mcp_server
    so the MCP host talks to stdin/stdout.
  * SSE    — mounted by FastAPI at /mcp (see backend.main). Point MCP Inspector's
    "SSE URL" at http://127.0.0.1:9000/mcp/sse once uvicorn is running.

This bundles two integration styles:
  1. Direct Python calls into platform plugins (classic MCP tool = local capability).
  2. Thin HTTP wrappers that hit the app's own REST API (MCP wrapping microservices —
     see platform_* tools and PLATFORM_SELF_URL in backend.config).

Composable OSS MCP servers live outside this repo; see GET /lesson/mcp for curated examples.

Run standalone stdio MCP:
    cd project && PYTHONPATH=. python -m backend.mcp_server
"""

from __future__ import annotations

import json
from textwrap import dedent

import httpx
from mcp.server.fastmcp import FastMCP

from .config import SKILLS, PLATFORM_SELF_URL
from .plugins.web_search import web_search as _web_search
from .plugins.calculator import calculator as _calculator
from .plugins.pdf_reader import read_file as _read_file
from .plugins.code_runner import run_code as _run_code
from .plugins.memory import (
    memory_store as _memory_store,
    memory_retrieve as _memory_retrieve,
    memory_count as _memory_count,
)

mcp = FastMCP(
    name="AssignmentPlatformBootcamp",
    instructions=dedent(
        """
        University Assignment Platform — MCP primer for Agentic AI bootcamp.
        Prefer web_search/calculator for facts and math.
        Use memory_* for Chroma episodic recall; memory_search before writing long answers.
        Use platform_* to exercise REST→MCP composition (PLATFORM_SELF_URL must reach FastAPI).

        MCP resources expose static teaching material; MCP prompts scaffold starter messages.
        """
    ).strip(),
)


# ── MCP tools — local plugins ───────────────────────────────────────────────────


@mcp.tool()
def web_search(query: str, max_results: int = 3) -> str:
    """Search the web for current information (DuckDuckGo-backed)."""
    return _web_search(query, max_results)


@mcp.tool()
def calculator(expression: str) -> str:
    """Evaluate a math expression. Supports +,-,*,/,**,sqrt,pi,log,exp."""
    return _calculator(expression)


@mcp.tool()
def read_file(path: str) -> str:
    """Read a .txt or .pdf file and return its content."""
    return _read_file(path)


@mcp.tool()
def run_code(code: str, language: str = "python") -> str:
    """Execute Python code in a sandboxed subprocess."""
    return _run_code(code, language)


@mcp.tool()
def memory_store(question: str, answer: str, subject: str = "", score: int = 0) -> str:
    """Save a Q&A pair to episodic memory (Chroma persistent store)."""
    return _memory_store(question, answer, subject, score)


@mcp.tool()
def memory_search(query: str, n_results: int = 3) -> str:
    """Semantic search across saved Q&A pairs (returns JSON string)."""
    return _memory_retrieve(query, n_results)


@mcp.tool()
def memory_chunk_count() -> str:
    """Return how many memories are stored (Chroma collection size)."""
    try:
        n = _memory_count()
        return json.dumps({"stored_chunks": n})
    except Exception as exc:  # pragma: no cover
        return json.dumps({"error": str(exc)})


# ── MCP tools — HTTP façade over the running FastAPI app ─────────────────────────


@mcp.tool()
def platform_ping_health() -> str:
    """
    Call GET /health on the Assignment Platform REST API.

    Demonstrates MCP as a façade that aggregates remote HTTP services — even the app itself.
    """
    url = f"{PLATFORM_SELF_URL}/health"
    try:
        r = httpx.get(url, timeout=8.0)
        return r.text if r.text else json.dumps({"status_code": r.status_code})
    except httpx.RequestError as exc:
        return json.dumps(
            {
                "error"    : str(exc),
                "hint"     : "Start uvicorn and check PLATFORM_SELF_URL in .env or backend.config",
                "tried_url": url,
            }
        )


@mcp.tool()
def platform_http_get_skills() -> str:
    """Fetch formatted skill catalogue from GET /skills (bootcamp analogue of MCP discovery)."""
    url = f"{PLATFORM_SELF_URL}/skills"
    try:
        r = httpx.get(url, timeout=8.0)
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("skills", [])
        lines = ["Skills exposed by REST (compare to MCP tool list):"]
        for row in rows:
            name = row.get("name", "?")
            desc = row.get("description", "")
            lines.append(f"  /{name} — {desc}")
        return "\n".join(lines)
    except Exception as exc:
        return json.dumps({"error": str(exc), "tried_url": url})


# ── MCP resources — read-only teaching surfaces ─────────────────────────────────


@mcp.resource("assignment://bootcamp/mcp-vocabulary")
def resource_mcp_vocabulary() -> str:
    """Plain-text cheat sheet: tools vs resources vs prompts vs transports."""
    return dedent(
        """
        MCP vocabulary (60-second recap)
        ---------------------------------
        • Tool       : Callable capability the host can invoke (often with JSON args).
        • Resource   : Readable URI-ish document the host pulls into context.
        • Prompt     : Saved template expanding into starter chat turns.
        • Transport  : stdio (pipes) vs HTTP+SSE streams — same logical server, different wire.

        Why this repo shows both transports
        -------------------------------------
        Production hosts often compose many MCP subprocesses via stdio. Remote debugging
        and workshops lean on SSE so instructors can probe the server without touching IDE configs.
        """
    ).strip()


@mcp.resource("assignment://bootcamp/pipeline-outline")
def resource_pipeline_outline() -> str:
    """High-level LangGraph steps students see in /stream logs."""
    return dedent(
        """
        Multi-agent pipeline (conceptual)
        ---------------------------------
        START → memory_retrieve → orchestrator → planner → researcher
              → writer → critic → (+ revisions) → memory_save → END

        MCP tools ≠ graph nodes directly; instead agents call Python plugins internally.
        The MCP server exposes the *same plugins* plus HTTP bridges for pedagogy.
        """
    ).strip()


@mcp.resource("assignment://config/skills.json")
def resource_skills_json() -> str:
    """Frozen JSON view of SKILL registry (helps compare REST /skills payload)."""
    return json.dumps(SKILLS, indent=2, ensure_ascii=False)


# ── MCP prompts — parameterized starter scaffolding ─────────────────────────────


@mcp.prompt(description="Starter turns for a slash-command assignment run")
def assignment_user_prompt(topic: str, suggested_command: str = "/research") -> list[dict]:
    """
    Returns a multi-turn template the host materializes inside the pane.
    Mirrors how students type into the Assignment AI web Terminal.
    """
    body = dedent(
        f"""
        I am practicing the bootcamp Assignment Platform multi-agent workflow.

        Topic or assignment brief:
        {topic}

        I will likely use `{suggested_command}` from the slash-command menu.
        Before I run the graph, list 3 clarifying questions I should answer for myself.
        """
    ).strip()
    return [{"role": "user", "content": body}]


@mcp.prompt(description="Reflection prompt after /critique or /plan")
def reflect_on_run(what_i_tried: str, observed_score: int | None = None) -> list[dict]:
    """Encourage metacognition after a pipeline execution."""
    score_line = f"The critic reported score {observed_score}/10." if observed_score is not None else ""
    body = dedent(
        f"""
        Here is what I attempted on the platform:
        {what_i_tried}

        {score_line}

        What should I iterate next? Tie advice to planner → researcher → writer → critic loop.
        """
    ).strip()
    return [{"role": "user", "content": body}]


if __name__ == "__main__":
    print("Assignment Platform MCP — stdio transport (Ctrl+D / kill to stop).", flush=True)
    mcp.run(transport="stdio")
