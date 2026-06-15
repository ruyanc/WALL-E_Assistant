"""后台 Service 主循环：提醒检测 + 番茄钟 wall-clock 推进。"""

from __future__ import annotations

import time

from notify_util import notify
from pomodoro_persist import load_snapshot, tick_snapshot
from reminder_store import ReminderStore


def has_active_reminders() -> bool:
    store = ReminderStore()
    return bool(store.items)


def check_reminders() -> None:
    store = ReminderStore(on_due=lambda text: notify("WALL-E 提醒", text))
    store.check_due()


def run_service_loop() -> None:
    from android_platform import acquire_wake_lock, release_wake_lock

    sec = 0
    wake = False
    while True:
        sec += 1
        snap = tick_snapshot(notify=True)
        if sec % 15 == 0:
            check_reminders()

        active = snap.is_active()
        reminders = has_active_reminders()
        if active or reminders:
            if active and not wake:
                acquire_wake_lock()
                wake = True
            elif not active and wake:
                release_wake_lock()
                wake = False
        elif wake:
            release_wake_lock()
            wake = False

        time.sleep(1)
