"""
天气查询工具
使用 wttr.in（免费，无需 API Key）获取实时天气
"""
import requests
from langchain_core.tools import tool


@tool
def query_weather(location: str) -> str:
    """查询某个城市的实时天气。
    Args:
        location: 城市名称，如 "Beijing"、"Shanghai"、"Tokyo"
    Returns:
        该城市的天气信息
    """
    try:
        resp = requests.get(
            f"https://wttr.in/{location}?format=%l:+%C+%t+%h+%w",
            timeout=10,
            headers={"User-Agent": "curl/8.0"},
        )
        if resp.status_code == 200:
            return f"🌤️ {resp.text.strip()}"
        else:
            return f"查询失败：无法获取「{location}」的天气"

    except requests.exceptions.RequestException as e:
        return f"天气服务连接失败：{e}"
