"""
CONCEPT 3 — Tool Execution and Observation Parsing
====================================================
After Claude calls a tool, YOU run the actual code and return the result.
This script shows the complete execution cycle:

  1. Claude asks for a tool call
  2. You detect the tool_use block
  3. You run the real function
  4. You return the result as a tool_result message
  5. Claude reads the observation and continues

Also covers: error handling, timeouts, and structured vs unstructured observations.

Run:
    conda run -n bootcamp python day2/concepts/03_tool_schemas.py
"""

import json
import math
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"


# ── Real tool implementations ─────────────────────────────────────────────────

def safe_calculator(expression: str) -> str:
    """Evaluate a math expression safely."""
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return "Error: only basic arithmetic allowed"
    try:
        result = eval(expression, {"__builtins__": {}}, {"sqrt": math.sqrt, "pi": math.pi})  # noqa: S307
        return f"{result}"
    except Exception as e:
        return f"Error: {e}"


def word_count(text: str) -> str:
    """Count words, sentences, and estimate reading time."""
    words     = len(text.split())
    sentences = text.count(".") + text.count("!") + text.count("?")
    read_time = max(1, round(words / 200))  # ~200 wpm average
    return json.dumps({
        "words"    : words,
        "sentences": sentences,
        "read_time_minutes": read_time,
    })


def get_assignment_info(subject: str) -> str:
    """Mock university database lookup."""
    db = {
        "physics"  : {"due": "2025-05-10", "type": "Lab Report", "weight": "25%"},
        "history"  : {"due": "2025-05-08", "type": "Essay",      "weight": "40%"},
        "math"     : {"due": "2025-05-12", "type": "Problem Set", "weight": "15%"},
    }
    key = subject.lower().strip()
    if key in db:
        return json.dumps(db[key])
    return json.dumps({"error": f"No assignment found for subject: {subject}"})


# ── Tool registry — maps tool names to functions ─────────────────────────────

TOOL_REGISTRY = {
    "calculator"         : safe_calculator,
    "word_count"         : word_count,
    "get_assignment_info": get_assignment_info,
}

TOOLS = [
    {
        "name"        : "calculator",
        "description" : "Evaluate math expressions. Supports +, -, *, /, %, sqrt, pi.",
        "input_schema": {
            "type"      : "object",
            "properties": {"expression": {"type": "string"}},
            "required"  : ["expression"],
        },
    },
    {
        "name"        : "word_count",
        "description" : "Count words and estimate reading time for a text.",
        "input_schema": {
            "type"      : "object",
            "properties": {"text": {"type": "string"}},
            "required"  : ["text"],
        },
    },
    {
        "name"        : "get_assignment_info",
        "description" : "Look up assignment due date, type, and weight for a subject.",
        "input_schema": {
            "type"      : "object",
            "properties": {"subject": {"type": "string"}},
            "required"  : ["subject"],
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Look up and run the requested tool. Always returns a string."""
    if tool_name not in TOOL_REGISTRY:
        return f"Error: tool '{tool_name}' not found"
    try:
        func = TOOL_REGISTRY[tool_name]
        # Map the named input fields to positional args
        if tool_name == "calculator":
            return func(tool_input["expression"])
        elif tool_name == "word_count":
            return func(tool_input["text"])
        elif tool_name == "get_assignment_info":
            return func(tool_input["subject"])
    except Exception as e:
        return f"Error executing {tool_name}: {e}"
    return "Error: unknown"


# ── Complete tool-use cycle ───────────────────────────────────────────────────

def run_with_tools(question: str) -> str:
    print(f"\n  User: {question}\n")
    messages = [{"role": "user", "content": question}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return next((b.text for b in response.content if hasattr(b, "text")), "")

        # Collect all tool calls from this response
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            print(f"  → Tool call: {block.name}({block.input})")
            result = execute_tool(block.name, block.input)
            print(f"  ← Observation: {result}")

            tool_results.append({
                "type"       : "tool_result",
                "tool_use_id": block.id,
                "content"    : result,
            })

        messages.append({"role": "user", "content": tool_results})


def show_error_handling() -> None:
    """Show how to handle tool errors gracefully."""
    print("\n" + "=" * 62)
    print("  ERROR HANDLING — what happens when a tool fails?")
    print("=" * 62)
    print("""
  Best practice: always return a string from tool execution.
  Never raise an exception — return an error string instead.

  Bad:   raise ValueError("tool failed")  ← crashes the loop
  Good:  return "Error: tool failed — <reason>"  ← Claude adapts

  Claude is surprisingly good at recovering from tool errors:
  it will try a different tool or answer from general knowledge.
""")
    # Show a failed tool call — missing subject
    result = execute_tool("get_assignment_info", {"subject": "quantum mechanics"})
    print(f"  Failed lookup result: {result}")
    print(f"  Claude can read this and say 'I couldn't find that assignment.'")


if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  TOOL EXECUTION DEMO")
    print("=" * 62)

    questions = [
        "What is the square root of 144 plus 7 squared?",
        "When is my physics assignment due and how much is it worth?",
        "I have a history essay and a math problem set — which is due first?",
    ]

    for q in questions:
        print("\n" + "─" * 62)
        answer = run_with_tools(q)
        print(f"\n  Final answer: {answer}")

    show_error_handling()

    print("\n" + "=" * 62)
    print("  SUMMARY")
    print("=" * 62)
    print("""
  The tool execution cycle:
    1. client.messages.create(..., tools=TOOLS)
    2. if stop_reason == "tool_use": extract tool_use blocks
    3. execute_tool(name, input) → string result
    4. append {"type": "tool_result", "content": result}
    5. call client.messages.create again (with the results)
    6. repeat until stop_reason == "end_turn"

  This is exactly what the ReAct loop does — automatically.
""")
