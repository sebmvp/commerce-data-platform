"""Unstructured evidence: seller notes, marketplace policies, playbooks."""
from __future__ import annotations

import json
from typing import Any

from ..validate import NoteRecord
from .base import IngestJob


class NoteIngest(IngestJob[NoteRecord]):
    source = "ops.notes"
    filename = "notes.jsonl"
    model = NoteRecord

    def natural_key(self, rec: NoteRecord) -> str:
        return rec.note_id

    def upsert(self, rec: NoteRecord, raw: dict[str, Any]) -> None:
        self.con.execute(
            """INSERT INTO ops.notes
               (note_id, kind, object_type, object_id, title, body, source_file, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?::jsonb)
               ON CONFLICT (note_id) DO UPDATE SET
                 body=excluded.body, title=excluded.title,
                 object_type=excluded.object_type, object_id=excluded.object_id""",
            [
                rec.note_id,
                rec.kind,
                rec.object_type,
                rec.object_id,
                rec.title,
                rec.body,
                str(self.path),
                json.dumps(raw, default=str),
            ],
        )
