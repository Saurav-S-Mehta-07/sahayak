from __future__ import annotations

import re

from app.utils.text_utils import clean_text

_PAGE_FOOTER = re.compile(r"^\s*(?:page\s+)?\d+\s*(?:of|/)\s*\d+\s*$", re.IGNORECASE)


def clean_page(text: str) -> str:
    lines = [line.rstrip() for line in clean_text(text).splitlines()]
    lines = [line for line in lines if not _PAGE_FOOTER.match(line)]
    return clean_text("\n".join(lines))
