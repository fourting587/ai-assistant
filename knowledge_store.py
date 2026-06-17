"""
知识库 RAG 引擎
基于 TF-IDF + 余弦相似度的检索增强生成
无需下载模型，完全离线可用
"""
import os
import sqlite3
import uuid
import re
from datetime import datetime
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class KnowledgeStore:
    """知识库——文档存储 + 语义检索"""

    def __init__(self, db_path: str = "data/knowledge.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(1, 3),
            max_features=10000,
        )
        self._initialized = False
        self._init_db()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    source      TEXT NOT NULL DEFAULT 'upload',
                    created_at  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id      TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    content     TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
            """)

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ─── 文档管理 ─────────────────────────────

    def add_document(self, title: str, content: str, chunk_size: int = 500,
                     chunk_overlap: int = 50) -> dict:
        """添加文档到知识库（自动分块）"""
        doc_id = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()

        chunks = self._chunk_text(content, chunk_size, chunk_overlap)

        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO documents (id, title, source, created_at) VALUES (?, ?, ?, ?)",
                (doc_id, title, "upload", now),
            )
            for i, chunk in enumerate(chunks):
                conn.execute(
                    "INSERT INTO chunks (doc_id, content, chunk_index) VALUES (?, ?, ?)",
                    (doc_id, chunk, i),
                )

        self._mark_dirty()
        return self.get_document(doc_id)

    def get_document(self, doc_id: str) -> Optional[dict]:
        """获取单个文档信息"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return None
            doc = dict(row)
            chunks = conn.execute(
                "SELECT content FROM chunks WHERE doc_id = ? ORDER BY chunk_index",
                (doc_id,),
            ).fetchall()
            doc["chunks"] = [c["content"] for c in chunks]
            doc["chunk_count"] = len(chunks)
            doc["total_chars"] = sum(len(c) for c in doc["chunks"])
            return doc

    def list_documents(self) -> list[dict]:
        """列出所有文档"""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT d.*, COUNT(c.id) AS chunk_count,
                       COALESCE(SUM(LENGTH(c.content)), 0) AS total_chars
                FROM documents d
                LEFT JOIN chunks c ON d.id = c.doc_id
                GROUP BY d.id
                ORDER BY d.created_at DESC
            """).fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            ok = cur.rowcount > 0
        if ok:
            self._mark_dirty()
        return ok

    def stats(self) -> dict:
        """知识库统计"""
        with self._get_conn() as conn:
            docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"documents": docs, "chunks": chunks}

    # ─── 语义搜索 ─────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """搜索知识库，返回最相关的文本块"""
        chunks = self._get_all_chunks()
        if not chunks:
            return []

        # 构建 TF-IDF 矩阵并查询
        try:
            matrix = self._build_tfidf([c["content"] for c in chunks])
            query_vec = self._vectorizer.transform([query])
            scores = cosine_similarity(query_vec, matrix).flatten()
        except ValueError:
            return []  # 词汇表为空

        # 取 top_k
        top_indices = scores.argsort()[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    **chunks[idx],
                    "score": round(float(scores[idx]), 4),
                })
        return results

    def search_with_context(self, query: str, top_k: int = 3) -> str:
        """搜索并格式化为上下文文本"""
        results = self.search(query, top_k)
        if not results:
            return ""

        lines = ["以下是从知识库中检索到的相关资料：\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] (相关度: {r['score']:.0%})")
            lines.append(r["content"])
            lines.append("")
        return "\n".join(lines)

    # ─── 内部方法 ─────────────────────────────

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """将文本按段落/句子分块"""
        # 先按段落分割
        paragraphs = re.split(r"\n\s*\n", text.strip())
        chunks = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) < chunk_size:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(current)
                # 如果段落本身超过 chunk_size，按句子切分
                if len(para) > chunk_size:
                    sentences = re.split(r"(?<=[。！？.!?])", para)
                    for sent in sentences:
                        if not sent.strip():
                            continue
                        if len(current) + len(sent) < chunk_size:
                            current = (current + sent).strip()
                        else:
                            if current:
                                chunks.append(current)
                            current = sent
                else:
                    current = para

        if current:
            chunks.append(current)

        # 应用重叠
        if overlap > 0 and len(chunks) > 1:
            overlapped = []
            for i, chunk in enumerate(chunks):
                if i > 0:
                    prev_tail = chunks[i - 1][-overlap:]
                    chunk = prev_tail + chunk
                overlapped.append(chunk)
            chunks = overlapped

        return chunks

    def _get_all_chunks(self) -> list[dict]:
        """获取所有文本块（带文档信息）"""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT c.id, c.content, c.doc_id, c.chunk_index, d.title
                FROM chunks c
                JOIN documents d ON c.doc_id = d.id
                ORDER BY c.doc_id, c.chunk_index
            """).fetchall()
        return [dict(r) for r in rows]

    def _build_tfidf(self, texts: list[str]):
        """构建 TF-IDF 矩阵（带缓存）"""
        return self._vectorizer.fit_transform(texts)

    def _mark_dirty(self):
        """标记需要重建索引"""
        self._initialized = False
