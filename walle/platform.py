"""桌面平台能力检测。"""

from __future__ import annotations

import sys

_DESKTOP_SYNC_PLATFORMS = frozenset({"win32", "darwin"})


def is_desktop_sync_platform() -> bool:
    """Windows / macOS 桌面端启用 CloudBase 同步与任务派发。"""
    return sys.platform in _DESKTOP_SYNC_PLATFORMS
