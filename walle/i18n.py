"""界面中英文翻译。"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

_LANG = "zh"

_WEEKDAY_ZH = ("一", "二", "三", "四", "五", "六", "日")
_WEEKDAY_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

_STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "app.name": "WALL-E 桌面宠物",
        "lang.zh": "简体中文",
        "lang.en": "English",
        "tray.open_panel": "打开控制台",
        "tray.toggle_pet": "显示/隐藏宠物",
        "tray.start_timer": "▶ 开始番茄钟",
        "tray.rest_now": "☕ 立即休息",
        "tray.stop_timer": "■ 停止计时",
        "tray.quit": "退出",
        "pet.welcome": "哇—力！点我打开控制台～",
        "pet.start_focus": "开始专注！瓦力陪你一起努力 ⏱️",
        "pet.work_start": "第 {cycle}/{total} 轮专注开始，加油！💪",
        "pet.rest_soon": "还有 2 分钟就要休息啦～再坚持一下！☕",
        "pet.all_done": "全部完成啦，你真棒！🎉 记得好好休息～",
        "pet.tray_all_done": "番茄钟全部完成，干得漂亮！🎉",
        "pet.reminder": "⏰ 提醒时间到：{text}",
        "pet.tray_reminder": "提醒：{text}",
        "pet.bulb_task": "📋 [{pri}优先级] {text}",
        "pet.pri_short_high": "高",
        "pet.pri_short_med": "中",
        "pet.pri_short_low": "低",
        "pet.menu.open_panel": "打开控制台",
        "pet.menu.start_timer": "▶ 开始番茄钟",
        "pet.menu.rest_now": "☕ 立即休息",
        "pet.menu.zoom_in": "放大瓦力 (+20)",
        "pet.menu.zoom_out": "缩小瓦力 (-20)",
        "pet.menu.quit": "退出",
        "panel.title": "WALL-E 桌面宠物 · 控制台",
        "panel.header": "WALL-E 控制台",
        "tab.todo": "📋 待办",
        "tab.notes": "📝 记事本",
        "tab.reminders": "⏰ 提醒",
        "tab.timer": "⏱️ 番茄钟",
        "todo.placeholder": "输入新任务，回车添加",
        "todo.add": "添加",
        "todo.hint": "示例：开会-高级，交周报-中级，取快递-低级 · 点击方块完成 · 右侧下拉改优先级 · 双击删除",
        "todo.clear_done": "清除已完成",
        "todo.clear_all": "清空全部",
        "prio.high": "高级",
        "prio.med": "中级",
        "prio.low": "低级",
        "notes.hint": "可添加多条小备忘，编辑后自动保存",
        "notes.placeholder": "新条目内容，回车或点添加",
        "notes.add": "添加条目",
        "notes.save_all": "全部保存",
        "notes.auto_saved": "已自动保存",
        "notes.saved": "已保存 ✓",
        "notes.empty": "还没有条目，在上方输入后点「添加条目」",
        "notes.entry_placeholder": "写点什么…",
        "notes.delete_tip": "删除此条",
        "remind.hint": "示例：每天 10:00 提醒喝水，每天 22:00 提醒休息",
        "remind.placeholder": "提醒内容，如：喝水、休息",
        "remind.time": "触发时间",
        "remind.repeat": "周期",
        "remind.add": "添加提醒",
        "remind.list_hint": "已设置的提醒（到点会通过瓦力气泡通知）",
        "remind.delete_sel": "删除选中",
        "remind.repeat.daily": "每天",
        "remind.repeat.weekdays": "工作日（周一至周五）",
        "remind.repeat.mon": "每周一",
        "remind.repeat.tue": "每周二",
        "remind.repeat.wed": "每周三",
        "remind.repeat.thu": "每周四",
        "remind.repeat.fri": "每周五",
        "remind.repeat.sat": "每周六",
        "remind.repeat.sun": "每周日",
        "remind.repeat.once": "单次（指定日期）",
        "remind.fmt.once": "单次 {date}",
        "remind.fmt.daily": "每天",
        "remind.fmt.weekdays": "工作日",
        "remind.fmt.weekly": "每周{day}",
        "timer.idle": "空闲中",
        "timer.working": "专注工作 · 第 {cycle}/{total} 轮",
        "timer.resting": "休息中 ☕",
        "timer.finished": "全部完成 🎉",
        "timer.settings": "计时设置",
        "timer.work_min": "工作时长（分钟）",
        "timer.rest_min": "休息时长（分钟）",
        "timer.cycles": "循环次数",
        "timer.sound": "休息提醒播放提示音",
        "timer.pet_size": "瓦力大小",
        "timer.pet_hint": "也可在桌面拖右下角缩放，或 Ctrl+滚轮",
        "timer.start": "▶ 开始",
        "timer.rest": "☕ 休息",
        "timer.stop": "■ 停止",
        "settings.language": "界面语言",
        "rest.title": "休息时间到啦！",
        "rest.end_btn": "✔ 我休息好了，提前结束",
        "rest.tip.0": "看看远处，让眼睛休息一下吧 👀",
        "rest.tip.1": "起来走动走动，喝口水～ 💧",
        "rest.tip.2": "伸个懒腰，放松肩颈 🧘",
        "rest.tip.3": "深呼吸，瓦力陪你一起放松 🌿",
        "rest.tip.4": "离开屏幕，眺望窗外的世界 🌤️",
        "seed.todo.meeting": "开会",
        "seed.todo.report": "交周报",
        "seed.todo.package": "取快递",
        "seed.remind.water": "喝水",
        "seed.remind.rest": "休息",
    },
    "en": {
        "app.name": "WALL-E Desktop Pet",
        "lang.zh": "简体中文",
        "lang.en": "English",
        "tray.open_panel": "Open Control Panel",
        "tray.toggle_pet": "Show/Hide Pet",
        "tray.start_timer": "▶ Start Pomodoro",
        "tray.rest_now": "☕ Rest Now",
        "tray.stop_timer": "■ Stop Timer",
        "tray.quit": "Quit",
        "pet.welcome": "WALL-E here! Click me to open the panel~",
        "pet.start_focus": "Focus time! WALL-E is with you ⏱️",
        "pet.work_start": "Round {cycle}/{total} — let's go! 💪",
        "pet.rest_soon": "2 minutes until break — hang in there! ☕",
        "pet.all_done": "All done! Great job! 🎉 Take a real break~",
        "pet.tray_all_done": "Pomodoro complete — well done! 🎉",
        "pet.reminder": "⏰ Reminder: {text}",
        "pet.tray_reminder": "Reminder: {text}",
        "pet.bulb_task": "📋 [{pri}] {text}",
        "pet.pri_short_high": "High",
        "pet.pri_short_med": "Med",
        "pet.pri_short_low": "Low",
        "pet.menu.open_panel": "Open Control Panel",
        "pet.menu.start_timer": "▶ Start Pomodoro",
        "pet.menu.rest_now": "☕ Rest Now",
        "pet.menu.zoom_in": "Enlarge WALL-E (+20)",
        "pet.menu.zoom_out": "Shrink WALL-E (-20)",
        "pet.menu.quit": "Quit",
        "panel.title": "WALL-E Desktop Pet · Control Panel",
        "panel.header": "WALL-E Control Panel",
        "tab.todo": "📋 To-Do",
        "tab.notes": "📝 Notes",
        "tab.reminders": "⏰ Reminders",
        "tab.timer": "⏱️ Pomodoro",
        "todo.placeholder": "New task, press Enter to add",
        "todo.add": "Add",
        "todo.hint": "e.g. Meeting-High, Report-Med, Package-Low · Click square to complete · Priority dropdown · Double-click to delete",
        "todo.clear_done": "Clear completed",
        "todo.clear_all": "Clear all",
        "prio.high": "High",
        "prio.med": "Medium",
        "prio.low": "Low",
        "notes.hint": "Multiple short notes; edits save automatically",
        "notes.placeholder": "New note, Enter or Add",
        "notes.add": "Add note",
        "notes.save_all": "Save all",
        "notes.auto_saved": "Auto-saved",
        "notes.saved": "Saved ✓",
        "notes.empty": "No notes yet — type above and tap Add",
        "notes.entry_placeholder": "Write something…",
        "notes.delete_tip": "Delete this note",
        "remind.hint": "e.g. Drink water daily at 10:00, rest at 22:00",
        "remind.placeholder": "Reminder text, e.g. water, break",
        "remind.time": "Time",
        "remind.repeat": "Repeat",
        "remind.add": "Add reminder",
        "remind.list_hint": "Active reminders (WALL-E bubble at due time)",
        "remind.delete_sel": "Delete selected",
        "remind.repeat.daily": "Every day",
        "remind.repeat.weekdays": "Weekdays (Mon–Fri)",
        "remind.repeat.mon": "Every Monday",
        "remind.repeat.tue": "Every Tuesday",
        "remind.repeat.wed": "Every Wednesday",
        "remind.repeat.thu": "Every Thursday",
        "remind.repeat.fri": "Every Friday",
        "remind.repeat.sat": "Every Saturday",
        "remind.repeat.sun": "Every Sunday",
        "remind.repeat.once": "Once (pick date)",
        "remind.fmt.once": "Once {date}",
        "remind.fmt.daily": "Daily",
        "remind.fmt.weekdays": "Weekdays",
        "remind.fmt.weekly": "Every {day}",
        "timer.idle": "Idle",
        "timer.working": "Focus · round {cycle}/{total}",
        "timer.resting": "Resting ☕",
        "timer.finished": "All done 🎉",
        "timer.settings": "Timer settings",
        "timer.work_min": "Work (minutes)",
        "timer.rest_min": "Break (minutes)",
        "timer.cycles": "Cycles",
        "timer.sound": "Play sound on break",
        "timer.pet_size": "WALL-E size",
        "timer.pet_hint": "Drag bottom-right corner or Ctrl+scroll on desktop",
        "timer.start": "▶ Start",
        "timer.rest": "☕ Break",
        "timer.stop": "■ Stop",
        "settings.language": "Language",
        "rest.title": "Break time!",
        "rest.end_btn": "✔ I'm rested — end early",
        "rest.tip.0": "Look into the distance and rest your eyes 👀",
        "rest.tip.1": "Stand up, stretch, drink some water 💧",
        "rest.tip.2": "Stretch your neck and shoulders 🧘",
        "rest.tip.3": "Deep breath — WALL-E relaxes with you 🌿",
        "rest.tip.4": "Step away and look outside 🌤️",
        "seed.todo.meeting": "Meeting",
        "seed.todo.report": "Weekly report",
        "seed.todo.package": "Pick up package",
        "seed.remind.water": "Drink water",
        "seed.remind.rest": "Rest",
    },
}


class _I18nHub(QObject):
    language_changed = Signal()


_hub = _I18nHub()


def current() -> str:
    return _LANG


def init_language(lang: str | None) -> None:
    """启动时从配置加载语言，不触发刷新信号。"""
    global _LANG
    _LANG = lang if lang in _STRINGS else "zh"


def set_language(lang: str) -> None:
    global _LANG
    if lang not in _STRINGS:
        lang = "zh"
    if _LANG != lang:
        _LANG = lang
        _hub.language_changed.emit()


def on_language_changed(slot: Callable[[], None]) -> None:
    _hub.language_changed.connect(slot)


def tr(key: str, **kwargs: Any) -> str:
    text = _STRINGS.get(_LANG, _STRINGS["zh"]).get(key)
    if text is None:
        text = _STRINGS["zh"].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def priority_labels() -> tuple[str, str, str]:
    return tr("prio.high"), tr("prio.med"), tr("prio.low")


def priority_short(priority: int) -> str:
    from .todo_manager import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_MED

    mapping = {
        PRIORITY_HIGH: tr("pet.pri_short_high"),
        PRIORITY_MED: tr("pet.pri_short_med"),
        PRIORITY_LOW: tr("pet.pri_short_low"),
    }
    return mapping.get(priority, tr("pet.pri_short_med"))


def remind_repeat_options() -> list[str]:
    return [
        tr("remind.repeat.daily"),
        tr("remind.repeat.weekdays"),
        tr("remind.repeat.mon"),
        tr("remind.repeat.tue"),
        tr("remind.repeat.wed"),
        tr("remind.repeat.thu"),
        tr("remind.repeat.fri"),
        tr("remind.repeat.sat"),
        tr("remind.repeat.sun"),
        tr("remind.repeat.once"),
    ]


def weekday_name(weekday: int) -> str:
    """0=Monday … 6=Sunday"""
    if _LANG == "en":
        return _WEEKDAY_EN[weekday % 7]
    return _WEEKDAY_ZH[weekday % 7]


def rest_tips() -> list[str]:
    return [tr(f"rest.tip.{i}") for i in range(5)]
