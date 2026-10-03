"""Interactive Terminal CLI interface for StudyRAG V2."""

import sys
import logging
from typing import Optional
from config import settings
from terminal.commands import TerminalCommandHandler
from database.conversations import ConversationManager

logger = logging.getLogger(__name__)

BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║                        StudyRAG V2                               ║
║           Offline Local AI Academic Study Assistant              ║
╚══════════════════════════════════════════════════════════════════╝
"""


def run_terminal_mode(
    rag_pipeline,
    vector_store,
    embedder,
    conversation_manager: Optional[ConversationManager] = None,
):
    """
    Launch interactive terminal REPL loop directly communicating with the RAG pipeline.
    """
    conv_manager = conversation_manager or ConversationManager()
    cmd_handler = TerminalCommandHandler(
        rag_pipeline=rag_pipeline,
        vector_store=vector_store,
        embedder=embedder,
        conversation_manager=conv_manager,
    )

    print(BANNER)
    # Check Ollama and Mongo connectivity
    ollama_ok = rag_pipeline.ollama_client.is_available()
    mongo_ok = conv_manager.mongo.is_available

    print(f" • Local Model  : {settings.OLLAMA_MODEL} ({'🟢 Online' if ollama_ok else '🔴 Offline'})")
    print(f" • MongoDB      : {'🟢 Connected (Persistent)' if mongo_ok else '🟡 Offline (Volatile Memory)'}")
    print(f" • Vectors      : {vector_store.count()} chunks from {len(vector_store.registry)} documents")
    print(f" • Top-K Chunks : {settings.TOP_K} (Cosine Similarity)")
    print("\nType your question directly or enter /help for commands.")
    print("──────────────────────────────────────────────────────────────────\n")

    current_conv_id = conv_manager.create_conversation()

    while True:
        try:
            prompt_symbol = f"StudyRAG [{current_conv_id[:6]}] > "
            user_input = input(prompt_symbol).strip()

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                current_conv_id = cmd_handler.handle_command(user_input, current_conv_id)
                continue

            # Process RAG query
            print("\n⏳ Searching study material and generating answer...\n")

            # Fetch conversation context
            conv_data = conv_manager.get_conversation(current_conv_id)
            history = conv_data.get("messages", []) if conv_data else []

            # Save user message
            conv_manager.add_message(
                conversation_id=current_conv_id,
                role="user",
                content=user_input,
            )

            # Stream response directly to stdout
            print("StudyRAG:\n")
            tokens_received = []
            retrieved_chunks = []
            sources = []

            for event in rag_pipeline.answer_question_stream(
                question=user_input,
                conversation_history=history,
                top_k=settings.TOP_K,
                min_similarity=settings.MIN_SIMILARITY,
            ):
                if event.get("event") == "retrieval":
                    retrieved_chunks = event.get("retrieved_chunks", [])
                    sources = event.get("sources", [])
                elif event.get("event") == "token":
                    token = event.get("token", "")
                    tokens_received.append(token)
                    sys.stdout.write(token)
                    sys.stdout.flush()
                elif event.get("event") == "done":
                    sources = event.get("sources", sources)

            full_answer = "".join(tokens_received)
            print("\n")

            # Display real sources
            if sources:
                print("──────────────────────────────────────────────────────────────────")
                print("Sources:")
                for idx, src in enumerate(sources, start=1):
                    doc = src.get("document") or src.get("source")
                    page = src.get("page") or src.get("page_number")
                    print(f"  {idx}. 📄 {doc} — Page {page}")
                print("──────────────────────────────────────────────────────────────────\n")

            # Show debug chunks if enabled
            if cmd_handler.debug_mode and retrieved_chunks:
                print("\n[Debug: Retrieved Context Chunks]")
                for idx, c in enumerate(retrieved_chunks, start=1):
                    doc = c.get("document_name") or c.get("source")
                    p = c.get("page_number") or c.get("page")
                    score = c.get("score", 0.0)
                    print(f"  [{idx}] {doc} (p.{p}) — Score: {score:.4f}")
                    snippet = c.get("text", "")[:120].replace("\n", " ")
                    print(f"      \"{snippet}...\"\n")

            # Save assistant message to conversation thread
            conv_manager.add_message(
                conversation_id=current_conv_id,
                role="assistant",
                content=full_answer,
                sources=sources,
                metadata={"model": settings.OLLAMA_MODEL, "retrieved_chunks": len(retrieved_chunks)},
            )

        except (KeyboardInterrupt, EOFError):
            print("\n\nUse /quit to exit or continue asking questions.\n")
        except Exception as e:
            print(f"\n[Error] {e}\n")
            logger.error(f"Error in terminal REPL: {e}", exc_info=True)
