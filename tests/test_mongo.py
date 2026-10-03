"""Unit tests for database/mongo.py and database/conversations.py in StudyRAG V2."""

import pytest
from database.mongo import MongoDBManager
from database.conversations import ConversationManager, generate_title


def test_generate_title():
    assert generate_title("Explain deadlock in operating systems") == "Deadlock in operating systems"
    assert generate_title("What is TCP three-way handshake?") == "TCP three-way handshake?"
    assert generate_title("How does virtual memory paging work?") == "Virtual memory paging work?"
    assert generate_title("") == "New Chat"



def test_conversation_lifecycle_in_memory():
    """Test conversation operations with simulated offline Mongo (memory fallback)."""
    # Create manager with unreachable Mongo port
    fake_mongo = MongoDBManager(uri="mongodb://localhost:99999/", timeout_ms=100)
    assert not fake_mongo.is_available

    manager = ConversationManager(mongo_manager=fake_mongo)

    # 1. Create conversation
    conv_id = manager.create_conversation(title="Initial Title")
    assert conv_id is not None

    # 2. Append user message
    msg1 = manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="Explain CPU Scheduling in OS",
    )
    assert msg1["role"] == "user"
    assert msg1["content"] == "Explain CPU Scheduling in OS"

    # 3. Append assistant message
    sources = [{"document": "OS.pdf", "page": 24, "score": 0.85}]
    msg2 = manager.add_message(
        conversation_id=conv_id,
        role="assistant",
        content="CPU scheduling is the process of allocating CPU time...",
        sources=sources,
        metadata={"model": "qwen3:1.7b", "retrieved_chunks": 10},
    )
    assert msg2["role"] == "assistant"
    assert len(msg2["sources"]) == 1

    # 4. Get conversation
    conv = manager.get_conversation(conv_id)
    assert conv is not None
    assert len(conv["messages"]) == 2
    assert conv["messages"][0]["role"] == "user"
    assert conv["messages"][1]["role"] == "assistant"

    # 5. List conversations
    convs = manager.list_conversations()
    assert len(convs) >= 1
    assert convs[0]["conversation_id"] == conv_id

    # 6. Update title
    success = manager.update_title(conv_id, "Updated OS Thread")
    assert success is True
    assert manager.get_conversation(conv_id)["title"] == "Updated OS Thread"

    # 7. Delete conversation
    del_success = manager.delete_conversation(conv_id)
    assert del_success is True
    assert manager.get_conversation(conv_id) is None


def test_conversation_persistence_if_mongo_connected():
    """Test real MongoDB integration if local Mongo server is available."""
    real_mongo = MongoDBManager.get_instance()
    if not real_mongo.is_available:
        pytest.skip("MongoDB service not reachable on localhost:27017")

    manager = ConversationManager(mongo_manager=real_mongo)
    conv_id = manager.create_conversation(title="Test Pytest Conversation")

    manager.add_message(
        conversation_id=conv_id,
        role="user",
        content="Test Question for Pytest",
    )

    conv = manager.get_conversation(conv_id)
    assert conv is not None
    assert conv["title"] == "Test Pytest Conversation"
    assert len(conv["messages"]) == 1

    # Clean up test conversation
    manager.delete_conversation(conv_id)
