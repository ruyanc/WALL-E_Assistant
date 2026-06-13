"""从自然语言解析提醒指令。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Tuple

from .reminder_manager import REPEAT_DAILY, REPEAT_ONCE, REPEAT_WEEKDAYS, REPEAT_WEEKLY

_WEEKDAY_MAP = {
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6,
}


@dataclass
class ParsedReminder:
    text: str
    hour: int
    minute: int
    repeat: str
    target_date: Optional[str] = None
    weekday: Optional[int] = None


def _parse_time(text: str) -> Optional[Tuple[int, int]]:
    m = re.search(r"(\d{1,2})\s*[:：点时]\s*(\d{1,2})?\s*分?", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return h, mi
    m = re.search(r"(\d{1,2})\s*点\s*半", text)
    if m:
        return int(m.group(1)), 30
    m = re.search(r"(\d{1,2})\s*点", text)
    if m:
        return int(m.group(1)), 0
    return None


def _strip_time_and_triggers(text: str) -> str:
    text = re.sub(
        r"(提醒我|提醒|定时提醒|闹钟|每天|工作日|每周[一二三四五六日天]|明天|后天|"
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?|"
        r"\d{1,2}\s*[:：点时]\s*\d{0,2}\s*分?|\d{1,2}\s*点\s*半?)",
        " ",
        text,
    )
    return re.sub(r"\s+", " ", text).strip(" ，,、:：")


def parse_reminder_add(message: str) -> Optional[ParsedReminder]:
    text = message.strip()
    if not any(w in text for w in ("提醒", "闹钟")):
        return None

    tm = _parse_time(text)
    if tm is None:
        return None
    hour, minute = tm

    body = _strip_time_and_triggers(text)
    if not body:
        return None

    today = date.today()
    if "明天" in text:
        target = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        return ParsedReminder(body, hour, minute, REPEAT_ONCE, target_date=target)
    if "后天" in text:
        target = (today + timedelta(days=2)).strftime("%Y-%m-%d")
        return ParsedReminder(body, hour, minute, REPEAT_ONCE, target_date=target)

    dm = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if dm:
        y, mo, d = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        target = date(y, mo, d).strftime("%Y-%m-%d")
        return ParsedReminder(body, hour, minute, REPEAT_ONCE, target_date=target)

    wm = re.search(r"每周([一二三四五六日天])", text)
    if wm:
        wd = _WEEKDAY_MAP.get(wm.group(1))
        if wd is not None:
            return ParsedReminder(body, hour, minute, REPEAT_WEEKLY, weekday=wd)

    if "工作日" in text:
        return ParsedReminder(body, hour, minute, REPEAT_WEEKDAYS)

    if "每天" in text or "每日" in text:
        return ParsedReminder(body, hour, minute, REPEAT_DAILY)

    # 默认：每天
    return ParsedReminder(body, hour, minute, REPEAT_DAILY)
