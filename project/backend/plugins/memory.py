import json
import uuid
import datetime
from pathlib import Path
from ..config import CHROMA_DIR, MEMORY_COLLECTION, EMBEDDING_MODEL, MEMORY_TOP_K

_chroma     = None
_collection = None
_embedder   = None


def _init():
    global _chroma, _collection, _embedder
    if _collection is not None:
        return
    import chromadb
    from sentence_transformers import SentenceTransformer
    _chroma     = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = _chroma.get_or_create_collection(MEMORY_COLLECTION)
    _embedder   = SentenceTransformer(EMBEDDING_MODEL)


def memory_store(question: str, answer: str, subject: str = "", score: int = 0) -> str:
    _init()
    doc_id = str(uuid.uuid4())
    text   = f"Q: {question}\nA: {answer}"
    _collection.upsert(
        ids        = [doc_id],
        embeddings = [_embedder.encode(text).tolist()],
        documents  = [text],
        metadatas  = [{
            "question" : question[:200],
            "subject"  : subject,
            "score"    : score,
            "timestamp": datetime.datetime.now().isoformat(),
        }],
    )
    return json.dumps({"stored": True, "id": doc_id, "total": _collection.count()})


def memory_retrieve(query: str, n_results: int = MEMORY_TOP_K) -> str:
    _init()
    if _collection.count() == 0:
        return json.dumps({"results": []})
    q_embed = _embedder.encode(query).tolist()
    results = _collection.query(
        query_embeddings=[q_embed],
        n_results=min(n_results, _collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    hits = [
        {"content": doc[:300], "similarity": round(1 - dist, 3), "metadata": meta}
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]
    return json.dumps({"results": hits, "total": _collection.count()})


def memory_count() -> int:
    _init()
    return _collection.count()
