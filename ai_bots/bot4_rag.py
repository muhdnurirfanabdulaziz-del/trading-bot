"""Bot 4 — Document Q&A (Layer 3: RAG over your own notes).

Answers questions using ONLY the content in notes.md. Uses simple keyword-overlap
retrieval so there's no vector database to set up — swap in embeddings later if
your notes grow large.
"""
import re
import sys
from pathlib import Path
import anthropic

MODEL = "claude-sonnet-4-6"
client = anthropic.Anthropic()

NOTES = Path(__file__).parent / "notes.md"


def load_chunks() -> list[str]:
    text = NOTES.read_text()
    return [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]


def retrieve(question: str, chunks: list[str], k: int = 3) -> list[str]:
    """Naive keyword-overlap retrieval — no vector DB required."""
    q_words = set(re.findall(r"\w+", question.lower()))
    scored = [
        (len(q_words & set(re.findall(r"\w+", chunk.lower()))), chunk)
        for chunk in chunks
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for score, chunk in scored[:k] if score > 0]


def ask(question: str) -> str:
    context = "\n\n".join(retrieve(question, load_chunks()))
    system = (
        "Answer the user's question using ONLY the notes below. "
        "If the notes don't cover it, say so plainly.\n\n"
        f"NOTES:\n{context}"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": question}],
    )
    return next((b.text for b in resp.content if b.type == "text"), "")


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What does a buy signal mean in this bot?"
    print(ask(question))
