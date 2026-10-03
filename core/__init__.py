"""Core components for LLM client and prompt templates."""

from core.ollama_client import OllamaClient
from core.prompts import build_rag_prompt, NO_CONTEXT_MESSAGE, SYSTEM_PROMPT

__all__ = ["OllamaClient", "build_rag_prompt", "NO_CONTEXT_MESSAGE", "SYSTEM_PROMPT"]
