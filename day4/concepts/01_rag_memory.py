"""
CONCEPT 1 — RAG Memory (Retrieval-Augmented Generation)
=========================================================
RAG = embed text → store in vector DB → retrieve by similarity → inject into prompt

This script shows the full cycle:
  1. Embed a document (turn it into a vector)
  2. Store it in ChromaDB
  3. Retrieve the most relevant chunk for a query
  4. Inject the retrieved context into a Claude prompt

Run:
    conda run -n bootcamp python day4/concepts/01_rag_memory.py
"""

from pathlib import Path
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
import anthropic

load_dotenv(Path(__file__).parents[2] / ".env")
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"

# ── Setup embedding model ─────────────────────────────────────────────────────
# sentence-transformers runs locally — no API key needed.
# "all-MiniLM-L6-v2" is fast, small, and good enough for educational use.
print("  Loading embedding model (first run downloads ~80MB)...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# ── Setup ChromaDB (in-memory for this demo) ──────────────────────────────────
chroma  = chromadb.Client()
collection = chroma.get_or_create_collection("assignment_memory")


# ── STEP 1: Embed and store documents ─────────────────────────────────────────

SAMPLE_DOCUMENTS = [
    {
        "id"  : "doc1",
        "text": (
            "Newton's First Law (Law of Inertia): An object at rest stays at rest and "
            "an object in motion stays in motion unless acted upon by an external force. "
            "Example: a ball rolling on ice keeps rolling."
        ),
        "metadata": {"subject": "physics", "topic": "newton_laws"},
    },
    {
        "id"  : "doc2",
        "text": (
            "Newton's Second Law: Force = mass × acceleration (F=ma). "
            "A heavier object needs more force to achieve the same acceleration. "
            "Example: pushing a shopping cart vs a car."
        ),
        "metadata": {"subject": "physics", "topic": "newton_laws"},
    },
    {
        "id"  : "doc3",
        "text": (
            "The French Revolution (1789-1799) was driven by Enlightenment ideas, "
            "financial crisis, and social inequality (Three Estates system). "
            "Key events: storming of the Bastille, Declaration of the Rights of Man."
        ),
        "metadata": {"subject": "history", "topic": "french_revolution"},
    },
    {
        "id"  : "doc4",
        "text": (
            "Mitosis produces two identical daughter cells for growth/repair. "
            "Meiosis produces four unique haploid cells for reproduction. "
            "Key difference: meiosis has two division rounds and enables genetic variation."
        ),
        "metadata": {"subject": "biology", "topic": "cell_division"},
    },
]


def store_documents(docs: list[dict]) -> None:
    print(f"\n  Storing {len(docs)} documents in ChromaDB...")
    for doc in docs:
        embedding = embedder.encode(doc["text"]).tolist()
        collection.add(
            ids        = [doc["id"]],
            embeddings = [embedding],
            documents  = [doc["text"]],
            metadatas  = [doc["metadata"]],
        )
    print(f"  Collection now has {collection.count()} documents.")


# ── STEP 2: Retrieve relevant context ────────────────────────────────────────

def retrieve(query: str, n_results: int = 2) -> list[str]:
    query_embedding = embedder.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
    )
    return results["documents"][0]  # list of matching document texts


# ── STEP 3: RAG-augmented Claude call ────────────────────────────────────────

def answer_with_rag(question: str) -> dict:
    context_docs = retrieve(question)
    context_block = "\n\n".join(f"[Context {i+1}]: {doc}" for i, doc in enumerate(context_docs))

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=(
            "You are a university assistant. Use the provided context to answer "
            "accurately. If the context doesn't cover the question, say so clearly."
        ),
        messages=[{
            "role"   : "user",
            "content": f"Context from memory:\n{context_block}\n\nQuestion: {question}",
        }],
    )
    return {
        "question": question,
        "context" : context_docs,
        "answer"  : response.content[0].text,
    }


def answer_without_rag(question: str) -> str:
    """Control: same question without retrieved context."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system="You are a university assistant. Answer concisely.",
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text


if __name__ == "__main__":
    print("\n" + "=" * 62)
    print("  RAG MEMORY DEMO")
    print("=" * 62)

    store_documents(SAMPLE_DOCUMENTS)

    test_questions = [
        "What's the difference between mitosis and meiosis?",
        "Explain Newton's second law with an example.",
    ]

    for question in test_questions:
        print("\n" + "─" * 62)
        print(f"  Question: {question}")
        print("─" * 62)

        print("\n  WITHOUT RAG:")
        no_rag = answer_without_rag(question)
        print(f"  {no_rag[:200]}...")

        print("\n  WITH RAG:")
        rag_result = answer_with_rag(question)
        print(f"  Retrieved contexts: {len(rag_result['context'])}")
        print(f"  {rag_result['answer'][:300]}...")

    print("\n" + "=" * 62)
    print("  KEY INSIGHT")
    print("=" * 62)
    print("""
  RAG answers are grounded in YOUR stored documents.
  The model can't hallucinate facts that contradict your knowledge base.

  Similarity search finds documents by MEANING not exact words:
    query: "cell division reproduction"
    → finds doc about mitosis/meiosis (different words, same concept)

  Day 5: the project stores every answered question in ChromaDB.
  Future questions retrieve similar past answers as context —
  the agent gets smarter the more questions it answers.
""")
