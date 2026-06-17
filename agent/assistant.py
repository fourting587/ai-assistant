"""
AI 智能助手 Agent 定义
基于 LangGraph 的 ReAct Agent，支持工具调用和对话记忆
"""
from typing import Optional
from datetime import datetime

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from config import Config

# ─── 系统提示词 ───────────────────────────────────


def _build_prompt() -> str:
    """生成含当前日期时间的系统提示词"""
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    return f"""你是一个拥有长期记忆和联网搜索能力的 AI 智能助理。

当前日期时间：{now}（北京时间）

## 🧠 记忆管理
你可以记住用户的信息（偏好、重要事实、任务等），并在需要时调用。
- 当用户告诉你个人信息时，主动记住它（add_memory）
- 当用户询问过去提到的事情时，先搜索记忆（search_memories）
- 可以随时查看、更新、删除记忆

## 🌤️ 天气
- query_weather：查询任意城市的实时天气

## 🔍 联网搜索
- web_search：搜索互联网获取最新信息
- 当遇到以下情况时，**必须使用** web_search：
  • 用户询问实时信息（新闻、股价、赛事比分等）
  • 你不知道的知识性问题（历史事件、人物、概念等）
  • 用户明确要求"搜索"或"查一下"
  • 你对某个信息不确定，需要验证
- 搜索后，基于搜索结果用自己的话总结回答

## 📋 行为准则
- 用中文回答用户
- 主动使用工具：不要只说"我会记住"，要实际调用 add_memory
- 如果用户问起过去的事但搜索不到，坦诚说"我还没记住这个"
- 重要信息用高 importance（7-10）存储
- 每次对话结束后，思考是否有需要记住的新信息
- 保持友好、专业
"""

# ─── LLM 工厂 ────────────────────────────────────


def _build_llm():
    """根据配置创建 LLM 实例，失败时返回 None"""
    provider = Config.LLM_PROVIDER

    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=Config.OPENAI_MODEL_NAME,
                temperature=0.7,
                api_key=Config.OPENAI_API_KEY,
            )
        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=Config.ANTHROPIC_MODEL_NAME,
                temperature=0.7,
                api_key=Config.ANTHROPIC_API_KEY,
            )
        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=Config.OLLAMA_MODEL,
                temperature=0.7,
                base_url=Config.OLLAMA_BASE_URL,
            )
        elif provider == "deepseek":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=Config.DEEPSEEK_MODEL_NAME,
                temperature=0.7,
                api_key=Config.DEEPSEEK_API_KEY,
                base_url=Config.DEEPSEEK_BASE_URL,
            )
        else:
            print(f"❌ 未知 LLM 提供商: {provider}")
            return None
    except Exception as e:
        print(f"❌ LLM 初始化失败 ({provider}): {e}")
        return None


def _build_dummy_llm():
    """当没有可用 LLM 时，返回一个抛出清晰错误的占位对象"""
    return None


# ─── Agent 构建 ───────────────────────────────────


class Assistant:
    """AI 智能助手"""

    def __init__(self, tools: list):
        self.tools = tools
        self.llm = _build_llm()
        self.ready = self.llm is not None

        if self.ready:
            self.memory = MemorySaver()
            self.agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
                prompt=_build_prompt(),
                checkpointer=self.memory,
            )
        else:
            self.memory = None
            self.agent = None

    @property
    def provider(self) -> str:
        return Config.LLM_PROVIDER if self.ready else "未配置"

    @property
    def model_name(self) -> str:
        if not self.ready:
            return "请设置 API Key"
        provider = Config.LLM_PROVIDER
        if provider == "openai":
            return Config.OPENAI_MODEL_NAME
        elif provider == "anthropic":
            return Config.ANTHROPIC_MODEL_NAME
        elif provider == "ollama":
            return Config.OLLAMA_MODEL
        elif provider == "deepseek":
            return Config.DEEPSEEK_MODEL_NAME
        return "未知"

    def _check_ready(self):
        if not self.ready:
            raise RuntimeError(
                "❌ AI 模型未配置。请按以下步骤设置：\n"
                "1. 在项目目录创建 .env 文件\n"
                "2. 填入 API Key（参考 .env.example）\n"
                "3. 重启后端服务\n\n"
                "或者安装 Ollama 本地运行：ollama pull qwen2.5"
            )

    def chat(self, message: str, thread_id: str = "default") -> str:
        """发送一条消息，返回完整响应文本"""
        self._check_ready()
        result = self.agent.invoke(
            {"messages": [("human", message)]},
            config={"configurable": {"thread_id": thread_id}},
        )
        for msg in reversed(result["messages"]):
            if msg.type == "ai":
                return msg.content
        return "（无响应）"

    def stream_chat(self, message: str, thread_id: str = "default"):
        """流式对话，逐 token yield 文本（打字机效果）"""
        self._check_ready()
        try:
            # 方式一：逐 token 流式（messages mode）
            for event, metadata in self.agent.stream(
                {"messages": [("human", message)]},
                config={"configurable": {"thread_id": thread_id}},
                stream_mode="messages",
            ):
                # 只产出 AI 文本 token，跳过工具调用等非文本事件
                if (
                    hasattr(event, "content")
                    and event.content
                    and getattr(event, "type", "") in ("ai", "AIMessageChunk")
                ):
                    yield event.content
        except Exception:
            # 方式二：降级到按步骤流式（values mode）
            full_text = ""
            for step in self.agent.stream(
                {"messages": [("human", message)]},
                config={"configurable": {"thread_id": thread_id}},
                stream_mode="values",
            ):
                msg = step["messages"][-1]
                if msg.type == "ai" and msg.content:
                    new = msg.content[len(full_text):]
                    if new:
                        yield new
                    full_text = msg.content
