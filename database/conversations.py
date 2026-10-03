"""Conversation and Message management for StudyRAG V2."""

import re
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from database.mongo import MongoDBManager

logger = logging.getLogger(__name__)


def generate_title(first_prompt: str) -> str:
    """Generate a clean, readable conversation title from the first prompt."""
    if not first_prompt:
        return "New Chat"

    # Remove common conversational prefixes
    cleaned = re.sub(
        r"^(explain|what is|what are|describe|tell me about|how to|how does|summarize|can you explain)\s+",
        "",
        first_prompt.strip(),
        flags=re.IGNORECASE,
    ).strip()

    # Capitalize appropriately and trim length
    if not cleaned:
        cleaned = first_prompt.strip()

    title = cleaned.split("\n")[0][:45].strip()
    # Capitalize first letter of each word or sentence
    if title:
        title = title[0].upper() + title[1:]
    return title or "Study Session"


class ConversationManager:
    """
    Handles CRUD operations for conversation threads and messages.
    Uses MongoDB when available, and falls back to an in-memory session cache
    if MongoDB is disconnected.
    """

    def __init__(self, mongo_manager: Optional[MongoDBManager] = None):
        self.mongo = mongo_manager or MongoDBManager.get_instance()
        # In-memory volatile store when MongoDB is offline
        self._memory_store: Dict[str, Dict[str, Any]] = {}

    def create_conversation(
        self,
        conversation_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> str:
        """Create a new conversation document and return its ID."""
        conv_id = conversation_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conv_doc = {
            "conversation_id": conv_id,
            "title": title or "New Chat",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }

        col = self.mongo.get_collection("conversations")
        if col is not None:
            try:
                col.update_one(
                    {"conversation_id": conv_id},
                    {"$setOnInsert": conv_doc},
                    upsert=True,
                )
                return conv_id
            except Exception as e:
                logger.error(f"Error creating conversation in MongoDB: {e}")

        # Fallback to memory
        self._memory_store[conv_id] = conv_doc
        return conv_id

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full conversation details including messages."""
        col = self.mongo.get_collection("conversations")
        if col is not None:
            try:
                doc = col.find_one({"conversation_id": conversation_id}, {"_id": 0})
                if doc:
                    return doc
            except Exception as e:
                logger.error(f"Error fetching conversation from MongoDB: {e}")

        # Fallback to memory
        return self._memory_store.get(conversation_id)

    def list_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List all conversations sorted by updated_at descending.
        Returns lightweight summaries (excludes heavy chunk metadata).
        """
        results: List[Dict[str, Any]] = []
        col = self.mongo.get_collection("conversations")
        if col is not None:
            try:
                cursor = col.find(
                    {},
                    {
                        "_id": 0,
                        "conversation_id": 1,
                        "title": 1,
                        "created_at": 1,
                        "updated_at": 1,
                        "messages": {"$slice": -1},  # only last message for preview
                    },
                ).sort("updated_at", -1).limit(limit)

                for doc in cursor:
                    msgs = doc.get("messages", [])
                    preview = msgs[-1].get("content", "")[:60] if msgs else ""
                    results.append({
                        "conversation_id": doc["conversation_id"],
                        "title": doc.get("title", "Untitled Chat"),
                        "created_at": doc.get("created_at"),
                        "updated_at": doc.get("updated_at"),
                        "message_count": len(msgs),
                        "preview": preview,
                    })
                return results
            except Exception as e:
                logger.error(f"Error listing conversations from MongoDB: {e}")

        # Fallback to memory
        for conv_id, doc in sorted(
            self._memory_store.items(),
            key=lambda item: item[1].get("updated_at", ""),
            reverse=True,
        )[:limit]:
            msgs = doc.get("messages", [])
            preview = msgs[-1].get("content", "")[:60] if msgs else ""
            results.append({
                "conversation_id": conv_id,
                "title": doc.get("title", "Untitled Chat"),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "message_count": len(msgs),
                "preview": preview,
            })
        return results

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Append a message to a conversation thread.
        Automatically sets conversation title on the first user message if needed.
        """
        now = datetime.now(timezone.utc).isoformat()
        message_obj = {
            "role": role,
            "content": content,
            "timestamp": now,
            "sources": sources or [],
            "metadata": metadata or {},
        }

        col = self.mongo.get_collection("conversations")
        if col is not None:
            try:
                # Ensure conversation exists
                conv = col.find_one({"conversation_id": conversation_id})
                if not conv:
                    new_title = generate_title(content) if role == "user" else "New Chat"
                    self.create_conversation(conversation_id=conversation_id, title=new_title)
                    conv = {"messages": [], "title": new_title}
                elif role == "user" and conv.get("title") in ("New Chat", "Untitled Chat", "", None):
                    new_title = generate_title(content)
                    col.update_one(
                        {"conversation_id": conversation_id},
                        {"$set": {"title": new_title}},
                    )

                col.update_one(
                    {"conversation_id": conversation_id},
                    {
                        "$push": {"messages": message_obj},
                        "$set": {"updated_at": now},
                    },
                )
                return message_obj
            except Exception as e:
                logger.error(f"Error appending message to MongoDB: {e}")

        # Memory store fallback
        if conversation_id not in self._memory_store:
            new_title = generate_title(content) if role == "user" else "New Chat"
            self.create_conversation(conversation_id=conversation_id, title=new_title)

        doc = self._memory_store[conversation_id]
        if role == "user" and doc.get("title") in ("New Chat", "Untitled Chat", "", None):
            doc["title"] = generate_title(content)

        doc["messages"].append(message_obj)
        doc["updated_at"] = now
        return message_obj


    def update_title(self, conversation_id: str, new_title: str) -> bool:
        """Update conversation title."""
        title_clean = new_title.strip()
        if not title_clean:
            return False

        col = self.mongo.get_collection("conversations")
        if col is not None:
            try:
                res = col.update_one(
                    {"conversation_id": conversation_id},
                    {"$set": {"title": title_clean, "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                return res.matched_count > 0
            except Exception as e:
                logger.error(f"Error updating title in MongoDB: {e}")

        if conversation_id in self._memory_store:
            self._memory_store[conversation_id]["title"] = title_clean
            self._memory_store[conversation_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation thread."""
        col = self.mongo.get_collection("conversations")
        if col is not None:
            try:
                res = col.delete_one({"conversation_id": conversation_id})
                return res.deleted_count > 0
            except Exception as e:
                logger.error(f"Error deleting conversation from MongoDB: {e}")

        if conversation_id in self._memory_store:
            del self._memory_store[conversation_id]
            return True
        return False

    def clear_all(self) -> bool:
        """Clear all conversation history."""
        col = self.mongo.get_collection("conversations")
        if col is not None:
            try:
                col.delete_many({})
            except Exception as e:
                logger.error(f"Error clearing conversations from MongoDB: {e}")

        self._memory_store.clear()
        return True
