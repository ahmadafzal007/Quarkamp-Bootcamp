import math


def calculator(expression: str) -> str:
    safe_names = {"sqrt": math.sqrt, "pi": math.pi, "abs": abs, "round": round, "pow": pow, "log": math.log, "exp": math.exp}
    try:
        result = eval(expression, {"__builtins__": {}}, safe_names)  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"
