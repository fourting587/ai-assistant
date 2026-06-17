"""会话存储测试"""


class TestSessionStore:
    def test_create_and_get(self, session_store):
        s = session_store.create_session()
        assert s["id"] is not None
        assert s["title"] == "新对话"
        assert s["message_count"] == 0

        g = session_store.get_session(s["id"])
        assert g["id"] == s["id"]

    def test_get_nonexistent(self, session_store):
        assert session_store.get_session("nonexistent") is None

    def test_list_sessions(self, session_store):
        s1 = session_store.create_session("对话一")
        s2 = session_store.create_session("对话二")
        sessions = session_store.list_sessions()
        assert len(sessions) >= 2

    def test_update_title(self, session_store):
        s = session_store.create_session()
        updated = session_store.update_session(s["id"], title="新标题")
        assert updated["title"] == "新标题"

    def test_delete(self, session_store):
        s = session_store.create_session()
        assert session_store.delete_session(s["id"]) is True
        assert session_store.get_session(s["id"]) is None

    def test_add_and_get_messages(self, session_store):
        s = session_store.create_session()
        session_store.add_message(s["id"], "user", "你好")
        session_store.add_message(s["id"], "assistant", "你好！有什么可以帮助你的吗？")

        msgs = session_store.get_messages(s["id"])
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "你好"
        assert msgs[1]["role"] == "assistant"
        assert "帮助" in msgs[1]["content"]

    def test_auto_title(self, session_store):
        s = session_store.create_session()
        session_store.auto_title(s["id"], "今天北京天气怎么样？")
        g = session_store.get_session(s["id"])
        assert g["title"] == "今天北京天气怎么样？"

    def test_auto_title_short(self, session_store):
        s = session_store.create_session()
        session_store.auto_title(s["id"], "嗨")
        g = session_store.get_session(s["id"])
        assert g["title"] == "新对话"  # 太短保持默认

    def test_delete_cascades_messages(self, session_store):
        s = session_store.create_session()
        session_store.add_message(s["id"], "user", "msg1")
        session_store.add_message(s["id"], "assistant", "msg2")
        session_store.delete_session(s["id"])
        msgs = session_store.get_messages(s["id"])
        assert len(msgs) == 0
