import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from memory.store import MemoryStore
from session_store import SessionStore


@pytest.fixture
def tmp_db():
    """提供临时数据库路径并在测试后清理"""
    path = tempfile.mktemp(suffix=".db")
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def memory_store(tmp_db):
    """记忆存储实例"""
    return MemoryStore(tmp_db)


@pytest.fixture
def session_store(tmp_db):
    """会话存储实例"""
    # SessionStore 默认用 data/sessions.db，这里覆盖 db_path
    store = SessionStore.__new__(SessionStore)
    store.db_path = tmp_db
    store._init_db()
    return store
