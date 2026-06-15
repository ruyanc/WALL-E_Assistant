"""增量同步合并（LWW）。"""

from __future__ import annotations

from typing import Any


def merge_records(
    local: dict[str, dict[str, Any]],
    remote: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged = dict(local)
    for key, remote_row in remote.items():
        local_row = merged.get(key)
        if local_row is None or float(remote_row["updated_at"]) > float(local_row["updated_at"]):
            merged[key] = remote_row
    return merged


def row_key(collection: str, record_id: str) -> str:
    return f"{collection}:{record_id}"
