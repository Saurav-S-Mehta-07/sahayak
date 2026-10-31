from __future__ import annotations

from pathlib import Path

from app.core.config import settings


def discover_pdfs(pdf_dir: Path = settings.pdf_dir) -> list[Path]:
    root = pdf_dir.resolve()
    if not root.exists():
        return []
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.as_posix().casefold(),
    )
