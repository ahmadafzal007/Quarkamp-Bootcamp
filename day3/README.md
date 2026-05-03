# Day 3 — Multi-Agent System with LangGraph

**Theory link:** Module 3.3 (Multi-Agent Systems, Specialisation, Handoffs) + Module 3.4  
**Duration:** 2 hours  
**Goal:** Split one monolithic agent into 5 specialised agents wired together as a LangGraph state machine.

---

## 2-Hour Schedule

| Time | Activity |
|------|----------|
| 0:00–0:20 | Whiteboard: why specialise? LangGraph state machine diagram |
| 0:20–0:40 | Run `concepts/01_langgraph_basics.py` — first graph |
| 0:40–0:55 | Run `concepts/02_state_machines.py` — conditional routing |
| 0:55–1:10 | Run `concepts/03_agent_handoffs.py` — context passing |
| 1:10–1:50 | **Lab:** build the 5-agent pipeline in `lab/multi_agent_graph.py` |
| 1:50–2:00 | Checkpoint: show a question flowing through all 5 agents |

> **Instructor note:** Day 3 is the hardest. Spend 5 extra minutes on the whiteboard  
> drawing the state dict flowing through each node before touching code.

---

## Setup

```bash
conda run -n bootcamp pip install langgraph
conda run -n bootcamp python day3/concepts/01_langgraph_basics.py
conda run -n bootcamp python day3/concepts/02_state_machines.py
conda run -n bootcamp python day3/concepts/03_agent_handoffs.py
```

---

## Key Concepts

### Why split into multiple agents?
- **Specialisation** — each agent is best-in-class at one task
- **Parallelism** — independent agents can run concurrently
- **Debuggability** — you can inspect and test each node independently
- **Cost control** — use cheap/fast models for simple nodes, powerful models only where needed

### LangGraph State Machine
```
State dict flows through every node.
Each node reads the state, does its job, returns updates.
Edges decide which node runs next (can be conditional).

START → Orchestrator → Planner → Researcher → Writer → Critic → END
                                      ↑___________________________↓
                                     (Critic can loop back to Writer)
```

### The 5 Agents
| Agent | Model | Job |
|-------|-------|-----|
| Orchestrator | fast (Haiku) | Classify question, choose pipeline path |
| Planner | balanced (Sonnet) | Break question into research subtasks |
| Researcher | balanced (Sonnet) | Gather information using tools |
| Writer | balanced (Sonnet) | Draft the answer |
| Critic | fast (Haiku) | Score + decide: pass or send back to Writer |

### Handoffs
When the Orchestrator finishes, it updates `state["plan"] = ...`.  
The Planner reads `state["question"]`, updates `state["subtasks"] = [...]`.  
Each node adds to the state — it never overwrites what came before.

---

## Lab Deliverable

`lab/multi_agent_graph.py` — a fully wired 5-agent LangGraph pipeline.

```bash
conda run -n bootcamp python day3/lab/multi_agent_graph.py
```
