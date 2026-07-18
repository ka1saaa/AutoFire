from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Contact:
    id: int
    nickname: str
    remark: str
    selected: bool
    updated_at: str

    @property
    def label(self) -> str:
        return self.remark or self.nickname


class Store:
    def __init__(self, path: Path):
        self.path = path
        self._setup()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            conn.close()

    def _setup(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY,
                    nickname TEXT NOT NULL,
                    remark TEXT NOT NULL DEFAULT '',
                    selected INTEGER NOT NULL DEFAULT 0 CHECK(selected IN (0, 1)),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    selected_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES('url', 'https://www.douyin.com/')"
            )

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def list_contacts(self, keyword: str = "") -> list[Contact]:
        keyword = f"%{keyword.strip()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM contacts
                WHERE nickname LIKE ? OR remark LIKE ?
                ORDER BY CASE WHEN remark = '' THEN nickname ELSE remark END COLLATE NOCASE, nickname COLLATE NOCASE
                """,
                (keyword, keyword),
            ).fetchall()
        return [Contact(row["id"], row["nickname"], row["remark"], bool(row["selected"]), row["updated_at"]) for row in rows]

    def selected_contacts(self) -> list[Contact]:
        return [item for item in self.list_contacts() if item.selected]

    def add_contact(self, nickname: str, remark: str = "") -> None:
        nickname, remark = nickname.strip(), remark.strip()
        if not nickname:
            raise ValueError("昵称不能为空")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO contacts(nickname, remark, selected, updated_at) VALUES (?, ?, 0, ?)",
                (nickname, remark, self._now()),
            )

    def update_contact(self, contact_id: int, nickname: str, remark: str) -> None:
        nickname, remark = nickname.strip(), remark.strip()
        if not nickname:
            raise ValueError("昵称不能为空")
        with self._connect() as conn:
            conn.execute(
                "UPDATE contacts SET nickname = ?, remark = ?, updated_at = ? WHERE id = ?",
                (nickname, remark, self._now(), contact_id),
            )

    def delete_contact(self, contact_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))

    def set_selected(self, ids: list[int], selected: bool) -> None:
        if not ids:
            return
        marks = ",".join("?" for _ in ids)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE contacts SET selected = ?, updated_at = ? WHERE id IN ({marks})",
                (int(selected), self._now(), *ids),
            )

    def selection_signature(self) -> str:
        value = "\n".join(f"{item.id}:{item.nickname}:{item.remark}" for item in self.selected_contacts())
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def needs_selection_confirmation(self) -> bool:
        return self.get_setting("confirmed_selection", "") != self.selection_signature()

    def confirm_current_selection(self) -> None:
        self.set_setting("confirmed_selection", self.selection_signature())

    def record_run(self, selected_count: int, status: str, details: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs(created_at, selected_count, status, details) VALUES (?, ?, ?, ?)",
                (self._now(), selected_count, status, details),
            )
