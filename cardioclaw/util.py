from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote


def stable_id(*parts: str, length: int = 20) -> str:
    normalized = "|".join(part.strip().lower() for part in parts if part)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length]


def slugify(value: str, max_length: int = 72) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:max_length].rstrip("-") or "episode"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(value, indent=2, ensure_ascii=False, default=_json_default) + "\n",
    )


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value)!r}")


def join_url(base: str, *parts: str) -> str:
    encoded = "/".join(quote(part.strip("/"), safe="-._~") for part in parts)
    return f"{base.rstrip('/')}/{encoded}"
