"""
Shared configuration for the entire backend.
All constants, paths, and model names live here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR.parent / "data"
CHROMA_DIR = DATA_DIR / "chroma"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AGENTOPS_API_KEY  = os.getenv("AGENTOPS_API_KEY",  "")
BRAVE_API_KEY     = os.getenv("BRAVE_API_KEY",     "")

# ── Model names ───────────────────────────────────────────────────────────────
MODEL_FAST     = "claude-haiku-4-5"    # Orchestrator, Critic, hooks
MODEL_BALANCED = "claude-sonnet-4-6"   # Planner, Researcher, Writer
MODEL_POWERFUL = "claude-opus-4-7"     # Available for /powerful skill flag

# ── Agent settings ────────────────────────────────────────────────────────────
MAX_ITERATIONS  = 8    # ReAct loop limit
MAX_REVISIONS   = 2    # Critic revision limit
MIN_SCORE       = 7    # Critic pass threshold

# ── Memory settings ───────────────────────────────────────────────────────────
MEMORY_COLLECTION  = "assignment_memory"
MEMORY_TOP_K       = 3     # number of past answers to retrieve
EMBEDDING_MODEL    = "all-MiniLM-L6-v2"

# ── Skills registry ───────────────────────────────────────────────────────────
SKILLS = {
    "research" : "Research a topic in depth",
    "plan"     : "Break a task into a structured plan",
    "critique" : "Review and improve a piece of writing",
    "summarize": "Summarise a topic or document",
    "help"     : "List available skills",
}

# ── A2A config ────────────────────────────────────────────────────────────────
A2A_HOST    = "0.0.0.0"
A2A_BASE_URL = os.getenv("A2A_BASE_URL", "http://localhost:8000")
