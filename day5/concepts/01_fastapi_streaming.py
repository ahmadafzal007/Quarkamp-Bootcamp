"""
CONCEPT 1 — FastAPI with SSE Streaming
========================================
SSE (Server-Sent Events) lets the server push data to the client
as it becomes available — perfect for streaming agent thoughts.

This script creates a minimal FastAPI app that:
  1. Accepts a question via POST /ask
  2. Streams agent events back as SSE
  3. Shows how the React frontend consumes the stream

Run:
    conda run -n bootcamp uvicorn day5.concepts.01_fastapi_streaming:app --reload --port 8001

Then test with:
    curl -N http://localhost:8001/stream?question=What+is+AI
"""

import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
app = FastAPI(title="SSE Streaming Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"


# ── SSE Event types ───────────────────────────────────────────────────────────
# We define structured events so the frontend knows what to do with each one.
# In the project, these match what Terminal.jsx listens for.

def make_event(event_type: str, data: dict) -> str:
    return json.dumps({"type": event_type, **data})


# ── Streaming generator ───────────────────────────────────────────────────────

async def stream_agent(question: str):
    """Yields SSE events as the agent processes the question."""

    # Event 1: session start
    yield make_event("session_start", {"message": "Processing your question..."})
    await asyncio.sleep(0.05)

    # Event 2: agent activity
    yield make_event("agent_start", {"agent": "Orchestrator", "message": "Routing question..."})
    await asyncio.sleep(0.3)

    yield make_event("agent_start", {"agent": "Researcher", "message": "Gathering information..."})
    await asyncio.sleep(0.1)

    # Event 3: tool call
    yield make_event("tool_call", {"tool": "web_search", "query": question[:50]})
    await asyncio.sleep(0.2)

    yield make_event("agent_start", {"agent": "Writer", "message": "Drafting answer..."})

    # Event 4: stream tokens from Claude
    with client.messages.stream(
        model=MODEL,
        max_tokens=400,
        system="You are a helpful university assistant. Answer clearly and concisely.",
        messages=[{"role": "user", "content": question}],
    ) as stream:
        for text in stream.text_stream:
            yield make_event("token", {"content": text})

    # Event 5: done
    usage = stream.get_final_message().usage
    yield make_event("done", {
        "input_tokens" : usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd"     : round((usage.input_tokens * 0.00000025 + usage.output_tokens * 0.00000125), 6),
    })


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/stream")
async def stream_endpoint(question: str = "What is machine learning?"):
    """SSE endpoint — connect with EventSource in the browser."""
    return EventSourceResponse(stream_agent(question))


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n  SSE Streaming Demo")
    print("  Open: http://localhost:8001/stream?question=What+is+quantum+computing")
    print("  Or:   curl -N 'http://localhost:8001/stream?question=Explain+DNA'\n")
    uvicorn.run(app, host="0.0.0.0", port=8001)
