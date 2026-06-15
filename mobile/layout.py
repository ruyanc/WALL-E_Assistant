"""按屏幕尺寸计算间距、字号与控件布局。"""

from __future__ import annotations

from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView


class FormScrollView(ScrollView):
    """表单/列表滚动：优先把触摸交给子控件（修复 Android 输入框无法聚焦）。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._focus_bound: set[int] = set()

    def _dispatch_touch(self, touch, method: str) -> bool:
        if self.collide_point(*touch.pos):
            for child in reversed(list(self.walk())):
                if child is self:
                    continue
                if child.dispatch(method, touch):
                    self._watch_focus_tree(child)
                    return True
        return False

    def _watch_focus_tree(self, widget) -> None:
        from ui_widgets import TextInput

        for w in widget.walk():
            if isinstance(w, TextInput) and id(w) not in self._focus_bound:
                self._focus_bound.add(id(w))
                w.bind(focus=self._on_field_focus)

    def _on_field_focus(self, _inst, focus: bool) -> None:
        if focus:
            self.do_scroll_x = False
            self.do_scroll_y = False
        else:
            self.do_scroll_x = False
            self.do_scroll_y = True

    def on_touch_down(self, touch):
        if self._dispatch_touch(touch, "on_touch_down"):
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._dispatch_touch(touch, "on_touch_move"):
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._dispatch_touch(touch, "on_touch_up"):
            return True
        return super().on_touch_up(touch)

from theme import (
    ACCENT,
    ACCENT_LIGHT,
    ACCENT_SOFT,
    ACCENT_TEXT,
    BG,
    BG_ELEVATED,
    BTN_DANGER,
    BTN_DANGER_TEXT,
    BTN_NEUTRAL,
    BTN_NEUTRAL_TEXT,
    BTN_SUCCESS,
    BTN_SUCCESS_TEXT,
    BTN_RADIUS_SM,
    CARD,
    CARD_BORDER,
    CARD_RADIUS,
    CARD_SHADOW,
    HINT,
    HINT_INPUT,
    INPUT_BG,
    INPUT_TEXT,
    NAV_ACTIVE_BG,
    NAV_BORDER,
    NAV_IDLE,
    SEGMENT_TRACK,
    SURFACE,
    SURFACE_WARM,
    TEXT,
    TEXT_MUTED,
    TEXT_SECONDARY,
)
from ui_widgets import Button, Label


class Metrics:
    """基于 Window.size 的响应式度量。"""

    pad = dp(14)
    nav_h = dp(58)
    btn_h = dp(46)
    btn_h_sm = dp(40)
    field_h = dp(44)
    font_xs = dp(11)
    font_sm = dp(13)
    font_md = dp(15)
    font_lg = dp(18)
    font_clock = dp(48)
    narrow = False
    content_w = dp(320)

    @classmethod
    def refresh(cls) -> None:
        w, h = Window.size
        short = min(w, h)
        cls.pad = max(dp(14), int(short * 0.036))
        cls.nav_h = max(dp(54), int(h * 0.075))
        cls.btn_h = max(dp(46), int(short * 0.058))
        cls.btn_h_sm = max(dp(40), int(short * 0.052))
        cls.field_h = max(dp(44), int(short * 0.055))
        cls.font_xs = max(dp(12), int(short * 0.029))
        cls.font_sm = max(dp(14), int(short * 0.034))
        cls.font_md = max(dp(16), int(short * 0.039))
        cls.font_lg = max(dp(19), int(short * 0.050))
        cls.font_clock = max(dp(46), int(short * 0.128))
        cls.narrow = w < dp(380)
        cls.content_w = max(dp(180), int(w - cls.pad * 2 - dp(12)))

    @classmethod
    def inner_width(cls, reserve: float = 0) -> int:
        return max(dp(120), int(cls.content_w - reserve))


def screen_root(page_tint: tuple | None = None, **kwargs) -> BoxLayout:
    m = Metrics
    defaults = dict(orientation="vertical", padding=(m.pad, m.pad, m.pad, dp(6)), spacing=dp(10))
    defaults.update(kwargs)
    root = BoxLayout(**defaults)
    tint = page_tint or ACCENT_LIGHT
    with root.canvas.before:
        Color(*BG)
        root._page_bg = Rectangle()
        Color(*tint)
        root._header_tint = RoundedRectangle(radius=[0, 0, dp(28), dp(28)])

    def _sync_page_bg(*_args) -> None:
        root._page_bg.pos = root.pos
        root._page_bg.size = root.size
        band_h = min(dp(168), root.height * 0.26)
        root._header_tint.pos = (root.x, root.y + root.height - band_h)
        root._header_tint.size = (root.width, band_h)

    root.bind(pos=_sync_page_bg, size=_sync_page_bg)
    return root


def scroll_screen(**kwargs) -> tuple[ScrollView, BoxLayout]:
    """整页可滚动的表单容器。"""
    m = Metrics
    inner = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        spacing=dp(10),
        padding=(0, 0, 0, dp(8)),
    )
    inner.bind(minimum_height=inner.setter("height"))
    scroll = FormScrollView(
        size_hint=(1, 1),
        bar_width=dp(4),
        do_scroll_x=False,
        scroll_type=["bars", "content"],
        bar_color=ACCENT_SOFT,
    )
    scroll.add_widget(inner)
    return scroll, inner


def scroll_list() -> tuple[ScrollView, BoxLayout]:
    box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=(0, dp(4)))
    box.bind(minimum_height=box.setter("height"))
    scroll = FormScrollView(
        size_hint=(1, 1),
        bar_width=dp(4),
        do_scroll_x=False,
        scroll_type=["bars", "content"],
        bar_color=ACCENT_SOFT,
    )
    scroll.add_widget(box)
    return scroll, box


def _attach_rounded_bg(widget, fill, radius: float | None = None, shadow: bool = False) -> None:
    r = radius if radius is not None else dp(CARD_RADIUS)
    with widget.canvas.before:
        if shadow:
            Color(*CARD_SHADOW)
            widget._shadow = RoundedRectangle(radius=[r, r, r, r])
        Color(*fill)
        bg = RoundedRectangle(radius=[r, r, r, r])
    offset = dp(2) if shadow else 0

    def _sync(*_args) -> None:
        if shadow:
            widget._shadow.pos = (widget.x + offset, widget.y - offset)
            widget._shadow.size = widget.size
        bg.pos = widget.pos
        bg.size = widget.size

    widget.bind(pos=_sync, size=_sync)
    widget._rounded_bg = bg


def info_bar(**kwargs) -> BoxLayout:
    """浅色圆角信息条，用于同步状态等。"""
    defaults = {
        "orientation": "horizontal",
        "size_hint_y": None,
        "spacing": dp(8),
        "padding": (dp(12), dp(10)),
    }
    defaults.update(kwargs)
    box = BoxLayout(**defaults)
    box.bind(minimum_height=box.setter("height"))
    _attach_rounded_bg(box, SURFACE_WARM, radius=dp(CARD_RADIUS))
    return box


def hint_label(text: str) -> Label:
    lbl = Label(
        text=text,
        color=TEXT_MUTED,
        font_size=Metrics.font_sm,
        size_hint_y=None,
        halign="left",
        valign="top",
    )
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", max(dp(28), val[1] + dp(6))))
    return lbl


def sync_status_label(**kwargs) -> Label:
    """可随文案自动增高的同步状态行。"""
    defaults = {
        "color": TEXT_SECONDARY,
        "font_size": Metrics.font_sm,
        "size_hint_y": None,
        "halign": "left",
        "valign": "top",
        "size_hint_x": 1,
    }
    defaults.update(kwargs)
    lbl = Label(**defaults)
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", max(dp(28), val[1] + dp(6))))
    return lbl


def section_title(text: str) -> Label:
    lbl = Label(
        text=text,
        color=TEXT,
        font_size=Metrics.font_md,
        bold=True,
        size_hint_y=None,
        halign="left",
        valign="top",
    )
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", max(dp(28), val[1] + dp(4))))
    return lbl


def empty_hint(text: str) -> Label:
    lbl = Label(
        text=text,
        color=TEXT_MUTED,
        font_size=Metrics.font_md,
        size_hint_y=None,
        height=dp(56),
        halign="center",
        valign="middle",
        padding=(dp(12), dp(8)),
    )
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0] - dp(24), None)))
    lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", max(dp(56), val[1] + dp(16))))
    return lbl


def primary_btn(text: str, **kwargs) -> Button:
    kwargs.setdefault("background_color", ACCENT)
    kwargs.setdefault("color", ACCENT_TEXT)
    kwargs.setdefault("font_size", Metrics.font_md)
    kwargs.setdefault("bold", True)
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", Metrics.btn_h)
    return Button(text=text, **kwargs)


def ghost_btn(text: str, **kwargs) -> Button:
    kwargs.setdefault("background_color", BTN_NEUTRAL)
    kwargs.setdefault("color", BTN_NEUTRAL_TEXT)
    kwargs.setdefault("font_size", Metrics.font_md)
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", Metrics.btn_h)
    return Button(text=text, **kwargs)


def success_btn(text: str, **kwargs) -> Button:
    kwargs.setdefault("background_color", BTN_SUCCESS)
    kwargs.setdefault("color", BTN_SUCCESS_TEXT)
    kwargs.setdefault("font_size", Metrics.font_sm)
    kwargs.setdefault("bold", True)
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", Metrics.btn_h_sm)
    return Button(text=text, **kwargs)


def danger_btn(text: str, **kwargs) -> Button:
    kwargs.setdefault("background_color", BTN_DANGER)
    kwargs.setdefault("color", BTN_DANGER_TEXT)
    kwargs.setdefault("font_size", Metrics.font_sm)
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", Metrics.btn_h_sm)
    return Button(text=text, **kwargs)


def compact_btn(text: str, **kwargs) -> Button:
    kwargs.setdefault("background_color", NAV_IDLE)
    kwargs.setdefault("color", TEXT)
    kwargs.setdefault("font_size", Metrics.font_sm)
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", Metrics.btn_h_sm)
    return Button(text=text, **kwargs)


FIELD_W_AUTH = dp(280)
FIELD_W_PHONE = dp(240)
FIELD_W_NICK = dp(200)
FIELD_H_ACCOUNT = dp(40)


def field_row(widget, *extra) -> BoxLayout:
    row = BoxLayout(size_hint_y=None, height=Metrics.field_h, spacing=dp(8))
    row.add_widget(widget)
    for item in extra:
        row.add_widget(item)
    spacer = BoxLayout(size_hint_x=1)
    row.add_widget(spacer)
    return row


def field_input(**kwargs) -> "TextInput":
    from kivy.utils import platform as kv_platform
    from ui_widgets import TextInput

    field_width = kwargs.pop("field_width", None)
    numeric = kwargs.pop("numeric", False)
    time_field = kwargs.pop("time_field", False)
    kwargs.setdefault("multiline", False)
    kwargs.setdefault("font_size", Metrics.font_md)
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", Metrics.field_h)
    kwargs.setdefault("padding", (dp(10), dp(10), dp(10), dp(10)))
    kwargs.setdefault("background_color", INPUT_BG)
    kwargs.setdefault("foreground_color", INPUT_TEXT)
    kwargs.setdefault("hint_text_color", HINT_INPUT)
    if kv_platform == "android" and not kwargs.get("password"):
        if numeric:
            kwargs.setdefault("input_type", "number")
        elif time_field:
            kwargs.setdefault("input_type", "time")
        else:
            kwargs.setdefault("input_type", "text")
    if field_width is not None:
        kwargs.setdefault("size_hint_x", None)
        kwargs["width"] = field_width
    return TextInput(**kwargs)


def field_input_row(widget, *, with_paste: bool = False) -> BoxLayout:
    """输入框行：可选右侧「粘贴」按钮。"""
    from ui_widgets import paste_from_clipboard

    row = BoxLayout(size_hint_y=None, height=Metrics.field_h, spacing=dp(8))
    if widget.size_hint_x is None:
        widget.size_hint_x = 1
    row.add_widget(widget)
    if with_paste:
        paste = ghost_btn("粘贴", size_hint_x=None, width=dp(58))
        paste.bind(on_release=lambda *_: paste_from_clipboard(widget))
        row.add_widget(paste)
    return row


def reason_popup(title: str, prompt: str, on_confirm) -> None:
    """填写理由弹窗；确认时调用 on_confirm(reason: str)。"""
    from kivy.uix.popup import Popup

    content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
    _attach_rounded_bg(content, CARD)
    prompt_lbl = Label(
        text=prompt,
        color=TEXT_SECONDARY,
        font_size=Metrics.font_sm,
        size_hint_y=None,
        halign="left",
        valign="top",
    )
    prompt_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    prompt_lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", max(dp(28), val[1] + dp(4))))
    content.add_widget(prompt_lbl)
    field = field_input(multiline=True)
    field.height = dp(88)
    content.add_widget(field)

    popup = Popup(
        title=title,
        content=content,
        size_hint=(0.92, None),
        height=dp(280),
        separator_height=0,
        background="",
    )

    def _open_focus(_dt: float) -> None:
        field.focus = True

    from kivy.clock import Clock

    Clock.schedule_once(_open_focus, 0.05)

    def _confirm(*_args) -> None:
        text = field.text.strip()
        popup.dismiss()
        if text:
            on_confirm(text)

    actions = BoxLayout(size_hint_y=None, height=Metrics.btn_h, spacing=dp(8))
    actions.add_widget(ghost_btn("取消", on_release=popup.dismiss))
    actions.add_widget(primary_btn("确定", on_release=_confirm))
    content.add_widget(actions)
    popup.open()


def bind_label_wrap(label: Label, width: int | None = None) -> None:
    w = width or Metrics.content_w

    def _sync(*_args) -> None:
        label.text_size = (w, None)
        label.texture_update()
        label.height = max(dp(32), label.texture_size[1] + dp(8))

    label.bind(width=_sync, text=_sync)
    _sync()


def priority_stripe(priority: int, height: float | None = None) -> BoxLayout:
    from theme import PRIORITY_COLORS

    stripe = BoxLayout(size_hint_x=None, width=dp(4), size_hint_y=1)
    if height:
        stripe.size_hint_y = None
        stripe.height = height
    color = PRIORITY_COLORS.get(priority, PRIORITY_COLORS[1])
    with stripe.canvas:
        Color(*color)
        bar = RoundedRectangle(radius=[dp(2), dp(2), dp(2), dp(2)])
    def _sync(*_args) -> None:
        bar.pos = stripe.pos
        bar.size = stripe.size
    stripe.bind(pos=_sync, size=_sync)
    return stripe


class Card(BoxLayout):
    """水平卡片（简单一行）。"""

    def __init__(self, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(56),
            spacing=dp(10),
            padding=(dp(12), dp(10)),
            **kwargs,
        )
        _attach_rounded_bg(self, CARD, shadow=True)

    def fit_content(self, label: Label, min_h: float | None = None, extra: float = 0) -> None:
        floor = min_h or Metrics.btn_h

        def _resize(*_args) -> None:
            self.height = max(floor, label.height + dp(20) + extra)

        label.bind(height=_resize)
        _resize()


class ItemCard(BoxLayout):
    """垂直卡片：正文 + 底部操作行，避免长文本与按钮挤在一行。"""

    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(12), dp(10)),
            **kwargs,
        )
        _attach_rounded_bg(self, CARD, shadow=True)
        body_row = BoxLayout(orientation="horizontal", size_hint_y=None, spacing=dp(10))
        self._body_row = body_row
        self._action_row: BoxLayout | None = None
        self.add_widget(body_row)

    def set_body(self, stripe: BoxLayout | None, content) -> None:
        self._body_row.clear_widgets()
        if stripe is not None:
            self._body_row.add_widget(stripe)
        self._body_row.add_widget(content)

    def set_actions(self, buttons: list[Button]) -> None:
        if self._action_row is not None:
            self.remove_widget(self._action_row)
            self._action_row = None
        if not buttons:
            return
        row = BoxLayout(size_hint_y=None, height=Metrics.btn_h_sm, spacing=dp(8))
        for btn in buttons:
            if btn.size_hint_x is None and btn.width:
                pass
            else:
                btn.size_hint_x = 1
            row.add_widget(btn)
        self._action_row = row
        self.add_widget(row)

    def fit_label(self, label: Label, min_h: float | None = None) -> None:
        floor = min_h or dp(52)
        action_h = Metrics.btn_h_sm + dp(8) if self._action_row else 0

        def _resize(*_args) -> None:
            self._body_row.height = max(dp(40), label.height + dp(4))
            for child in self._body_row.children:
                if child is not label:
                    child.height = self._body_row.height
            self.height = max(floor + action_h, self._body_row.height + dp(20) + action_h)

        label.bind(height=_resize)
        _resize()

    def fit_widget(self, widget, min_body_h: float, extra_bottom: float = 0) -> None:
        action_h = Metrics.btn_h_sm + dp(8) if self._action_row else 0

        def _resize(*_args) -> None:
            h = max(min_body_h, widget.height)
            self._body_row.height = h
            self.height = h + dp(20) + action_h + extra_bottom

        widget.bind(height=_resize)
        _resize()


class SegmentedBar(BoxLayout):
    """分段切换；选项多时自动两行排列。"""

    def __init__(self, options: list[tuple[str, str]], on_select, **kwargs):
        use_grid = len(options) > 3 or Metrics.narrow
        super().__init__(
            orientation="vertical" if use_grid else "horizontal",
            size_hint_y=None,
            spacing=dp(6),
            padding=(dp(6), dp(6)),
            **kwargs,
        )
        _attach_rounded_bg(self, SEGMENT_TRACK, radius=dp(BTN_RADIUS_SM))
        if use_grid:
            self.height = Metrics.btn_h_sm * 2 + dp(18)
        else:
            self.height = Metrics.btn_h_sm + dp(12)

        self._on_select = on_select
        self._buttons: dict[str, Button] = {}
        container: BoxLayout | GridLayout
        inner_h = self.height - dp(12)
        if use_grid:
            container = GridLayout(cols=2, spacing=dp(6), size_hint_y=None, height=inner_h)
        else:
            container = BoxLayout(spacing=dp(6), size_hint_y=None, height=inner_h - dp(6))
        self.add_widget(container)

        font = Metrics.font_sm if use_grid else Metrics.font_md
        for label, key in options:
            btn = ghost_btn(label, size_hint_x=1, font_size=font, height=Metrics.btn_h_sm)
            btn.bind(on_release=lambda _b, k=key: self.select(k))
            self._buttons[key] = btn
            container.add_widget(btn)
        if options:
            self.select(options[0][1])

    def select(self, key: str) -> None:
        for k, btn in self._buttons.items():
            if k == key:
                btn.background_color = ACCENT
                btn.color = ACCENT_TEXT
                btn.bold = True
            else:
                btn.background_color = NAV_IDLE
                btn.color = TEXT
                btn.bold = False
        self._on_select(key)


class BottomNav(BoxLayout):
    """底部主导航。"""

    def __init__(self, screen_manager, items: list[tuple[str, str]], **kwargs):
        super().__init__(
            size_hint_y=None,
            height=Metrics.nav_h,
            spacing=dp(4),
            padding=(dp(6), dp(8), dp(6), dp(10)),
            **kwargs,
        )
        with self.canvas.before:
            from kivy.graphics import Line

            Color(*NAV_BORDER)
            self._top_line = Line(points=[0, 0, 0, 0], width=dp(1))
            Color(*BG_ELEVATED)
            self._bar_bg = RoundedRectangle(radius=[dp(18), dp(18), 0, 0])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self._sm = screen_manager
        self._buttons: dict[str, Button] = {}
        font = Metrics.font_xs if len(items) > 4 else Metrics.font_sm
        for text, name in items:
            btn = ghost_btn(text, size_hint_x=1, font_size=font, height=Metrics.nav_h - dp(18))
            btn.bind(on_release=lambda _b, n=name: self.select(n))
            self._buttons[name] = btn
            self.add_widget(btn)
        screen_manager.bind(current=self._on_screen)
        if items:
            self.select(items[0][1])

    def _sync_bg(self, *_args) -> None:
        self._bar_bg.pos = self.pos
        self._bar_bg.size = self.size
        x, y = self.pos
        w = self.width
        self._top_line.points = [x, y + self.height, x + w, y + self.height]

    def select(self, name: str) -> None:
        self._sm.current = name

    def _on_screen(self, _sm, name: str) -> None:
        for n, btn in self._buttons.items():
            if n == name:
                btn.background_color = NAV_ACTIVE_BG
                btn.color = ACCENT
                btn.bold = True
            else:
                btn.background_color = NAV_IDLE
                btn.color = TEXT
                btn.bold = False
