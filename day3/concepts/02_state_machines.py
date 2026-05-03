"""
CONCEPT 2 — Conditional Edges and State Machines
==================================================
A "state machine" routes differently based on the current state.
LangGraph supports conditional edges: the next node depends on a condition.

This script shows:
  - conditional_edge: route to A or B based on a function
  - loops: a node can send execution back to an earlier node
  - END: how to terminate the graph

Use case: Orchestrator decides whether to use the simple path or
the research path based on question complexity.

Run:
    conda run -n bootcamp python day3/concepts/02_state_machines.py
"""

from pathlib import Path
from typing import TypedDict, Literal
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"


class AssignmentState(TypedDict):
    question    : str
    complexity  : str    # "simple" or "complex" — set by Orchestrator
    answer      : str
    revision_count: int
    quality_score : int
    agent_log   : list[str]


# ── Nodes ─────────────────────────────────────────────────────────────────────

def orchestrator_node(state: AssignmentState) -> dict:
    """Classifies the question: simple (direct answer) or complex (needs research)."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=20,
        system=(
            "Classify this question as SIMPLE or COMPLEX.\n"
            "SIMPLE = can be answered from general knowledge in 2-3 sentences.\n"
            "COMPLEX = requires research, calculations, or multi-step reasoning.\n"
            "Reply with one word only: SIMPLE or COMPLEX"
        ),
        messages=[{"role": "user", "content": state["question"]}],
    )
    complexity = response.content[0].text.strip().upper()
    if complexity not in ("SIMPLE", "COMPLEX"):
        complexity = "COMPLEX"
    print(f"  [Orchestrator] Complexity: {complexity}")
    return {
        "complexity": complexity.lower(),
        "agent_log" : state["agent_log"] + [f"Orchestrator({complexity})"],
    }


def quick_answer_node(state: AssignmentState) -> dict:
    """Fast path for simple questions."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system="Answer this university question clearly and concisely.",
        messages=[{"role": "user", "content": state["question"]}],
    )
    print(f"  [QuickAnswer] Answered directly.")
    return {
        "answer"   : response.content[0].text,
        "quality_score": 8,  # assumed good for simple questions
        "agent_log": state["agent_log"] + ["QuickAnswer"],
    }


def deep_research_node(state: AssignmentState) -> dict:
    """Slow path for complex questions — more thorough."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=700,
        system=(
            "You are a thorough academic researcher. "
            "Provide a detailed, well-structured answer with examples."
        ),
        messages=[{"role": "user", "content": state["question"]}],
    )
    print(f"  [DeepResearch] Produced detailed answer.")
    return {
        "answer"   : response.content[0].text,
        "agent_log": state["agent_log"] + ["DeepResearch"],
    }


def critic_node(state: AssignmentState) -> dict:
    """Scores the answer. If score < 7, the Writer will revise."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=50,
        system="Score this answer 1-10. Reply with only the integer number.",
        messages=[{
            "role"   : "user",
            "content": f"Question: {state['question']}\nAnswer: {state['answer'][:300]}",
        }],
    )
    try:
        score = int(response.content[0].text.strip())
    except ValueError:
        score = 7

    print(f"  [Critic] Score: {score}/10  |  Revisions so far: {state['revision_count']}")
    return {
        "quality_score": score,
        "agent_log"    : state["agent_log"] + [f"Critic(score={score})"],
    }


def revise_node(state: AssignmentState) -> dict:
    """Improves a low-scoring answer."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=700,
        system="Improve this answer. Make it clearer, more accurate, and better structured.",
        messages=[{
            "role"   : "user",
            "content": f"Question: {state['question']}\nCurrent answer: {state['answer']}\nImprove it.",
        }],
    )
    print(f"  [Revise] Improved the answer.")
    return {
        "answer"        : response.content[0].text,
        "revision_count": state["revision_count"] + 1,
        "agent_log"     : state["agent_log"] + ["Revise"],
    }


# ── Conditional edge functions ────────────────────────────────────────────────

def route_by_complexity(state: AssignmentState) -> Literal["quick_answer", "deep_research"]:
    """After Orchestrator: route to the right answering path."""
    if state["complexity"] == "simple":
        return "quick_answer"
    return "deep_research"


def route_after_critic(state: AssignmentState) -> Literal["revise", "__end__"]:
    """After Critic: revise if score is low AND we haven't revised too many times."""
    if state["quality_score"] < 7 and state["revision_count"] < 2:
        print(f"  [Router] Score {state['quality_score']} < 7 → sending back for revision")
        return "revise"
    print(f"  [Router] Score {state['quality_score']} ≥ 7 (or max revisions) → finishing")
    return END


# ── Build the graph ───────────────────────────────────────────────────────────

def build_conditional_graph():
    graph = StateGraph(AssignmentState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("quick_answer", quick_answer_node)
    graph.add_node("deep_research", deep_research_node)
    graph.add_node("critic",       critic_node)
    graph.add_node("revise",       revise_node)

    graph.add_edge(START, "orchestrator")

    # Conditional: after Orchestrator, go to quick_answer OR deep_research
    graph.add_conditional_edges("orchestrator", route_by_complexity)

    # Both paths converge at critic
    graph.add_edge("quick_answer",  "critic")
    graph.add_edge("deep_research", "critic")

    # Conditional loop: critic → revise OR end
    graph.add_conditional_edges("critic", route_after_critic)

    # After revision, re-evaluate
    graph.add_edge("revise", "critic")

    return graph.compile()


if __name__ == "__main__":
    app = build_conditional_graph()

    test_cases = [
        ("Simple question:", "What is the capital of France?"),
        ("Complex question:", "Explain how CRISPR-Cas9 gene editing works and its ethical implications."),
    ]

    for label, question in test_cases:
        print("\n" + "=" * 62)
        print(f"  {label}")
        print(f"  {question}")
        print("=" * 62)

        result = app.invoke({
            "question"      : question,
            "complexity"    : "",
            "answer"        : "",
            "revision_count": 0,
            "quality_score" : 0,
            "agent_log"     : [],
        })

        print(f"\n  Path taken: {' → '.join(result['agent_log'])}")
        print(f"  Final score: {result['quality_score']}/10")
        print(f"  Answer preview: {result['answer'][:120]}...")

    print("\n" + "=" * 62)
    print("  KEY INSIGHT")
    print("=" * 62)
    print("""
  Conditional edges = routing logic pulled out of the agent.
  The Critic node doesn't need to know it might loop — the graph
  handles the routing based on the state values.

  This separation means:
    - You can change the routing rule without touching any agent
    - You can test the Critic in isolation with a fake state
    - The loop automatically terminates via the max-revision guard
""")
