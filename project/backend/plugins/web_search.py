def web_search(query: str, max_results: int = 3) -> str:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"• {r['title']}\n  {r['body'][:250]}")
        return "\n\n".join(results) if results else "No results found."
    except ImportError:
        return "web_search unavailable: pip install duckduckgo-search"
    except Exception as e:
        return f"Search error: {e}"
