"""
CONCEPT 3 — Chain-of-Thought vs Direct Answering
==================================================
CoT forces the model to reason BEFORE concluding.
This script runs the same hard question three ways:

  1. Direct    — just answer
  2. CoT       — think step by step
  3. Structured CoT — think in labelled stages (best for agents)

Then shows where Tree-of-Thought would go beyond CoT.

Run:
    conda run -n bootcamp python day1/concepts/03_chain_of_thought.py
"""

from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"

# A question that benefits from careful reasoning
QUESTION = (
    "A student has 3 assignments due. Essay (8hrs, worth 40%), "
    "Lab report (3hrs, worth 20%), Quiz (1hr, worth 10%). "
    "They have 6 hours left. What should they do and why?"
)


def ask(system_prompt: str, user_message: str) -> tuple[str, int]:
    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text, response.usage.output_tokens


# ── STYLE 1: Direct ──────────────────────────────────────────────────────────

DIRECT_SYSTEM = (
    "You are a university advisor. Answer student questions clearly and concisely."
)

# ── STYLE 2: Basic CoT ───────────────────────────────────────────────────────

COT_SYSTEM = (
    "You are a university advisor. "
    "Before answering, think step by step. "
    "Show your reasoning, then give a final recommendation."
)

# ── STYLE 3: Structured CoT (best for agents) ────────────────────────────────
# By labelling each phase we get consistent, parseable output.
# The agent pipeline can extract just the RECOMMENDATION section
# without re-prompting.

STRUCTURED_COT_SYSTEM = (
    "You are a university advisor. Always respond in this exact format:\n\n"
    "ANALYSIS:\n"
    "<break down the constraints and trade-offs>\n\n"
    "REASONING:\n"
    "<apply the constraints to rank options>\n\n"
    "RECOMMENDATION:\n"
    "<specific, actionable advice — what to do and in what order>\n\n"
    "CONFIDENCE: <High/Medium/Low — and why>"
)


def run_comparison() -> None:
    print("\n" + "=" * 62)
    print("  CHAIN-OF-THOUGHT COMPARISON")
    print("=" * 62)
    print(f"\n  Question: {QUESTION}\n")

    styles = [
        ("1. Direct (no CoT)",          DIRECT_SYSTEM),
        ("2. Basic CoT",                 COT_SYSTEM),
        ("3. Structured CoT",            STRUCTURED_COT_SYSTEM),
    ]

    token_counts = {}
    for name, system in styles:
        print(f"  Calling: {name}...")
        answer, tokens = ask(system, QUESTION)
        token_counts[name] = tokens

        print("\n" + "─" * 62)
        print(f"  {name}")
        print("─" * 62)
        print(answer)

    print("\n" + "=" * 62)
    print("  TOKEN USAGE (output tokens)")
    print("=" * 62)
    for name, count in token_counts.items():
        bar = "█" * (count // 10)
        print(f"  {name[:30]:<30} {count:>4} tokens  {bar}")

    print("\n" + "=" * 62)
    print("  WHAT TO NOTICE")
    print("=" * 62)
    print("""
  Direct:         Fast but shallow. May miss important trade-offs.
  Basic CoT:      Reasons more carefully but output format varies.
  Structured CoT: Predictable sections → easy to parse in code.
                  The agent pipeline can extract RECOMMENDATION
                  without an extra LLM call.

  Structured CoT uses more tokens but saves downstream calls.
  For agents, predictable output format > brevity.
""")


def explain_tot() -> None:
    print("=" * 62)
    print("  TREE-OF-THOUGHT — when CoT isn't enough")
    print("=" * 62)
    print("""
  CoT  = one chain:   Thought1 → Thought2 → Thought3 → Answer
  ToT  = branching:   Branch A ──→ Dead end (backtrack)
                      Branch B ──→ Dead end (backtrack)
                      Branch C ──→ Answer ✓

  Use ToT when:
    • The problem has multiple plausible strategies
    • Mistakes early invalidate the whole chain
    • You need verifiable correctness (math proofs, code puzzles)

  Practical ToT with Claude:
    1. Generate N candidate reasoning paths (temperature > 0)
    2. Evaluate each path with a critic prompt
    3. Select the path with the highest score

  For the university platform, CoT is enough — Day 2 onwards
  we focus on *tool use* rather than planning complexity.
""")


if __name__ == "__main__":
    run_comparison()
    explain_tot()
