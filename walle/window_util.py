"""窗口置顶工具（Windows 下使用 HWND_TOPMOST 增强 Qt 行为）。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QWidget

if sys.platform == "win32":
    import ctypes

    _HWND_TOPMOST = -1
    _SWP_TOPMOST = 0x0002 | 0x0001 | 0x0010 | 0x0040  # NOMOVE | NOSIZE | NOACTIVATE | SHOWWINDOW
else:
    ctypes = None  # type: ignore[assignment]


def raise_window_topmost(widget: QWidget) -> None:
    """将窗口提升到所有普通窗口之上（不抢焦点）。"""
    if not widget.isVisible():
        return
    widget.raise_()
    if sys.platform == "darwin":
        return
    if sys.platform != "win32" or ctypes is None:
        return
    try:
        hwnd = int(widget.winId())
        if hwnd:
            ctypes.windll.user32.SetWindowPos(hwnd, _HWND_TOPMOST, 0, 0, 0, 0, _SWP_TOPMOST)
    except (OSError, AttributeError, TypeError, ValueError):
        pass
