# Day 1 — Single Reasoning Agent with Chain-of-Thought

**Theory link:** Module 1 (Agentic AI Fundamentals) + Module 2.1–2.2 (Advanced Planning)  
**Duration:** 2 hours  
**Goal:** Build and run your first agent — a single LLM with a structured identity, goal, and CoT reasoning.

---

## 2-Hour Schedule

| Time | Activity |
|------|----------|
| 0:00–0:20 | Instructor demo + PPARM whiteboard |
| 0:20–0:35 | Run `concepts/01_pparm_framework.py` together |
| 0:35–0:50 | Run `concepts/02_system_prompts.py` — compare outputs |
| 0:50–1:05 | Run `concepts/03_chain_of_thought.py` — CoT vs direct |
| 1:05–1:45 | **Lab:** build `lab/assignment_agent_v1.py` |
| 1:45–2:00 | Checkpoint: demo your agent to the class |

---

## Setup (do this first)

```bash
# Copy and fill in your API key
cp setup/.env.example .env
# Edit .env and paste your ANTHROPIC_API_KEY

# Run all concept scripts from the Bootcamp root
conda run -n bootcamp python day1/concepts/01_pparm_framework.py
conda run -n bootcamp python day1/concepts/02_system_prompts.py
conda run -n bootcamp python day1/concepts/03_chain_of_thought.py
```

---

## Key Concepts

### The PPARM Framework
Every agentic AI system has five layers:

```
Perception  →  How the agent receives input from the world
Planning    →  How it breaks the task into steps (CoT lives here)
Action      →  How it executes (LLM call, tool call, code run)
Reflection  →  How it judges its own output
Memory      →  How it stores and retrieves past context
```

### Why RAG alone isn't enough
RAG retrieves facts. An agent *does things* — it plans, decides, loops, and calls tools. RAG is one piece of an agent's memory system, not a replacement for reasoning.

### Chain-of-Thought vs Tree-of-Thought
- **CoT**: one linear chain of reasoning steps — fast, cheap, great for most tasks
- **ToT**: explores multiple reasoning branches in parallel — better for hard math/logic, expensive

### System Prompt Engineering
Three components every agent system prompt needs:
1. **Role** — who the agent is
2. **Goal** — what it optimises for
3. **Constraints** — what it must never do

---

## Lab Deliverable

A working `assignment_agent_v1.py` that:
- Accepts any assignment question from stdin
- Uses CoT to reason step by step
- Shows all five PPARM phases in the output
- Ends with a self-critique score

Run it:
```bash
conda run -n bootcamp python day1/lab/assignment_agent_v1.py
```
