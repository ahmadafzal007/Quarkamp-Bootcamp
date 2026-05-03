"""
MCP Server — exposes all plugins as a standard MCP interface.

Run standalone:
    conda run -n bootcamp python -m project.backend.mcp_server

Or import and mount in FastAPI (see main.py).
"""

from mcp.server.fastmcp import FastMCP
from .plugins.web_search import web_search as _web_search
from .plugins.calculator import calculator as _calculator
from .plugins.pdf_reader import read_file as _read_file
from .plugins.code_runner import run_code as _run_code
from .plugins.memory import memory_store as _memory_store, memory_retrieve as _memory_retrieve

mcp = FastMCP(
    name        = "AssignmentPlatformTools",
    instructions= (
        "Tools for the University Assignment Platform. "
        "Use web_search for facts, calculator for math, "
        "memory_* for persistent context across sessions."
    ),
)


@mcp.tool()
def web_search(query: str, max_results: int = 3) -> str:
    """Search the web for current information."""
    return _web_search(query, max_results)


@mcp.tool()
def calculator(expression: str) -> str:
    """Evaluate a math expression. Supports +,-,*,/,**,sqrt,pi,log,exp."""
    return _calculator(expression)


@mcp.tool()
def read_file(path: str) -> str:
    """Read a .txt or .pdf file and return its content."""
    return _read_file(path)


@mcp.tool()
def run_code(code: str, language: str = "python") -> str:
    """Execute Python code in a sandboxed subprocess."""
    return _run_code(code, language)


@mcp.tool()
def memory_store(question: str, answer: str, subject: str = "", score: int = 0) -> str:
    """Save a Q&A pair to persistent memory (ChromaDB)."""
    return _memory_store(question, answer, subject, score)


@mcp.tool()
def memory_search(query: str, n_results: int = 3) -> str:
    """Search memory for similar past Q&A pairs."""
    return _memory_retrieve(query, n_results)


if __name__ == "__main__":
    print("Starting MCP server on stdio...")
    mcp.run(transport="stdio")
