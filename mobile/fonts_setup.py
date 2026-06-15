"""注册支持中文的 UI 字体（常规 + 粗体）。"""

from __future__ import annotations

import os
from pathlib import Path

from kivy.core.text import LabelBase

UI_FONT = "WalleUI"
UI_FONT_BOLD = "WalleUIBold"
_FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
_FONT_FILE = _FONT_DIR / "walle_ui.ttf"
_FONT_BOLD_FILE = _FONT_DIR / "walle_ui_bold.ttf"
_registered = False
_has_bold = False


def register_fonts() -> str | None:
    global _registered, _has_bold
    if not _FONT_FILE.is_file():
        return None
    if not _registered:
        LabelBase.register(name=UI_FONT, fn_regular=str(_FONT_FILE))
        if _FONT_BOLD_FILE.is_file():
            LabelBase.register(name=UI_FONT_BOLD, fn_regular=str(_FONT_BOLD_FILE))
            _has_bold = True
        _registered = True
    return UI_FONT


def has_bold_font() -> bool:
    return _has_bold


def font_kwargs(kwargs: dict) -> dict:
    bold = kwargs.get("bold", False)
    if _registered:
        if bold and _has_bold:
            kwargs["font_name"] = UI_FONT_BOLD
            kwargs["bold"] = False
        else:
            kwargs.setdefault("font_name", UI_FONT)
    return kwargs


def font_candidates() -> list[Path]:
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    wsl_win = Path("/mnt/c/Windows/Fonts")
    names = (
        "msyh.ttc",
        "msyhbd.ttc",
        "msyhl.ttc",
        "simhei.ttf",
        "simsun.ttc",
        "NotoSansSC-Regular.otf",
    )
    out: list[Path] = []
    for base in (win, wsl_win):
        for name in names:
            p = base / name
            if p.is_file():
                out.append(p)
    bundled = _FONT_DIR / "walle_ui.ttf"
    if bundled.is_file():
        out.append(bundled)
    return out
