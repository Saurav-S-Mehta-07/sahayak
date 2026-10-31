from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.dependencies import get_runtime  # noqa: E402


if __name__ == "__main__":
    runtime = get_runtime()
    collection = runtime.vector_store.collection
    existing_ids = collection.get(include=["metadatas"])["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)
    runtime.ingestion.clear_metadata()
    print(runtime.ingestion.ingest())
