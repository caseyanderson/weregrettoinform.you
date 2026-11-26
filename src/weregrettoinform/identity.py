"""Load local identity data used only for structural detection."""

from __future__ import annotations

import json
from pathlib import Path


def load_name_forms(path: Path) -> set[str]:
    identity = json.loads(path.read_text(encoding="utf-8"))
    name = identity["name"]

    first = name.get("first", "")
    middle = name.get("middle", "")
    last = name.get("last", "")

    return {
        " ".join(part for part in (first, middle, last) if part),
        " ".join(part for part in (first, last) if part),
        first,
    } - {""}
