from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.dependencies import get_runtime  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(get_runtime().ingestion.ingest(), indent=2, ensure_ascii=False))
