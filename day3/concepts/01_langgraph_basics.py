"""
CONCEPT 1 — LangGraph Basics
==============================
LangGraph lets you build agent pipelines as directed graphs.
Each node is a Python function. State flows between nodes as a dict.

This script builds the simplest possible graph: two nodes, one edge.
  START → node_a → node_b → END

Run:
    conda run -n bootcamp python day3/concepts/01_langgraph_basics.py
"""

from pathlib import Path
from typing import TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"


# ── STEP 1: Define the State ──────────────────────────────────────────────────
# The State is a TypedDict — every node reads from it and writes to it.
# Think of it as a shared notepad that flows through the graph.

class AssignmentState(TypedDict):
    question    : str       # set by the user (never changes)
    plan        : str       # set by the Planner node
    answer      : str       # set by the Writer node
    agent_log   : list[str] # every node appends its name here


# ── STEP 2: Define nodes (each node is a function) ────────────────────────────
# Each node:
#   - receives the current state
#   - does its work
#   - returns a DICT of only the fields it wants to update

def planner_node(state: AssignmentState) -> dict:
    print("  [Planner] Running...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system="You are a planning assistant. List 3 steps to answer the question. Be brief.",
        messages=[{"role": "user", "content": state["question"]}],
    )
    plan = response.content[0].text
    print(f"  [Planner] Plan created: {plan[:60]}...")
    return {
        "plan"     : plan,
        "agent_log": state["agent_log"] + ["Planner"],
    }


def writer_node(state: AssignmentState) -> dict:
    print("  [Writer] Running...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system="You are a university writing assistant. Follow the plan and answer clearly.",
        messages=[{
            "role"   : "user",
            "content": f"Plan:\n{state['plan']}\n\nQuestion:\n{state['question']}",
        }],
    )
    answer = response.content[0].text
    print(f"  [Writer] Answer drafted: {answer[:60]}...")
    return {
        "answer"   : answer,
        "agent_log": state["agent_log"] + ["Writer"],
    }


# ── STEP 3: Build the graph ───────────────────────────────────────────────────

def build_simple_graph() -> StateGraph:
    graph = StateGraph(AssignmentState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("writer",  writer_node)

    # Add edges: START → planner → writer → END
    graph.add_edge(START,     "planner")
    graph.add_edge("planner", "writer")
    graph.add_edge("writer",  END)

    return graph.compile()


# ── STEP 4: Run the graph ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  LANGGRAPH BASICS — 2-node pipeline")
    print("=" * 62)

    app = build_simple_graph()

    initial_state: AssignmentState = {
        "question"  : "Explain the difference between mitosis and meiosis.",
        "plan"      : "",
        "answer"    : "",
        "agent_log" : [],
    }

    print(f"\n  Input: {initial_state['question']}\n")
    print("  Running graph...")

    result = app.invoke(initial_state)

    print("\n" + "─" * 62)
    print("  RESULT")
    print("─" * 62)
    print(f"  Agents ran: {' → '.join(result['agent_log'])}")
    print(f"\n  Answer:\n{result['answer']}")

    print("\n" + "=" * 62)
    print("  KEY INSIGHT")
    print("=" * 62)
    print("""
  The state dict is the "baton" passed between nodes.

  Each node only knows about the state — not about other nodes.
  This means you can:
    - Test each node independently
    - Swap a node without changing others
    - Add a new node anywhere in the graph

  Tomorrow (Day 4) we add memory: the state persists across
  graph runs by saving/loading from ChromaDB.
""")
