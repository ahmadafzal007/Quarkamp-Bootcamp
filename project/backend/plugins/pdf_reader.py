from pathlib import Path


def read_file(path: str, max_chars: int = 4000) -> str:
    fp = Path(path)
    if not fp.exists():
        return f"File not found: {path}"
    if fp.suffix.lower() == ".pdf":
        try:
            import PyPDF2
            with open(fp, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
            return text[:max_chars] + ("...[truncated]" if len(text) > max_chars else "")
        except Exception as e:
            return f"PDF error: {e}"
    try:
        return fp.read_text(encoding="utf-8")[:max_chars]
    except Exception as e:
        return f"Read error: {e}"
