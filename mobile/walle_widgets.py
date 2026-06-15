"""瓦力形象组件：页头、空状态与吉祥物面板。"""

from __future__ import annotations

from pathlib import Path

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image

from layout import Metrics, _attach_rounded_bg
from sprite import WalleSprite
from theme import MASCOT_BG, TEXT, TEXT_MUTED
from ui_widgets import Label

_ASSETS = Path(__file__).resolve().parent / "assets"
_ICON = _ASSETS / "icon.png"

# 各功能页默认动作
PAGE_ANIMS = {
    "todo": "wave",
    "notes": "talk",
    "remind": "look",
    "timer": "idle",
    "account": "happy",
    "empty": "idle",
    "login": "wave",
}


def walle_icon(size: float | None = None) -> Image:
    """静态瓦力图标（横幅等小尺寸场景）。"""
    s = size or dp(28)
    img = Image(
        source=str(_ICON) if _ICON.is_file() else "",
        size_hint=(None, None),
        size=(s, s),
        allow_stretch=True,
        keep_ratio=True,
    )
    return img


class WalleMascotPanel(BoxLayout):
    """圆角浅金底上的瓦力动画。"""

    def __init__(self, anim: str = "idle", size: float | None = None, **kwargs):
        s = size or dp(56)
        super().__init__(
            size_hint=(None, None),
            size=(s, s),
            padding=(dp(4), dp(4)),
            **kwargs,
        )
        _attach_rounded_bg(self, MASCOT_BG, radius=dp(12))
        pad = max(dp(4), int(s * 0.08))
        inner_size = max(dp(32), s - pad * 2)
        self._sprite = WalleSprite(
            anim=anim,
            size_hint=(None, None),
            size=(inner_size, inner_size),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self.add_widget(self._sprite)

    def set_anim(self, name: str) -> None:
        self._sprite.set_anim(name)

    def set_active(self, active: bool) -> None:
        if active:
            self._sprite.resume()
        else:
            self._sprite.pause()


def walle_page_header(
    title: str,
    subtitle: str | None = None,
    anim: str = "wave",
    mascot_size: float | None = None,
) -> BoxLayout:
    """功能页顶部：瓦力 + 标题 + 可选副标题。"""
    mascot_sz = mascot_size or dp(58)
    row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        spacing=dp(12),
        padding=(0, dp(4), 0, dp(6)),
    )
    mascot = WalleMascotPanel(anim=anim, size=mascot_sz)
    row.add_widget(mascot)

    text_col = BoxLayout(orientation="vertical", size_hint_x=1, spacing=dp(4))
    title_lbl = Label(
        text=title,
        color=TEXT,
        font_size=Metrics.font_lg,
        bold=True,
        size_hint_y=None,
        halign="left",
        valign="bottom",
    )
    title_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    title_lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", max(dp(24), val[1] + dp(2))))
    text_col.add_widget(title_lbl)

    if subtitle:
        sub_lbl = Label(
            text=subtitle,
            color=TEXT_MUTED,
            font_size=Metrics.font_sm,
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        sub_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        sub_lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", max(dp(20), val[1] + dp(4))))
        text_col.add_widget(sub_lbl)

    row.add_widget(text_col)
    row.height = max(mascot_sz + dp(8), text_col.minimum_height + dp(8))
    row.bind(minimum_height=row.setter("height"))
    row._walle_mascot = mascot
    return row


def walle_empty(text: str, anim: str = "idle") -> BoxLayout:
    """空列表：居中瓦力 + 说明文字。"""
    box = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        spacing=dp(10),
        padding=(dp(16), dp(20)),
    )
    mascot_row = BoxLayout(size_hint_y=None, height=dp(88))
    mascot_row.add_widget(Label())
    mascot_row.add_widget(WalleMascotPanel(anim=anim, size=dp(76)))
    mascot_row.add_widget(Label())
    box.add_widget(mascot_row)

    lbl = Label(
        text=text,
        color=TEXT_MUTED,
        font_size=Metrics.font_md,
        size_hint_y=None,
        halign="center",
        valign="top",
    )
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0] - dp(32), None)))
    lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", max(dp(40), val[1] + dp(8))))
    box.add_widget(lbl)
    box.bind(minimum_height=box.setter("height"))
    return box


def walle_section_title(text: str, anim: str = "talk") -> BoxLayout:
    """带小瓦力图标的分区标题行（静态图标，降低动画开销）。"""
    row = BoxLayout(size_hint_y=None, spacing=dp(8), padding=(0, dp(2)))
    mini_box = BoxLayout(size_hint=(None, None), size=(dp(32), dp(32)), padding=(dp(3), dp(3)))
    _attach_rounded_bg(mini_box, MASCOT_BG, radius=dp(8))
    mini_box.add_widget(walle_icon(dp(24)))
    lbl = Label(
        text=text,
        color=TEXT,
        font_size=Metrics.font_md,
        bold=True,
        size_hint_x=1,
        halign="left",
        valign="middle",
    )
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    row.add_widget(mini_box)
    row.add_widget(lbl)
    row.height = dp(40)
    return row


def set_screen_mascots_active(screen, active: bool) -> None:
    """暂停/恢复屏幕内瓦力动画（非当前页应暂停以节省资源）。"""
    for widget in screen.walk():
        if isinstance(widget, WalleMascotPanel):
            widget.set_active(active)
