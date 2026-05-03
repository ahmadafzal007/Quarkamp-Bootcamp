"""
LAB 4b — MCP Tool Server
==========================
An MCP server that exposes all our tools through a standard interface.
Any agent — local or remote — can discover and call these tools.

Tools exposed:
  - web_search     DuckDuckGo search
  - calculator     Safe Python eval
  - read_file      .txt / .pdf reader
  - memory_store   Save to ChromaDB
  - memory_search  Query ChromaDB

Run:
    conda run -n bootcamp python day4/lab/mcp_server.py

This will start the MCP server on stdio (standard MCP transport).
The project's FastAPI app wraps this into HTTP on Day 5.
"""

import math
import json
import uuid
import datetime
from pathlib import Path
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parents[2] / ".env")

# ── MCP server instance ───────────────────────────────────────────────────────
mcp = FastMCP(
    name        = "AssignmentPlatformTools",
    instructions= (
        "Tools for the University Assignment Platform. "
        "Use web_search for facts, calculator for math, "
        "memory_* for persistent context."
    ),
)

# ── ChromaDB (lazy init) ──────────────────────────────────────────────────────

_chroma     = None
_collection = None
_embedder   = None

def _get_memory():
    global _chroma, _collection, _embedder
    if _collection is None:
        import chromadb
        from sentence_transformers import SentenceTransformer
        CHROMA_PATH = Path(__file__).parents[2] / "data" / "chroma"
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _chroma     = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = _chroma.get_or_create_collection("assignment_memory")
        _embedder   = SentenceTransformer("all-MiniLM-L6-v2")
    return _collection, _embedder


# ── Tool: web_search ──────────────────────────────────────────────────────────

@mcp.tool()
def web_search(query: str, max_results: int = 3) -> str:
    """Search the web using DuckDuckGo. Returns top results as plain text."""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"• {r['title']}\n  {r['body'][:200]}")
        return "\n\n".join(results) if results else "No results found."
    except ImportError:
        return "web_search unavailable: pip install duckduckgo-search"
    except Exception as e:
        return f"Search error: {e}"


# ── Tool: calculator ─────────────────────────────────────────────────────────

@mcp.tool()
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression safely.
    Supports: +, -, *, /, **, %, sqrt, pi, abs, round
    Example: "sqrt(144) + 2**8"
    """
    safe_chars = set("0123456789+-*/().% ")
    if not all(c in safe_chars for c in expression.replace("sqrt", "").replace("pi", "").replace("abs", "").replace("round", "")):
        return "Error: unsupported characters in expression"
    try:
        result = eval(expression, {"__builtins__": {}}, {  # noqa: S307
            "sqrt": math.sqrt, "pi": math.pi,
            "abs": abs, "round": round, "pow": pow,
        })
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"


# ── Tool: read_file ───────────────────────────────────────────────────────────

@mcp.tool()
def read_file(path: str, max_chars: int = 3000) -> str:
    """
    Read a .txt or .pdf file and return its content.
    For PDFs, returns extracted text (first max_chars characters).
    """
    file_path = Path(path)
    if not file_path.exists():
        return f"File not found: {path}"
    if not file_path.is_file():
        return f"Not a file: {path}"

    if file_path.suffix.lower() == ".pdf":
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text   = "\n".join(p.extract_text() or "" for p in reader.pages)
            return text[:max_chars] + ("... [truncated]" if len(text) > max_chars else "")
        except ImportError:
            return "PDF support requires: pip install PyPDF2"
        except Exception as e:
            return f"PDF error: {e}"

    try:
        content = file_path.read_text(encoding="utf-8")
        return content[:max_chars] + ("... [truncated]" if len(content) > max_chars else "")
    except Exception as e:
        return f"File read error: {e}"


# ── Tool: memory_store ────────────────────────────────────────────────────────

@mcp.tool()
def memory_store(question: str, answer: str, subject: str = "", score: int = 0) -> str:
    """
    Save a Q&A pair to persistent memory (ChromaDB vector store).
    Returns the stored document ID.
    """
    try:
        coll, emb = _get_memory()
        doc_id    = str(uuid.uuid4())
        text      = f"Q: {question}\nA: {answer}"
        coll.upsert(
            ids        = [doc_id],
            embeddings = [emb.encode(text).tolist()],
            documents  = [text],
            metadatas  = [{
                "question" : question[:200],
                "subject"  : subject,
                "score"    : score,
                "timestamp": datetime.datetime.now().isoformat(),
            }],
        )
        return json.dumps({"stored": True, "id": doc_id, "total_in_memory": coll.count()})
    except Exception as e:
        return json.dumps({"stored": False, "error": str(e)})


# ── Tool: memory_search ───────────────────────────────────────────────────────

@mcp.tool()
def memory_search(query: str, n_results: int = 3) -> str:
    """
    Search memory for similar past Q&A pairs.
    Returns top n_results matches as JSON.
    """
    try:
        coll, emb = _get_memory()
        if coll.count() == 0:
            return json.dumps({"results": [], "message": "Memory is empty"})
        q_embed = emb.encode(query).tolist()
        results = coll.query(
            query_embeddings = [q_embed],
            n_results        = min(n_results, coll.count()),
            include          = ["documents", "metadatas", "distances"],
        )
        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "content"   : doc[:300],
                "similarity": round(1 - dist, 3),
                "metadata"  : meta,
            })
        return json.dumps({"results": hits, "total_in_memory": coll.count()})
    except Exception as e:
        return json.dumps({"results": [], "error": str(e)})


# ── Resource: server info ─────────────────────────────────────────────────────

@mcp.resource("config://server-info")
def server_info() -> str:
    """Returns metadata about this MCP server and its available tools."""
    return json.dumps({
        "name"   : "AssignmentPlatformTools",
        "version": "1.0.0",
        "tools"  : ["web_search", "calculator", "read_file", "memory_store", "memory_search"],
        "transport": "stdio",
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting MCP server: AssignmentPlatformTools")
    print("Transport: stdio")
    print("Tools: web_search, calculator, read_file, memory_store, memory_search")
    print("Press Ctrl+C to stop.\n")
    mcp.run(transport="stdio")
