"""
配置管理模块
支持 OpenAI / Anthropic / Ollama / DeepSeek 四种 LLM 提供商
"""
import os
import time
from dotenv import load_dotenv

load_dotenv()

# 应用时区设置
_tz = os.getenv("TZ")
if _tz:
    os.environ["TZ"] = _tz
    try:
        time.tzset()
    except AttributeError:
        pass  # Windows 不支持 tzset


class Config:
    # LLM 提供商选择
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

    # Anthropic Claude
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL_NAME = os.getenv("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-20250514")

    # Ollama
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    # DeepSeek（兼容 OpenAI API）
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # 数据库
    DB_PATH = os.getenv("DB_PATH", "data/memories.db")

    @classmethod
    def validate(cls):
        """检查必要的配置是否存在"""
        if cls.LLM_PROVIDER == "openai" and not cls.OPENAI_API_KEY:
            print("⚠️  未设置 OPENAI_API_KEY，将尝试使用 Ollama 本地模型")
            return cls._check_ollama()
        elif cls.LLM_PROVIDER == "anthropic" and not cls.ANTHROPIC_API_KEY:
            print("⚠️  未设置 ANTHROPIC_API_KEY，将尝试使用 Ollama 本地模型")
            return cls._check_ollama()
        elif cls.LLM_PROVIDER == "deepseek" and not cls.DEEPSEEK_API_KEY:
            print("⚠️  未设置 DEEPSEEK_API_KEY，将尝试使用 Ollama 本地模型")
            return cls._check_ollama()
        return True

    @classmethod
    def _check_ollama(cls):
        import requests
        try:
            resp = requests.get(f"{cls.OLLAMA_BASE_URL}/api/tags", timeout=3)
            if resp.status_code == 200:
                cls.LLM_PROVIDER = "ollama"
                print(f"✅ 已切换到 Ollama 本地模型: {cls.OLLAMA_MODEL}")
                return True
        except Exception:
            pass
        print("❌ 无法连接到任何 LLM 服务。请设置 API_KEY 或启动 Ollama。")
        return False
