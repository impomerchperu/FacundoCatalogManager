from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_benchmark_report(
    output_path: str | Path | None,
    payload: dict[str, Any],
) -> Path | None:
    """Persist a benchmark payload as an atomically replaced JSON artifact."""
    if output_path is None:
        return None

    raw_path = str(output_path).strip()
    if not raw_path:
        return None

    path = Path(raw_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_name(f"{path.name}.tmp")
    content = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    temporary_path.write_text(f"{content}\n", encoding="utf-8")
    temporary_path.replace(path)
    return path
