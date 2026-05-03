# Day 4 — RAG Memory + MCP Tool Integration + A2A

**Theory link:** Module 3.1–3.2 (Memory Systems, Hierarchical Memory, Context Engineering)  
**Duration:** 2 hours  
**Goal:** Give the multi-agent system persistent memory (ChromaDB RAG) and expose all tools as a standard MCP server. Introduce A2A.

---

## 2-Hour Schedule

| Time | Activity |
|------|----------|
| 0:00–0:15 | Recap Day 3 + memory hierarchy diagram |
| 0:15–0:35 | Run `concepts/01_rag_memory.py` — embed, store, retrieve |
| 0:35–0:50 | Run `concepts/02_vector_stores.py` — ChromaDB deep dive |
| 0:50–1:05 | Run `concepts/03_mcp_protocol.py` — MCP server basics |
| 1:05–1:45 | **Lab:** add memory to the Day 3 graph + spin up MCP server |
| 1:45–2:00 | Checkpoint: ask a question, check ChromaDB stored it |

---

## Setup

```bash
conda run -n bootcamp pip install chromadb sentence-transformers mcp
conda run -n bootcamp python day4/concepts/01_rag_memory.py
conda run -n bootcamp python day4/concepts/02_vector_stores.py
conda run -n bootcamp python day4/concepts/03_mcp_protocol.py
```

---

## Key Concepts

### Memory Hierarchy
```
Working Memory    → state dict in LangGraph (lost when graph ends)
Episodic Memory   → ChromaDB vector store (persists across sessions)
Semantic Memory   → hard-coded knowledge base / system prompt facts
```

### RAG vs Fine-tuning
| | RAG | Fine-tuning |
|---|---|---|
| When | facts change often | facts are stable, behaviour changes |
| Cost | cheap (just storage) | expensive (GPU compute) |
| Speed | adds latency (retrieval) | no latency |
| Update | instant | requires retraining |
| Use case | our platform ✓ | specialised domain models |

### MCP (Model Context Protocol)
MCP is Anthropic's standard for exposing tools as servers.
Any agent — local or remote — can call your tools through one interface.

```
Agent ←→ MCP Client ←→ MCP Protocol (JSON-RPC) ←→ MCP Server ←→ Your tools
```

### A2A (Agent-to-Agent Protocol)
Our platform exposes an A2A endpoint. External agents can:
- Discover our capabilities (GET /a2a/.well-known/agent.json)
- Delegate tasks to our Researcher (POST /a2a/tasks)
- Retrieve results (GET /a2a/tasks/{id})

---

## Lab Deliverables

1. `lab/rag_agent.py` — Day 3 agent with ChromaDB memory
2. `lab/mcp_server.py` — MCP server exposing all plugins

```bash
# Terminal 1: start MCP server
conda run -n bootcamp python day4/lab/mcp_server.py

# Terminal 2: run agent with memory
conda run -n bootcamp python day4/lab/rag_agent.py
```
