"""
配置管理模块
支持 OpenAI / Anthropic / Ollama / DeepSeek 四种 LLM 提供商
启动时校验必填配置项
"""
import os
import time
import sys
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# 应用时区设置
_tz = os.getenv("TZ")
if _tz:
    os.environ["TZ"] = _tz
    try:
        time.tzset()
    except AttributeError:
        pass


class Config:
    # LLM 提供商
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL_NAME: str = os.getenv("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-20250514")

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL_NAME: str = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # Database
    DB_PATH: str = os.getenv("DB_PATH", "data/memories.db")

    # 需要 API Key 的提供商列表
    _API_KEY_CONFIGS: dict[str, tuple[str, str, str]] = {
        "openai": ("OPENAI_API_KEY", "OPENAI_API_KEY", "OpenAI"),
        "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "Anthropic"),
        "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", "DeepSeek"),
    }

    @classmethod
    def validate(cls) -> bool:
        """检查配置，缺失 API Key 时尝试 fallback 到 Ollama"""
        if cls.LLM_PROVIDER in cls._API_KEY_CONFIGS:
            _, env_key, name = cls._API_KEY_CONFIGS[cls.LLM_PROVIDER]
            api_key = getattr(cls, env_key, "")
            if not api_key:
                print(f"⚠️  未设置 {env_key}，将尝试使用 Ollama 本地模型")
                return cls._check_ollama()
        return True

    @classmethod
    def _check_ollama(cls) -> bool:
        """检查 Ollama 是否可用"""
        import requests
        try:
            resp = requests.get(f"{cls.OLLAMA_BASE_URL}/api/tags", timeout=3)
            if resp.status_code == 200:
                cls.LLM_PROVIDER = "ollama"
                print(f"✅ 已切换到 Ollama 本地模型: {cls.OLLAMA_MODEL}")
                return True
        except requests.RequestException:
            pass
        print(f"❌ 无法连接到 LLM 服务。请在 .env 中设置 API Key 或启动 Ollama。")
        return False

    @classmethod
    def validate_strict(cls) -> None:
        """严格校验——启动时调用，失败则退出"""
        if not cls.validate():
            print("\n💡 快速开始: cp .env.example .env 然后编辑 .env 填入 API Key")
            sys.exit(1)
