"""
Pre-flight check — run this before Day 1.
  conda run -n bootcamp python setup/verify_setup.py
"""
import importlib
import os
import sys
from pathlib import Path

PACKAGES = [
    ("anthropic",            "anthropic"),
    ("langgraph",            "langgraph"),
    ("langchain_core",       "langchain-core"),
    ("chromadb",             "chromadb"),
    ("sentence_transformers","sentence-transformers"),
    ("fastapi",              "fastapi"),
    ("uvicorn",              "uvicorn[standard]"),
    ("sse_starlette",        "sse-starlette"),
    ("dotenv",               "python-dotenv"),
    ("duckduckgo_search",    "duckduckgo-search"),
    ("PyPDF2",               "PyPDF2"),
    ("agentops",             "agentops"),
    ("mcp",                  "mcp"),
    ("rich",                 "rich"),
    ("typer",                "typer"),
]

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
BOLD  = "\033[1m"
RESET = "\033[0m"

ok  = f"{GREEN}✓{RESET}"
bad = f"{RED}✗{RESET}"

def check_packages() -> bool:
    all_ok = True
    for module, install_name in PACKAGES:
        try:
            importlib.import_module(module)
            print(f"  {ok} {install_name}")
        except ImportError:
            print(f"  {bad} {install_name}  →  pip install {install_name}")
            all_ok = False
    return all_ok

def check_env_file() -> bool:
    env_path = Path(".env")
    if not env_path.exists():
        # also check parent dirs up to Bootcamp root
        for p in Path(__file__).parents:
            candidate = p / ".env"
            if candidate.exists():
                env_path = candidate
                break

    if not env_path.exists():
        print(f"  {bad} .env not found — copy setup/.env.example to the project root")
        return False

    from dotenv import load_dotenv
    load_dotenv(env_path)
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key.startswith("sk-ant-..."):
        print(f"  {bad} ANTHROPIC_API_KEY not set in {env_path}")
        return False
    print(f"  {ok} ANTHROPIC_API_KEY  ({key[:16]}...)")
    return True

def check_api() -> bool:
    try:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv()
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=20,
            messages=[{"role": "user", "content": "Reply with exactly: SETUP OK"}],
        )
        reply = resp.content[0].text.strip()
        print(f"  {ok} Live API call succeeded → \"{reply}\"")
        return True
    except Exception as e:
        print(f"  {bad} API call failed: {e}")
        return False

def check_node() -> bool:
    import subprocess
    result = subprocess.run(["node", "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  {ok} Node.js {result.stdout.strip()}")
        return True
    print(f"  {bad} Node.js not found — install from nodejs.org (needed for Day 5 frontend)")
    return False

def check_docker() -> bool:
    import subprocess
    result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  {ok} {result.stdout.strip()}")
        return True
    print(f"  {YELLOW}!{RESET} Docker not found — needed for Day 5 only")
    return True  # non-blocking

print(f"\n{BOLD}{'='*52}{RESET}")
print(f"{BOLD}  AGENTIC AI BOOTCAMP — SETUP VERIFICATION{RESET}")
print(f"{BOLD}{'='*52}{RESET}")

print(f"\n{BOLD}[1/4] Python packages{RESET}")
pkg_ok = check_packages()

print(f"\n{BOLD}[2/4] API keys (.env){RESET}")
env_ok = check_env_file()

if env_ok:
    print(f"\n{BOLD}[3/4] Live API test{RESET}")
    api_ok = check_api()
else:
    print(f"\n{BOLD}[3/4] Live API test{RESET}  (skipped — fix .env first)")
    api_ok = False

print(f"\n{BOLD}[4/4] Node.js + Docker{RESET}")
check_node()
check_docker()

print(f"\n{BOLD}{'='*52}{RESET}")
if pkg_ok and env_ok and api_ok:
    print(f"{GREEN}{BOLD}  ALL CHECKS PASSED — you're ready for Day 1! 🚀{RESET}")
else:
    print(f"{RED}{BOLD}  SOME CHECKS FAILED — fix the items above.{RESET}")
print(f"{BOLD}{'='*52}{RESET}\n")

sys.exit(0 if (pkg_ok and env_ok and api_ok) else 1)
