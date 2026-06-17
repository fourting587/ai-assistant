"""会话管理和消息持久化存储——SQLite"""
import sqlite3
import os
import uuid
from datetime import datetime
from typing import Optional


class SessionStore:
    def __init__(self, db_path: str = "data/sessions.db") -> None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL DEFAULT '新对话',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role       TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                    content    TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
            """)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_session(self, title: str = "新对话") -> dict:
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute("INSERT INTO sessions (id,title,created_at,updated_at) VALUES (?,?,?,?)",
                         (session_id, title, now, now))
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                return None
            s = dict(row)
            s["message_count"] = conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE session_id=?", (session_id,)).fetchone()["c"]
            return s

    def list_sessions(self, limit: int = 50) -> list[dict]:
        with self._get_conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT s.*, COUNT(m.id) AS message_count FROM sessions s "
                "LEFT JOIN messages m ON s.id=m.session_id "
                "GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ?", (limit,)).fetchall()]

    def update_session(self, session_id: str, title: Optional[str] = None) -> Optional[dict]:
        now = datetime.now().isoformat()
        updates, vals = ["updated_at=?"], [now]
        if title is not None:
            updates.append("title=?")
            vals.append(title)
        vals.append(session_id)
        with self._get_conn() as conn:
            conn.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE id=?", vals)
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            return conn.execute("DELETE FROM sessions WHERE id=?", (session_id,)).rowcount > 0

    def add_message(self, session_id: str, role: str, content: str) -> dict:
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cur = conn.execute("INSERT INTO messages (session_id,role,content,created_at) VALUES (?,?,?,?)",
                               (session_id, role, content, now))
            conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
            return dict(conn.execute("SELECT * FROM messages WHERE id=?", (cur.lastrowid,)).fetchone())

    def get_messages(self, session_id: str, limit: int = 200) -> list[dict]:
        with self._get_conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM messages WHERE session_id=? ORDER BY created_at ASC LIMIT ?",
                (session_id, limit)).fetchall()]

    def auto_title(self, session_id: str, first_msg: str) -> None:
        title = first_msg.strip()[:30]
        if len(title) < 2:
            title = "新对话"
        self.update_session(session_id, title)
