"""记忆存储 CRUD 测试"""


class TestMemoryStore:
    def test_add_and_get(self, memory_store):
        m = memory_store.add("我喜欢喝冰美式", "preference", 8)
        assert m is not None
        assert m["content"] == "我喜欢喝冰美式"
        assert m["memory_type"] == "preference"
        assert m["importance"] == 8
        assert m["id"] > 0

        # get
        g = memory_store.get(m["id"])
        assert g["content"] == "我喜欢喝冰美式"

    def test_get_nonexistent(self, memory_store):
        assert memory_store.get(999) is None

    def test_update(self, memory_store):
        m = memory_store.add("旧内容", "general", 5)
        updated = memory_store.update(m["id"], content="新内容", importance=9)
        assert updated["content"] == "新内容"
        assert updated["importance"] == 9
        assert updated["memory_type"] == "general"

    def test_update_nonexistent(self, memory_store):
        assert memory_store.update(999, content="x") is None

    def test_delete(self, memory_store):
        m = memory_store.add("待删除", "general", 3)
        assert memory_store.delete(m["id"]) is True
        assert memory_store.get(m["id"]) is None

    def test_delete_nonexistent(self, memory_store):
        assert memory_store.delete(999) is False

    def test_list_all(self, memory_store):
        memory_store.add("A", "general", 5)
        memory_store.add("B", "user_info", 8)
        memory_store.add("C", "general", 3)
        all_m = memory_store.list_all()
        assert len(all_m) == 3

    def test_list_by_type(self, memory_store):
        memory_store.add("A", "general", 5)
        memory_store.add("B", "preference", 7)
        prefs = memory_store.list_all("preference")
        assert len(prefs) == 1
        assert prefs[0]["memory_type"] == "preference"

    def test_search(self, memory_store):
        memory_store.add("我喜欢喝咖啡", "preference", 6)
        memory_store.add("正在学 Python", "user_info", 8)
        results = memory_store.search("咖啡")
        assert len(results) == 1
        assert "咖啡" in results[0]["content"]

    def test_stats(self, memory_store):
        memory_store.add("A", "general", 5)
        memory_store.add("B", "preference", 9)
        s = memory_store.stats()
        assert s["total"] == 2
        assert s["by_type"]["general"] == 1
        assert s["by_type"]["preference"] == 1
        assert 6 <= s["avg_importance"] <= 8

    def test_list_ordering(self, memory_store):
        """默认按重要性降序"""
        m1 = memory_store.add("低", "general", 3)
        m2 = memory_store.add("高", "general", 10)
        all_m = memory_store.list_all()
        assert all_m[0]["importance"] >= all_m[1]["importance"]
