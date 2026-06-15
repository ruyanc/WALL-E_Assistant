"""同步后端配置与客户端工厂。"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .auth import AuthManager


class SyncBackendError(Exception):
    pass


@dataclass
class SyncBackendConfig:
    backend: str = "cloudbase"
    cloudbase_env_id: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""

    @property
    def configured(self) -> bool:
        if self.backend == "supabase":
            return bool(self.supabase_url and self.supabase_anon_key)
        return bool(self.cloudbase_env_id)


def _sync_config_candidates(primary: Path) -> list[Path]:
    candidates = [primary]
    if getattr(sys, "frozen", False):
        install_dir = Path(sys.executable).resolve().parent
        candidates.append(install_dir / "sync_config.json")
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def read_sync_config_env_id(config_path: Path) -> str:
    """读取 sync_config.json 中的环境 ID（不含 settings 覆盖）。"""
    if not config_path.is_file():
        return ""
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if isinstance(raw, dict):
            return str(raw.get("cloudbase_env_id", "") or "").strip()
    except (json.JSONDecodeError, OSError, TypeError):
        pass
    return ""


def load_backend_config(config_path: Path, settings_env_id: str = "") -> SyncBackendConfig:
    backend = os.environ.get("WALLE_SYNC_BACKEND", "cloudbase").strip().lower()
    env_id = os.environ.get("WALLE_CLOUDBASE_ENV_ID", "").strip() or settings_env_id.strip()
    url = os.environ.get("WALLE_SUPABASE_URL", "").strip()
    anon_key = os.environ.get("WALLE_SUPABASE_ANON_KEY", "").strip()

    for path in _sync_config_candidates(config_path):
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(raw, dict):
                continue
            if not os.environ.get("WALLE_SYNC_BACKEND"):
                backend = str(raw.get("backend", backend)).strip().lower() or backend
            if not env_id:
                env_id = str(raw.get("cloudbase_env_id", "")).strip()
            if not url:
                url = str(raw.get("supabase_url", "")).strip()
            if not anon_key:
                anon_key = str(raw.get("supabase_anon_key", "")).strip()
            if env_id or url or anon_key:
                break
        except (json.JSONDecodeError, OSError, TypeError):
            continue

    return SyncBackendConfig(
        backend=backend or "cloudbase",
        cloudbase_env_id=env_id,
        supabase_url=url.rstrip("/"),
        supabase_anon_key=anon_key,
    )


def create_sync_client(config: SyncBackendConfig, auth: "AuthManager", *, sync_meta_path=None):
    if not config.configured:
        raise SyncBackendError("backend_not_configured")
    if config.backend == "supabase":
        from .supabase_client import SupabaseClient

        return SupabaseClient(config, auth)
    from .cloudbase_client import CloudBaseClient

    return CloudBaseClient(config, auth, sync_meta_path=sync_meta_path)
