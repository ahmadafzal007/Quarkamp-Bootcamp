# Day 2 — Tool-Using ReAct Agent

**Theory link:** Module 2.2–2.4 (ReAct Pattern, Tool Utilisation, Function Calling)  
**Duration:** 2 hours  
**Goal:** Give the Day 1 agent real tools — web search, calculator, file reader — and watch the ReAct loop.

---

## 2-Hour Schedule

| Time | Activity |
|------|----------|
| 0:00–0:15 | Recap Day 1 + ReAct whiteboard |
| 0:15–0:35 | Run `concepts/01_react_pattern.py` — watch the loop |
| 0:35–0:55 | Run `concepts/02_function_calling.py` — tool schemas |
| 0:55–1:10 | Run `concepts/03_tool_schemas.py` — parsing observations |
| 1:10–1:50 | **Lab:** extend Day 1 agent with tools in `lab/react_agent.py` |
| 1:50–2:00 | Checkpoint: run the agent with a question that needs web search |

---

## Setup

```bash
conda run -n bootcamp pip install duckduckgo-search PyPDF2
conda run -n bootcamp python day2/concepts/01_react_pattern.py
conda run -n bootcamp python day2/concepts/02_function_calling.py
conda run -n bootcamp python day2/concepts/03_tool_schemas.py
```

---

## Key Concepts

### The ReAct Loop
```
while not done:
    Thought  → agent reasons about what to do next
    Action   → agent calls a tool
    Observation → tool returns result
    (loop back to Thought with the new observation)
Final Answer → agent concludes
```

### Function Calling (Tool Use) with Claude
Claude doesn't just receive text — you can define **tools** as JSON schemas.
When Claude wants to use a tool it returns a `tool_use` block instead of text.
Your code executes the tool and returns the result as a `tool_result`.

```python
# You define:
tools = [{"name": "web_search", "input_schema": {"query": {"type": "string"}}}]

# Claude returns:
{"type": "tool_use", "name": "web_search", "input": {"query": "..."}}

# You execute and return:
{"type": "tool_result", "content": "...search results..."}
```

### Guardrails
- **Max iterations** — stop after N loops to prevent infinite loops
- **Fallback** — if a tool fails, return a graceful error observation
- **Allowed tools** — the agent can only call tools you explicitly define

---

## Lab Deliverable

`lab/react_agent.py` — the Day 1 agent extended with:
- Web search (DuckDuckGo)
- Calculator (safe Python eval)
- File reader (reads .txt and .pdf)
- Full ReAct loop with iteration counter

```bash
conda run -n bootcamp python day2/lab/react_agent.py
```
