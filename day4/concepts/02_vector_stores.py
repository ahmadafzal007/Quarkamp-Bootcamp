"""
CONCEPT 2 — Vector Stores with ChromaDB
=========================================
A vector store is a database that stores embeddings and lets you search
by semantic similarity instead of exact keyword match.

This script shows:
  1. Collections and persistent storage
  2. Filtering by metadata
  3. Similarity scoring
  4. Updating and deleting documents
  5. When to use RAG vs fine-tuning

Run:
    conda run -n bootcamp python day4/concepts/02_vector_stores.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer

load_dotenv(Path(__file__).parents[2] / ".env")

print("  Loading embedding model...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# ── PERSISTENT ChromaDB (survives restarts, unlike ephemeral Client()) ────────
DATA_DIR = Path(__file__).parents[2] / "data" / "chroma_demo"
DATA_DIR.mkdir(parents=True, exist_ok=True)
chroma = chromadb.PersistentClient(path=str(DATA_DIR))


def part1_collections():
    """Collections are like tables — separate namespaces for different data."""
    print("\n" + "=" * 62)
    print("  PART 1: Collections")
    print("=" * 62)

    # Create or get two separate collections
    physics_col = chroma.get_or_create_collection("physics_notes")
    history_col  = chroma.get_or_create_collection("history_notes")

    physics_docs = [
        ("ph1", "Kinetic energy = 0.5 × mass × velocity²", {"chapter": "3"}),
        ("ph2", "Potential energy = mass × gravity × height",  {"chapter": "3"}),
        ("ph3", "Conservation of energy: total energy in a closed system is constant.", {"chapter": "4"}),
    ]
    history_docs = [
        ("hi1", "The Roman Empire fell in 476 AD due to military, economic, and political factors.", {"era": "ancient"}),
        ("hi2", "The Industrial Revolution began in Britain around 1760 with textile machinery.", {"era": "modern"}),
    ]

    for doc_id, text, meta in physics_docs:
        physics_col.upsert(
            ids=[doc_id],
            embeddings=[embedder.encode(text).tolist()],
            documents=[text],
            metadatas=[meta],
        )
    for doc_id, text, meta in history_docs:
        history_col.upsert(
            ids=[doc_id],
            embeddings=[embedder.encode(text).tolist()],
            documents=[text],
            metadatas=[meta],
        )

    print(f"  physics_notes: {physics_col.count()} docs")
    print(f"  history_notes: {history_col.count()} docs")
    print("  Collections keep subjects separate — no cross-contamination.")
    return physics_col, history_col


def part2_metadata_filtering(physics_col):
    """Filter by metadata before doing similarity search."""
    print("\n" + "=" * 62)
    print("  PART 2: Metadata Filtering")
    print("=" * 62)

    query    = "energy in physical systems"
    q_embed  = embedder.encode(query).tolist()

    # Without filter: searches all documents
    all_results = physics_col.query(
        query_embeddings=[q_embed],
        n_results=3,
    )
    print(f"\n  Without filter ({physics_col.count()} docs searched):")
    for doc in all_results["documents"][0]:
        print(f"    • {doc[:80]}")

    # With filter: only search Chapter 3
    ch3_results = physics_col.query(
        query_embeddings=[q_embed],
        n_results=3,
        where={"chapter": "3"},
    )
    print(f"\n  With filter (chapter=3 only):")
    for doc in ch3_results["documents"][0]:
        print(f"    • {doc[:80]}")

    print("\n  Use metadata filters to scope searches:")
    print("  e.g., only search this student's past answers, or this subject.")


def part3_similarity_scores(physics_col):
    """Understand what the distance scores mean."""
    print("\n" + "=" * 62)
    print("  PART 3: Similarity Scores")
    print("=" * 62)

    queries = [
        "energy and work in physics",              # should be very similar
        "photosynthesis in plants",                # should be dissimilar
    ]

    for query in queries:
        results = physics_col.query(
            query_embeddings=[embedder.encode(query).tolist()],
            n_results=2,
            include=["documents", "distances"],
        )
        print(f"\n  Query: \"{query}\"")
        for doc, dist in zip(results["documents"][0], results["distances"][0]):
            similarity = 1 - dist  # ChromaDB uses cosine distance by default
            bar = "█" * int(similarity * 20)
            print(f"    [{bar:<20}] {similarity:.2f}  {doc[:60]}")

    print("""
  Distance 0.0 = identical.  Distance 2.0 = opposite.
  Typical good match: < 0.5 distance (> 0.5 similarity).
  Use a threshold to filter out irrelevant results.
""")


def part4_upsert_delete(physics_col):
    """Documents can be updated or removed at any time."""
    print("\n" + "=" * 62)
    print("  PART 4: Upsert and Delete")
    print("=" * 62)

    # Add a new document
    new_text = "Newton's Law of Gravitation: F = G × m1 × m2 / r²"
    physics_col.upsert(
        ids=["ph4"],
        embeddings=[embedder.encode(new_text).tolist()],
        documents=[new_text],
        metadatas=[{"chapter": "5"}],
    )
    print(f"  After upsert: {physics_col.count()} docs")

    # Update it (same id, new content)
    updated_text = "Newton's Law of Gravitation: F = G × m1 × m2 / r²  (G = 6.674×10⁻¹¹ N⋅m²/kg²)"
    physics_col.upsert(
        ids=["ph4"],
        embeddings=[embedder.encode(updated_text).tolist()],
        documents=[updated_text],
        metadatas=[{"chapter": "5"}],
    )
    print(f"  After update: still {physics_col.count()} docs (upsert = update if exists)")

    # Delete it
    physics_col.delete(ids=["ph4"])
    print(f"  After delete: {physics_col.count()} docs")


if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  CHROMADB VECTOR STORE DEEP DIVE")
    print("=" * 62)

    physics_col, history_col = part1_collections()
    part2_metadata_filtering(physics_col)
    part3_similarity_scores(physics_col)
    part4_upsert_delete(physics_col)

    print("\n" + "=" * 62)
    print("  IN THE PROJECT (Day 5)")
    print("=" * 62)
    print("""
  Collection: "assignments"
    - id:       UUID per answered question
    - document: question + answer (concatenated for retrieval)
    - metadata: {student_id, subject, skill, timestamp, score}

  On each new question:
    1. Query collection for top-3 similar past answers
    2. Inject them as context into the Researcher node
    3. After the run: upsert the new Q&A pair

  This means the system gets better with every question answered.
""")
