from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = "".join(char for char in text if char in "\n\t" or unicodedata.category(char)[0] != "C")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)
    return text.strip()


def slugify(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "unknown-scheme"


def scheme_name_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[_-]+", " ", stem)
    return re.sub(r"\s+", " ", stem).strip()
