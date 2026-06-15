"""记事本存储（支持 CloudBase 同步）。"""



from __future__ import annotations



import json

import sys

import time

import uuid

from dataclasses import asdict, dataclass, field

from pathlib import Path

from typing import Any, Callable, List



from storage import notes_path





def _migrate_id(raw_id: object) -> str:

    root = Path(__file__).resolve().parents[1]

    if str(root) not in sys.path:

        sys.path.insert(0, str(root))

    from walle.sync.ids import migrate_id



    return migrate_id(raw_id, namespace="note")





@dataclass

class NoteEntry:

    id: str

    text: str

    created: float = field(default_factory=time.time)

    updated_at: float = field(default_factory=time.time)

    deleted: bool = False





class NotesStore:

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:

        self._entries: List[NoteEntry] = []

        self._on_change = on_change

        self._loading = False

        self.load()



    @property

    def entries(self) -> List[NoteEntry]:

        return [e for e in self._entries if not e.deleted]



    def add(self, text: str = "") -> NoteEntry:

        now = time.time()

        entry = NoteEntry(id=str(uuid.uuid4()), text=text.strip(), created=now, updated_at=now)

        self._entries.insert(0, entry)

        self._changed()

        return entry



    def update(self, note_id: str, text: str) -> None:

        for e in self._entries:

            if e.id == note_id and not e.deleted and e.text != text:

                e.text = text

                e.updated_at = time.time()

                self._changed()

                return



    def remove(self, note_id: str) -> None:

        for e in self._entries:

            if e.id == note_id and not e.deleted:

                e.deleted = True

                e.updated_at = time.time()

                self._changed()

                return



    def export_sync_records(self) -> list[dict[str, Any]]:

        return [

            {

                "record_id": entry.id,

                "collection": "note",

                "payload": asdict(entry),

                "updated_at": entry.updated_at,

                "deleted": entry.deleted,

            }

            for entry in self._entries

        ]



    def import_sync_records(self, rows: list[dict[str, Any]]) -> None:

        by_id: dict[str, NoteEntry] = {}

        for row in rows:

            payload = row.get("payload") or {}

            if not isinstance(payload, dict):

                continue

            note_id = _migrate_id(payload.get("id", row.get("record_id")))

            payload = dict(payload)

            payload["id"] = note_id

            payload.setdefault("updated_at", float(row.get("updated_at", time.time())))

            payload["deleted"] = bool(row.get("deleted", payload.get("deleted", False)))

            try:

                by_id[note_id] = NoteEntry(**{k: v for k, v in payload.items() if k in NoteEntry.__dataclass_fields__})

            except TypeError:

                continue

        if not by_id:

            return

        self._loading = True

        try:

            self._entries = sorted(by_id.values(), key=lambda e: -e.updated_at)

            self.save()

            if self._on_change:

                self._on_change()

        finally:

            self._loading = False



    def _changed(self) -> None:

        if self._loading:

            return

        self.save()

        if self._on_change:

            self._on_change()



    def save(self) -> None:

        try:

            with open(notes_path(), "w", encoding="utf-8") as f:

                json.dump({"entries": [asdict(e) for e in self._entries]}, f, ensure_ascii=False, indent=2)

        except OSError:

            pass



    def load(self) -> None:

        path = notes_path()

        if not path.exists():

            return

        try:

            with open(path, "r", encoding="utf-8-sig") as f:

                data = json.load(f)

            self._entries = []

            for raw in data.get("entries", []):

                raw = dict(raw)

                raw["id"] = str(raw.get("id", uuid.uuid4()))

                raw.setdefault("updated_at", raw.get("created", time.time()))

                raw.setdefault("deleted", False)

                self._entries.append(

                    NoteEntry(**{k: v for k, v in raw.items() if k in NoteEntry.__dataclass_fields__})

                )

        except (json.JSONDecodeError, OSError, TypeError):

            self._entries = []


