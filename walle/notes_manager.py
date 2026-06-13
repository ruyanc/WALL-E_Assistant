"""记事本数据管理：多条目小文本，保存到 %APPDATA%\\WALL-E\\notes.json。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import List

from PySide6.QtCore import QObject, QTimer, Signal

from .config import NOTES_LEGACY_PATH, NOTES_PATH


@dataclass
class NoteEntry:
    id: int
    text: str
    created: float = field(default_factory=time.time)


class NotesManager(QObject):
    """管理多条记事本条目，延迟自动落盘。"""

    changed = Signal()  # 增删条目时发出，供界面重建列表

    def __init__(self) -> None:
        super().__init__()
        self._entries: List[NoteEntry] = []
        self._next_id = 1
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._flush)
        self.load()

    @property
    def entries(self) -> List[NoteEntry]:
        return list(self._entries)

    def find(self, note_id: int) -> NoteEntry | None:
        for e in self._entries:
            if e.id == note_id:
                return e
        return None

    def add(self, text: str = "") -> NoteEntry:
        entry = NoteEntry(id=self._next_id, text=text.strip())
        self._next_id += 1
        self._entries.insert(0, entry)  # 新条目置顶
        self._after_structure_change()
        return entry

    def update_text(self, note_id: int, text: str, *, save_now: bool = False) -> None:
        entry = self.find(note_id)
        if entry is None or entry.text == text:
            return
        entry.text = text
        if save_now:
            self._flush()
        else:
            self._save_timer.start(500)

    def remove(self, note_id: int) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != note_id]
        if len(self._entries) != before:
            self._after_structure_change()
            return True
        return False

    def _after_structure_change(self) -> None:
        self._flush()
        self.changed.emit()

    def _flush(self) -> None:
        try:
            payload = {
                "next_id": self._next_id,
                "entries": [asdict(e) for e in self._entries],
            }
            with open(NOTES_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def save(self) -> None:
        self._save_timer.stop()
        self._flush()

    def load(self) -> None:
        if NOTES_PATH.exists():
            try:
                with open(NOTES_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._next_id = data.get("next_id", 1)
                self._entries = [NoteEntry(**e) for e in data.get("entries", [])]
                return
            except (json.JSONDecodeError, OSError, TypeError):
                pass

        # 从旧版单文件 notes.txt 迁移
        if NOTES_LEGACY_PATH.exists():
            try:
                legacy = NOTES_LEGACY_PATH.read_text(encoding="utf-8").strip()
                if legacy:
                    self._entries = [NoteEntry(id=1, text=legacy)]
                    self._next_id = 2
                    self._flush()
                    return
            except OSError:
                pass

        self._entries = []
        self._next_id = 1
