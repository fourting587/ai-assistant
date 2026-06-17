"""AI 智能助手 Agent——LangGraph ReAct Agent + 多模型支持"""
from typing import Optional, Generator
from datetime import datetime

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from config import Config


def _build_prompt() -> str:
    """生成含当前日期的系统提示词"""
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
- 遇到实时信息、不知道的知识、用户要求搜索时，**必须使用** web_search

## 📋 行为准则
- 用中文回答用户
- 主动使用工具，不要只嘴上说
- 重要信息用高 importance（7-10）存储
- 保持友好、专业
"""


def _build_llm():
    """创建 LLM 实例，失败返回 None"""
    provider = Config.LLM_PROVIDER
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=Config.OPENAI_MODEL_NAME, temperature=0.7, api_key=Config.OPENAI_API_KEY)
        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=Config.ANTHROPIC_MODEL_NAME, temperature=0.7, api_key=Config.ANTHROPIC_API_KEY)
        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(model=Config.OLLAMA_MODEL, temperature=0.7, base_url=Config.OLLAMA_BASE_URL)
        elif provider == "deepseek":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=Config.DEEPSEEK_MODEL_NAME, temperature=0.7,
                              api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_BASE_URL)
        else:
            print(f"❌ 未知 LLM 提供商: {provider}")
            return None
    except Exception as e:
        print(f"❌ LLM 初始化失败 ({provider}): {e}")
        return None


class Assistant:
    """AI 智能助手"""

    def __init__(self, tools: list) -> None:
        self.tools = tools
        self.llm = _build_llm()
        self.ready: bool = self.llm is not None

        if self.ready:
            self.memory = MemorySaver()
            self.agent = create_react_agent(
                model=self.llm, tools=self.tools,
                prompt=_build_prompt(), checkpointer=self.memory,
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
        m = {"openai": Config.OPENAI_MODEL_NAME, "anthropic": Config.ANTHROPIC_MODEL_NAME,
             "ollama": Config.OLLAMA_MODEL, "deepseek": Config.DEEPSEEK_MODEL_NAME}
        return m.get(Config.LLM_PROVIDER, "未知")

    def _check_ready(self) -> None:
        if not self.ready:
            raise RuntimeError("AI 模型未配置。请在 .env 中设置 API Key 后重启。")

    def chat(self, message: str, thread_id: str = "default") -> str:
        """非流式对话"""
        self._check_ready()
        result = self.agent.invoke(
            {"messages": [("human", message)]},
            config={"configurable": {"thread_id": thread_id}},
        )
        for msg in reversed(result["messages"]):
            if msg.type == "ai":
                return msg.content
        return "（无响应）"

    def stream_chat(self, message: str, thread_id: str = "default") -> Generator[str, None, None]:
        """流式对话，逐 token 产出"""
        self._check_ready()
        try:
            for event, meta in self.agent.stream(
                {"messages": [("human", message)]},
                config={"configurable": {"thread_id": thread_id}},
                stream_mode="messages",
            ):
                if getattr(event, "content", None) and getattr(event, "type", "") in ("ai", "AIMessageChunk"):
                    yield event.content
        except Exception:
            full = ""
            for step in self.agent.stream(
                {"messages": [("human", message)]},
                config={"configurable": {"thread_id": thread_id}},
                stream_mode="values",
            ):
                msg = step["messages"][-1]
                if msg.type == "ai" and msg.content:
                    new = msg.content[len(full):]
                    if new:
                        yield new
                    full = msg.content
