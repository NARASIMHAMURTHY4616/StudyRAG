#!/usr/bin/env python3
"""
StudyRAG V2 - First-Class Terminal Interface (CLI).
Direct execution without web/Flask overhead.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings
from embeddings.embedder import Embedder
from vectorstore.local_store import LocalVectorStore
from retrieval.retriever import Retriever
from rag.pipeline import RAGPipeline
from database.mongo import MongoDBManager
from database.conversations import ConversationManager
from ingestion.pdf_loader import load_pdf, compute_pdf_hash
from ingestion.chunker import chunk_documents

# Set logging level for clean CLI
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("StudyRAG-CLI")

CLI_BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║                    StudyRAG V2 Terminal                          ║
║         Offline Local AI Academic Study Assistant                ║
╚══════════════════════════════════════════════════════════════════╝
"""

HELP_COMMANDS = """
Available Slash Commands:
───────────────────────────────────────────────────────────────────
  /help                  Show this command reference
  /documents             List all indexed study documents
  /chats                 List previous chat sessions from MongoDB
  /new                   Start a new chat conversation
  /history               View messages in the current conversation
  /open <id or num>      Load and switch to a previous conversation
  /add <file1.pdf> ...   Upload and index one or more PDF files
  /add-dir <folder>      Ingest all PDF files from a directory
  /model [name]          View or change the active Ollama model
  /sources               Show sources from the most recent answer
  /clear                 Clear the terminal screen and chat context
  /debug                 Toggle retrieval score inspection
  /exit or /quit         Exit StudyRAG Terminal
───────────────────────────────────────────────────────────────────
Tip: Type any question directly to query your study materials!
"""


class StudyRAGCLI:
    """Terminal CLI Controller for StudyRAG V2."""

    def __init__(self):
        settings.ensure_directories()
        self.embedder = Embedder()
        self.vector_store = LocalVectorStore()
        self.retriever = Retriever(embedder=self.embedder, vector_store=self.vector_store)
        self.rag_pipeline = RAGPipeline(retriever=self.retriever)
        self.mongo = MongoDBManager.get_instance()
        self.conv_manager = ConversationManager(mongo_manager=self.mongo)
        self.current_conv_id: Optional[str] = None
        self.last_sources: List[dict] = []
        self.debug_mode: bool = False

    def ingest_single_file(self, file_path: Path, verbose: bool = True) -> bool:
        """Ingest a single PDF file with progress output."""
        if not file_path.is_file() or not file_path.name.lower().endswith(".pdf"):
            if verbose:
                print(f"❌ Error: '{file_path}' is not a valid PDF file.")
            return False

        filename = file_path.name
        dest_path = settings.DOCUMENT_DIR / filename

        try:
            # Copy file to document store if outside
            if file_path.resolve() != dest_path.resolve():
                dest_path.write_bytes(file_path.read_bytes())

            file_hash = compute_pdf_hash(dest_path)

            if self.vector_store.is_document_indexed(filename, file_hash):
                info = self.vector_store.registry.get(filename, {})
                if verbose:
                    print(f"ℹ️  '{filename}' already indexed ({info.get('pages_count', 0)} pages, {info.get('chunks_count', 0)} chunks). Skipped.")
                return True

            if verbose:
                print(f"\nProcessing '{filename}':")
                print("  [1/3] Reading PDF & extracting pages...")

            pages = load_pdf(dest_path)
            total_pages = len(pages)
            if total_pages == 0:
                if verbose:
                    print(f"  ⚠️  '{filename}' contains no readable text pages.")
                return False

            if verbose:
                print(f"  [2/3] Creating ~{settings.TARGET_CHUNKS_PER_PAGE} semantic chunks per page ({total_pages} pages)...")

            chunks = chunk_documents(
                pages,
                target_chunks=settings.TARGET_CHUNKS_PER_PAGE,
                overlap_words=settings.CHUNK_OVERLAP,
            )
            total_chunks = len(chunks)
            if total_chunks == 0:
                if verbose:
                    print(f"  ⚠️  No chunks generated from '{filename}'.")
                return False

            if verbose:
                print(f"  [3/3] Generating embeddings ({total_chunks} chunks on CPU)...")

            chunk_texts = [c["text"] for c in chunks]
            vectors = self.embedder.embed_documents(chunk_texts)

            if filename in self.vector_store.registry:
                self.vector_store.remove_document(filename)

            self.vector_store.add(vectors, chunks)
            self.vector_store.register_document(
                filename=filename,
                sha256_hash=file_hash,
                pages_count=total_pages,
                chunks_count=total_chunks,
            )

            # Sync with Mongo documents collection if available
            doc_col = self.mongo.get_collection("documents")
            if doc_col is not None:
                try:
                    doc_col.update_one(
                        {"filename": filename},
                        {"$set": {
                            "filename": filename,
                            "pages": total_pages,
                            "chunks": total_chunks,
                            "hash": file_hash,
                            "status": "ready",
                        }},
                        upsert=True,
                    )
                except Exception:
                    pass

            if verbose:
                print(f"  ✓ '{filename}' indexed successfully! ({total_pages} pages, {total_chunks} chunks)")
                print(f"  Total Vectors in DB: {self.vector_store.count()}\n")
            return True

        except Exception as e:
            if verbose:
                print(f"  ❌ Failed to index '{filename}': {e}")
            return False

    def ingest_files(self, file_paths: List[str]):
        """Ingest multiple files."""
        for path_str in file_paths:
            path = Path(path_str).expanduser().resolve()
            self.ingest_single_file(path, verbose=True)

    def ingest_directory(self, dir_path_str: str):
        """Ingest all PDFs in a directory."""
        dir_path = Path(dir_path_str).expanduser().resolve()
        if not dir_path.is_dir():
            print(f"❌ Error: Directory '{dir_path}' not found.")
            return

        pdf_files = list(dir_path.glob("*.pdf")) + list(dir_path.glob("*.PDF"))
        if not pdf_files:
            print(f"⚠️ No PDF files found in '{dir_path}'.")
            return

        print(f"\nFound {len(pdf_files)} PDF(s) in {dir_path}. Ingesting...\n")
        ingested = 0
        for pdf in sorted(pdf_files):
            if self.ingest_single_file(pdf, verbose=True):
                ingested += 1
        print(f"Finished. Successfully indexed {ingested}/{len(pdf_files)} documents.\n")

    def list_documents(self):
        """Display indexed documents table."""
        registry = self.vector_store.registry
        if not registry:
            print("\n[Documents] No study documents are currently indexed.")
            print("Use '/add <file.pdf>' or '/add-dir <folder>' to index study materials.\n")
            return

        print(f"\nIndexed Documents ({len(registry)} total, {self.vector_store.count()} vectors):")
        print("───────────────────────────────────────────────────────────────────")
        for idx, (filename, info) in enumerate(registry.items(), start=1):
            pages = info.get("pages_count", "?")
            chunks = info.get("chunks_count", "?")
            print(f"  {idx}. 📄 {filename}")
            print(f"     Pages: {pages} | Chunks: {chunks} | Status: Ready")
        print("───────────────────────────────────────────────────────────────────\n")

    def list_chats(self):
        """Display list of previous chats."""
        chats = self.conv_manager.list_conversations(limit=20)
        if not chats:
            print("\n[Chats] No previous chat sessions found.\n")
            return

        print("\nPrevious Chat Sessions:")
        print("───────────────────────────────────────────────────────────────────")
        for idx, chat in enumerate(chats, start=1):
            title = chat.get("title", "Untitled")
            cid = chat.get("conversation_id", "")
            date_str = (chat.get("updated_at") or "")[:10]
            print(f"  [{idx}] {title} ({date_str})")
            print(f"      ID: {cid}")
        print("───────────────────────────────────────────────────────────────────")
        print("Use '/open <number or ID>' to resume a conversation.\n")

    def show_history(self):
        """Show messages in current conversation."""
        if not self.current_conv_id:
            print("\n[Context] No messages in the current session yet.\n")
            return

        conv = self.conv_manager.get_conversation(self.current_conv_id)
        if not conv or not conv.get("messages"):
            print("\n[Context] Current conversation has no messages.\n")
            return

        print(f"\nConversation: {conv.get('title', 'New Chat')}")
        print("───────────────────────────────────────────────────────────────────")
        for msg in conv.get("messages", []):
            role_label = "You" if msg.get("role") == "user" else "StudyRAG"
            print(f"\n{role_label}:\n{msg.get('content')}")
        print("───────────────────────────────────────────────────────────────────\n")

    def start_interactive_session(self):
        """Main Interactive REPL Loop."""
        print(CLI_BANNER)

        ollama_ok = self.rag_pipeline.ollama_client.is_available()
        mongo_ok = self.mongo.is_available
        doc_count = len(self.vector_store.registry)
        chat_count = len(self.conv_manager.list_conversations(limit=100))

        print(f" Model     : {settings.OLLAMA_MODEL} ({'🟢 Online' if ollama_ok else '🔴 Offline'})")
        print(f" Vector DB : {self.vector_store.count()} vectors from {doc_count} document(s)")
        print(f" MongoDB   : {'🟢 Connected' if mongo_ok else '🟡 Volatile Memory'}")
        print(f" Documents : {doc_count}")
        print(f" Chats     : {chat_count}")
        print("\nType your question or /help for commands.")
        print("───────────────────────────────────────────────────────────────────\n")

        self.current_conv_id = self.conv_manager.create_conversation()

        while True:
            try:
                prompt_label = f"You [{self.current_conv_id[:6]}] > "
                user_input = input(prompt_label).strip()

                if not user_input:
                    continue

                # Handle Slash Commands
                if user_input.startswith("/"):
                    self.execute_command(user_input)
                    continue

                # Process RAG query
                self.process_query(user_input)

            except (KeyboardInterrupt, EOFError):
                print("\n\nSession paused. Use /exit to quit or ask another question.\n")
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

    def execute_command(self, cmd_line: str):
        """Execute a slash command inside interactive mode."""
        parts = cmd_line.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help":
            print(HELP_COMMANDS)

        elif cmd in ("/documents", "/docs"):
            self.list_documents()

        elif cmd in ("/chats", "/list"):
            self.list_chats()

        elif cmd == "/history":
            self.show_history()

        elif cmd == "/new":
            self.current_conv_id = self.conv_manager.create_conversation()
            print(f"\n✨ Started new conversation thread (ID: {self.current_conv_id[:8]}...)\n")

        elif cmd in ("/add", "/upload"):
            if not args:
                print("\n❌ Usage: /add <file1.pdf> [<file2.pdf> ...]\n")
            else:
                self.ingest_files(args)

        elif cmd in ("/add-dir", "/upload-dir"):
            if not args:
                print("\n❌ Usage: /add-dir <directory_path>\n")
            else:
                self.ingest_directory(args[0])

        elif cmd == "/open":
            if not args:
                print("\n❌ Usage: /open <number_or_conversation_id>\n")
            else:
                self.open_chat(args[0])

        elif cmd == "/model":
            if args:
                new_model = args[0]
                settings.OLLAMA_MODEL = new_model
                self.rag_pipeline.ollama_client.model = new_model
                print(f"\nActive model set to: {new_model}\n")
            else:
                models = self.rag_pipeline.ollama_client.list_models()
                print(f"\nCurrent Model: {settings.OLLAMA_MODEL}")
                print(f"Available Models: {', '.join(models)}\n")

        elif cmd == "/sources":
            if not self.last_sources:
                print("\nNo sources recorded from the last query.\n")
            else:
                print("\nLast Retrieved Sources:")
                print("───────────────────────────────────────────────────────────────────")
                for idx, src in enumerate(self.last_sources, start=1):
                    doc = src.get("document") or src.get("source", "Document")
                    page = src.get("page") or src.get("page_number", "?")
                    score = src.get("score")
                    score_str = f" (Similarity: {score:.2f})" if score else ""
                    print(f"  [{idx}] 📄 {doc} — Page {page}{score_str}")
                print("───────────────────────────────────────────────────────────────────\n")

        elif cmd == "/debug":
            self.debug_mode = not self.debug_mode
            print(f"\nDebug Mode is now: {'ON' if self.debug_mode else 'OFF'}\n")

        elif cmd == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            self.current_conv_id = self.conv_manager.create_conversation()
            print("Cleared screen and started a fresh context.\n")

        elif cmd in ("/exit", "/quit"):
            print("\n👋 Exiting StudyRAG. Happy studying!\n")
            sys.exit(0)

        else:
            print(f"\n❌ Unknown command '{cmd}'. Type /help for available commands.\n")

    def open_chat(self, target: str):
        """Open an existing chat."""
        chats = self.conv_manager.list_conversations(limit=30)
        target_id = None

        if target.isdigit():
            idx = int(target)
            if 1 <= idx <= len(chats):
                target_id = chats[idx - 1]["conversation_id"]
        else:
            for c in chats:
                if c["conversation_id"].startswith(target):
                    target_id = c["conversation_id"]
                    break

        if not target_id:
            print(f"\n❌ Conversation '{target}' not found.\n")
            return

        self.current_conv_id = target_id
        conv = self.conv_manager.get_conversation(target_id)
        print(f"\n📖 Loaded chat: {conv.get('title', 'Untitled')}")
        print(f"   Messages: {len(conv.get('messages', []))}\n")

    def process_query(self, question: str):
        """Run grounded RAG query with streaming tokens and follow-up prompt."""
        print("\nStudyRAG:\n")

        conv = self.conv_manager.get_conversation(self.current_conv_id)
        history = conv.get("messages", []) if conv else []

        # Record user message
        self.conv_manager.add_message(
            conversation_id=self.current_conv_id,
            role="user",
            content=question,
        )

        tokens_received = []
        retrieved_chunks = []
        sources = []

        for event in self.rag_pipeline.answer_question_stream(
            question=question,
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
        self.last_sources = sources
        print("\n")

        # Display Sources
        if sources:
            print("───────────────────────────────────────────────────────────────────")
            print("Sources:")
            for idx, src in enumerate(sources, start=1):
                doc = src.get("document") or src.get("source")
                page = src.get("page") or src.get("page_number")
                print(f"  [{idx}] 📄 {doc} — Page {page}")
            print("───────────────────────────────────────────────────────────────────\n")

        # Display Debug Chunks if enabled
        if self.debug_mode and retrieved_chunks:
            print("\n[Debug: Top 10 Retrieved Chunks]")
            for idx, c in enumerate(retrieved_chunks, start=1):
                doc = c.get("document_name") or c.get("source")
                p = c.get("page_number") or c.get("page")
                score = c.get("score", 0.0)
                snippet = (c.get("chunk_text") or c.get("text", "")).replace("\n", " ")[:90]
                print(f"  #{idx} {doc} (p.{p}) | Score: {score:.3f} | \"{snippet}...\"")
            print()

        # Save assistant message to conversation thread
        self.conv_manager.add_message(
            conversation_id=self.current_conv_id,
            role="assistant",
            content=full_answer,
            sources=sources,
            metadata={"model": settings.OLLAMA_MODEL, "retrieved_chunks": len(retrieved_chunks)},
        )


def main():
    parser = argparse.ArgumentParser(description="StudyRAG V2 - Terminal CLI")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # add subcommand
    add_parser = subparsers.add_parser("add", help="Upload and index PDF document(s)")
    add_parser.add_argument("files", nargs="+", help="Path(s) to PDF file(s)")

    # add-dir subcommand
    dir_parser = subparsers.add_parser("add-dir", help="Upload and index all PDFs in a directory")
    dir_parser.add_argument("directory", help="Path to directory containing PDFs")

    # documents subcommand
    subparsers.add_parser("documents", help="List all indexed documents")

    # chats subcommand
    subparsers.add_parser("chats", help="List previous chat sessions")

    args = parser.parse_args()
    cli = StudyRAGCLI()

    if args.command == "add":
        cli.ingest_files(args.files)
    elif args.command == "add-dir":
        cli.ingest_directory(args.directory)
    elif args.command == "documents":
        cli.list_documents()
    elif args.command == "chats":
        cli.list_chats()
    else:
        # Launch Interactive Session
        cli.start_interactive_session()


if __name__ == "__main__":
    main()
