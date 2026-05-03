from .web_search import web_search
from .calculator import calculator
from .pdf_reader import read_file
from .code_runner import run_code
from .memory import memory_store, memory_retrieve

PLUGIN_REGISTRY = {
    "web_search"     : web_search,
    "calculator"     : calculator,
    "read_file"      : read_file,
    "run_code"       : run_code,
    "memory_store"   : memory_store,
    "memory_retrieve": memory_retrieve,
}

PLUGIN_SCHEMAS = [
    {
        "name"        : "web_search",
        "description" : "Search the web for current information. Use for any factual question.",
        "input_schema": {
            "type"      : "object",
            "properties": {
                "query"      : {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name"        : "calculator",
        "description" : "Evaluate a math expression. Use for ALL arithmetic.",
        "input_schema": {
            "type"      : "object",
            "properties": {"expression": {"type": "string"}},
            "required"  : ["expression"],
        },
    },
    {
        "name"        : "read_file",
        "description" : "Read a .txt or .pdf file. Needs an absolute path.",
        "input_schema": {
            "type"      : "object",
            "properties": {"path": {"type": "string"}},
            "required"  : ["path"],
        },
    },
    {
        "name"        : "memory_retrieve",
        "description" : "Search memory for similar past Q&A pairs.",
        "input_schema": {
            "type"      : "object",
            "properties": {
                "query"    : {"type": "string"},
                "n_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
]


def execute_plugin(name: str, inputs: dict) -> str:
    """Dispatch a plugin call and always return a string."""
    fn = PLUGIN_REGISTRY.get(name)
    if fn is None:
        return f"Unknown plugin: {name}"
    try:
        return str(fn(**inputs))
    except Exception as e:
        return f"Plugin error ({name}): {e}"
