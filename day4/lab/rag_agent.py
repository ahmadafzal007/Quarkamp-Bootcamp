"""
LAB 4a — Multi-Agent System with RAG Memory
=============================================
The Day 3 graph extended with:
  - ChromaDB persistent memory
  - Memory injection into the Researcher node
  - Auto-save every answered question to memory
  - /memory command to search past answers

Run:
    conda run -n bootcamp python day4/lab/rag_agent.py
"""

import json
import re
import operator
import datetime
import uuid
from pathlib import Path
from typing import TypedDict, Annotated, Literal
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
import chromadb
from sentence_transformers import SentenceTransformer
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client   = anthropic.Anthropic()

# ── Memory layer ──────────────────────────────────────────────────────────────

CHROMA_PATH = Path(__file__).parents[2] / "data" / "chroma"
CHROMA_PATH.mkdir(parents=True, exist_ok=True)

print("  Initialising memory layer...")
embedder   = SentenceTransformer("all-MiniLM-L6-v2")
chroma     = chromadb.PersistentClient(path=str(CHROMA_PATH))
collection = chroma.get_or_create_collection("assignment_memory")
print(f"  Memory loaded: {collection.count()} stored answer(s).")


def memory_retrieve(query: str, n: int = 3) -> list[str]:
    if collection.count() == 0:
        return []
    q_embed = embedder.encode(query).tolist()
    results = collection.query(query_embeddings=[q_embed], n_results=min(n, collection.count()))
    return results["documents"][0]


def memory_store(question: str, answer: str, score: int) -> None:
    doc_id = str(uuid.uuid4())
    text   = f"Q: {question}\nA: {answer}"
    collection.upsert(
        ids        = [doc_id],
        embeddings = [embedder.encode(text).tolist()],
        documents  = [text],
        metadatas  = [{"question": question[:200], "score": score, "timestamp": datetime.datetime.now().isoformat()}],
    )


# ── Models ────────────────────────────────────────────────────────────────────

MODEL_FAST     = "claude-haiku-4-5"
MODEL_BALANCED = "claude-sonnet-4-6"


# ── State ─────────────────────────────────────────────────────────────────────

class AssignmentState(TypedDict):
    question       : str
    memory_context : list[str]
    subtasks       : list[str]
    research       : dict[str, str]
    draft          : str
    critique       : str
    final_answer   : str
    quality_score  : int
    revision_count : int
    agent_log      : Annotated[list[str], operator.add]


def _call(model, system, user, max_tokens=600):
    return client.messages.create(
        model=model, max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    ).content[0].text


def _log(agent, msg):
    entry = f"[{agent}] {msg}"
    print(f"  {entry}")
    return [entry]


# ── Nodes ─────────────────────────────────────────────────────────────────────

def memory_retrieval_node(state: AssignmentState) -> dict:
    """NEW: retrieve similar past Q&As before any agent runs."""
    past = memory_retrieve(state["question"])
    return {
        "memory_context": past,
        "agent_log"     : _log("Memory", f"Retrieved {len(past)} similar past answer(s)"),
    }


def planner_node(state: AssignmentState) -> dict:
    context_hint = ""
    if state["memory_context"]:
        context_hint = (
            f"\n\nSimilar past answers from memory:\n"
            + "\n".join(f"  - {c[:100]}" for c in state["memory_context"])
        )
    result = _call(
        MODEL_BALANCED,
        system='Output ONLY a JSON array of 3 research subtasks. Example: ["task1","task2"]',
        user=state["question"] + context_hint,
        max_tokens=200,
    )
    match = re.search(r"\[.*\]", result, re.DOTALL)
    try:
        subtasks = json.loads(match.group()) if match else ["Research the topic", "Find examples", "Summarise"]
    except Exception:
        subtasks = ["Research the topic", "Find examples", "Summarise"]
    return {"subtasks": subtasks, "agent_log": _log("Planner", f"{len(subtasks)} subtasks")}


def researcher_node(state: AssignmentState) -> dict:
    findings = {}
    # Inject memory context for relevant subtasks
    memory_block = ""
    if state["memory_context"]:
        memory_block = "\n\nRelevant past knowledge:\n" + "\n".join(
            f"  {c[:150]}" for c in state["memory_context"]
        )

    for subtask in state["subtasks"]:
        finding = _call(
            MODEL_BALANCED,
            system="You are a research assistant. Answer in 3-4 precise sentences.",
            user=f"Subtask: {subtask}\nContext: {state['question']}{memory_block}",
            max_tokens=250,
        )
        findings[subtask] = finding

    return {"research": findings, "agent_log": _log("Researcher", f"{len(findings)} findings")}


def writer_node(state: AssignmentState) -> dict:
    notes = "\n\n".join(f"• {t}:\n  {f}" for t, f in state["research"].items())
    critique = f"\n\nAddress this critique:\n{state['critique']}" if state.get("critique") and state["revision_count"] > 0 else ""
    draft = _call(
        MODEL_BALANCED,
        system="Write a clear, structured academic answer. Intro → main points → conclusion.",
        user=f"Question: {state['question']}\n\nResearch:\n{notes}{critique}",
        max_tokens=800,
    )
    return {"draft": draft, "agent_log": _log("Writer", f"Draft #{state['revision_count'] + 1}")}


def critic_node(state: AssignmentState) -> dict:
    result = _call(
        MODEL_FAST,
        system="Reply ONLY in this format:\nScore: X/10\nStrengths: ...\nWeaknesses: ...\nVerdict: PASS or REVISE",
        user=f"Question: {state['question']}\n\nAnswer:\n{state['draft']}",
        max_tokens=150,
    )
    try:
        score = int(re.search(r"Score:\s*(\d+)", result).group(1))
    except Exception:
        score = 7

    updates: dict = {
        "critique"     : result,
        "quality_score": score,
        "agent_log"    : _log("Critic", f"Score {score}/10"),
    }
    if score >= 7 or state["revision_count"] >= 2:
        updates["final_answer"] = state["draft"]
    return updates


def memory_save_node(state: AssignmentState) -> dict:
    """NEW: save the final answer to ChromaDB."""
    if state.get("final_answer"):
        memory_store(state["question"], state["final_answer"], state["quality_score"])
        return {"agent_log": _log("Memory", f"Saved to ChromaDB (score {state['quality_score']}/10)")}
    return {"agent_log": _log("Memory", "Nothing to save yet")}


def should_revise(state: AssignmentState) -> Literal["writer", "__end__"]:
    if state["quality_score"] < 7 and state["revision_count"] < 2:
        return "writer"
    return END


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AssignmentState)
    g.add_node("memory_retrieve", memory_retrieval_node)
    g.add_node("planner",         planner_node)
    g.add_node("researcher",      researcher_node)
    g.add_node("writer",          writer_node)
    g.add_node("critic",          critic_node)
    g.add_node("memory_save",     memory_save_node)

    g.add_edge(START,              "memory_retrieve")
    g.add_edge("memory_retrieve",  "planner")
    g.add_edge("planner",          "researcher")
    g.add_edge("researcher",       "writer")
    g.add_edge("writer",           "critic")
    g.add_conditional_edges("critic", should_revise, {"writer": "writer", END: "memory_save"})
    g.add_edge("memory_save",      END)
    return g.compile()


app = build_graph()


def run(question: str) -> AssignmentState:
    return app.invoke({
        "question"      : question,
        "memory_context": [],
        "subtasks"      : [],
        "research"      : {},
        "draft"         : "",
        "critique"      : "",
        "final_answer"  : "",
        "quality_score" : 0,
        "revision_count": 0,
        "agent_log"     : [],
    })


def search_memory(query: str) -> None:
    results = memory_retrieve(query, n=5)
    if not results:
        print("  No memory yet. Ask some questions first!")
        return
    print(f"\n  Top {len(results)} similar past answer(s):")
    for i, r in enumerate(results, 1):
        lines = r.split("\n")
        q_line = next((l for l in lines if l.startswith("Q:")), lines[0])
        print(f"  [{i}] {q_line[:80]}")


def main():
    print("\n" + "═" * 62)
    print("  AssignmentBot v4 — Multi-Agent + RAG Memory")
    print(f"  Memory: ChromaDB at {CHROMA_PATH}")
    print("  Commands: /memory <query>, /quit")
    print("═" * 62 + "\n")

    while True:
        try:
            q = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not q:
            continue
        if q == "/quit":
            break
        if q.startswith("/memory"):
            query = q[7:].strip() or "any topic"
            search_memory(query)
            continue

        print()
        result = run(q)
        print("\n" + "═" * 60)
        print("  FINAL ANSWER")
        print("═" * 60)
        print(result["final_answer"])
        print(f"\n  Score: {result['quality_score']}/10  |  Memory: {collection.count()} stored")
        print()


if __name__ == "__main__":
    main()
