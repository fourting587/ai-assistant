#!/usr/bin/env python3
"""
AI 智能助理 - 带长期记忆的 LangChain 应用
支持：记忆增删改查、天气查询、自然语言对话
"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from memory.store import MemoryStore
from tools.memory_tools import get_memory_tools
from tools.weather_tools import query_weather
from agent.assistant import Assistant


BANNER = r"""
╔══════════════════════════════════════════╗
║        🧠 AI 智能助理 v1.0              ║
║    带长期记忆 · 工具调用 · 自然语言      ║
╚══════════════════════════════════════════╝
"""

HELP_TEXT = """
📖 可用命令：
  /help      - 显示此帮助
  /memory    - 查看所有记忆
  /stats     - 记忆统计信息
  /clear     - 清屏
  /exit      - 退出

💡 试试说：
  • "记住我喜欢喝咖啡"
  • "我今年 22 岁，正在找实习"
  • "今天北京天气怎么样？"
  • "我记得什么关于我的信息？"
  • "把那个喜好改成喝茶"
  • "帮我看看都有什么记忆"
"""


def print_stream(assistant: Assistant, message: str, thread_id: str):
    """流式输出"""
    print(f"\n  🤖 助理: ", end="", flush=True)
    for chunk in assistant.stream_chat(message, thread_id):
        print(chunk, end="", flush=True)
    print()


def main():
    # ── 启动 ──────────────────────────────────
    os.system("clear" if os.name == "posix" else "cls")
    print(BANNER)

    if not Config.validate():
        sys.exit(1)

    # ── 初始化 ─────────────────────────────────
    store = MemoryStore(Config.DB_PATH)
    tools = get_memory_tools(store) + [query_weather]
    assistant = Assistant(tools)

    print(f"  🚀 模型: {assistant.provider} / {assistant.model_name}")
    print(f"  💾 记忆库: {os.path.abspath(Config.DB_PATH)}")
    print(HELP_TEXT)

    thread_id = "default"

    # ── 对话循环 ─────────────────────────────
    while True:
        try:
            user_input = input("\n  🧑 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  👋 再见！")
            break

        if not user_input:
            continue

        # ── 特殊命令 ──────────────────────────
        if user_input.startswith("/"):
            cmd = user_input[1:].lower()

            if cmd in ("exit", "quit", "再见", "退出"):
                print("\n  👋 再见！")
                break

            elif cmd in ("help", "帮助"):
                print(HELP_TEXT)

            elif cmd in ("memory", "记忆"):
                memories = store.list_all()
                if not memories:
                    print("\n  📭 还没有任何记忆")
                else:
                    print(f"\n  📝 共有 {len(memories)} 条记忆：\n")
                    for m in memories:
                        print(
                            f"     [#{m['id']}] [{m['memory_type']}] "
                            f"(★{m['importance']}) {m['content'][:100]}"
                        )

            elif cmd in ("stats", "统计"):
                stats = store.stats()
                print(f"\n  📊 记忆统计")
                print(f"     总计: {stats['total']} 条")
                for t, c in stats['by_type'].items():
                    print(f"     {t}: {c} 条")
                print(f"     平均重要性: {stats['avg_importance']}/10")

            elif cmd == "clear":
                os.system("clear" if os.name == "posix" else "cls")

            else:
                print(f"\n  ❌ 未知命令: /{cmd}，输入 /help 查看帮助")
            continue

        # ── 对话 ──────────────────────────────
        print_stream(assistant, user_input, thread_id)


if __name__ == "__main__":
    main()
