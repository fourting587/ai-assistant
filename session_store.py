"""
会话管理和消息持久化存储
基于 SQLite，保存对话历史和会话元数据
"""
import sqlite3
import os
import uuid
from datetime import datetime
from typing import Optional


class SessionStore:
    """会话存储——管理多轮对话和消息历史"""

    def __init__(self, db_path: str = "data/sessions.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL DEFAULT '新对话',
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role        TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                    content     TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
            """)

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ─── 会话 CRUD ─────────────────────────────

    def create_session(self, title: str = "新对话") -> dict:
        """创建新会话"""
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now),
            )
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取单个会话"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return None
            msg_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM messages WHERE session_id = ?", (session_id,)
            ).fetchone()["cnt"]
            s = dict(row)
            s["message_count"] = msg_count
            return s

    def list_sessions(self, limit: int = 50) -> list[dict]:
        """列出所有会话（按更新时间倒序）"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT s.*, COUNT(m.id) AS message_count "
                "FROM sessions s LEFT JOIN messages m ON s.id = m.session_id "
                "GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_session(self, session_id: str, title: str = None) -> Optional[dict]:
        """更新会话标题"""
        now = datetime.now().isoformat()
        updates = ["updated_at = ?"]
        values = [now]
        if title is not None:
            updates.append("title = ?")
            values.append(title)
        values.append(session_id)
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?", values
            )
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其所有消息"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cur.rowcount > 0

    # ─── 消息 CRUD ─────────────────────────────

    def add_message(self, session_id: str, role: str, content: str) -> dict:
        """添加一条消息并更新会话时间"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
            )
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
            return dict(row)

    def get_messages(self, session_id: str, limit: int = 200) -> list[dict]:
        """获取会话的消息历史"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def auto_title(self, session_id: str, first_msg: str):
        """根据第一条消息自动命名会话"""
        title = first_msg.strip()[:30]
        if len(title) < 2:
            title = "新对话"
        self.update_session(session_id, title)
