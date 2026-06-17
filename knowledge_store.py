"""知识库 RAG 引擎——TF-IDF + 余弦相似度，零依赖离线运行"""
import os
import sqlite3
import uuid
import re
from datetime import datetime
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class KnowledgeStore:
    def __init__(self, db_path: str = "data/knowledge.db") -> None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(1, 3), max_features=10000)
        self._init_db()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL,
                    source     TEXT NOT NULL DEFAULT 'upload',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id      TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    content     TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
            """)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def add_document(self, title: str, content: str, chunk_size: int = 500,
                     chunk_overlap: int = 50) -> Optional[dict]:
        doc_id = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        chunks = self._chunk_text(content, chunk_size, chunk_overlap)
        with self._get_conn() as conn:
            conn.execute("INSERT INTO documents (id,title,source,created_at) VALUES (?,?,?,?)",
                         (doc_id, title, "upload", now))
            for i, chunk in enumerate(chunks):
                conn.execute("INSERT INTO chunks (doc_id,content,chunk_index) VALUES (?,?,?)",
                             (doc_id, chunk, i))
        return self.get_document(doc_id)

    def get_document(self, doc_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
            if not row:
                return None
            doc = dict(row)
            chunks = conn.execute("SELECT content FROM chunks WHERE doc_id=? ORDER BY chunk_index",
                                  (doc_id,)).fetchall()
            doc["chunks"] = [c["content"] for c in chunks]
            doc["chunk_count"] = len(chunks)
            doc["total_chars"] = sum(len(c) for c in doc["chunks"])
            return doc

    def list_documents(self) -> list[dict]:
        with self._get_conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT d.*, COUNT(c.id) AS chunk_count, COALESCE(SUM(LENGTH(c.content)),0) AS total_chars "
                "FROM documents d LEFT JOIN chunks c ON d.id=c.doc_id "
                "GROUP BY d.id ORDER BY d.created_at DESC").fetchall()]

    def delete_document(self, doc_id: str) -> bool:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
            return conn.execute("DELETE FROM documents WHERE id=?", (doc_id,)).rowcount > 0

    def stats(self) -> dict:
        with self._get_conn() as conn:
            docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"documents": docs, "chunks": chunks}

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        chunks = self._get_all_chunks()
        if not chunks:
            return []
        try:
            matrix = self._vectorizer.fit_transform([c["content"] for c in chunks])
            q_vec = self._vectorizer.transform([query])
            scores = cosine_similarity(q_vec, matrix).flatten()
        except ValueError:
            return []
        indices = scores.argsort()[::-1][:top_k]
        return [{**chunks[i], "score": round(float(scores[i]), 4)} for i in indices if scores[i] > 0]

    def search_with_context(self, query: str, top_k: int = 3) -> str:
        results = self.search(query, top_k)
        if not results:
            return ""
        lines = ["以下是从知识库中检索到的相关资料：\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] (相关度: {r['score']:.0%})\n{r['content']}\n")
        return "\n".join(lines)

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        paragraphs = re.split(r"\n\s*\n", text.strip())
        chunks, current = [], ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) < chunk_size:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(current)
                if len(para) > chunk_size:
                    sentences = re.split(r"(?<=[。！？.!?])", para)
                    for sent in (s for s in sentences if s.strip()):
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
        if overlap > 0 and len(chunks) > 1:
            chunks = [chunks[0]] + [chunks[i - 1][-overlap:] + chunks[i] for i in range(1, len(chunks))]
        return chunks

    def _get_all_chunks(self) -> list[dict]:
        with self._get_conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT c.id,c.content,c.doc_id,c.chunk_index,d.title "
                "FROM chunks c JOIN documents d ON c.doc_id=d.id ORDER BY c.doc_id,c.chunk_index").fetchall()]
