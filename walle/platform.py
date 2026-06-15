"""桌面平台能力检测。"""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont

_DESKTOP_SYNC_PLATFORMS = frozenset({"win32", "darwin"})


def is_desktop_sync_platform() -> bool:
    """Windows / macOS 桌面端启用 CloudBase 同步与任务派发。"""
    return sys.platform in _DESKTOP_SYNC_PLATFORMS


def is_macos() -> bool:
    return sys.platform == "darwin"


def menu_font_family() -> str:
    return ui_font_family()


def ui_font_family() -> str:
    if is_macos():
        return '"PingFang SC", "Helvetica Neue", sans-serif'
    return '"Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif'


def header_font() -> QFont:
    font = QFont()
    if is_macos():
        font.setFamilies(["PingFang SC", "Helvetica Neue", "sans-serif"])
    else:
        font.setFamilies(["Microsoft YaHei UI", "PingFang SC", "Segoe UI", "sans-serif"])
    font.setPointSize(16)
    font.setBold(True)
    return font


def panel_window_title(*, logged_in: bool = False, account: str | None = None) -> str:
    """控制台窗口标题；macOS 使用短标题避免顶栏/标签截断。"""
    from .i18n import tab_label, tr

    if is_macos():
        if logged_in and account:
            return tab_label("panel.header.logged_in").format(account=account)
        return tab_label("panel.title")
    if logged_in and account:
        return tr("panel.header.logged_in", account=account)
    return tr("panel.title")


def application_display_name() -> str:
    from .i18n import tr

    if is_macos():
        return tr("app.menu_name")
    return tr("app.name")
