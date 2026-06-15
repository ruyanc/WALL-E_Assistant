"""打包前将 walle/sync 复制到 mobile/walle，供 APK 收录（无需 PySide6）。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

MOBILE = Path(__file__).resolve().parent
DEST = MOBILE / "walle"
CONFIG_STUB = MOBILE / "walle_config_stub.py"


def _project_root() -> Path:
    env = os.environ.get("WALLE_PROJECT_ROOT")
    if env:
        return Path(env)
    parent = MOBILE.parent
    if (parent / "walle" / "sync").is_dir():
        return parent
    return parent


ROOT = _project_root()
SYNC_SRC = ROOT / "walle" / "sync"

SKIP_NAMES = {
    "service.py",
    "__pycache__",
}

MOBILE_WALLE_INIT = """\"\"\"WALL-E 移动端 walle 包。\"\"\"\n\n__version__ = "1.2.1"\n"""

MOBILE_SYNC_INIT = """\"\"\"移动端同步子包（不含桌面 Qt SyncService）。\"\"\"\n\n__all__ = []\n"""


def main() -> None:
    if not SYNC_SRC.is_dir():
        raise SystemExit(
            f"walle/sync not found at {SYNC_SRC}\n"
            f"Set WALLE_PROJECT_ROOT to the repo root (e.g. export WALLE_PROJECT_ROOT=/mnt/c/.../WALL-E)"
        )
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    (DEST / "__init__.py").write_text(MOBILE_WALLE_INIT, encoding="utf-8")

    if CONFIG_STUB.is_file():
        shutil.copy2(CONFIG_STUB, DEST / "config.py")
    else:
        raise SystemExit(f"缺少移动端配置模板: {CONFIG_STUB}")

    shutil.copytree(
        SYNC_SRC,
        DEST / "sync",
        ignore=lambda _d, names: [n for n in names if n in SKIP_NAMES],
    )
    (DEST / "sync" / "__init__.py").write_text(MOBILE_SYNC_INIT, encoding="utf-8")
    print(f"Copied mobile sync bundle to {DEST}")


if __name__ == "__main__":
    main()
