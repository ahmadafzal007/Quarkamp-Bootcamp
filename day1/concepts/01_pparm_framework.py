"""
CONCEPT 1 — The PPARM Framework
================================
Every agentic AI system has five layers. This script walks through each one
with live Claude API calls so you can SEE what each phase does.

Run:
    conda run -n bootcamp python day1/concepts/01_pparm_framework.py
"""

import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic

# Load .env from the project root (works from any subdirectory)
load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"   # fast + cheap for learning

QUESTION = "Explain Newton's three laws of motion with a real-world example for each."

# ─────────────────────────────────────────────────────────────────────────────
# P — PERCEPTION
# The agent receives input and turns it into structured data.
# In a real product this might include image parsing, audio transcription,
# API responses, database rows, etc.
# ─────────────────────────────────────────────────────────────────────────────

def perceive(raw_input: str) -> dict:
    perception = {
        "raw_input"  : raw_input,
        "type"       : "assignment_question",
        "word_count" : len(raw_input.split()),
        "timestamp"  : datetime.datetime.now().isoformat(),
    }
    print("\n┌─ PERCEPTION " + "─" * 48)
    for k, v in perception.items():
        print(f"│  {k}: {v}")
    print("└" + "─" * 61)
    return perception


# ─────────────────────────────────────────────────────────────────────────────
# P — PLANNING
# Before acting, a smart agent breaks the task into steps.
# This is where Chain-of-Thought (CoT) happens.
# Cheaper to plan first and act once than to act blindly and retry.
# ─────────────────────────────────────────────────────────────────────────────

def plan(perception: dict) -> str:
    print("\n┌─ PLANNING " + "─" * 50)
    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=(
            "You are a planning assistant. "
            "Given a task, produce a numbered list of 3-5 steps to answer it well. "
            "Be concise — one line per step."
        ),
        messages=[{
            "role"   : "user",
            "content": f"Task: {perception['raw_input']}",
        }],
    )
    plan_text = response.content[0].text
    print("│\n" + "\n".join(f"│  {line}" for line in plan_text.splitlines()))
    print("└" + "─" * 61)
    return plan_text


# ─────────────────────────────────────────────────────────────────────────────
# A — ACTION
# The agent executes its plan.
# On Day 1: one LLM call.
# On Day 2: LLM call + real tool calls (web search, calculator, etc.).
# ─────────────────────────────────────────────────────────────────────────────

def act(perception: dict, plan_text: str) -> str:
    print("\n┌─ ACTION " + "─" * 52)
    print("│  Calling Claude with the plan as context...")
    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=(
            "You are a university assignment assistant. "
            "Follow the provided plan exactly. "
            "Write clearly for a first-year university student."
        ),
        messages=[{
            "role"   : "user",
            "content": (
                f"Plan to follow:\n{plan_text}\n\n"
                f"Question to answer:\n{perception['raw_input']}"
            ),
        }],
    )
    answer = response.content[0].text
    print("│  ✓ Response received")
    print("│  Tokens used:", response.usage.input_tokens, "in /", response.usage.output_tokens, "out")
    print("└" + "─" * 61)
    return answer


# ─────────────────────────────────────────────────────────────────────────────
# R — REFLECTION
# The agent evaluates its own output.
# A low score could trigger a retry or escalation to a more powerful model.
# ─────────────────────────────────────────────────────────────────────────────

def reflect(answer: str, original_question: str) -> dict:
    print("\n┌─ REFLECTION " + "─" * 47)
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=(
            "You are a strict academic evaluator. "
            "Score the answer 1-10 and give ONE specific improvement suggestion. "
            "Format: Score: X/10 | Suggestion: <one sentence>"
        ),
        messages=[{
            "role"   : "user",
            "content": f"Question: {original_question}\n\nAnswer:\n{answer}",
        }],
    )
    feedback = response.content[0].text
    print(f"│  {feedback}")
    print("└" + "─" * 61)
    return {"feedback": feedback, "answer": answer}


# ─────────────────────────────────────────────────────────────────────────────
# M — MEMORY
# Day 1: simple Python list (in-process, lost on exit).
# Day 3: state dict flowing through LangGraph.
# Day 4: ChromaDB vector store — persists across sessions.
# ─────────────────────────────────────────────────────────────────────────────

_session_memory: list[dict] = []

def remember(perception: dict, result: dict) -> None:
    _session_memory.append({
        "question": perception["raw_input"],
        "answer"  : result["answer"][:120] + "...",
        "saved_at": datetime.datetime.now().isoformat(),
    })
    print(f"\n┌─ MEMORY " + "─" * 52)
    print(f"│  Stored entry #{len(_session_memory)} in session memory.")
    print(f"│  Total items in memory: {len(_session_memory)}")
    print("└" + "─" * 61)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — run the full PPARM loop
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  PPARM FRAMEWORK DEMO")
    print("  Watch each phase execute in sequence.")
    print("=" * 62)
    print(f"\nQuestion: \"{QUESTION}\"")

    perception = perceive(QUESTION)
    plan_text  = plan(perception)
    answer     = act(perception, plan_text)
    result     = reflect(answer, QUESTION)
    remember(perception, result)

    print("\n" + "=" * 62)
    print("  FINAL ANSWER")
    print("=" * 62)
    print(result["answer"])
    print("\n" + "=" * 62)
    print("  KEY INSIGHT")
    print("=" * 62)
    print("""
  Without planning (P), the action (A) is often shallow.
  Without reflection (R), bad answers are never caught.
  Without memory (M), the agent forgets everything on restart.

  Day 2 adds real tools to the Action phase.
  Day 3 splits each phase across specialised agents.
  Day 4 upgrades Memory from a list → a vector database.
""")
