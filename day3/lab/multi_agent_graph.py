"""
LAB 3 — Multi-Agent System with LangGraph
==========================================
5 specialised agents wired into a LangGraph state machine:

  Orchestrator → Planner → Researcher → Writer → Critic
                                                    ↓
                                           (loop back to Writer if score < 7)

Each agent has:
  - Its own system prompt (specialised role)
  - Its own model choice (cost optimised)
  - A clearly defined "inbox" (what state fields it reads)
  - A clearly defined "outbox" (what fields it updates)

Run:
    conda run -n bootcamp python day3/lab/multi_agent_graph.py

This becomes the core of project/backend/graph.py on Day 5.
"""

import json
import re
import operator
import datetime
from pathlib import Path
from typing import TypedDict, Annotated, Literal
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()

# ── Model assignments (cost-optimised) ────────────────────────────────────────
MODEL_FAST     = "claude-haiku-4-5"    # Orchestrator, Critic
MODEL_BALANCED = "claude-sonnet-4-6"   # Planner, Researcher, Writer


# ── Shared State ─────────────────────────────────────────────────────────────

class AssignmentState(TypedDict):
    # Input
    question      : str
    skill         : str               # "research" | "plan" | "critique" | "summarize"

    # Agent outputs (each agent owns one section)
    route         : str               # Orchestrator → which path to take
    subtasks      : list[str]         # Planner
    research      : dict[str, str]    # Researcher: {subtask: finding}
    draft         : str               # Writer
    critique      : str               # Critic feedback
    final_answer  : str               # Critic-approved answer
    quality_score : int               # Critic score

    # Meta
    revision_count: int
    agent_log     : Annotated[list[str], operator.add]
    started_at    : str


def _call(model: str, system: str, user: str, max_tokens: int = 600) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _log(agent: str, msg: str) -> list[str]:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] [{agent}] {msg}"
    print(f"  {entry}")
    return [entry]


# ── Agent 1: Orchestrator ─────────────────────────────────────────────────────
# Classifies the question and decides the pipeline route.

def orchestrator(state: AssignmentState) -> dict:
    result = _call(
        MODEL_FAST,
        system=(
            "You are a routing agent for a university assignment platform. "
            "Classify the question into ONE of these routes:\n"
            "  research   — needs information gathering\n"
            "  plan       — needs task breakdown / project planning\n"
            "  critique   — student wants feedback on their existing work\n"
            "  summarize  — needs a summary of a topic or document\n"
            "Reply with ONLY one word: research, plan, critique, or summarize"
        ),
        user=state["question"],
        max_tokens=10,
    )
    route = result.strip().lower()
    if route not in ("research", "plan", "critique", "summarize"):
        route = "research"
    return {
        "route"    : route,
        "agent_log": _log("Orchestrator", f"Route: {route}"),
    }


# ── Agent 2: Planner ─────────────────────────────────────────────────────────
# Breaks the question into concrete research subtasks.

def planner(state: AssignmentState) -> dict:
    result = _call(
        MODEL_BALANCED,
        system=(
            "You are a research planner. Given a question, output a JSON array "
            "of 3-4 specific research subtasks needed to answer it thoroughly. "
            'Output ONLY the JSON array. Example: ["Find X", "Explain Y"]'
        ),
        user=state["question"],
        max_tokens=200,
    )
    match = re.search(r"\[.*\]", result, re.DOTALL)
    try:
        subtasks = json.loads(match.group()) if match else ["Research the main topic", "Find examples", "Identify key concepts"]
    except Exception:
        subtasks = ["Research the main topic", "Find examples", "Identify key concepts"]

    return {
        "subtasks" : subtasks,
        "agent_log": _log("Planner", f"Created {len(subtasks)} subtasks: {subtasks}"),
    }


# ── Agent 3: Researcher ──────────────────────────────────────────────────────
# Executes each subtask and builds a research dict.
# Day 4 adds real tools (web_search, ChromaDB) to this node.

def researcher(state: AssignmentState) -> dict:
    findings: dict[str, str] = {}
    for subtask in state["subtasks"]:
        finding = _call(
            MODEL_BALANCED,
            system=(
                "You are a thorough research assistant. "
                "Answer the subtask in 3-4 precise sentences. "
                "Be factual and specific — no fluff."
            ),
            user=f"Subtask: {subtask}\nBroader context: {state['question']}",
            max_tokens=250,
        )
        findings[subtask] = finding

    return {
        "research" : findings,
        "agent_log": _log("Researcher", f"Gathered {len(findings)} findings"),
    }


# ── Agent 4: Writer ───────────────────────────────────────────────────────────
# Synthesises research into a well-structured answer.

def writer(state: AssignmentState) -> dict:
    research_block = "\n\n".join(
        f"• {task}:\n  {finding}"
        for task, finding in state["research"].items()
    )
    critique_context = ""
    if state.get("critique") and state["revision_count"] > 0:
        critique_context = f"\n\nPrevious critique to address:\n{state['critique']}"

    draft = _call(
        MODEL_BALANCED,
        system=(
            "You are an expert academic writer for university students.\n"
            "Synthesise the research notes into a clear, coherent answer.\n"
            "Structure: brief intro → main points → conclusion.\n"
            "Write for a first-year student: clear, no unexplained jargon."
        ),
        user=(
            f"Question: {state['question']}\n\n"
            f"Research notes:\n{research_block}"
            f"{critique_context}"
        ),
        max_tokens=800,
    )
    return {
        "draft"    : draft,
        "agent_log": _log("Writer", f"Draft written (revision #{state['revision_count']})"),
    }


# ── Agent 5: Critic ───────────────────────────────────────────────────────────
# Scores the draft and either approves or sends back for revision.

def critic(state: AssignmentState) -> dict:
    result = _call(
        MODEL_FAST,
        system=(
            "You are a rigorous academic critic. Evaluate the answer and reply in this EXACT format:\n"
            "Score: X/10\n"
            "Strengths: <one sentence>\n"
            "Weaknesses: <one sentence>\n"
            "Verdict: PASS or REVISE"
        ),
        user=f"Question: {state['question']}\n\nAnswer:\n{state['draft']}",
        max_tokens=150,
    )
    # Parse score
    try:
        score_match = re.search(r"Score:\s*(\d+)", result)
        score = int(score_match.group(1)) if score_match else 7
    except Exception:
        score = 7

    verdict = "PASS" if score >= 7 else "REVISE"
    log_msg = f"Score {score}/10 → {verdict}"

    if verdict == "PASS":
        return {
            "critique"     : result,
            "final_answer" : state["draft"],
            "quality_score": score,
            "agent_log"    : _log("Critic", log_msg),
        }
    return {
        "critique"     : result,
        "quality_score": score,
        "agent_log"    : _log("Critic", log_msg),
    }


# ── Routing functions ─────────────────────────────────────────────────────────

def should_revise(state: AssignmentState) -> Literal["writer", "__end__"]:
    if state["quality_score"] < 7 and state["revision_count"] < 2:
        return "writer"
    return END


# ── Build the graph ───────────────────────────────────────────────────────────

def build_assignment_graph():
    g = StateGraph(AssignmentState)

    g.add_node("orchestrator", orchestrator)
    g.add_node("planner",      planner)
    g.add_node("researcher",   researcher)
    g.add_node("writer",       writer)
    g.add_node("critic",       critic)

    g.add_edge(START,          "orchestrator")
    g.add_edge("orchestrator", "planner")
    g.add_edge("planner",      "researcher")
    g.add_edge("researcher",   "writer")
    g.add_edge("writer",       "critic")

    g.add_conditional_edges("critic", should_revise, {
        "writer" : "writer",
        END      : END,
    })

    return g.compile()


# ── CLI ───────────────────────────────────────────────────────────────────────

def run(question: str) -> AssignmentState:
    app = build_assignment_graph()
    initial: AssignmentState = {
        "question"      : question,
        "skill"         : "research",
        "route"         : "",
        "subtasks"      : [],
        "research"      : {},
        "draft"         : "",
        "critique"      : "",
        "final_answer"  : "",
        "quality_score" : 0,
        "revision_count": 0,
        "agent_log"     : [],
        "started_at"    : datetime.datetime.now().isoformat(),
    }
    return app.invoke(initial)


def main():
    print("\n" + "═" * 62)
    print("  MULTI-AGENT ASSIGNMENT PLATFORM — Day 3 Lab")
    print("  Agents: Orchestrator → Planner → Researcher → Writer → Critic")
    print("═" * 62 + "\n")

    while True:
        try:
            question = input("  Ask a question (or /quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if question == "/quit":
            break
        if not question:
            continue

        print()
        result = run(question)

        print("\n" + "─" * 62)
        print("  PIPELINE SUMMARY")
        print("─" * 62)
        print(f"  Route:    {result['route']}")
        print(f"  Score:    {result['quality_score']}/10")
        print(f"  Revisions:{result['revision_count']}")
        print()
        print("  FINAL ANSWER:")
        print("─" * 62)
        print(result["final_answer"])
        print()


if __name__ == "__main__":
    main()
