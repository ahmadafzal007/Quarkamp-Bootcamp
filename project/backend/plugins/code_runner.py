import subprocess
import tempfile
import os


def run_code(code: str, language: str = "python", timeout: int = 10) -> str:
    """Run code in a subprocess sandbox. Only Python supported for now."""
    if language != "python":
        return f"Unsupported language: {language}. Only python is supported."
    # Block dangerous patterns
    forbidden = ["import os", "import sys", "subprocess", "open(", "__import__", "eval(", "exec("]
    for pattern in forbidden:
        if pattern in code:
            return f"Blocked: '{pattern}' is not allowed in sandboxed code."
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            fname = f.name
        result = subprocess.run(
            ["python", fname],
            capture_output=True, text=True, timeout=timeout,
        )
        os.unlink(fname)
        if result.returncode == 0:
            return result.stdout[:2000] or "(no output)"
        return f"Error:\n{result.stderr[:1000]}"
    except subprocess.TimeoutExpired:
        return f"Timeout: code took more than {timeout}s"
    except Exception as e:
        return f"Run error: {e}"
