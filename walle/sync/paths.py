"""同步相关文件路径（桌面 / 移动端共用）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SyncPaths:
    auth: Path
    sync_meta: Path
    assignments: Path
    sync_config: Path
    contacts: Path

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> "SyncPaths":
        return cls(
            auth=data_dir / "auth.json",
            sync_meta=data_dir / "sync_meta.json",
            assignments=data_dir / "assignments.json",
            sync_config=data_dir / "sync_config.json",
            contacts=data_dir / "contact_nicknames.json",
        )
