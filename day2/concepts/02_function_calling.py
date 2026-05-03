"""
CONCEPT 2 — Function Calling (Tool Use) with Claude
=====================================================
Claude's tool use API lets you define callable functions as JSON schemas.
Claude then decides *when* and *how* to call them.

This script shows:
  1. How to define a tool schema
  2. What Claude's response looks like when it calls a tool
  3. How to detect and parse tool calls in your code

Run:
    conda run -n bootcamp python day2/concepts/02_function_calling.py
"""

import json
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"


# ── PART 1: Define tool schemas ───────────────────────────────────────────────
# Each tool is a dict with name, description, and input_schema.
# Claude reads the description to decide when to call the tool.
# The input_schema is standard JSON Schema — Claude fills in the fields.

EXAMPLE_TOOLS = [
    {
        "name"       : "search_university_database",
        "description": (
            "Search the university's course and assignment database. "
            "Use this when the student asks about specific courses, deadlines, or grades."
        ),
        "input_schema": {
            "type"      : "object",
            "properties": {
                "query"      : {"type": "string",  "description": "Search query"},
                "category"   : {
                    "type"  : "string",
                    "enum"  : ["courses", "assignments", "grades", "deadlines"],
                    "description": "Category to search within",
                },
                "student_id" : {"type": "string",  "description": "Student ID (optional)"},
            },
            "required": ["query", "category"],
        },
    },
    {
        "name"       : "calculate_grade",
        "description": "Calculate a student's weighted average grade from component scores.",
        "input_schema": {
            "type"      : "object",
            "properties": {
                "components": {
                    "type" : "array",
                    "items": {
                        "type"      : "object",
                        "properties": {
                            "name"  : {"type": "number"},
                            "weight": {"type": "number"},
                        },
                    },
                    "description": "List of {name, score, weight} objects",
                },
            },
            "required": ["components"],
        },
    },
    {
        "name"       : "send_reminder",
        "description": "Send an assignment reminder to a student's email.",
        "input_schema": {
            "type"      : "object",
            "properties": {
                "student_email": {"type": "string"},
                "message"      : {"type": "string"},
                "send_at"      : {"type": "string", "description": "ISO datetime"},
            },
            "required": ["student_email", "message"],
        },
    },
]


def show_tool_call_structure() -> None:
    """Send a message that forces Claude to call a tool, then print the raw response."""
    print("\n" + "=" * 62)
    print("  PART 1: What does a tool call look like in the API response?")
    print("=" * 62)

    question = (
        "What assignments are due this week for student ID S12345? "
        "I need to know all categories."
    )
    print(f"\n  User: {question}\n")

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        tools=EXAMPLE_TOOLS,
        messages=[{"role": "user", "content": question}],
    )

    print(f"  Stop reason: {response.stop_reason}")
    print(f"  Content blocks ({len(response.content)} total):\n")

    for i, block in enumerate(response.content):
        print(f"  Block {i}: type = {block.type}")
        if block.type == "text":
            print(f"    text: {block.text}")
        elif block.type == "tool_use":
            print(f"    id:     {block.id}")
            print(f"    name:   {block.name}")
            print(f"    input:  {json.dumps(block.input, indent=4)}")


def show_tool_choice_control() -> None:
    """Show how to force or prevent tool calls."""
    print("\n" + "=" * 62)
    print("  PART 2: Controlling whether Claude uses tools")
    print("=" * 62)

    question = "What is 15% of 340?"

    # tool_choice="auto"  → Claude decides (default)
    # tool_choice="any"   → Claude must call at least one tool
    # tool_choice="none"  → Claude cannot call any tools

    for choice_label, kwargs in [
        ("auto (Claude decides)",  {"tool_choice": {"type": "auto"}}),
        ("none (no tools allowed)", {"tool_choice": {"type": "none"}}),
    ]:
        response = client.messages.create(
            model=MODEL,
            max_tokens=200,
            tools=EXAMPLE_TOOLS,
            messages=[{"role": "user", "content": question}],
            **kwargs,
        )
        answer = ""
        for block in response.content:
            if block.type == "text":
                answer = block.text[:100]
            elif block.type == "tool_use":
                answer = f"[TOOL CALL] {block.name}({block.input})"

        print(f"\n  tool_choice={choice_label}")
        print(f"  stop_reason: {response.stop_reason}")
        print(f"  response:    {answer}")


def show_multiple_tools_in_one_turn() -> None:
    """Claude can call multiple tools in a single response."""
    print("\n" + "=" * 62)
    print("  PART 3: Multiple tool calls in one turn")
    print("=" * 62)

    question = (
        "I need to know the assignments due this week AND calculate "
        "what grade I need on the final exam to pass the course."
    )
    print(f"\n  User: {question}\n")

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        tools=EXAMPLE_TOOLS,
        messages=[{"role": "user", "content": question}],
    )

    tool_calls = [b for b in response.content if b.type == "tool_use"]
    print(f"  Claude made {len(tool_calls)} tool call(s) in one response:")
    for tc in tool_calls:
        print(f"    → {tc.name}({list(tc.input.keys())})")

    print("""
  Key insight: Claude can batch multiple tool calls in a single
  response when it needs parallel information. Your code must
  handle ALL of them before sending the results back.
""")


if __name__ == "__main__":
    show_tool_call_structure()
    show_tool_choice_control()
    show_multiple_tools_in_one_turn()
