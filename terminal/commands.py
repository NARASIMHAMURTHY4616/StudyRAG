"""Terminal command handlers for StudyRAG V2."""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import List, Optional
from config import settings
from ingestion.pdf_loader import load_pdf, compute_pdf_hash
from ingestion.chunker import chunk_documents
from database.conversations import ConversationManager

logger = logging.getLogger(__name__)

HELP_TEXT = """
StudyRAG V2 Terminal Commands:
----------------------------------------------------------------------
/help                   Show this help menu
/upload <file1> [...]   Upload and index one or more PDF files
/upload-dir <directory> Ingest all PDF files from a directory
/documents              List all indexed documents, pages, and chunks
/delete <filename>      Remove a document from the vector store
/new                    Start a fresh conversation thread
/history                View past conversations stored in MongoDB
/open <id or number>    Load and resume a past conversation
/clear                  Clear screen and current conversation context
/settings               Show current model, top-k, and DB status
/debug                  Toggle retrieval score inspection
/quit or /exit          Exit StudyRAG Terminal
----------------------------------------------------------------------
Tip: Just type your question directly without a slash to ask StudyRAG!
"""


class TerminalCommandHandler:
    """Dispatches and executes terminal commands."""

    def __init__(
        self,
        rag_pipeline,
        vector_store,
        embedder,
        conversation_manager: ConversationManager,
    ):
        self.pipeline = rag_pipeline
        self.vector_store = vector_store
        self.embedder = embedder
        self.conv_manager = conversation_manager
        self.debug_mode = False

    def handle_command(self, cmd_line: str, current_conv_id: str) -> Optional[str]:
        """
        Process a slash command. Returns new current_conv_id if modified, else current.
        """
        parts = cmd_line.strip().split()
        if not parts:
            return current_conv_id

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help":
            print(HELP_TEXT)

        elif cmd == "/settings":
            self._show_settings()

        elif cmd == "/debug":
            self.debug_mode = not self.debug_mode
            status_str = "ENABLED" if self.debug_mode else "DISABLED"
            print(f"\n[Debug Mode {status_str}] Retrieval inspection will {'now' if self.debug_mode else 'no longer'} display.\n")

        elif cmd == "/documents":
            self._list_documents()

        elif cmd == "/upload":
            if not args:
                print("\n[Error] Usage: /upload <path/to/doc1.pdf> [<path/to/doc2.pdf> ...]\n")
            else:
                self._upload_files(args)

        elif cmd == "/upload-dir":
            if not args:
                print("\n[Error] Usage: /upload-dir <path/to/directory>\n")
            else:
                self._upload_dir(args[0])

        elif cmd == "/delete":
            if not args:
                print("\n[Error] Usage: /delete <filename.pdf>\n")
            else:
                self._delete_document(args[0])

        elif cmd == "/new":
            new_id = self.conv_manager.create_conversation()
            print(f"\n✨ Started new conversation thread (ID: {new_id[:8]}...)\n")
            return new_id

        elif cmd == "/history":
            self._list_history()

        elif cmd == "/open":
            if not args:
                print("\n[Error] Usage: /open <conversation_id_or_number>\n")
            else:
                new_id = self._open_conversation(args[0])
                if new_id:
                    return new_id

        elif cmd == "/clear":
            # Clear terminal screen
            os.system("cls" if os.name == "nt" else "clear")
            new_id = self.conv_manager.create_conversation()
            print("Cleared screen and started a fresh context.\n")
            return new_id

        elif cmd in ("/quit", "/exit"):
            print("\nExiting StudyRAG V2. Happy studying!\n")
            sys.exit(0)

        else:
            print(f"\n[Unknown command '{cmd}'] Type /help for available commands.\n")

        return current_conv_id

    def _show_settings(self):
        mongo_status = "Connected (Persistent)" if self.conv_manager.mongo.is_available else "Offline (Volatile Memory)"
        ollama_status = "Online" if self.pipeline.ollama_client.is_available() else "Offline / Not Reachable"

        print("\n══════════════════════════════════════════════")
        print("           StudyRAG V2 Settings               ")
        print("══════════════════════════════════════════════")
        print(f" LLM Model       : {settings.OLLAMA_MODEL}")
        print(f" Ollama Host     : {settings.OLLAMA_BASE_URL} ({ollama_status})")
        print(f" Embedding Model : {settings.EMBEDDING_MODEL}")
        print(f" Top-K Retrieval : {settings.TOP_K}")
        print(f" Min Similarity  : {settings.MIN_SIMILARITY}")
        print(f" Target Chunks/Pg: {settings.TARGET_CHUNKS_PER_PAGE}")
        print(f" MongoDB Status  : {mongo_status}")
        print(f" FAISS Vectors   : {self.vector_store.count()}")
        print(f" Indexed Docs    : {len(self.vector_store.registry)}")
        print(f" Debug Mode      : {'ON' if self.debug_mode else 'OFF'}")
        print("══════════════════════════════════════════════\n")

    def _list_documents(self):
        registry = self.vector_store.registry
        if not registry:
            print("\n[Documents] No study documents are currently indexed.")
            print("Use '/upload <file.pdf>' or '/upload-dir <folder>' to index study material.\n")
            return

        print(f"\nIndexed Documents ({len(registry)} total, {self.vector_store.count()} vectors):")
        print("──────────────────────────────────────────────────────────────")
        for idx, (filename, info) in enumerate(registry.items(), start=1):
            pages = info.get("pages_count", "?")
            chunks = info.get("chunks_count", "?")
            indexed_at = info.get("indexed_at", "Unknown")
            print(f"{idx}. 📄 {filename}")
            print(f"   Pages: {pages} | Chunks: {chunks} | Added: {indexed_at}")
        print("──────────────────────────────────────────────────────────────\n")

    def _upload_files(self, file_paths: List[str]):
        for path_str in file_paths:
            path = Path(path_str).expanduser().resolve()
            if not path.is_file():
                print(f"[Error] File not found: {path_str}")
                continue

            if not path.name.lower().endswith(".pdf"):
                print(f"[Error] Unsupported format '{path.name}'. Only PDF files are supported.")
                continue

            self._process_single_pdf(path)

    def _upload_dir(self, dir_path_str: str):
        dir_path = Path(dir_path_str).expanduser().resolve()
        if not dir_path.is_dir():
            print(f"[Error] Directory not found: {dir_path_str}")
            return

        pdf_files = list(dir_path.glob("*.pdf")) + list(dir_path.glob("*.PDF"))
        if not pdf_files:
            print(f"[Warning] No PDF files found in {dir_path}")
            return

        print(f"\nFound {len(pdf_files)} PDF documents in {dir_path}. Ingesting...")
        for pdf in sorted(pdf_files):
            self._process_single_pdf(pdf)

    def _process_single_pdf(self, source_path: Path):
        filename = source_path.name
        dest_path = settings.DOCUMENT_DIR / filename

        try:
            # Copy to document dir if not already there
            if source_path != dest_path:
                shutil.copy2(source_path, dest_path)

            file_hash = compute_pdf_hash(dest_path)

            if self.vector_store.is_document_indexed(filename, file_hash):
                doc_info = self.vector_store.registry.get(filename, {})
                print(f"ℹ️  '{filename}' is already indexed ({doc_info.get('pages_count')} pages, {doc_info.get('chunks_count')} chunks). Skipped.")
                return

            print(f"⚙️  Extracting pages from '{filename}'...")
            pages = load_pdf(dest_path)
            total_pages = len(pages)
            if total_pages == 0:
                print(f"⚠️  '{filename}' contains no readable pages.")
                return

            print(f"⚙️  Generating ~3 semantic chunks per page ({total_pages} pages)...")
            chunks = chunk_documents(pages, target_chunks=settings.TARGET_CHUNKS_PER_PAGE)
            total_chunks = len(chunks)
            if total_chunks == 0:
                print(f"⚠️  No text could be extracted from '{filename}'.")
                return

            print(f"⚙️  Computing embeddings on CPU for {total_chunks} chunks...")
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
            print(f"✅ Successfully indexed '{filename}' ({total_pages} pages, {total_chunks} chunks). Total store: {self.vector_store.count()} vectors.\n")

        except Exception as e:
            print(f"❌ Failed to ingest '{filename}': {e}\n")
            logger.error(f"Error in terminal upload for {filename}: {e}", exc_info=True)

    def _delete_document(self, filename: str):
        if filename not in self.vector_store.registry:
            print(f"\n[Error] Document '{filename}' is not currently indexed.\n")
            return

        try:
            self.vector_store.remove_document(filename)
            doc_file = settings.DOCUMENT_DIR / filename
            if doc_file.exists():
                doc_file.unlink(missing_ok=True)
            print(f"\n🗑️  Deleted '{filename}' from index. Remaining vectors: {self.vector_store.count()}\n")
        except Exception as e:
            print(f"\n❌ Error deleting '{filename}': {e}\n")

    def _list_history(self):
        conversations = self.conv_manager.list_conversations(limit=15)
        if not conversations:
            print("\n[History] No saved conversations found in MongoDB.\n")
            return

        print("\nRecent Conversations:")
        print("──────────────────────────────────────────────────────────────")
        for idx, conv in enumerate(conversations, start=1):
            title = conv.get("title", "Untitled")
            cid = conv.get("conversation_id", "")
            updated = conv.get("updated_at", "")[:19].replace("T", " ")
            print(f"[{idx}] {title}")
            print(f"    ID: {cid} | Updated: {updated}")
        print("──────────────────────────────────────────────────────────────")
        print("Use '/open <number or ID>' to resume a conversation.\n")

    def _open_conversation(self, target: str) -> Optional[str]:
        conversations = self.conv_manager.list_conversations(limit=20)
        target_id = None

        if target.isdigit():
            idx = int(target)
            if 1 <= idx <= len(conversations):
                target_id = conversations[idx - 1]["conversation_id"]
            else:
                print(f"\n[Error] Number {idx} out of range (1-{len(conversations)}).\n")
                return None
        else:
            # Match by id prefix
            for conv in conversations:
                if conv["conversation_id"].startswith(target):
                    target_id = conv["conversation_id"]
                    break

        if not target_id:
            print(f"\n[Error] Conversation '{target}' not found.\n")
            return None

        conv_data = self.conv_manager.get_conversation(target_id)
        if not conv_data:
            print(f"\n[Error] Could not load conversation '{target_id}'.\n")
            return None

        print(f"\n📖 Loaded conversation: {conv_data.get('title', 'Untitled')}")
        print("──────────────────────────────────────────────────────────────")
        for msg in conv_data.get("messages", []):
            role_label = "You" if msg.get("role") == "user" else "StudyRAG"
            print(f"\n{role_label}: {msg.get('content')}")
        print("──────────────────────────────────────────────────────────────\n")
        return target_id
