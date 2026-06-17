"""
长期记忆存储层
基于 SQLite，支持记忆的增删改查、分类和重要性评分
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional


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
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
            """)

    @staticmethod
    def _dict_factory(cursor, row):
        """将查询结果直接转为 dict"""
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    def _get_conn(self):
        """获取数据库连接（每次调用独立，避免线程问题）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = self._dict_factory
        return conn

    # ─── CRUD ───────────────────────────────────────────

    def add(self, content: str, memory_type: str = "general",
            importance: int = 5) -> dict:
        """添加一条记忆"""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO memories (content, memory_type, importance, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (content, memory_type, importance, now, now),
            )
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return row

    def get(self, memory_id: int) -> Optional[dict]:
        """根据 ID 获取单条记忆"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
            return row if row else None

    def update(self, memory_id: int, content: str = None,
               memory_type: str = None, importance: int = None) -> Optional[dict]:
        """更新记忆（只传需要修改的字段）"""
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
        """删除记忆"""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    # ─── 查询 ───────────────────────────────────────────

    def list_all(self, memory_type: str = None, limit: int = 50) -> list[dict]:
        """列出所有记忆，可按类型过滤、按重要性降序"""
        if memory_type:
            rows = self._get_conn().execute(
                "SELECT * FROM memories WHERE memory_type = ? "
                "ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (memory_type, limit),
            ).fetchall()
        else:
            rows = self._get_conn().execute(
                "SELECT * FROM memories ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return rows

    def search(self, keyword: str, limit: int = 20) -> list[dict]:
        """全文搜索记忆内容"""
        rows = self._get_conn().execute(
            "SELECT * FROM memories WHERE content LIKE ? "
            "ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (f"%{keyword}%", limit),
        ).fetchall()
        return rows

    # ─── 统计 ───────────────────────────────────────────

    def stats(self) -> dict:
        """记忆统计"""
        with self._get_conn() as conn:
            total_row = conn.execute("SELECT COUNT(*) AS cnt FROM memories").fetchone()
            total = total_row["cnt"] if total_row else 0
            by_type_rows = conn.execute(
                "SELECT memory_type, COUNT(*) AS cnt FROM memories GROUP BY memory_type"
            ).fetchall()
            avg_row = conn.execute(
                "SELECT AVG(importance) AS avg_imp FROM memories"
            ).fetchone()
            avg_imp = avg_row["avg_imp"] if avg_row and avg_row["avg_imp"] else 0
        return {
            "total": total,
            "by_type": {r["memory_type"]: r["cnt"] for r in by_type_rows},
            "avg_importance": round(avg_imp, 1),
        }
