#!/usr/bin/env python3
"""
AI 智能助理 — FastAPI 后端
提供 REST API + SSE 流式对话 + 会话管理 + 文件上传
"""
import sys
import os
import json
import uuid
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
from memory.store import MemoryStore
from session_store import SessionStore
from tools.memory_tools import get_memory_tools
from tools.weather_tools import query_weather
from tools.search_tools import web_search
from agent.assistant import Assistant

# ── 初始化 ──
store = MemoryStore(Config.DB_PATH)
session_store = SessionStore()
tools = get_memory_tools(store) + [query_weather, web_search]
assistant = Assistant(tools)

# ── FastAPI ──
app = FastAPI(title="🧠 AI 智能助理", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── 数据模型 ──

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    session_id: str = Field("default", description="会话 ID")

class MemoryCreate(BaseModel):
    content: str
    memory_type: str = "general"
    importance: int = 5

class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    memory_type: Optional[str] = None
    importance: Optional[int] = Field(None, ge=1, le=10)

# ═══════════════════════════════════════════════
#  📝 对话（支持会话管理）
# ═══════════════════════════════════════════════

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        reply = assistant.chat(req.message, req.session_id)
        _save_chat(req.session_id, req.message, reply)
        return {"reply": reply}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_stream():
        full = ""
        try:
            for chunk in assistant.stream_chat(req.message, req.session_id):
                full += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            _save_chat(req.session_id, req.message, full)
            yield f"data: {json.dumps({'type': 'done', 'content': full}, ensure_ascii=False)}\n\n"
        except RuntimeError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'服务器错误: {e}'}, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _save_chat(session_id: str, user_msg: str, assistant_reply: str):
    """持久化保存对话到 SQLite"""
    try:
        # 自动创建会话（如果是新会话）
        sess = session_store.get_session(session_id)
        if not sess:
            sess = session_store.create_session(session_id)
        # 保存消息
        session_store.add_message(session_id, "user", user_msg)
        session_store.add_message(session_id, "assistant", assistant_reply)
        # 首次消息自动命名
        if sess["message_count"] == 0:
            session_store.auto_title(session_id, user_msg)
    except Exception:
        pass  # 保存失败不影响主流程


# ═══════════════════════════════════════════════
#  💬 会话管理
# ═══════════════════════════════════════════════

@app.get("/api/sessions")
def list_sessions():
    """获取所有会话"""
    return {"sessions": session_store.list_sessions()}


@app.post("/api/sessions")
def create_session():
    """创建新会话"""
    sess = session_store.create_session()
    return sess


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """删除会话"""
    ok = session_store.delete_session(session_id)
    if not ok:
        raise HTTPException(404, "会话不存在")
    return {"ok": True}


@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    """获取会话消息历史"""
    messages = session_store.get_messages(session_id)
    return {"messages": messages}


@app.put("/api/sessions/{session_id}")
def rename_session(session_id: str, title: str = Query(...)):
    """重命名会话"""
    sess = session_store.update_session(session_id, title)
    if not sess:
        raise HTTPException(404, "会话不存在")
    return sess


# ═══════════════════════════════════════════════
#  📁 文件上传
# ═══════════════════════════════════════════════

UPLOAD_DIR = os.path.join(ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 支持提取文本的文件类型
TEXT_EXTENSIONS = {".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
                   ".json", ".csv", ".yaml", ".yml", ".xml", ".html", ".css",
                   ".sql", ".sh", ".java", ".c", ".cpp", ".h", ".rs", ".go",
                   ".rb", ".php", ".swift", ".kt", ".scala", ".r", ".pl"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件并提取文本内容"""
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    ext = os.path.splitext(file.filename)[1].lower()
    content_type = file.content_type or ""

    # 读取文件内容
    raw = await file.read()
    size = len(raw)

    if size > 10 * 1024 * 1024:
        raise HTTPException(413, "文件超过 10MB 限制")

    # 提取文本
    text_content = ""
    file_type = "unknown"

    if ext in TEXT_EXTENSIONS or "text" in content_type:
        text_content = raw.decode("utf-8", errors="replace")
        file_type = "text"
    elif ext == ".pdf":
        try:
            import io
            import PyPDF2
            pdf = PyPDF2.PdfReader(io.BytesIO(raw))
            text_content = "\n".join(page.extract_text() or "" for page in pdf.pages)
            file_type = "pdf"
        except ImportError:
            text_content = f"[PDF 文件: {file.filename}，请安装 PyPDF2 以提取内容]"
            file_type = "pdf_meta"
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"):
        file_type = "image"
        text_content = f"[图片文件: {file.filename} ({size//1024}KB)]"
    else:
        text_content = f"[文件: {file.filename} ({size//1024}KB, {ext})]"

    # 截断过长内容
    if len(text_content) > 50000:
        text_content = text_content[:50000] + "\n\n[...内容过长已截断]"

    # 保存到本地（可选）
    save_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{file.filename}")
    with open(save_path, "wb") as f:
        f.write(raw)

    return {
        "filename": file.filename,
        "size": size,
        "type": file_type,
        "content": text_content,
        "saved_path": save_path,
    }


# ═══════════════════════════════════════════════
#  🧠 记忆管理
# ═══════════════════════════════════════════════

@app.get("/api/memories")
def list_memories(memory_type: Optional[str] = Query(None), limit: int = Query(50, le=200)):
    return {"memories": store.list_all(memory_type, limit)}

@app.get("/api/memories/search")
def search_memories(q: str = Query(...)):
    return {"results": store.search(q)}

@app.get("/api/memories/stats")
def memory_stats():
    return store.stats()

@app.get("/api/memories/{memory_id}")
def get_memory(memory_id: int):
    mem = store.get(memory_id)
    if not mem:
        raise HTTPException(404, "记忆不存在")
    return mem

@app.post("/api/memories")
def add_memory(body: MemoryCreate):
    return store.add(body.content, body.memory_type, body.importance)

@app.put("/api/memories/{memory_id}")
def update_memory(memory_id: int, body: MemoryUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    mem = store.update(memory_id, **updates)
    if not mem:
        raise HTTPException(404, "记忆不存在")
    return mem

@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    ok = store.delete(memory_id)
    if not ok:
        raise HTTPException(404, "记忆不存在")
    return {"ok": True}

# ═══════════════════════════════════════════════
#  🌤️ 天气 & 🔍 搜索
# ═══════════════════════════════════════════════

@app.get("/api/weather")
def weather(location: str = Query(...)):
    result = query_weather.invoke({"location": location})
    return {"result": result}

# ═══════════════════════════════════════════════
#  ⚙️ 系统
# ═══════════════════════════════════════════════

@app.get("/api/status")
def system_status():
    return {
        "ready": assistant.ready,
        "provider": assistant.provider,
        "model": assistant.model_name,
        "memory_stats": store.stats(),
        "sessions": len(session_store.list_sessions()),
    }

@app.post("/api/model/switch")
def switch_model(provider: str = Query(...), model: Optional[str] = None):
    return {
        "tip": f"请在 .env 中将 LLM_PROVIDER 改为 {provider}，然后重启服务",
        "current": {"provider": assistant.provider, "model": assistant.model_name},
    }

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
    status = "✅" if assistant.ready else "⚠️"
    print(f"🧠 AI 智能助理 v1.1 → http://localhost:8000")
    print(f"  {status} 模型: {assistant.provider}/{assistant.model_name}")
    print(f"  💾 记忆库: {os.path.abspath(Config.DB_PATH)}")
    print(f"  💬 会话管理 + 📁 文件上传 已启用")
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
