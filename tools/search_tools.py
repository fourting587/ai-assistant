"""
智能搜索工具
使用 Bing 搜索引擎（在中国可访问，无需 API Key）获取最新信息
"""
import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """搜索互联网获取最新信息。当遇到不知道的问题、需要实时数据或最新消息时使用。
    Args:
        query: 搜索关键词（中文/英文均可）
        max_results: 返回结果数量，默认5条
    Returns:
        搜索结果列表（标题、链接、摘要）
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        }

        resp = requests.get(
            f"https://www.bing.com/search?q={query}&count={max_results}",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        results = soup.select(".b_algo")

        if not results:
            return f"未找到关于「{query}」的相关结果"

        lines = [f"🔍 关于「{query}」找到以下结果：\n"]
        for i, item in enumerate(results[:max_results], 1):
            title_el = item.select_one("h2 a")
            snippet_el = item.select_one(".b_caption p")
            link_el = title_el.get("href", "") if title_el else ""

            title = title_el.get_text(strip=True) if title_el else "无标题"
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            lines.append(f"  {i}. {title}")
            lines.append(f"     {link_el}")
            if snippet:
                lines.append(f"     {snippet[:200]}")
            lines.append("")

        return "\n".join(lines)

    except requests.exceptions.Timeout:
        return "⏱️ 搜索超时，请稍后重试"
    except requests.exceptions.RequestException as e:
        return f"❌ 搜索失败：{e}"
    except Exception as e:
        return f"❌ 搜索出错：{e}"
