from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable


def split_csvish(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;\n]", value or "") if part.strip()]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (value or "").lower())).strip()


def stable_id(parts: Iterable[str], length: int = 12) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]


def truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."
