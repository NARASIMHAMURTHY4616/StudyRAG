"""StudyRAG Configuration Settings."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of Project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if present
load_dotenv(BASE_DIR / ".env")

# Offline Environment Setup (prevent HuggingFace hub network checks and retries)
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "true").lower() in ("true", "1", "yes")
if OFFLINE_MODE:
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"

# Ollama LLM Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "15m")
OLLAMA_THINK = os.getenv("OLLAMA_THINK", "false").lower() in ("true", "1", "yes")
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "512"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

# Embedding Model Configuration
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

# Retrieval Configuration (Default V2 performance: TOP_K=4)
TOP_K = int(os.getenv("TOP_K", "4"))
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.25"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "8000"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "4"))

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "studyrag")

# Page-aware Chunking Configuration
TARGET_CHUNKS_PER_PAGE = int(os.getenv("TARGET_CHUNKS_PER_PAGE", "3"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "700"))

# Visual Learning Engine Configuration (V2.2)
VISUAL_LEARNING_ENABLED = os.getenv("VISUAL_LEARNING_ENABLED", "true").lower() in ("true", "1", "yes")
VISUAL_IMAGE_GENERATION_ENABLED = os.getenv("VISUAL_IMAGE_GENERATION_ENABLED", "false").lower() in ("true", "1", "yes")
GENERATED_VISUALS_DIR = BASE_DIR / os.getenv("GENERATED_VISUALS_DIR", "data/generated_visuals")
VISUAL_MAX_PROMPT_LENGTH = int(os.getenv("VISUAL_MAX_PROMPT_LENGTH", "1000"))
VISUAL_MAX_OUTPUT_TOKENS = int(os.getenv("VISUAL_MAX_OUTPUT_TOKENS", "1024"))
VISUAL_ALLOWED_FORMATS = os.getenv("VISUAL_ALLOWED_FORMATS", "svg,mermaid,json,png").split(",")
MERMAID_ASSET_PATH = os.getenv("MERMAID_ASSET_PATH", "/static/vendor/mermaid/mermaid.min.js")
IMAGE_GENERATION_BACKEND = os.getenv("IMAGE_GENERATION_BACKEND", "none").lower()

# Storage Directories
DOCUMENT_DIR = BASE_DIR / os.getenv("DOCUMENT_DIR", "data/documents")
CHUNK_DIR = BASE_DIR / os.getenv("CHUNK_DIR", "data/chunks")
EMBEDDING_DIR = BASE_DIR / os.getenv("EMBEDDING_DIR", "data/embeddings")
VECTOR_DB_DIR = BASE_DIR / os.getenv("VECTOR_DB_DIR", "data/vector_db")

# Vector DB File Paths
VECTOR_INDEX_FILE = VECTOR_DB_DIR / "faiss_index.bin"
METADATA_FILE = VECTOR_DB_DIR / "chunks_metadata.json"
INDEXED_REGISTRY_FILE = VECTOR_DB_DIR / "indexed_documents.json"

# Server & Diagnostic Configuration
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
DEBUG_RAG = os.getenv("DEBUG_RAG", "false").lower() in ("true", "1", "yes")
DEBUG_PERFORMANCE = os.getenv("DEBUG_PERFORMANCE", "true").lower() in ("true", "1", "yes")

# Auto-create all required data directories
def ensure_directories():
    """Ensure all runtime directories exist."""
    for directory in [DOCUMENT_DIR, CHUNK_DIR, EMBEDDING_DIR, VECTOR_DB_DIR, GENERATED_VISUALS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

ensure_directories()

