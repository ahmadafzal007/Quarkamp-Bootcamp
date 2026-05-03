"""
LAB 1 — Assignment Agent v1
=============================
Your first complete agent. It:
  • Receives an assignment question (PERCEPTION)
  • Breaks it into a step-by-step plan (PLANNING / CoT)
  • Executes the plan with Claude (ACTION)
  • Self-critiques the answer (REFLECTION)
  • Stores the result in session memory (MEMORY)

This is the foundation. Every day we add one more layer on top.

Run:
    conda run -n bootcamp python day1/lab/assignment_agent_v1.py

After Day 2  → agent gains tools (web search, calculator)
After Day 3  → agent becomes a 5-node LangGraph pipeline
After Day 4  → memory upgrades from a list to ChromaDB
After Day 5  → this runs behind a React UI via FastAPI
"""

import os
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")

# ── Agent identity ────────────────────────────────────────────────────────────

AGENT_NAME    = "AssignmentBot v1"
AGENT_VERSION = "1.0.0"
MODEL         = "claude-haiku-4-5"

SYSTEM_PROMPT = """\
You are AssignmentBot — an expert academic assistant for university students.

ROLE: Help students understand and answer their assignments at a deep level.

GOAL: Produce clear, accurate, well-structured answers that help the student
genuinely understand the topic, not just copy an answer.

CONSTRAINTS:
- Never write an assignment *for* the student verbatim — explain and guide.
- Never claim certainty on contested academic topics; signal uncertainty.
- Never give medical, legal, or financial advice even if asked as homework.
- Always cite reasoning, not just conclusions.

OUTPUT FORMAT:
## Understanding the Question
<what the question is really asking>

## Step-by-Step Answer
<numbered steps, each with explanation>

## Key Takeaway
<one sentence the student should remember>
"""

# ── Memory (Day 1: in-process list; Day 4: upgrades to ChromaDB) ─────────────

class SessionMemory:
    def __init__(self):
        self._store: list[dict] = []

    def save(self, question: str, answer: str, score: int) -> None:
        self._store.append({
            "id"       : len(self._store) + 1,
            "question" : question,
            "answer"   : answer[:200] + "..." if len(answer) > 200 else answer,
            "score"    : score,
            "timestamp": datetime.datetime.now().isoformat(),
        })

    def recall_recent(self, n: int = 3) -> list[dict]:
        return self._store[-n:]

    def __len__(self):
        return len(self._store)


memory = SessionMemory()
client = anthropic.Anthropic()


# ── PPARM phases ──────────────────────────────────────────────────────────────

def perceive(raw_input: str) -> dict:
    return {
        "raw_input"  : raw_input.strip(),
        "word_count" : len(raw_input.split()),
        "timestamp"  : datetime.datetime.now().isoformat(),
    }


def plan(perception: dict) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=(
            "You are a planning assistant. Given an assignment question, "
            "list 3-5 concrete steps to answer it thoroughly. One line per step."
        ),
        messages=[{
            "role"   : "user",
            "content": f"Assignment question: {perception['raw_input']}",
        }],
    )
    return response.content[0].text


def act(perception: dict, plan_text: str, recent_context: list[dict]) -> str:
    context_block = ""
    if recent_context:
        context_block = "\n\nPrevious questions this session (for context only):\n"
        for item in recent_context:
            context_block += f"- {item['question']}\n"

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role"   : "user",
            "content": (
                f"Plan:\n{plan_text}"
                f"{context_block}\n\n"
                f"Question: {perception['raw_input']}"
            ),
        }],
    )
    return response.content[0].text


def reflect(answer: str, question: str) -> tuple[str, int]:
    response = client.messages.create(
        model=MODEL,
        max_tokens=150,
        system=(
            "You are a strict academic evaluator. "
            "Reply in this exact format only:\n"
            "Score: X/10\n"
            "Issue: <one specific problem or 'None'>\n"
            "Fix: <one-sentence improvement or 'N/A'>"
        ),
        messages=[{
            "role"   : "user",
            "content": f"Question: {question}\n\nAnswer:\n{answer}",
        }],
    )
    feedback = response.content[0].text
    try:
        score_line = [l for l in feedback.splitlines() if l.startswith("Score:")][0]
        score = int(score_line.split("/")[0].replace("Score:", "").strip())
    except (IndexError, ValueError):
        score = 7
    return feedback, score


# ── CLI interface ─────────────────────────────────────────────────────────────

def print_header() -> None:
    print("\n" + "═" * 62)
    print(f"  {AGENT_NAME}  (v{AGENT_VERSION})")
    print(f"  Model: {MODEL}  |  Type /help for commands")
    print("═" * 62 + "\n")


def print_help() -> None:
    print("""
  Commands:
    /history    — show questions answered this session
    /clear      — clear session memory
    /quit       — exit
    <anything else> — treated as an assignment question
""")


def run_agent(question: str) -> None:
    print(f"\n  [1/5] Perceiving...")
    p = perceive(question)

    print(f"  [2/5] Planning (CoT)...")
    plan_text = plan(p)
    print(f"        Plan: {plan_text.splitlines()[0]}...")

    print(f"  [3/5] Acting...")
    context = memory.recall_recent(3)
    answer = act(p, plan_text, context)

    print(f"  [4/5] Reflecting...")
    feedback, score = reflect(answer, question)

    print(f"  [5/5] Storing in memory...")
    memory.save(question, answer, score)

    print("\n" + "─" * 62)
    print(answer)
    print("\n" + "─" * 62)
    print(f"  Self-critique: {feedback}")
    print(f"  Memory: {len(memory)} item(s) stored this session.")
    print("─" * 62)


def main() -> None:
    print_header()
    print("  Ask any assignment question. Type /help for commands.\n")

    while True:
        try:
            user_input = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("\n  Goodbye!")
            break

        if user_input == "/help":
            print_help()
            continue

        if user_input == "/history":
            items = memory.recall_recent(10)
            if not items:
                print("\n  No history yet.\n")
            else:
                print("\n  Session history:")
                for item in items:
                    print(f"  [{item['id']}] (score {item['score']}/10) {item['question'][:60]}")
                print()
            continue

        if user_input == "/clear":
            memory._store.clear()
            print("\n  Memory cleared.\n")
            continue

        run_agent(user_input)


if __name__ == "__main__":
    main()
