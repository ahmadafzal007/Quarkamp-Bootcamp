"""
CONCEPT 3 — Agent Handoffs and Context Preservation
=====================================================
When one agent finishes and the next one starts, the state carries
everything forward. This script shows:

  1. How to pass structured context between agents
  2. How each agent's output becomes the next agent's input
  3. How to build an agent "inbox" — each agent only reads
     what it needs from the state (not the whole history)

This pattern scales to 100+ agents in a production system.

Run:
    conda run -n bootcamp python day3/concepts/03_agent_handoffs.py
"""

from pathlib import Path
from typing import TypedDict, Annotated
import operator
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"


# ── State with reducer ────────────────────────────────────────────────────────
# The Annotated[list, operator.add] syntax tells LangGraph:
# "when a node returns a new list for agent_log, ADD it — don't replace it."
# This prevents nodes from accidentally wiping each other's logs.

class PipelineState(TypedDict):
    question    : str
    subtasks    : list[str]      # Planner's output
    research    : dict[str, str] # Researcher's output: {subtask: finding}
    draft       : str            # Writer's first draft
    final_answer: str            # Critic-approved answer
    handoff_log : Annotated[list[str], operator.add]  # auto-appended


def _log(state: PipelineState, agent: str, msg: str) -> list[str]:
    entry = f"[{agent}] {msg}"
    print(f"  {entry}")
    return [entry]  # LangGraph will ADD this to handoff_log


# ── Planner: question → subtasks ──────────────────────────────────────────────

def planner(state: PipelineState) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=(
            "You are a task planner. Given a question, output a JSON array of "
            "3 research subtasks. Example: [\"Find X\", \"Explain Y\", \"Compare Z\"]"
            " Output ONLY the JSON array."
        ),
        messages=[{"role": "user", "content": state["question"]}],
    )
    import json, re
    text = response.content[0].text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    try:
        subtasks = json.loads(match.group()) if match else ["Research the topic", "Find examples", "Summarise findings"]
    except Exception:
        subtasks = ["Research the topic", "Find examples", "Summarise findings"]

    return {
        "subtasks"   : subtasks,
        "handoff_log": _log(state, "Planner", f"Created {len(subtasks)} subtasks"),
    }


# ── Researcher: subtasks → research findings ──────────────────────────────────

def researcher(state: PipelineState) -> dict:
    findings = {}
    for subtask in state["subtasks"]:
        response = client.messages.create(
            model=MODEL,
            max_tokens=200,
            system="You are a concise research assistant. Answer in 2-3 sentences.",
            messages=[{
                "role"   : "user",
                "content": f"Research subtask: {subtask}\nContext: {state['question']}",
            }],
        )
        findings[subtask] = response.content[0].text

    return {
        "research"   : findings,
        "handoff_log": _log(state, "Researcher", f"Completed {len(findings)} subtasks"),
    }


# ── Writer: question + research → draft ──────────────────────────────────────

def writer(state: PipelineState) -> dict:
    research_block = "\n\n".join(
        f"**{task}**\n{finding}"
        for task, finding in state["research"].items()
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=(
            "You are an academic writer. Synthesise the research notes into a "
            "clear, well-structured answer. Use the findings but write fluently."
        ),
        messages=[{
            "role"   : "user",
            "content": f"Question: {state['question']}\n\nResearch notes:\n{research_block}",
        }],
    )
    return {
        "draft"      : response.content[0].text,
        "handoff_log": _log(state, "Writer", "Draft completed"),
    }


# ── Critic: draft → final_answer ─────────────────────────────────────────────

def critic(state: PipelineState) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=(
            "You are a meticulous academic editor. "
            "Improve this draft: fix clarity, remove redundancy, "
            "ensure every claim is supported. Return the improved version only."
        ),
        messages=[{
            "role"   : "user",
            "content": f"Question: {state['question']}\n\nDraft:\n{state['draft']}",
        }],
    )
    return {
        "final_answer": response.content[0].text,
        "handoff_log" : _log(state, "Critic", "Final answer approved"),
    }


# ── Build and run ─────────────────────────────────────────────────────────────

def build_pipeline():
    g = StateGraph(PipelineState)
    g.add_node("planner",    planner)
    g.add_node("researcher", researcher)
    g.add_node("writer",     writer)
    g.add_node("critic",     critic)

    g.add_edge(START,        "planner")
    g.add_edge("planner",    "researcher")
    g.add_edge("researcher", "writer")
    g.add_edge("writer",     "critic")
    g.add_edge("critic",     END)

    return g.compile()


if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  AGENT HANDOFFS — 4-node pipeline")
    print("=" * 62)

    app = build_pipeline()
    question = "How does the immune system fight viral infections?"

    print(f"\n  Question: {question}\n")
    print("  Executing pipeline...")
    print()

    result = app.invoke({
        "question"    : question,
        "subtasks"    : [],
        "research"    : {},
        "draft"       : "",
        "final_answer": "",
        "handoff_log" : [],
    })

    print("\n" + "─" * 62)
    print("  HANDOFF LOG (what each agent saw and passed on):")
    print("─" * 62)
    for entry in result["handoff_log"]:
        print(f"  {entry}")

    print("\n" + "─" * 62)
    print("  FINAL ANSWER:")
    print("─" * 62)
    print(result["final_answer"])

    print("\n" + "=" * 62)
    print("  KEY INSIGHT — What makes handoffs work")
    print("=" * 62)
    print("""
  1. Each agent only reads the state fields IT needs:
       Planner    reads: question
       Researcher reads: question, subtasks
       Writer     reads: question, research
       Critic     reads: question, draft

  2. Each agent only writes the fields IT owns.
     Writing to another agent's field is a design smell.

  3. The Annotated[list, operator.add] pattern means logs
     accumulate correctly even if two agents run in parallel.

  Tomorrow (Day 4): the Researcher node gets real tools,
  and the state persists to ChromaDB between runs.
""")
