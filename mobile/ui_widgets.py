"""带中文字体与圆角样式的 Kivy 控件封装。"""

from __future__ import annotations

from kivy.metrics import dp
from kivy.utils import platform as kv_platform
from kivy.uix.button import Button as KivyButton
from kivy.uix.label import Label as KivyLabel
from kivy.uix.spinner import Spinner as KivySpinner
from kivy.uix.textinput import TextInput as KivyTextInput
from kivy.graphics import Color, RoundedRectangle

from fonts_setup import font_kwargs
from theme import (
    BTN_PRESS_FACTOR,
    BTN_RADIUS,
    BTN_RADIUS_SM,
    HINT_INPUT,
    INPUT_BG,
    INPUT_BORDER,
    INPUT_FOCUS_BORDER,
    INPUT_RADIUS,
    INPUT_TEXT,
    TEXT,
)


def _corner_radius(height: float | None, explicit: float | None) -> float:
    if explicit is not None:
        return explicit
    if height and height <= dp(42):
        return dp(BTN_RADIUS_SM)
    return dp(BTN_RADIUS)


class Label(KivyLabel):
    def __init__(self, **kwargs):
        super().__init__(**font_kwargs(kwargs))


class Button(KivyButton):
    """无边框圆角按钮，支持 background_color 动态切换。"""

    def __init__(self, **kwargs):
        corner = kwargs.pop("corner_radius", None)
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("border", (0, 0, 0, 0))
        kwargs.setdefault("background_color", (1, 1, 1, 1))
        height = kwargs.get("height")
        r = _corner_radius(height, corner)
        super().__init__(**font_kwargs(kwargs))
        with self.canvas.before:
            self._fill = Color(*self.background_color)
            self._rect = RoundedRectangle(radius=[r, r, r, r])
        self.bind(pos=self._sync_bg, size=self._sync_bg)
        self.bind(background_color=self._on_background_color)
        self.bind(state=self._on_state)
        self.bind(disabled=self._on_disabled)

    def _sync_bg(self, *_args) -> None:
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _base_rgb(self) -> tuple[float, float, float]:
        c = self.background_color
        return c[0], c[1], c[2]

    def _apply_fill(self, rgb: tuple[float, float, float], alpha: float) -> None:
        self._fill.rgb = rgb
        self._fill.a = alpha

    def _on_background_color(self, _inst, _value) -> None:
        if self.state != "down":
            self._on_state(self, self.state)

    def _on_state(self, _inst, state: str) -> None:
        rgb = self._base_rgb()
        alpha = 0.42 if self.disabled else 1.0
        if state == "down" and not self.disabled:
            f = BTN_PRESS_FACTOR
            self._apply_fill((rgb[0] * f, rgb[1] * f, rgb[2] * f), alpha)
        else:
            self._apply_fill(rgb, alpha)

    def _on_disabled(self, _inst, disabled: bool) -> None:
        self._on_state(self, self.state)


class _RoundedFieldMixin:
    """输入框 / 下拉框共用圆角底。"""

    _field_inset = dp(1)

    def _init_rounded_field(self, radius: float, *, track_focus: bool = False) -> None:
        inner_r = max(radius - dp(1), dp(6))
        with self.canvas.before:
            self._border_color = Color(*INPUT_BORDER)
            self._border = RoundedRectangle(radius=[radius, radius, radius, radius])
            self._bg_color = Color(*INPUT_BG)
            self._bg = RoundedRectangle(radius=[inner_r, inner_r, inner_r, inner_r])
        self.bind(pos=self._sync_field_bg, size=self._sync_field_bg)
        if track_focus:
            self.bind(focus=self._on_field_focus)

    def _sync_field_bg(self, *_args) -> None:
        inset = self._field_inset
        self._border.pos = self.pos
        self._border.size = self.size
        self._bg.pos = (self.x + inset, self.y + inset)
        self._bg.size = (self.width - inset * 2, self.height - inset * 2)

    def _on_field_focus(self, _inst, focus: bool) -> None:
        c = INPUT_FOCUS_BORDER if focus else INPUT_BORDER
        self._border_color.rgb = c[:3]


def paste_from_clipboard(text_input: KivyTextInput) -> bool:
    """从系统剪贴板粘贴到输入框（授权码等长文本）。"""
    try:
        from kivy.core.clipboard import Clipboard

        data = Clipboard.paste()
    except Exception:
        return False
    if not data:
        return False
    text_input.text = str(data).strip()
    return True


class TextInput(KivyTextInput, _RoundedFieldMixin):
    def __init__(self, **kwargs):
        kwargs.setdefault("foreground_color", INPUT_TEXT)
        kwargs.setdefault("hint_text_color", HINT_INPUT)
        kwargs.setdefault("cursor_color", INPUT_TEXT)
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_active", "")
        kwargs.setdefault("background_disabled_normal", "")
        kwargs.setdefault("multiline", False)
        kwargs.setdefault("write_tab", False)
        if kv_platform == "android" and not kwargs.get("password"):
            kwargs.setdefault("input_type", "text")
        super().__init__(**font_kwargs(kwargs))
        self._init_rounded_field(dp(INPUT_RADIUS), track_focus=True)

    def insert_text(self, substring, from_undo=False):
        if substring and not from_undo and not self.multiline:
            substring = str(substring).replace("\n", "").replace("\r", "")
        return super().insert_text(substring, from_undo=from_undo)


class SpinnerOption(KivyButton):
    """下拉选项：中文字体 + 黑字浅底。"""

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(44))
        kwargs.setdefault("padding", (dp(12), dp(10)))
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("border", (0, 0, 0, 0))
        kwargs.setdefault("background_color", INPUT_BG)
        kwargs.setdefault("color", INPUT_TEXT)
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        super().__init__(**font_kwargs(kwargs))
        self.bind(size=self._sync_text_size)

    def _sync_text_size(self, inst, size) -> None:
        inst.text_size = (max(dp(40), size[0] - dp(16)), None)


class Spinner(KivySpinner, _RoundedFieldMixin):
    def __init__(self, **kwargs):
        kwargs.setdefault("option_cls", SpinnerOption)
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("border", (0, 0, 0, 0))
        kwargs.setdefault("background_color", INPUT_BG)
        kwargs.setdefault("color", INPUT_TEXT)
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        kwargs.setdefault("padding", (dp(10), dp(10)))
        super().__init__(**font_kwargs(kwargs))
        self._init_rounded_field(dp(INPUT_RADIUS))
        self.bind(size=self._sync_text_size)
        self.bind(on_text=self._sync_text_size)

    def _sync_text_size(self, *_args) -> None:
        pad = dp(28)
        self.text_size = (max(dp(40), self.width - pad), None)

    def _build_dropdown(self, *largs):
        super()._build_dropdown(*largs)
        if self._dropdown is not None:
            self._dropdown.auto_width = True
            self._dropdown.max_height = dp(240)
