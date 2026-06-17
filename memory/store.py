"""
长期记忆存储层
基于 SQLite，支持记忆的增删改查、分类和重要性评分
支持按会话隔离（session_id）
"""
import sqlite3
import contextvars
import os
from datetime import datetime
from typing import Optional


# 线程本地存储当前会话 ID
_current_session = contextvars.ContextVar("current_session", default="")


def set_current_session(session_id: str):
    """设置当前请求的会话 ID（由 API 层调用）"""
    _current_session.set(session_id)


def get_current_session() -> str:
    """获取当前会话 ID"""
    return _current_session.get()


class MemoryStore:
    """长期记忆存储——AI 助手的「大脑」"""

    def __init__(self, db_path: str = "data/memories.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
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
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id);
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
            """)
            # 兼容旧表：尝试添加 session_id 列
            try:
                conn.execute("ALTER TABLE memories ADD COLUMN session_id TEXT NOT NULL DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # 列已存在

    @staticmethod
    def _dict_factory(cursor, row):
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = self._dict_factory
        return conn

    # ─── CRUD ───────────────────────────────────────────

    def add(self, content: str, memory_type: str = "general",
            importance: int = 5) -> dict:
        """添加一条记忆（自动绑定当前会话）"""
        now = datetime.now().isoformat()
        session_id = get_current_session()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO memories (content, memory_type, importance, session_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (content, memory_type, importance, session_id, now, now),
            )
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return row

    def get(self, memory_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
            return row if row else None

    def update(self, memory_id: int, content: str = None,
               memory_type: str = None, importance: int = None) -> Optional[dict]:
        updates = {"updated_at": datetime.now().isoformat()}
        if content is not None:
            updates["content"] = content
        if memory_type is not None:
            updates["memory_type"] = memory_type
        if importance is not None:
            updates["importance"] = max(1, min(10, importance))

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [memory_id]

        with self._get_conn() as conn:
            cursor = conn.execute(
                f"UPDATE memories SET {set_clause} WHERE id = ?", values
            )
            if cursor.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
            return row

    def delete(self, memory_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    # ─── 查询（仅当前会话） ─────────────────────────

    def list_all(self, memory_type: str = None, limit: int = 50) -> list[dict]:
        """列出当前会话的记忆"""
        session_id = get_current_session()
        with self._get_conn() as conn:
            if memory_type:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE session_id = ? AND memory_type = ? "
                    "ORDER BY importance DESC, updated_at DESC LIMIT ?",
                    (session_id, memory_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE session_id = ? "
                    "ORDER BY importance DESC, updated_at DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
        return rows

    def search(self, keyword: str, limit: int = 20) -> list[dict]:
        """在当前会话中搜索记忆"""
        session_id = get_current_session()
        rows = self._get_conn().execute(
            "SELECT * FROM memories WHERE session_id = ? AND content LIKE ? "
            "ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (session_id, f"%{keyword}%", limit),
        ).fetchall()
        return rows

    def stats(self) -> dict:
        """记忆统计（仅当前会话）"""
        session_id = get_current_session()
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM memories WHERE session_id = ?",
                (session_id,),
            ).fetchone()["cnt"]
            by_type = conn.execute(
                "SELECT memory_type, COUNT(*) AS cnt FROM memories "
                "WHERE session_id = ? GROUP BY memory_type",
                (session_id,),
            ).fetchall()
            avg_row = conn.execute(
                "SELECT AVG(importance) AS avg_imp FROM memories WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            avg_imp = avg_row["avg_imp"] if avg_row and avg_row["avg_imp"] else 0
        return {
            "total": total,
            "by_type": {r["memory_type"]: r["cnt"] for r in by_type},
            "avg_importance": round(avg_imp, 1),
        }
