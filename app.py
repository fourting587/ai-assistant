#!/usr/bin/env python3
"""
AI 智能助理 — FastAPI 后端
提供 REST API + SSE 流式对话 + 全栈前端
"""
import sys
import os
import json
from typing import Optional

# ── 项目根目录 ──
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import Config
from memory.store import MemoryStore
from tools.memory_tools import get_memory_tools
from tools.weather_tools import query_weather
from tools.search_tools import web_search
from agent.assistant import Assistant

# ── 初始化（即使无 API Key 也不会崩溃） ──
store = MemoryStore(Config.DB_PATH)
tools = get_memory_tools(store) + [query_weather, web_search]
assistant = Assistant(tools)

# ── FastAPI 应用 ──

app = FastAPI(
    title="🧠 AI 智能助理",
    description="带长期记忆的 AI 助手 — LangChain + FastAPI",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 数据模型 ──


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    thread_id: str = Field("default", description="对话会话 ID")


class MemoryCreate(BaseModel):
    content: str = Field(..., description="记忆内容")
    memory_type: str = Field("general", description="类型")
    importance: int = Field(5, ge=1, le=10, description="重要性 1-10")


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    memory_type: Optional[str] = None
    importance: Optional[int] = Field(None, ge=1, le=10)


# ═══════════════════════════════════════════════
#  📝 对话
# ═══════════════════════════════════════════════


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """非流式对话，返回完整回复"""
    try:
        reply = assistant.chat(req.message, req.thread_id)
        return {"reply": reply}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式对话，前端逐块接收打字机效果"""

    async def event_stream():
        try:
            full = ""
            for chunk in assistant.stream_chat(req.message, req.thread_id):
                full += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'content': full}, ensure_ascii=False)}\n\n"
        except RuntimeError as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'服务器错误: {e}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ═══════════════════════════════════════════════
#  🧠 记忆管理
# ═══════════════════════════════════════════════


@app.get("/api/memories")
def list_memories(
    memory_type: Optional[str] = Query(None, description="筛选类型"),
    limit: int = Query(50, le=200),
):
    """获取所有记忆列表"""
    return {"memories": store.list_all(memory_type, limit)}


@app.get("/api/memories/search")
def search_memories(q: str = Query(..., description="搜索关键词")):
    """搜索记忆"""
    return {"results": store.search(q)}


@app.get("/api/memories/stats")
def memory_stats():
    """记忆统计"""
    return store.stats()


@app.get("/api/memories/{memory_id}")
def get_memory(memory_id: int):
    """获取单条记忆"""
    mem = store.get(memory_id)
    if not mem:
        raise HTTPException(404, "记忆不存在")
    return mem


@app.post("/api/memories")
def add_memory(body: MemoryCreate):
    """添加新记忆"""
    mem = store.add(body.content, body.memory_type, body.importance)
    return mem


@app.put("/api/memories/{memory_id}")
def update_memory(memory_id: int, body: MemoryUpdate):
    """更新记忆"""
    updates = {}
    if body.content is not None:
        updates["content"] = body.content
    if body.memory_type is not None:
        updates["memory_type"] = body.memory_type
    if body.importance is not None:
        updates["importance"] = body.importance
    mem = store.update(memory_id, **updates)
    if not mem:
        raise HTTPException(404, "记忆不存在")
    return mem


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    """删除记忆"""
    ok = store.delete(memory_id)
    if not ok:
        raise HTTPException(404, "记忆不存在")
    return {"ok": True}


# ═══════════════════════════════════════════════
#  🌤️ 天气
# ═══════════════════════════════════════════════


@app.get("/api/weather")
def weather(location: str = Query(..., description="城市名")):
    """查询天气"""
    result = query_weather.invoke({"location": location})
    return {"result": result}


# ═══════════════════════════════════════════════
#  ⚙️ 系统
# ═══════════════════════════════════════════════


@app.get("/api/status")
def system_status():
    """系统状态"""
    return {
        "ready": assistant.ready,
        "provider": assistant.provider,
        "model": assistant.model_name,
        "memory_stats": store.stats(),
    }


@app.post("/api/model/switch")
def switch_model(provider: str = Query(...), model: Optional[str] = None):
    """切换模型（需要重启生效）"""
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
    model_info = f"{assistant.provider}/{assistant.model_name}"
    print(f"🧠 AI 智能助理后端 → http://localhost:8000")
    print(f"  {status} 模型: {model_info}")
    print(f"  💾 记忆库: {os.path.abspath(Config.DB_PATH)}")
    if not assistant.ready:
        print(f"  ⚡ 请编辑 .env 文件填入 API Key 后重启服务")
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
