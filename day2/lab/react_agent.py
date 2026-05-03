"""
LAB 2 — Tool-Using ReAct Agent
================================
Day 1's agent could only think. Today it can ACT.

New tools:
  - web_search   → DuckDuckGo search
  - calculator   → safe Python eval
  - read_file    → read .txt or .pdf files

The agent runs the full ReAct loop:
  Thought → Action → Observation → ... → Final Answer

Run:
    conda run -n bootcamp python day2/lab/react_agent.py

After Day 3 → this logic moves into a LangGraph node (Researcher agent)
After Day 4 → tools are exposed as MCP servers
After Day 5 → runs behind FastAPI + React UI
"""

import os
import json
import math
import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")

# ── Config ─────────────────────────────────────────────────────────────────────

MODEL          = "claude-haiku-4-5"
MAX_ITERATIONS = 8

SYSTEM_PROMPT = """\
You are AssignmentBot v2 — an expert academic assistant with access to tools.

ROLE: Help university students answer assignment questions accurately.
GOAL: Use tools to gather real information before answering. Never make up facts.

TOOL USAGE RULES:
- Use web_search for anything requiring current or factual information
- Use calculator for ALL arithmetic (never do math in your head)
- Use read_file only if the student provides a file path

REASONING:
- Before each tool call, briefly state your reasoning (one sentence)
- After receiving an observation, state what you learned

OUTPUT (when done):
## Answer
<clear, structured answer>

## Sources Used
<list of tools called and what each contributed>
"""

# ── Tool implementations ──────────────────────────────────────────────────────

def web_search(query: str, max_results: int = 3) -> str:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"• {r['title']}: {r['body'][:200]}")
        if results:
            return "\n".join(results)
        return "No results found for that query."
    except ImportError:
        return "web_search unavailable: pip install duckduckgo-search"
    except Exception as e:
        return f"Search error: {e}"


def calculator(expression: str) -> str:
    safe_chars = set("0123456789+-*/().% ")
    if not all(c in safe_chars for c in expression):
        return "Error: only basic arithmetic (+, -, *, /, %, ())"
    try:
        result = eval(expression, {"__builtins__": {}}, {  # noqa: S307
            "sqrt": math.sqrt, "pi": math.pi, "abs": abs, "round": round,
        })
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"


def read_file(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return f"File not found: {path}"
    if file_path.suffix.lower() == ".pdf":
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
            return text[:3000] + ("..." if len(text) > 3000 else "")
        except ImportError:
            return "PDF reading unavailable: pip install PyPDF2"
        except Exception as e:
            return f"PDF read error: {e}"
    try:
        return file_path.read_text(encoding="utf-8")[:3000]
    except Exception as e:
        return f"File read error: {e}"


# ── Tool registry & schemas ───────────────────────────────────────────────────

TOOL_REGISTRY = {
    "web_search": web_search,
    "calculator": calculator,
    "read_file" : read_file,
}

TOOLS = [
    {
        "name"        : "web_search",
        "description" : "Search the web for current information. Use for any factual question.",
        "input_schema": {
            "type"      : "object",
            "properties": {
                "query"      : {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Number of results (default 3)"},
            },
            "required": ["query"],
        },
    },
    {
        "name"        : "calculator",
        "description" : "Evaluate math expressions. Use for ALL arithmetic.",
        "input_schema": {
            "type"      : "object",
            "properties": {"expression": {"type": "string", "description": "e.g. '15 * 8.5 / 100'"}},
            "required"  : ["expression"],
        },
    },
    {
        "name"        : "read_file",
        "description" : "Read a .txt or .pdf file. Use when the student provides a file path.",
        "input_schema": {
            "type"      : "object",
            "properties": {"path": {"type": "string", "description": "Absolute or relative file path"}},
            "required"  : ["path"],
        },
    },
]


def execute_tool(name: str, inputs: dict) -> str:
    if name not in TOOL_REGISTRY:
        return f"Unknown tool: {name}"
    try:
        fn = TOOL_REGISTRY[name]
        if name == "web_search":
            return fn(inputs["query"], inputs.get("max_results", 3))
        if name == "calculator":
            return fn(inputs["expression"])
        if name == "read_file":
            return fn(inputs["path"])
    except Exception as e:
        return f"Tool execution error: {e}"
    return "Error"


# ── ReAct loop ────────────────────────────────────────────────────────────────

class ReActAgent:
    def __init__(self):
        self.client  = anthropic.Anthropic()
        self.history: list[dict] = []

    def run(self, question: str) -> str:
        messages   = [{"role": "user", "content": question}]
        iteration  = 0
        tools_used = []

        print(f"\n  Question: {question}")

        while iteration < MAX_ITERATIONS:
            iteration += 1
            print(f"\n  {'─'*55}")
            print(f"  Iteration {iteration}/{MAX_ITERATIONS}")

            response = self.client.messages.create(
                model=MODEL,
                max_tokens=600,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            # Print any text blocks (Claude's thinking)
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    print(f"\n  [Thought] {block.text[:200]}...")

            if response.stop_reason == "end_turn":
                final = next((b.text for b in response.content if hasattr(b, "text")), "")
                self._store(question, final, tools_used)
                return final

            # Handle tool calls
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                name   = block.name
                inputs = block.input
                tools_used.append(name)

                print(f"\n  [Action] {name}({inputs})")
                obs = execute_tool(name, inputs)
                print(f"  [Observation] {obs[:150]}{'...' if len(obs) > 150 else ''}")

                tool_results.append({
                    "type"       : "tool_result",
                    "tool_use_id": block.id,
                    "content"    : obs,
                })

            messages.append({"role": "user", "content": tool_results})

        return "Reached max iterations. See partial output above."

    def _store(self, question: str, answer: str, tools: list) -> None:
        self.history.append({
            "question"  : question,
            "answer"    : answer[:200],
            "tools_used": tools,
            "timestamp" : datetime.datetime.now().isoformat(),
        })


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    agent = ReActAgent()

    print("\n" + "═" * 60)
    print("  AssignmentBot v2 — ReAct Agent with Tools")
    print(f"  Model: {MODEL}  |  Max iterations: {MAX_ITERATIONS}")
    print("  Tools: web_search, calculator, read_file")
    print("  Type /quit to exit, /history to see past questions")
    print("═" * 60 + "\n")

    while True:
        try:
            q = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if not q:
            continue
        if q == "/quit":
            print("\n  Goodbye!")
            break
        if q == "/history":
            if not agent.history:
                print("  No history yet.")
            for i, h in enumerate(agent.history, 1):
                print(f"  [{i}] {h['question'][:60]} (tools: {h['tools_used']})")
            continue

        answer = agent.run(q)
        print("\n" + "═" * 60)
        print("  FINAL ANSWER")
        print("═" * 60)
        print(answer)


if __name__ == "__main__":
    main()
