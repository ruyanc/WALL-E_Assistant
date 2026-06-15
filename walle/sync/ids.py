"""同步用 ID 与时间戳工具。"""

from __future__ import annotations

import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def migrate_id(raw_id: object, *, namespace: str) -> str:
    """将旧版整数 id 稳定映射为 UUID 字符串。"""
    if isinstance(raw_id, str) and raw_id:
        return raw_id
    try:
        num = int(raw_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return new_id()
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"walle-{namespace}-{num}"))
