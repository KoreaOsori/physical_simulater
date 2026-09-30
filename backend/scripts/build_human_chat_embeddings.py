"""One-off build script (docs/31-human-chat-semantic-search.md): embeds
every doc in the human chat corpus (app/data/human_chat_context.py's
`_build_corpus()` -- region anatomical notes, disorder descriptions, gene
descriptions, all already-cited real data) with OpenAI's
text-embedding-3-small model, and writes the result to
app/data/sources/human/human_chat_embeddings.json as a committed build
artifact. Runtime (human_chat_context.semantic_search_corpus) only embeds
the user's QUERY live -- corpus embeddings are never recomputed on request.

Run manually whenever the chat corpus changes (a new region note, disorder,
or gene description) -- there's no drift detection beyond the model/
dimensions check `_load_doc_embeddings` already does:

    cd backend
    ./.venv/Scripts/python scripts/build_human_chat_embeddings.py

Needs a real OPENAI_API_KEY in backend/.env (same key the chat endpoint
already uses) -- this is a real, billed API call, though tiny: ~1,000 short
docs (~60 chars average) is on the order of 15-20K tokens total, a few
thousandths of a cent at this model's published per-token rate.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from openai import OpenAI  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.data.human_chat_context import (  # noqa: E402
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EMBEDDINGS_PATH,
    _build_corpus,
)

# The embeddings API accepts a batch of inputs per call -- real published
# OpenAI limit is much higher, but a modest batch size keeps any single
# request small/retriable and progress visible.
BATCH_SIZE = 100


def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY not set in backend/.env -- cannot build real embeddings.")

    docs = _build_corpus()
    print(f"Embedding {len(docs)} corpus docs with {EMBEDDING_MODEL} (dimensions={EMBEDDING_DIMENSIONS})...")

    client = OpenAI(api_key=settings.openai_api_key)
    doc_embeddings: dict[str, list[float]] = {}

    for start in range(0, len(docs), BATCH_SIZE):
        batch = docs[start : start + BATCH_SIZE]
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[doc.text for doc in batch],
            dimensions=EMBEDDING_DIMENSIONS,
        )
        for doc, item in zip(batch, response.data):
            doc_embeddings[doc.id] = item.embedding
        print(f"  {min(start + BATCH_SIZE, len(docs))}/{len(docs)}")
        time.sleep(0.1)  # polite pacing, not a rate-limit necessity at this volume

    payload = {
        "model": EMBEDDING_MODEL,
        "dimensions": EMBEDDING_DIMENSIONS,
        "doc_count": len(doc_embeddings),
        "doc_embeddings": doc_embeddings,
    }
    EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EMBEDDINGS_PATH.write_text(json.dumps(payload), encoding="utf-8")
    print(f"Wrote {len(doc_embeddings)} embeddings to {EMBEDDINGS_PATH} ({EMBEDDINGS_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
