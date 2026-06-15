"""番茄钟持久化（基于 wall-clock，供主进程与后台 Service 共享）。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from enum import Enum

from storage import pomodoro_state_path


class PomodoroState(Enum):
    IDLE = "idle"
    WORKING = "working"
    RESTING = "resting"
    FINISHED = "finished"


@dataclass
class PomodoroSnapshot:
    state: str = PomodoroState.IDLE.value
    end_at: float = 0.0
    current_cycle: int = 0
    total_cycles: int = 3
    work_seconds: int = 50 * 60
    rest_seconds: int = 10 * 60

    @property
    def enum_state(self) -> PomodoroState:
        try:
            return PomodoroState(self.state)
        except ValueError:
            return PomodoroState.IDLE

    def remaining(self) -> int:
        if self.enum_state not in (PomodoroState.WORKING, PomodoroState.RESTING):
            return 0
        return max(0, int(self.end_at - time.time()))

    def is_active(self) -> bool:
        return self.enum_state in (PomodoroState.WORKING, PomodoroState.RESTING)


def load_snapshot() -> PomodoroSnapshot:
    path = pomodoro_state_path()
    if not path.exists():
        return PomodoroSnapshot()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        snap = PomodoroSnapshot(**{k: v for k, v in raw.items() if k in PomodoroSnapshot.__dataclass_fields__})
        if snap.is_active() and snap.remaining() <= 0:
            return advance_snapshot(snap, notify=False)
        return snap
    except (OSError, json.JSONDecodeError, TypeError):
        return PomodoroSnapshot()


def save_snapshot(snap: PomodoroSnapshot) -> None:
    try:
        with open(pomodoro_state_path(), "w", encoding="utf-8") as f:
            json.dump(asdict(snap), f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def advance_snapshot(snap: PomodoroSnapshot, *, notify: bool = True) -> PomodoroSnapshot:
    state = snap.enum_state
    if state == PomodoroState.WORKING:
        if snap.current_cycle >= snap.total_cycles:
            snap.state = PomodoroState.FINISHED.value
            snap.end_at = 0
            if notify:
                from notify_util import notify

                notify("WALL-E", "番茄钟全部完成 🎉", urgent=True)
        else:
            snap.state = PomodoroState.RESTING.value
            snap.end_at = time.time() + snap.rest_seconds
            if notify:
                from notify_util import notify

                notify("WALL-E", "该休息了 ☕", urgent=True)
    elif state == PomodoroState.RESTING:
        snap.current_cycle += 1
        if snap.current_cycle > snap.total_cycles:
            snap.state = PomodoroState.FINISHED.value
            snap.end_at = 0
            if notify:
                from notify_util import notify

                notify("WALL-E", "番茄钟全部完成 🎉", urgent=True)
        else:
            snap.state = PomodoroState.WORKING.value
            snap.end_at = time.time() + snap.work_seconds
            if notify:
                from notify_util import notify

                notify("WALL-E", f"第 {snap.current_cycle}/{snap.total_cycles} 轮专注开始")
    save_snapshot(snap)
    return snap


def tick_snapshot(*, notify: bool = True) -> PomodoroSnapshot:
    snap = load_snapshot()
    if snap.is_active() and snap.remaining() <= 0:
        snap = advance_snapshot(snap, notify=notify)
    return snap
