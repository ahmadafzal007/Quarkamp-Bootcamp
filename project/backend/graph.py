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


# ── Build ─────────────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AssignmentState)

    g.add_node("memory_retrieve", memory_retrieve_node)
    g.add_node("orchestrator",    orchestrator_node)
    g.add_node("planner",         planner_node)
    g.add_node("researcher",      researcher_node)
    g.add_node("writer",          writer_node)
    g.add_node("critic",          critic_node)
    g.add_node("memory_save",     memory_save_node)

    g.add_edge(START,              "memory_retrieve")
    g.add_edge("memory_retrieve",  "orchestrator")
    g.add_edge("orchestrator",     "planner")
    g.add_edge("planner",          "researcher")
    g.add_edge("researcher",       "writer")
    g.add_edge("writer",           "critic")
    g.add_conditional_edges("critic", should_revise, {
        "writer": "writer",
        END     : "memory_save",
    })
    g.add_edge("memory_save", END)

    return g.compile()


_app = None

def get_graph():
    global _app
    if _app is None:
        _app = build_graph()
    return _app


def run_pipeline(question: str, skill: str = "") -> AssignmentState:
    app = get_graph()
    initial: AssignmentState = {
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
    return app.invoke(initial)
