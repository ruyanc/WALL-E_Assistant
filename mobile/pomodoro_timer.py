"""番茄钟（wall-clock 持久化，与后台 Service 共享状态）。"""

from __future__ import annotations

import time
from typing import Callable

from pomodoro_persist import PomodoroSnapshot, PomodoroState, load_snapshot, save_snapshot


class PomodoroTimer:
    def __init__(
        self,
        on_tick: Callable[[int, PomodoroState, int, int], None] | None = None,
        on_state: Callable[[PomodoroState], None] | None = None,
    ) -> None:
        self._on_tick = on_tick
        self._on_state = on_state
        self._snap = load_snapshot()

    @property
    def state(self) -> PomodoroState:
        return self._snap.enum_state

    @property
    def current_cycle(self) -> int:
        return self._snap.current_cycle

    @property
    def total_cycles(self) -> int:
        return self._snap.total_cycles

    @property
    def remaining(self) -> int:
        return self._snap.remaining()

    @property
    def work_seconds(self) -> int:
        return self._snap.work_seconds

    @property
    def rest_seconds(self) -> int:
        return self._snap.rest_seconds

    def configure(self, work_minutes: int, rest_minutes: int, cycles: int) -> None:
        self._snap.work_seconds = max(1, int(work_minutes)) * 60
        self._snap.rest_seconds = max(1, int(rest_minutes)) * 60
        self._snap.total_cycles = max(1, int(cycles))
        save_snapshot(self._snap)

    def start(self) -> None:
        self._snap.current_cycle = 1
        self._snap.state = PomodoroState.WORKING.value
        self._snap.end_at = time.time() + self._snap.work_seconds
        save_snapshot(self._snap)
        self._emit_state()
        self._emit_tick()

    def stop(self) -> None:
        self._snap = PomodoroSnapshot(
            work_seconds=self._snap.work_seconds,
            rest_seconds=self._snap.rest_seconds,
            total_cycles=self._snap.total_cycles,
        )
        save_snapshot(self._snap)
        self._emit_state()
        self._emit_tick()

    def start_rest_now(self) -> None:
        self._snap.state = PomodoroState.RESTING.value
        self._snap.end_at = time.time() + self._snap.rest_seconds
        save_snapshot(self._snap)
        self._emit_state()
        self._emit_tick()

    def tick(self) -> None:
        """桌面调试：本地推进（Android 由后台 Service 推进）。"""
        from pomodoro_persist import advance_snapshot

        if self._snap.is_active() and self._snap.remaining() <= 0:
            self._snap = advance_snapshot(self._snap, notify=True)
        else:
            self._snap = load_snapshot()
        if self._snap.is_active() or self._snap.enum_state == PomodoroState.FINISHED:
            self._emit_tick()
            self._emit_state()

    def sync_from_disk(self) -> None:
        self._snap = load_snapshot()
        self._emit_tick()
        self._emit_state()

    def is_active(self) -> bool:
        self._snap = load_snapshot()
        return self._snap.is_active()

    def _emit_tick(self) -> None:
        if self._on_tick:
            self._on_tick(self.remaining, self.state, self.current_cycle, self.total_cycles)

    def _emit_state(self) -> None:
        if self._on_state:
            self._on_state(self.state)

    @staticmethod
    def format_time(seconds: int) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
