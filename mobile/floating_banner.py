"""应用内顶部横幅（前台时模拟悬浮提示，无需系统悬浮窗权限）。"""

from __future__ import annotations

from kivy.animation import Animation
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout

from layout import Metrics
from theme import ACCENT, BANNER_BG, BANNER_TEXT, CARD_RADIUS
from ui_widgets import Label


from walle_widgets import walle_icon


class _BannerBar(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(52),
            padding=(dp(14), dp(10)),
            spacing=dp(10),
            **kwargs,
        )
        from kivy.graphics import Color, RoundedRectangle

        with self.canvas.before:
            Color(*BANNER_BG)
            self._bg = RoundedRectangle(radius=[dp(CARD_RADIUS), dp(CARD_RADIUS), 0, 0])
        self.bind(pos=self._sync, size=self._sync)

        self.add_widget(walle_icon(dp(30)))

        self._title = Label(
            text="",
            color=ACCENT,
            font_size=Metrics.font_sm,
            bold=True,
            size_hint_x=None,
            width=dp(64),
            halign="left",
            valign="middle",
        )
        self._title.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        self.add_widget(self._title)

        self._message = Label(
            text="",
            color=BANNER_TEXT,
            font_size=Metrics.font_sm,
            halign="left",
            valign="middle",
            size_hint_x=1,
        )
        self._message.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        self.add_widget(self._message)

    def _sync(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size


class BannerHost(FloatLayout):
    """在根布局上叠加可滑入的横幅。"""

    def __init__(self, content, **kwargs):
        super().__init__(**kwargs)
        self.add_widget(content)
        self._banner = _BannerBar(pos_hint={"x": 0, "top": 1})
        self._banner.opacity = 0
        self._banner.disabled = True
        self.add_widget(self._banner)
        self._anim: Animation | None = None
        self._hide_ev = None

    def show(self, title: str, message: str, duration: float = 3.5) -> None:
        from kivy.clock import Clock

        self._banner._title.text = title
        self._banner._message.text = message
        self._banner.height = max(dp(52), Metrics.font_sm * 2 + dp(24))
        if self._hide_ev is not None:
            self._hide_ev.cancel()
        if self._anim is not None:
            self._anim.cancel(self._banner)
        self._banner.disabled = False
        self._banner.y = self.height
        show = Animation(y=self.height - self._banner.height, opacity=1, duration=0.22, t="out_quad")
        show.start(self._banner)
        self._anim = show
        self._hide_ev = Clock.schedule_once(lambda _dt: self._hide(), duration)

    def _hide(self) -> None:
        self._hide_ev = None
        hide = Animation(y=self.height, opacity=0, duration=0.18, t="in_quad")
        hide.bind(on_complete=lambda *_: setattr(self._banner, "disabled", True))
        hide.start(self._banner)
        self._anim = hide


_banner_host: BannerHost | None = None


def register_banner_host(host: BannerHost) -> None:
    global _banner_host
    _banner_host = host


def show_in_app_banner(title: str, message: str) -> bool:
    if _banner_host is None:
        return False
    _banner_host.show(title, message)
    return True
