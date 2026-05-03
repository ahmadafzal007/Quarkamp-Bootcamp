"""
CONCEPT 3 — MCP (Model Context Protocol) Server
================================================
MCP is Anthropic's open standard for exposing tools to AI agents.
Instead of hard-coding tools into each agent, you run an MCP *server*
and any agent — local or remote — can discover and call your tools.

This script:
  1. Creates a simple MCP server with 3 tools
  2. Shows what the server looks like to a client
  3. Explains how our project's MCP server fits the architecture

To see the MCP server in action, this script prints what it *would* expose.
The full running server is in day4/lab/mcp_server.py.

Run:
    conda run -n bootcamp python day4/concepts/03_mcp_protocol.py
"""

import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")


# ── What a tool schema looks like in MCP ─────────────────────────────────────

def explain_mcp_schema():
    print("\n" + "=" * 62)
    print("  PART 1: MCP Tool Schema")
    print("=" * 62)

    schema = {
        "name"       : "web_search",
        "description": "Search the web for current information on a topic.",
        "inputSchema": {
            "type"      : "object",
            "properties": {
                "query"      : {"type": "string",  "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results (default 3)"},
            },
            "required": ["query"],
        },
    }

    print("\n  MCP tool schema (same JSON Schema as Claude's tool_use API):")
    print(json.dumps(schema, indent=4))
    print("""
  Key point: MCP tool schemas are almost identical to Claude tool schemas.
  The difference is in the transport layer (JSON-RPC over stdio/HTTP),
  not the schema format.
""")


def explain_mcp_vs_direct():
    print("\n" + "=" * 62)
    print("  PART 2: Direct Tool Calls vs MCP")
    print("=" * 62)
    print("""
  WITHOUT MCP (Days 1-3):
    Agent code calls tool function directly.
    web_search() is defined IN the agent file.
    Adding a new agent = copy-paste all tool code.

  WITH MCP (Day 4+):
    Agent connects to MCP server via protocol.
    web_search() is defined ONCE in the server.
    Any agent, any language, any machine can call it.

  Direct:
    agent.py → import web_search → call web_search()

  MCP:
    agent.py → MCP Client → JSON-RPC → MCP Server → web_search()
    other_agent.py → same MCP Client → same server
    external_ai.py → same server

  Trade-off: MCP adds network overhead but enables:
    - Tool reuse across agents
    - Tool versioning
    - Access control (who can call which tools)
    - Monitoring (every tool call is logged centrally)
""")


def explain_our_mcp_server():
    print("\n" + "=" * 62)
    print("  PART 3: Our Project's MCP Server")
    print("=" * 62)

    our_tools = [
        {
            "name"       : "web_search",
            "description": "Search the web via DuckDuckGo",
            "inputs"     : ["query", "max_results"],
        },
        {
            "name"       : "calculator",
            "description": "Evaluate math expressions safely",
            "inputs"     : ["expression"],
        },
        {
            "name"       : "read_file",
            "description": "Read .txt or .pdf files",
            "inputs"     : ["path"],
        },
        {
            "name"       : "memory_store",
            "description": "Save a Q&A pair to ChromaDB",
            "inputs"     : ["question", "answer", "metadata"],
        },
        {
            "name"       : "memory_retrieve",
            "description": "Retrieve similar past answers from ChromaDB",
            "inputs"     : ["query", "n_results"],
        },
    ]

    print("\n  Tools exposed by our MCP server:")
    for tool in our_tools:
        inputs = ", ".join(tool["inputs"])
        print(f"    • {tool['name']:<20} inputs: {inputs}")

    print("""
  MCP server runs on: stdio (same process) or HTTP (separate process)
  In the project: runs as a FastAPI endpoint on /mcp

  Any agent can call ANY tool without knowing where it's implemented:
    researcher_agent.py → mcp_client.call("web_search", query="...")
    writer_agent.py     → mcp_client.call("memory_retrieve", ...)
""")


def explain_a2a():
    print("\n" + "=" * 62)
    print("  PART 4: A2A — Agent-to-Agent Protocol")
    print("=" * 62)
    print("""
  MCP = exposing TOOLS to agents
  A2A = exposing AGENTS to other agents

  A2A endpoint structure (our project):

    GET  /a2a/.well-known/agent.json    → AgentCard (capabilities)
    POST /a2a/tasks                     → Submit a task to our agent
    GET  /a2a/tasks/{id}                → Get task status/result

  AgentCard example:
    {
      "name": "AssignmentPlatform",
      "description": "University assignment research agent",
      "version": "1.0.0",
      "skills": [
        {"id": "research", "name": "Research a Topic"},
        {"id": "critique", "name": "Critique an Essay"}
      ]
    }

  Use case:
    Student A's agent (their laptop) sends a research task to
    Student B's agent (who specialised in chemistry).
    This is the future of the internet: agents calling agents.

  Day 5 lab: we wire the A2A server into FastAPI.
""")


if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  MCP PROTOCOL — CONCEPTS")
    print("=" * 62)
    explain_mcp_schema()
    explain_mcp_vs_direct()
    explain_our_mcp_server()
    explain_a2a()

    print("\n" + "=" * 62)
    print("  NEXT STEP: Run the actual MCP server")
    print("=" * 62)
    print("""
  conda run -n bootcamp python day4/lab/mcp_server.py

  Then run the agent that connects to it:
  conda run -n bootcamp python day4/lab/rag_agent.py
""")
