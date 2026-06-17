#!/usr/bin/env python3
"""
AI 智能助理 — FastAPI 后端
REST API + SSE 流式对话 + 会话管理 + 文件上传 + RAG 知识库
"""
import sys, os, json, uuid
from typing import Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import uvicorn
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import Config
from memory.store import MemoryStore, set_current_session
from session_store import SessionStore
from knowledge_store import KnowledgeStore
from tools.memory_tools import get_memory_tools
from tools.weather_tools import query_weather
from tools.search_tools import web_search
from agent.assistant import Assistant

# ── 初始化 ──
store = MemoryStore(Config.DB_PATH)
session_store = SessionStore()
knowledge_store = KnowledgeStore()
tools = get_memory_tools(store) + [query_weather, web_search]
assistant = Assistant(tools)

app = FastAPI(title="🧠 AI 智能助理", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── 全局异常处理 ──
class AppException(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status

@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status, content={"error": exc.message})

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    from fastapi.responses import JSONResponse
    import traceback
    print(f"❌ 未捕获异常: {exc}\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"error": f"服务器内部错误: {type(exc).__name__}"})


# ── 数据模型 ──
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "general"
    importance: int = 5

class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    memory_type: Optional[str] = None
    importance: Optional[int] = None

# ═══════════════════════════════════════════════
#  📝 对话 + RAG
# ═══════════════════════════════════════════════

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_stream():
        full = ""
        try:
            set_current_session(req.session_id)
            rag_ctx = knowledge_store.search_with_context(req.message, top_k=3)
            msg = f"{req.message}\n\n{rag_ctx}" if rag_ctx else req.message
            for chunk in assistant.stream_chat(msg, req.session_id):
                full += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            _save_chat(req.session_id, req.message, full)
            yield f"data: {json.dumps({'type': 'done', 'content': full}, ensure_ascii=False)}\n\n"
        except RuntimeError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'服务器错误: {e}'}, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/api/chat")
async def chat(req: ChatRequest):
    set_current_session(req.session_id)
    try:
        rag_ctx = knowledge_store.search_with_context(req.message, top_k=3)
        msg = f"{req.message}\n\n{rag_ctx}" if rag_ctx else req.message
        reply = assistant.chat(msg, req.session_id)
        _save_chat(req.session_id, req.message, reply)
        return {"reply": reply}
    except RuntimeError as e:
        raise HTTPException(503, str(e))

def _save_chat(session_id, user_msg, reply):
    try:
        s = session_store.get_session(session_id)
        if not s:
            s = session_store.create_session(session_id)
        session_store.add_message(session_id, "user", user_msg)
        session_store.add_message(session_id, "assistant", reply)
        if s["message_count"] == 0:
            session_store.auto_title(session_id, user_msg)
    except Exception:
        pass

# ═══════════════════════════════════════════════
#  💬 会话管理
# ═══════════════════════════════════════════════

@app.get("/api/sessions")
def list_sessions():
    return {"sessions": session_store.list_sessions()}

@app.post("/api/sessions")
def create_session():
    return session_store.create_session()

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    if not session_store.delete_session(session_id):
        raise HTTPException(404, "会话不存在")
    return {"ok": True}

@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    return {"messages": session_store.get_messages(session_id)}

@app.put("/api/sessions/{session_id}")
def rename_session(session_id: str, title: str = Query(...)):
    s = session_store.update_session(session_id, title)
    if not s:
        raise HTTPException(404, "会话不存在")
    return s

# ═══════════════════════════════════════════════
#  📁 文件上传
# ═══════════════════════════════════════════════

UPLOAD_DIR = os.path.join(ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
TEXT_EXTS = {".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".json",
             ".csv", ".yaml", ".yml", ".xml", ".html", ".css", ".sql", ".sh",
             ".java", ".c", ".cpp", ".h", ".rs", ".go", ".rb", ".php"}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "文件超过 10MB")

    ext = os.path.splitext(file.filename)[1].lower()
    text, file_type = "", "unknown"

    if ext in TEXT_EXTS or "text" in file.content_type or "":
        text = raw.decode("utf-8", errors="replace")
        file_type = "text"
    elif ext == ".pdf":
        try:
            import io, PyPDF2
            pdf = PyPDF2.PdfReader(io.BytesIO(raw))
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            file_type = "pdf"
        except ImportError:
            text = f"[PDF: {file.filename}]"
            file_type = "pdf_meta"
    else:
        text = f"[文件: {file.filename} ({(len(raw)//1024)}KB)]"

    text = text[:50000]
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{file.filename}")
    with open(path, "wb") as f:
        f.write(raw)

    return {"filename": file.filename, "size": len(raw), "type": file_type, "content": text, "saved_path": path}

# ═══════════════════════════════════════════════
#  📚 知识库 RAG
# ═══════════════════════════════════════════════

@app.get("/api/knowledge")
def list_knowledge():
    docs = knowledge_store.list_documents()
    return {"documents": docs, "stats": knowledge_store.stats()}

@app.post("/api/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "文件超过 10MB")

    ext = os.path.splitext(file.filename)[1].lower()
    text = ""
    if ext in TEXT_EXTS or "text" in (file.content_type or ""):
        text = raw.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        try:
            import io, PyPDF2
            pdf = PyPDF2.PdfReader(io.BytesIO(raw))
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            raise HTTPException(400, "PDF 解析不可用")
    else:
        raise HTTPException(400, f"不支持: {ext}")

    text = text[:100000]
    if len(text) < 20:
        raise HTTPException(400, "内容太少")

    doc = knowledge_store.add_document(file.filename, text)
    return {"ok": True, "document": doc}

@app.delete("/api/knowledge/{doc_id}")
def delete_knowledge(doc_id: str):
    if not knowledge_store.delete_document(doc_id):
        raise HTTPException(404, "文档不存在")
    return {"ok": True}

@app.get("/api/knowledge/query")
def query_knowledge(query: str = Query(...), top_k: int = Query(3)):
    return {"results": knowledge_store.search(query, top_k)}

# ═══════════════════════════════════════════════
#  🧠 记忆管理
# ═══════════════════════════════════════════════

@app.get("/api/memories")
def list_memories(memory_type: str = Query(None), limit: int = Query(50, le=200)):
    return {"memories": store.list_all(memory_type, limit)}

@app.get("/api/memories/search")
def search_memories(q: str = Query(...)):
    return {"results": store.search(q)}

@app.get("/api/memories/stats")
def memory_stats():
    return store.stats()

@app.get("/api/memories/{memory_id}")
def get_memory(memory_id: int):
    m = store.get(memory_id)
    if not m:
        raise HTTPException(404, "记忆不存在")
    return m

@app.post("/api/memories")
def add_memory(body: MemoryCreate):
    return store.add(body.content, body.memory_type, body.importance)

@app.put("/api/memories/{memory_id}")
def update_memory(memory_id: int, body: MemoryUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    m = store.update(memory_id, **updates)
    if not m:
        raise HTTPException(404, "记忆不存在")
    return m

@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    if not store.delete(memory_id):
        raise HTTPException(404, "记忆不存在")
    return {"ok": True}

# ═══════════════════════════════════════════════
#  🌤️ 天气 & ⚙️ 系统
# ═══════════════════════════════════════════════

@app.get("/api/weather")
def weather(location: str = Query(...)):
    return {"result": query_weather.invoke({"location": location})}

@app.get("/api/status")
def system_status():
    return {
        "ready": assistant.ready, "provider": assistant.provider,
        "model": assistant.model_name, "memory_stats": store.stats(),
        "sessions": len(session_store.list_sessions()),
        "knowledge": knowledge_store.stats(),
    }

@app.post("/api/model/switch")
def switch_model(provider: str = Query(...), model: Optional[str] = None):
    return {"tip": f"修改 .env 中 LLM_PROVIDER={provider} 后重启", "current": {"provider": assistant.provider, "model": assistant.model_name}}

# ═══════════════════════════════════════════════
#  🌐 前端
# ═══════════════════════════════════════════════

static_dir = os.path.join(ROOT, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

# ═══════════════════════════════════════════════
#  🚀 启动
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    s = "✅" if assistant.ready else "⚠️"
    print(f"🧠 AI 智能助理 v1.2 → http://localhost:8000")
    print(f"  {s} 模型: {assistant.provider}/{assistant.model_name}")
    print(f"  📚 RAG 知识库已启用")
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
