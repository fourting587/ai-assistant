# 🧠 AI 智能助理 — 带长期记忆的全栈应用

[![CI](https://github.com/fourting587/ai-assistant/actions/workflows/test.yml/badge.svg)](https://github.com/fourting587/ai-assistant/actions/workflows/test.yml)

基于 **LangChain + LangGraph + FastAPI** 的 AI 助手，支持**长期记忆**（增删改查）、**天气查询** 和 **自然语言对话**，提供 REST API 和 Web 界面。

## 功能

| 功能 | 说明 |
|------|------|
| 🧠 **长期记忆** | 自动记住用户信息，支持增删改查和搜索 |
| 💬 **多会话管理** | 创建/切换/删除对话，历史持久化 |
| 🌤️ **天气查询** | 查询任意城市实时天气（免费，无需 API Key） |
| 🔍 **联网搜索** | Bing 搜索获取最新信息 |
| 📁 **文件上传** | 上传 TXT/PDF/代码等，AI 读取分析 |
| 💬 **流式输出** | 逐 token 打字机效果 |
| 🔌 **多模型** | DeepSeek / OpenAI / Claude / Ollama 一键切换 |
| 🌐 **Web 界面** | 美观的聊天界面 + 记忆/会话管理面板 |

## 🐳 Docker 一键部署（推荐）

```bash
# 1. 配置 API Key
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 2. 启动
docker compose up -d

# 3. 访问 http://localhost:8000
```

使用 Ollama 本地模型：
```bash
docker compose --profile local up -d
docker exec ollama ollama pull qwen2.5
# .env: LLM_PROVIDER=ollama
docker compose restart app
```

## 🚀 本地运行

### 1. 安装
```bash
cd ai-assistant
pip install -r requirements.txt
```

### 2. 配置
```bash
cp .env.example .env
# 编辑 .env 填入 API Key
```

### 3. 运行
```bash
python app.py
# 访问 http://localhost:8000
```

## 🧪 运行测试

```bash
python -m pytest tests/ -v
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
