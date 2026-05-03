"""
CONCEPT 2 — System Prompt Engineering
======================================
The system prompt is the agent's identity card. It defines:
  • Role      — who the agent IS
  • Goal      — what it optimises for
  • Constraints — what it must NEVER do
  • Output format — how it should respond

This script runs the same question through three different system prompts
and prints the outputs side-by-side so you can see the difference.

Run:
    conda run -n bootcamp python day1/concepts/02_system_prompts.py
"""

from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"

QUESTION = "What causes inflation and how does it affect students?"

# ─────────────────────────────────────────────────────────────────────────────
# Three system prompts for the same agent — same model, different identity.
# ─────────────────────────────────────────────────────────────────────────────

PROMPTS = {

    "Generic (no engineering)": (
        "You are a helpful assistant."
    ),

    "Role + Goal (better)": (
        "You are an expert economics tutor at a top university. "
        "Your goal is to explain complex economic concepts clearly "
        "to first-year students who have no prior economics background. "
        "Use analogies and everyday examples."
    ),

    "Role + Goal + Constraints + Format (best)": (
        "You are an expert economics tutor at a top university.\n\n"
        "GOAL: Help first-year students understand economics using "
        "simple language, relatable analogies, and concrete examples.\n\n"
        "CONSTRAINTS:\n"
        "- Never use jargon without immediately explaining it\n"
        "- Never give advice about personal finances or investments\n"
        "- Never claim certainty on contested economic topics\n\n"
        "OUTPUT FORMAT:\n"
        "1. One-sentence plain-English definition\n"
        "2. How it works (3 bullet points max)\n"
        "3. What it means for students specifically\n"
        "4. One analogy that makes it click"
    ),
}


def ask(system_prompt: str, question: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text


def print_comparison(question: str) -> None:
    print("\n" + "=" * 62)
    print(f"  QUESTION: {question}")
    print("=" * 62)

    results = {}
    for name, prompt in PROMPTS.items():
        print(f"\n  Calling: {name}...")
        results[name] = ask(prompt, question)

    for name, answer in results.items():
        print("\n" + "─" * 62)
        print(f"  PROMPT: {name}")
        print("─" * 62)
        print(answer)

    print("\n" + "=" * 62)
    print("  WHAT TO NOTICE")
    print("=" * 62)
    print("""
  Generic:     Rambling, inconsistent structure, may use jargon.
  Role+Goal:   More focused tone, better audience calibration.
  Full:        Predictable structure, constraint-safe, scannable.

  The full prompt costs the same tokens as the generic one.
  Better prompts are free — they just require engineering.

  For your agent:
    system prompt = role + goal + constraints + output format
""")


if __name__ == "__main__":
    print_comparison(QUESTION)

    # Bonus: show prompt length vs output quality
    print("\n" + "─" * 62)
    print("  PROMPT LENGTH ANALYSIS")
    print("─" * 62)
    for name, prompt in PROMPTS.items():
        words = len(prompt.split())
        print(f"  {name[:45]:<45} {words:>3} words")
    print("""
  Takeaway: spending ~50 extra words on a system prompt reliably
  produces more useful, safer, and more consistent outputs.
""")
