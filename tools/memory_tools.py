"""
记忆管理工具——将 MemoryStore 封装为 LangChain Tool
AI 助手通过这些工具实现对自己记忆的增删改查
"""
from langchain_core.tools import tool
from memory.store import MemoryStore


def get_memory_tools(store: MemoryStore) -> list:
    """工厂函数：注入 MemoryStore 实例，返回 LangChain Tool 列表"""

    @tool
    def add_memory(content: str, memory_type: str = "general",
                   importance: int = 5) -> str:
        """添加一条新记忆。
        Args:
            content: 记忆内容（如用户信息、偏好、重要事实）
            memory_type: 记忆类型 (general|user_info|preference|fact|task)
            importance: 重要程度 1-10（10=最重要）
        Returns:
            添加成功的确认信息
        """
        mem = store.add(content, memory_type, importance)
        return f"✅ 已记住（#{mem['id']}）：{content}"

    @tool
    def read_memory(memory_id: int) -> str:
        """根据 ID 读取一条记忆。
        Args:
            memory_id: 记忆的 ID 编号
        Returns:
            记忆的详细信息
        """
        mem = store.get(memory_id)
        if not mem:
            return f"❌ 未找到 ID 为 {memory_id} 的记忆"
        return (
            f"[#{mem['id']}] {mem['content']}\n"
            f"  类型: {mem['memory_type']} | "
            f"重要性: {mem['importance']}/10 | "
            f"创建: {mem['created_at'][:19]}"
        )

    @tool
    def update_memory(memory_id: int, content: str = None,
                      memory_type: str = None, importance: int = None) -> str:
        """更新一条已有的记忆。
        Args:
            memory_id: 要更新的记忆 ID
            content: 新的记忆内容（可选，不传则不修改）
            memory_type: 新的记忆类型（可选）
            importance: 新的重要程度 1-10（可选）
        Returns:
            更新后的记忆信息
        """
        result = store.update(memory_id, content, memory_type, importance)
        if not result:
            return f"❌ 未找到 ID 为 {memory_id} 的记忆"
        return f"✅ 已更新 #{memory_id}: {result['content']}"

    @tool
    def delete_memory(memory_id: int) -> str:
        """删除一条记忆。
        Args:
            memory_id: 要删除的记忆 ID
        Returns:
            操作结果
        """
        success = store.delete(memory_id)
        if not success:
            return f"❌ 未找到 ID 为 {memory_id} 的记忆"
        return f"🗑️ 已删除记忆 #{memory_id}"

    @tool
    def list_memories(memory_type: str = None, limit: int = 20) -> str:
        """列出所有记忆，可按类型筛选。
        Args:
            memory_type: 筛选类型（general|user_info|preference|fact|task），不传则列出全部
            limit: 返回条数上限
        Returns:
            记忆列表
        """
        memories = store.list_all(memory_type, limit)
        if not memories:
            return "📭 还没有任何记忆"

        lines = [f"📝 共有 {len(memories)} 条记忆：\n"]
        for m in memories:
            lines.append(
                f"  [#{m['id']}] [{m['memory_type']}] "
                f"(★{m['importance']}) {m['content'][:80]}"
            )
        return "\n".join(lines)

    @tool
    def search_memories(keyword: str) -> str:
        """搜索记忆内容中的关键词。
        Args:
            keyword: 要搜索的关键词
        Returns:
            匹配的记忆列表
        """
        results = store.search(keyword)
        if not results:
            return f"🔍 没有找到包含「{keyword}」的记忆"
        lines = [f"🔍 搜索「{keyword}」找到 {len(results)} 条结果：\n"]
        for m in results:
            lines.append(
                f"  [#{m['id']}] [{m['memory_type']}] "
                f"(★{m['importance']}) {m['content'][:80]}"
            )
        return "\n".join(lines)

    return [add_memory, read_memory, update_memory,
            delete_memory, list_memories, search_memories]
