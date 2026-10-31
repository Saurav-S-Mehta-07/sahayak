from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.dependencies import get_runtime  # noqa: E402
from app.rag.query_processor import QueryProcessor  # noqa: E402


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one retrieval-only test query.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    processed = QueryProcessor().process(args.query)
    results = get_runtime().retriever.retrieve(processed.variants, top_k=args.top_k)
    if not results:
        print("No matching indexed passages.")
        raise SystemExit(1)
    for result in results:
        metadata = result["metadata"]
        print(
            f"{metadata.get('document_name')} page {metadata.get('page_number')} "
            f"(similarity={result['similarity_score']:.3f})"
        )
        print(result["document"])
        print()
