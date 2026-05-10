"""
LangGraph pipeline — the heart of the platform.
Wires all 5 agents into a state machine with conditional routing.

Flow:
  START → memory_retrieve → orchestrator → planner → researcher
        → writer → critic → (revise? → writer) → memory_save → END
"""

import operator
import json
import datetime
import uuid
import queue as _queue
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, START, END

from .agents import (
    orchestrator_node, planner_node,
    researcher_node, writer_node, critic_node,
)
from .plugins.memory import memory_retrieve, memory_store
from .config import MIN_SCORE, MAX_REVISIONS


# ── State ─────────────────────────────────────────────────────────────────────

class AssignmentState(TypedDict):
    # Input
    question      : str
    skill         : str

    # Pipeline data
    route         : str
    memory_context: list[str]
    subtasks      : list[str]
    research      : dict[str, str]
    draft         : str
    critique      : str
    final_answer  : str
    quality_score : int
    revision_count: int

    # Meta
    session_id    : str
    started_at    : str
    agent_log     : Annotated[list[str], operator.add]


# ── Memory nodes ──────────────────────────────────────────────────────────────

def memory_retrieve_node(state: AssignmentState) -> dict:
    raw = memory_retrieve(state["question"], n_results=3)
    parsed = json.loads(raw)
    past = [r["content"] for r in parsed.get("results", [])]
    return {
        "memory_context": past,
        "agent_log"     : [f"[Memory] Retrieved {len(past)} past answer(s)"],
    }


def memory_save_node(state: AssignmentState) -> dict:
    if state.get("final_answer"):
        memory_store(
            question=state["question"],
            answer  =state["final_answer"],
            subject =state.get("route", ""),
            score   =state.get("quality_score", 0),
        )
        return {"agent_log": [f"[Memory] Saved (score={state['quality_score']}/10)"]}
    return {"agent_log": ["[Memory] Nothing to save"]}


# ── Routing ───────────────────────────────────────────────────────────────────

def should_revise(state: AssignmentState) -> Literal["writer", "__end__"]:
    if state["quality_score"] < MIN_SCORE and state["revision_count"] < MAX_REVISIONS:
        return "writer"
    return END


# ── Graph builder (shared) ────────────────────────────────────────────────────

def _make_initial(question: str, skill: str) -> AssignmentState:
    return {
        "question"      : question,
        "skill"         : skill,
        "route"         : "",
        "memory_context": [],
        "subtasks"      : [],
        "research"      : {},
        "draft"         : "",
        "critique"      : "",
        "final_answer"  : "",
        "quality_score" : 0,
        "revision_count": 0,
        "session_id"    : str(uuid.uuid4()),
        "started_at"    : datetime.datetime.now().isoformat(),
        "agent_log"     : [],
    }


def _build_graph(node_map: dict):
    """Build and compile a StateGraph from the given node name → function map."""
    g = StateGraph(AssignmentState)

    g.add_node("memory_retrieve", node_map["memory_retrieve"])
    g.add_node("orchestrator",    node_map["orchestrator"])
    g.add_node("planner",         node_map["planner"])
    g.add_node("researcher",      node_map["researcher"])
    g.add_node("writer",          node_map["writer"])
    g.add_node("critic",          node_map["critic"])
    g.add_node("memory_save",     node_map["memory_save"])

    g.add_edge(START,             "memory_retrieve")
    g.add_edge("memory_retrieve", "orchestrator")
    g.add_edge("orchestrator",    "planner")
    g.add_edge("planner",         "researcher")
    g.add_edge("researcher",      "writer")
    g.add_edge("writer",          "critic")
    g.add_conditional_edges("critic", should_revise, {
        "writer": "writer",
        END     : "memory_save",
    })
    g.add_edge("memory_save", END)

    return g.compile()


# ── Plain pipeline (cached) ───────────────────────────────────────────────────

_plain_nodes = {
    "memory_retrieve": memory_retrieve_node,
    "orchestrator"   : orchestrator_node,
    "planner"        : planner_node,
    "researcher"     : researcher_node,
    "writer"         : writer_node,
    "critic"         : critic_node,
    "memory_save"    : memory_save_node,
}

_app = None

def get_graph():
    global _app
    if _app is None:
        _app = _build_graph(_plain_nodes)
    return _app


def run_pipeline(question: str, skill: str = "") -> AssignmentState:
    return get_graph().invoke(_make_initial(question, skill))


# ── Streaming pipeline ────────────────────────────────────────────────────────

_DISPLAY_NAMES = {
    "memory_retrieve": "Memory",
    "orchestrator"   : "Orchestrator",
    "planner"        : "Planner",
    "researcher"     : "Researcher",
    "writer"         : "Writer",
    "critic"         : "Critic",
    "memory_save"    : "MemorySave",
}


def run_pipeline_streaming(question: str, skill: str = "", event_q: _queue.Queue = None) -> AssignmentState:
    """
    Run the full agent pipeline and emit real-time events to event_q.

    Events pushed to event_q:
      {"type": "agent_start", "agent": "<DisplayName>"}
      {"type": "agent_log",   "agent": "<DisplayName>", "entry": "<log text>"}
    """

    def wrap(node_key, fn):
        display = _DISPLAY_NAMES.get(node_key, node_key)

        def wrapped(state):
            if event_q is not None:
                event_q.put({"type": "agent_start", "agent": display})
            result = fn(state)
            if event_q is not None:
                new_logs = result.get("agent_log", [])
                entry = new_logs[-1] if new_logs else f"[{display}] completed"
                event_q.put({"type": "agent_log", "agent": display, "entry": entry})
            return result

        return wrapped

    wrapped_nodes = {k: wrap(k, fn) for k, fn in _plain_nodes.items()}
    app = _build_graph(wrapped_nodes)
    return app.invoke(_make_initial(question, skill))
