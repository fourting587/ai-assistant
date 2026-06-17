"""长期记忆存储——SQLite 持久化，支持会话隔离"""
import sqlite3
import os
import contextvars
from datetime import datetime
from typing import Optional

_current_session = contextvars.ContextVar("current_session", default="")

def set_current_session(session_id: str) -> None:
    _current_session.set(session_id)

def get_current_session() -> str:
    return _current_session.get()


class MemoryStore:
    def __init__(self, db_path: str = "data/memories.db") -> None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    content     TEXT    NOT NULL,
                    memory_type TEXT    NOT NULL DEFAULT 'general',
                    importance  INTEGER NOT NULL DEFAULT 5 CHECK(importance BETWEEN 1 AND 10),
                    session_id  TEXT    NOT NULL DEFAULT '',
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_type     ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_session  ON memories(session_id);
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
            """)
            try:
                conn.execute("ALTER TABLE memories ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")
            except sqlite3.OperationalError:
                pass

    @staticmethod
    def _dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict:
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = self._dict_factory
        return conn

    def add(self, content: str, memory_type: str = "general",
            importance: int = 5) -> Optional[dict]:
        now = datetime.now().isoformat()
        sid = get_current_session()
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO memories (content,memory_type,importance,session_id,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?)", (content, memory_type, importance, sid, now, now))
            return conn.execute("SELECT * FROM memories WHERE id=?", (cur.lastrowid,)).fetchone()

    def get(self, memory_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()

    def update(self, memory_id: int, content: Optional[str] = None,
               memory_type: Optional[str] = None,
               importance: Optional[int] = None) -> Optional[dict]:
        updates: dict = {"updated_at": datetime.now().isoformat()}
        if content is not None: updates["content"] = content
        if memory_type is not None: updates["memory_type"] = memory_type
        if importance is not None: updates["importance"] = max(1, min(10, importance))
        clause = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [memory_id]
        with self._get_conn() as conn:
            if conn.execute(f"UPDATE memories SET {clause} WHERE id=?", vals).rowcount == 0:
                return None
            return conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()

    def delete(self, memory_id: int) -> bool:
        with self._get_conn() as conn:
            return conn.execute("DELETE FROM memories WHERE id=?", (memory_id,)).rowcount > 0

    def list_all(self, memory_type: Optional[str] = None, limit: int = 50) -> list[dict]:
        sid = get_current_session()
        with self._get_conn() as conn:
            if memory_type:
                return conn.execute(
                    "SELECT * FROM memories WHERE session_id=? AND memory_type=? "
                    "ORDER BY importance DESC, updated_at DESC LIMIT ?", (sid, memory_type, limit)).fetchall()
            return conn.execute(
                "SELECT * FROM memories WHERE session_id=? "
                "ORDER BY importance DESC, updated_at DESC LIMIT ?", (sid, limit)).fetchall()

    def search(self, keyword: str, limit: int = 20) -> list[dict]:
        sid = get_current_session()
        return self._get_conn().execute(
            "SELECT * FROM memories WHERE session_id=? AND content LIKE ? "
            "ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (sid, f"%{keyword}%", limit)).fetchall()

    def stats(self) -> dict:
        sid = get_current_session()
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM memories WHERE session_id=?", (sid,)).fetchone()["c"]
            by_type = conn.execute("SELECT memory_type, COUNT(*) AS c FROM memories WHERE session_id=? GROUP BY memory_type", (sid,)).fetchall()
            avg = conn.execute("SELECT AVG(importance) AS a FROM memories WHERE session_id=?", (sid,)).fetchone()["a"] or 0
        return {"total": total, "by_type": {r["memory_type"]: r["c"] for r in by_type}, "avg_importance": round(float(avg), 1)}
