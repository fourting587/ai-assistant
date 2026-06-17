# 🧠 AI 智能助理 — 带长期记忆的全栈应用

基于 **LangChain + LangGraph + FastAPI** 的 AI 助手，支持**长期记忆**（增删改查）、**天气查询** 和 **自然语言对话**，提供 REST API 和 Web 界面。

## 功能

| 功能 | 说明 |
|------|------|
| 🧠 **长期记忆** | 自动记住用户信息，支持增删改查和搜索 |
| 🌤️ **天气查询** | 查询任意城市实时天气（免费，无需 API Key） |
| 💬 **自然语言** | AI 自主决定何时调用工具，支持流式打字机效果 |
| 🔄 **对话记忆** | 同一会话内上下文连贯 |
| 🔌 **多模型** | OpenAI / Claude / Ollama 本地模型一键切换 |
| 🌐 **Web 界面** | 美观的聊天界面 + 记忆管理面板 |

## 快速开始

### 1. 安装

```bash
cd ai-assistant
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# OpenAI（推荐）
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here

# 或 Anthropic Claude
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key

# 或 Ollama 本地模型（免费）
# LLM_PROVIDER=ollama
# OLLAMA_MODEL=qwen2.5
```

### 3. 运行

```bash
# 启动 FastAPI 后端（自动提供 Web 界面）
python app.py
```

打开浏览器访问 **http://localhost:8000**

### 无需 API Key？

安装 [Ollama](https://ollama.com) 后拉取模型即可：
```bash
ollama pull qwen2.5
# .env 里设置 LLM_PROVIDER=ollama
python app.py
```

## Web 界面截图预览

```
┌─────────────────────────────────────────────────────────┐
│  ☰ 🧠 AI 智能助理     💾 3 条记忆    [GPT-4o-mini ▼] 🗑️│
├──────────────┬──────────────────────────────────────────┤
│ 🧠 记忆      │  👤 你                                   │
│ ──────────   │  记住我喜欢喝冰美式                       │
│ 🔍 搜索...   │                                          │
│              │  🧠 AI 助理                              │
│ [偏好] ★★★★  │  好的，我记住了！📝                       │
│  我喜欢喝冰美式│  你喜欢的饮料是冰美式                    │
│  ✏️  🗑️     │                                          │
│              │  👤 你                                   │
│ [用户信息] ★★│  今天北京天气怎么样？                      │
│  正在找实习   │                                          │
│  ✏️  🗑️     │  🧠 AI 助理                              │
│              │  🌤️ 北京: Sunny +30°C ...                │
│ [+ 添加...]  │                                          │
│ 3 条记忆     │  ▷ 输入消息...                    [➤]    │
└──────────────┴──────────────────────────────────────────┘
```

## API 文档

启动后端后访问 **http://localhost:8000/docs** 查看 Swagger 文档。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 非流式对话 |
| `/api/chat/stream` | POST | SSE 流式对话 |
| `/api/memories` | GET | 获取记忆列表 |
| `/api/memories` | POST | 添加记忆 |
| `/api/memories/search?q=` | GET | 搜索记忆 |
| `/api/memories/stats` | GET | 记忆统计 |
| `/api/memories/{id}` | GET | 获取单条记忆 |
| `/api/memories/{id}` | PUT | 更新记忆 |
| `/api/memories/{id}` | DELETE | 删除记忆 |
| `/api/weather?location=` | GET | 查询天气 |
| `/api/status` | GET | 系统状态 |
| `/api/model/switch` | POST | 切换模型 |

## 项目结构

```
ai-assistant/
├── app.py                    # FastAPI 后端入口
├── config.py                 # 多模型配置
├── main.py                   # CLI 入口（可选）
├── requirements.txt          # 依赖
├── .env.example              # 环境变量模板
├── memory/store.py           # SQLite 长期记忆存储
├── tools/memory_tools.py     # 记忆 CRUD LangChain 工具
├── tools/weather_tools.py    # 天气查询工具
├── agent/assistant.py        # LangGraph ReAct Agent
├── static/                   # Web 前端
│   ├── index.html            # 主页面
│   ├── style.css             # 样式
│   └── script.js             # 交互逻辑
└── README.md
```

## 技术栈

- **LangChain + LangGraph** — Agent 编排与工具调用
- **FastAPI** — REST API + SSE 流式传输
- **SQLite** — 长期记忆持久化
- **ReAct Agent** — 推理 + 工具调用
- **wttr.in** — 免费天气 API
- **Vanilla JS** — 零依赖前端
