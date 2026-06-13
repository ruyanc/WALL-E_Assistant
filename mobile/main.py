"""WALL-E 安卓版（Kivy）。桌面可运行调试，Buildozer 打包为 APK。"""

from __future__ import annotations

from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from sprite import WalleSprite
from todo_store import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MED, PRIORITY_LABELS, TodoStore

PRIORITY_COLORS = {
    PRIORITY_HIGH: (0.91, 0.30, 0.24, 1),
    PRIORITY_MED: (0.20, 0.60, 0.86, 1),
    PRIORITY_LOW: (0.18, 0.80, 0.44, 1),
}


class PetScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        self.sprite = WalleSprite(size_hint=(1, 0.55))
        root.add_widget(self.sprite)
        self.hint = Label(
            text="瓦力陪你专注与休息 ☀",
            size_hint=(1, None),
            height=dp(36),
            color=(0.95, 0.92, 0.88, 1),
        )
        root.add_widget(self.hint)
        row = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        for label, anim in (("张望", "look"), ("说话", "talk"), ("开心", "happy")):
            btn = Button(text=label)
            btn.bind(on_release=lambda _b, a=anim: self.sprite.set_anim(a))
            row.add_widget(btn)
        root.add_widget(row)
        self.add_widget(root)


class TodoScreen(Screen):
    def __init__(self, store: TodoStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        form = BoxLayout(size_hint=(1, None), height=dp(44), spacing=dp(8))
        self.input = TextInput(hint_text="新任务", multiline=False)
        self.prio = Spinner(
            text="中级",
            values=("高级", "中级", "低级"),
            size_hint=(None, 1),
            width=dp(88),
        )
        add_btn = Button(text="添加", size_hint=(None, 1), width=dp(72))
        add_btn.bind(on_release=self._add)
        self.input.bind(on_text_validate=lambda *_: self._add())
        form.add_widget(self.input)
        form.add_widget(self.prio)
        form.add_widget(add_btn)
        root.add_widget(form)

        self.list_box = BoxLayout(orientation="vertical", spacing=dp(6))
        scroll_wrap = BoxLayout(orientation="vertical")
        scroll_wrap.add_widget(self.list_box)
        root.add_widget(scroll_wrap)

        self.add_widget(root)
        self.refresh()

    def _prio_value(self) -> int:
        return {"高级": PRIORITY_HIGH, "中级": PRIORITY_MED, "低级": PRIORITY_LOW}[self.prio.text]

    def _add(self, *_args) -> None:
        self.store.add(self.input.text, self._prio_value())
        self.input.text = ""

    def refresh(self) -> None:
        self.list_box.clear_widgets()
        pri_map = {"高级": PRIORITY_HIGH, "中级": PRIORITY_MED, "低级": PRIORITY_LOW}
        for t in self.store.pending() + [x for x in self.store.tasks if x.done]:
            row = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(8))
            with row.canvas.before:
                Color(0.12, 0.11, 0.10, 1)
                row._bg = Rectangle(pos=row.pos, size=row.size)  # type: ignore[attr-defined]
            row.bind(pos=lambda w, *_: setattr(w._bg, "pos", w.pos), size=lambda w, *_: setattr(w._bg, "size", w.size))

            stripe = BoxLayout(size_hint=(None, 1), width=dp(4))
            r, g, b, a = PRIORITY_COLORS.get(t.priority, PRIORITY_COLORS[PRIORITY_MED])
            with stripe.canvas:
                Color(r, g, b, a)
                stripe._bar = Rectangle(pos=stripe.pos, size=stripe.size)
            stripe.bind(pos=lambda w, *_: setattr(w._bar, "pos", w.pos), size=lambda w, *_: setattr(w._bar, "size", w.size))
            row.add_widget(stripe)

            label = Label(
                text=t.text,
                color=(0.43, 0.42, 0.39, 1) if t.done else (0.95, 0.92, 0.88, 1),
                strikethrough=t.done,
            )
            row.add_widget(label)

            done_btn = Button(text="✓" if t.done else "□", size_hint=(None, 1), width=dp(44))
            done_btn.bind(on_release=lambda _b, tid=t.id: self.store.toggle(tid))
            row.add_widget(done_btn)

            del_btn = Button(text="×", size_hint=(None, 1), width=dp(44))
            del_btn.bind(on_release=lambda _b, tid=t.id: self.store.remove(tid))
            row.add_widget(del_btn)
            self.list_box.add_widget(row)


class TimerScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._seconds = 50 * 60
        self._running = False
        self._ev = None

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
        self.status = Label(text="准备开始", font_size=dp(18))
        self.clock_lbl = Label(text="50:00", font_size=dp(42), bold=True)
        root.add_widget(self.status)
        root.add_widget(self.clock_lbl)

        row = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(8))
        start = Button(text="开始 50 分钟")
        start.bind(on_release=self._start_work)
        rest = Button(text="休息 10 分钟")
        rest.bind(on_release=self._start_rest)
        stop = Button(text="停止")
        stop.bind(on_release=self._stop)
        row.add_widget(start)
        row.add_widget(rest)
        row.add_widget(stop)
        root.add_widget(row)
        self.add_widget(root)

    def _fmt(self, sec: int) -> str:
        sec = max(0, sec)
        return f"{sec // 60:02d}:{sec % 60:02d}"

    def _tick(self, _dt: float) -> None:
        if self._seconds <= 0:
            self._stop()
            self.status.text = "时间到！"
            return
        self._seconds -= 1
        self.clock_lbl.text = self._fmt(self._seconds)

    def _start_work(self, *_a) -> None:
        self._seconds = 50 * 60
        self._run("专注中…")

    def _start_rest(self, *_a) -> None:
        self._seconds = 10 * 60
        self._run("休息中 ☕")

    def _run(self, label: str) -> None:
        self._stop()
        self.status.text = label
        self._running = True
        self.clock_lbl.text = self._fmt(self._seconds)
        self._ev = Clock.schedule_interval(self._tick, 1)

    def _stop(self, *_a) -> None:
        if self._ev is not None:
            self._ev.cancel()
            self._ev = None
        self._running = False
        if self.status.text not in ("时间到！",):
            self.status.text = "已停止"


class WalleMobileApp(App):
    title = "WALL-E"

    def build(self):
        self.store = TodoStore(on_change=self._on_todo_changed)
        sm = ScreenManager()
        self.todo_screen = TodoScreen(self.store, name="todo")
        sm.add_widget(PetScreen(name="pet"))
        sm.add_widget(self.todo_screen)
        sm.add_widget(TimerScreen(name="timer"))

        nav = BoxLayout(orientation="vertical")
        nav.add_widget(sm)
        bar = BoxLayout(size_hint=(1, None), height=dp(52), spacing=dp(4))
        for text, name in (("瓦力", "pet"), ("待办", "todo"), ("番茄钟", "timer")):
            btn = Button(text=text)
            btn.bind(on_release=lambda _b, n=name: setattr(sm, "current", n))
            bar.add_widget(btn)
        nav.add_widget(bar)
        return nav

    def _on_todo_changed(self) -> None:
        if hasattr(self, "todo_screen"):
            self.todo_screen.refresh()

    def on_pause(self):
        return True


def ensure_assets() -> bool:
    """打包前需将 walle/assets 复制到 mobile/assets。"""
    frames = Path(__file__).resolve().parent / "assets" / "frames"
    return frames.is_dir() and any(frames.glob("*.png"))


if __name__ == "__main__":
    if not ensure_assets():
        print("缺少 mobile/assets，请先运行：python mobile/prepare_assets.py")
        raise SystemExit(1)
    WalleMobileApp().run()
