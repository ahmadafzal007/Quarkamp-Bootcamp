"""
CONCEPT 1 — The ReAct Pattern
==============================
ReAct = Reason + Act (interleaved)

Instead of planning once and acting once (Day 1), a ReAct agent:
  1. Thinks about what to do (Thought)
  2. Calls a tool (Action)
  3. Reads the result (Observation)
  4. Loops back to step 1 until it has an answer

This script implements ReAct from scratch using a MOCK tool so you
can see the loop mechanics without needing real API keys for the tools.

Run:
    conda run -n bootcamp python day2/concepts/01_react_pattern.py
"""

from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"

# ── Mock tools (no real API keys needed for this concept demo) ────────────────

MOCK_TOOL_RESPONSES = {
    "web_search": {
        "climate change effects students": (
            "Students face disrupted academic calendars from extreme weather events. "
            "University campuses see increased energy costs. Mental health impacts "
            "from eco-anxiety are rising among 18-25 year olds. Source: UNESCO 2024."
        ),
        "default": "Search results: multiple relevant articles found on this topic.",
    },
    "calculator": {
        "2+2": "4",
        "default": "Result: 42",
    },
}

def mock_tool(name: str, inputs: dict) -> str:
    """Simulates tool execution without real API calls."""
    if name == "calculator":
        try:
            expr = inputs.get("expression", "")
            safe_chars = set("0123456789+-*/.(). ")
            if all(c in safe_chars for c in expr):
                return f"Result: {eval(expr)}"  # noqa: S307
        except Exception:
            pass
        return "Result: calculation failed"

    if name == "web_search":
        query = inputs.get("query", "").lower()
        for key, val in MOCK_TOOL_RESPONSES["web_search"].items():
            if key != "default" and key in query:
                return val
        return MOCK_TOOL_RESPONSES["web_search"]["default"]

    return f"Tool '{name}' returned: {inputs}"


# ── Tool definitions (the schema Claude sees) ─────────────────────────────────

TOOLS = [
    {
        "name"       : "web_search",
        "description": "Search the web for current information on a topic.",
        "input_schema": {
            "type"      : "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required"  : ["query"],
        },
    },
    {
        "name"       : "calculator",
        "description": "Evaluate a mathematical expression. Use for any arithmetic.",
        "input_schema": {
            "type"      : "object",
            "properties": {"expression": {"type": "string", "description": "Math expression e.g. '12 * 8 / 3'"}},
            "required"  : ["expression"],
        },
    },
]

# ── ReAct loop ─────────────────────────────────────────────────────────────────

def react(question: str, max_iterations: int = 5) -> str:
    print("\n" + "═" * 62)
    print(f"  REACT LOOP — max {max_iterations} iterations")
    print("═" * 62)
    print(f"\n  Question: {question}\n")

    messages = [{"role": "user", "content": question}]
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"┌─ ITERATION {iteration} " + "─" * (49 - len(str(iteration))))

        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            tools=TOOLS,
            messages=messages,
        )

        # Add Claude's response to message history
        messages.append({"role": "assistant", "content": response.content})

        # ── Check stop reason ─────────────────────────────────────────────────
        if response.stop_reason == "end_turn":
            # Claude decided it has a final answer
            final_text = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            print(f"│  THOUGHT: {final_text[:120]}...")
            print(f"│  → Stop reason: end_turn (Claude has an answer)")
            print("└" + "─" * 61)
            return final_text

        if response.stop_reason == "tool_use":
            # Claude wants to call one or more tools
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name   = block.name
                    tool_inputs = block.input

                    print(f"│  ACTION: {tool_name}({tool_inputs})")
                    observation = mock_tool(tool_name, tool_inputs)
                    print(f"│  OBSERVATION: {observation[:100]}")

                    tool_results.append({
                        "type"       : "tool_result",
                        "tool_use_id": block.id,
                        "content"    : observation,
                    })

            print("└" + "─" * 61)

            # Feed the observations back as a user message
            messages.append({"role": "user", "content": tool_results})

    return "Max iterations reached. Partial answer based on gathered information."


if __name__ == "__main__":
    # Question that benefits from tool use
    answer = react("How does climate change affect university students, and what percentage of the global population are students?")

    print("\n" + "=" * 62)
    print("  FINAL ANSWER")
    print("=" * 62)
    print(answer)

    print("\n" + "=" * 62)
    print("  KEY INSIGHT")
    print("=" * 62)
    print("""
  Notice how Claude:
  1. Decided to search rather than hallucinate
  2. Read the search result
  3. Used the result to give a grounded answer

  This is fundamentally different from Day 1's plan-then-act:
    Day 1: Plan once → Act once → Done
    Day 2: Think → Act → Observe → Think again → ... → Done

  The loop continues until Claude says "I have enough information."
  The max_iterations guardrail prevents infinite loops.
""")
