"""番茄钟 / 工作休息循环 状态机。

支持配置：工作分钟数、休息分钟数、循环次数。
状态流转：
    idle  ->（开始）-> working -> resting -> working ... -> finished
每秒发出一次 tick，状态切换时发出对应信号，供 UI 与全屏提醒响应。
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, QTimer, Signal


class PomodoroState(Enum):
    IDLE = "idle"
    WORKING = "working"
    RESTING = "resting"
    FINISHED = "finished"


class PomodoroTimer(QObject):
    # 剩余秒数, 当前状态, 当前循环(从1开始), 总循环
    tick = Signal(int, object, int, int)
    state_changed = Signal(object)   # PomodoroState
    rest_started = Signal(int)       # 休息时长(秒)
    rest_ended = Signal()
    work_started = Signal(int, int)  # 当前循环, 总循环
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        self.work_seconds = 50 * 60
        self.rest_seconds = 10 * 60
        self.total_cycles = 3

        self.state = PomodoroState.IDLE
        self.current_cycle = 0
        self.remaining = 0

    # ------------------------------------------------------------------ 配置
    def configure(self, work_minutes: int, rest_minutes: int, cycles: int) -> None:
        self.work_seconds = max(1, int(work_minutes)) * 60
        self.rest_seconds = max(1, int(rest_minutes)) * 60
        self.total_cycles = max(1, int(cycles))

    # ------------------------------------------------------------------ 控制
    def start(self) -> None:
        """从头开始一轮完整的番茄钟循环。"""
        self.current_cycle = 1
        self._enter_working()
        self._timer.start()

    def stop(self) -> None:
        """完全停止并回到空闲。"""
        self._timer.stop()
        self._set_state(PomodoroState.IDLE)
        self.current_cycle = 0
        self.remaining = 0
        self._emit_tick()

    def pause(self) -> None:
        self._timer.stop()

    def resume(self) -> None:
        if self.state in (PomodoroState.WORKING, PomodoroState.RESTING):
            self._timer.start()

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    def start_rest_now(self) -> None:
        """立即提前进入休息状态（不改变循环计数）。"""
        if self.current_cycle == 0:
            self.current_cycle = 1
        self._enter_resting()
        self._timer.start()

    def end_rest_now(self) -> None:
        """提前结束当前休息，进入下一段工作或完成。"""
        if self.state != PomodoroState.RESTING:
            return
        self._advance_after_rest()

    def skip_to_rest(self) -> None:
        """工作中提前结束工作，立刻进入休息。"""
        if self.state == PomodoroState.WORKING:
            self._enter_resting()

    # ------------------------------------------------------------------ 内部
    def _enter_working(self) -> None:
        self.remaining = self.work_seconds
        self._set_state(PomodoroState.WORKING)
        self.work_started.emit(self.current_cycle, self.total_cycles)
        self._emit_tick()

    def _enter_resting(self) -> None:
        self.remaining = self.rest_seconds
        self._set_state(PomodoroState.RESTING)
        self.rest_started.emit(self.rest_seconds)
        self._emit_tick()

    def _advance_after_rest(self) -> None:
        self.rest_ended.emit()
        if self.current_cycle >= self.total_cycles:
            self._finish()
        else:
            self.current_cycle += 1
            self._enter_working()

    def _finish(self) -> None:
        self._timer.stop()
        self._set_state(PomodoroState.FINISHED)
        self.remaining = 0
        self._emit_tick()
        self.finished.emit()

    def _set_state(self, state: PomodoroState) -> None:
        if state != self.state:
            self.state = state
            self.state_changed.emit(state)

    def _on_tick(self) -> None:
        self.remaining -= 1
        if self.remaining <= 0:
            if self.state == PomodoroState.WORKING:
                self._enter_resting()
            elif self.state == PomodoroState.RESTING:
                self._advance_after_rest()
            return
        self._emit_tick()

    def _emit_tick(self) -> None:
        self.tick.emit(self.remaining, self.state, self.current_cycle, self.total_cycles)

    @staticmethod
    def format_time(seconds: int) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
