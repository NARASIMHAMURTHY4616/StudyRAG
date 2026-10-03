"""MongoDB connection and lifecycle manager for StudyRAG V2."""

import logging
from typing import Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import settings

logger = logging.getLogger(__name__)


class MongoDBManager:
    """
    Manages MongoDB connection with robust fallback and health detection.
    If MongoDB is unreachable, persistent history is gracefully disabled while
    keeping the core offline RAG engine fully operational.
    """

    _instance: Optional["MongoDBManager"] = None

    def __init__(
        self,
        uri: str = settings.MONGO_URI,
        db_name: str = settings.MONGO_DB,
        timeout_ms: int = 2000,
    ):
        self.uri = uri
        self.db_name = db_name
        self.timeout_ms = timeout_ms
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._is_connected = False
        self.connect()

    @classmethod
    def get_instance(cls) -> "MongoDBManager":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = MongoDBManager()
        return cls._instance

    def connect(self) -> bool:
        """Attempt connection to MongoDB."""
        try:
            self._client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=self.timeout_ms,
                connectTimeoutMS=self.timeout_ms,
            )
            # Trigger quick server ping
            self._client.admin.command("ping")
            self._db = self._client[self.db_name]
            self._is_connected = True
            self._ensure_indexes()
            logger.info(f"Connected to MongoDB at '{self.uri}' (Database: '{self.db_name}')")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            self._is_connected = False
            self._client = None
            self._db = None
            logger.warning(
                f"MongoDB connection failed ({e}). Running in offline volatile mode: "
                "Chat history persistence disabled, core RAG remains available."
            )
            return False
        except Exception as e:
            self._is_connected = False
            self._client = None
            self._db = None
            logger.error(f"Unexpected MongoDB initialization error: {e}")
            return False

    def _ensure_indexes(self) -> None:
        """Create indexes for performance."""
        if not self._is_connected or self._db is None:
            return
        try:
            conv_col = self._db["conversations"]
            conv_col.create_index("conversation_id", unique=True)
            conv_col.create_index([("updated_at", -1)])
        except Exception as e:
            logger.warning(f"Could not create MongoDB indexes: {e}")

    @property
    def is_available(self) -> bool:
        """Check if MongoDB is actively reachable."""
        if not self._is_connected or self._client is None:
            # Try to reconnect once if previous attempt failed
            return self.connect()
        try:
            self._client.admin.command("ping")
            return True
        except Exception:
            self._is_connected = False
            return False

    @property
    def db(self) -> Optional[Database]:
        """Return the database handle if connected."""
        if self.is_available:
            return self._db
        return None

    def get_collection(self, name: str) -> Optional[Collection]:
        """Get a collection handle if connected."""
        db = self.db
        if db is not None:
            return db[name]
        return None

    def close(self) -> None:
        """Close connection cleanly."""
        if self._client:
            self._client.close()
            self._is_connected = False
