"""StudyRAG V2 - Offline Local AI Study Assistant (Web UI & Terminal Mode)."""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from werkzeug.utils import secure_filename

from config import settings
from core.ollama_client import OllamaClient
from embeddings.embedder import Embedder
from vectorstore.local_store import LocalVectorStore
from retrieval.retriever import Retriever
from rag.pipeline import RAGPipeline
from ingestion.pdf_loader import load_pdf, compute_pdf_hash
from ingestion.chunker import chunk_documents
from database.mongo import MongoDBManager
from database.conversations import ConversationManager
from terminal.cli import run_terminal_mode

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("StudyRAG")

# Ensure required directories exist
settings.ensure_directories()

# Initialize Singletons
logger.info("Initializing StudyRAG V2 Components...")
ollama_client = OllamaClient()
embedder = Embedder()
vector_store = LocalVectorStore()
retriever = Retriever(embedder=embedder, vector_store=vector_store)
rag_pipeline = RAGPipeline(retriever=retriever, ollama_client=ollama_client)
mongo_manager = MongoDBManager.get_instance()
conv_manager = ConversationManager(mongo_manager=mongo_manager)
logger.info("StudyRAG V2 Components initialized.")

# Initialize Flask App
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit


@app.route("/", methods=["GET"])
def index():
    """Render modern ChatGPT-style main interface."""
    ollama_ok = ollama_client.is_available()
    doc_count = len(vector_store.registry)
    vector_count = vector_store.count()
    return render_template(
        "index.html",
        ollama_ok=ollama_ok,
        doc_count=doc_count,
        vector_count=vector_count,
        ollama_model=settings.OLLAMA_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
        default_top_k=settings.TOP_K,
        default_min_sim=settings.MIN_SIMILARITY,
    )


# ==========================================
# Chat & RAG Streaming Endpoints
# ==========================================

@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """
    SSE Streaming endpoint for real-time progressive response generation.
    Maintains conversation thread in MongoDB and enforces context grounding.
    """
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    conv_id = data.get("conversation_id")
    top_k = int(data.get("top_k", settings.TOP_K))
    min_similarity = float(data.get("min_similarity", settings.MIN_SIMILARITY))
    model = data.get("model") or settings.OLLAMA_MODEL

    if not question:
        return jsonify({"error": "Question is required."}), 400

    # Ensure conversation thread exists
    if not conv_id:
        conv_id = conv_manager.create_conversation()

    # Load existing conversation history for context preservation
    conv_data = conv_manager.get_conversation(conv_id)
    history = conv_data.get("messages", []) if conv_data else []

    # Record user message in DB
    conv_manager.add_message(
        conversation_id=conv_id,
        role="user",
        content=question,
    )

    # Re-fetch title in case it was auto-generated on first message
    updated_conv = conv_manager.get_conversation(conv_id)
    current_title = updated_conv.get("title", "New Chat") if updated_conv else "New Chat"

    def generate_sse():
        # Emit conversation metadata
        yield f"data: {json.dumps({'event': 'conversation_id', 'conversation_id': conv_id, 'title': current_title})}\n\n"

        accumulated_tokens = []
        retrieved_chunks = []
        sources = []

        try:
            for event in rag_pipeline.answer_question_stream(
                question=question,
                conversation_history=history,
                top_k=top_k,
                min_similarity=min_similarity,
                model=model,
            ):
                if event.get("event") == "retrieval":
                    retrieved_chunks = event.get("retrieved_chunks", [])
                    sources = event.get("sources", [])
                    yield f"data: {json.dumps(event)}\n\n"
                elif event.get("event") == "token":
                    accumulated_tokens.append(event.get("token", ""))
                    yield f"data: {json.dumps(event)}\n\n"
                elif event.get("event") == "done":
                    sources = event.get("sources", sources)
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

        full_answer = "".join(accumulated_tokens).strip()

        # Save assistant message to MongoDB with verified sources
        conv_manager.add_message(
            conversation_id=conv_id,
            role="assistant",
            content=full_answer,
            sources=sources,
            metadata={
                "model": model,
                "retrieved_chunks": len(retrieved_chunks),
                "top_k": top_k,
                "min_similarity": min_similarity,
            },
        )

    resp = Response(stream_with_context(generate_sse()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@app.route("/ask", methods=["POST"])
def ask():
    """Synchronous question answering endpoint (V1 backwards-compatible)."""
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    top_k = int(data.get("top_k", settings.TOP_K))
    min_similarity = float(data.get("min_similarity", settings.MIN_SIMILARITY))

    if not question:
        return jsonify({"error": "Question is required.", "status": "error"}), 400

    result = rag_pipeline.answer_question(
        question=question,
        top_k=top_k,
        min_similarity=min_similarity,
    )
    return jsonify(result)


# ==========================================
# Conversation History Endpoints
# ==========================================

@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    """List all stored conversations for the sidebar."""
    convs = conv_manager.list_conversations(limit=100)
    return jsonify(convs)


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    """Create a new conversation."""
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    conv_id = conv_manager.create_conversation(title=title)
    return jsonify({"conversation_id": conv_id, "title": title or "New Chat"}), 201


@app.route("/api/conversations/<conv_id>", methods=["GET"])
def get_conversation(conv_id):
    """Retrieve full messages for a conversation."""
    conv = conv_manager.get_conversation(conv_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify(conv)


@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
def delete_conversation(conv_id):
    """Delete a conversation thread."""
    success = conv_manager.delete_conversation(conv_id)
    return jsonify({"success": success})


@app.route("/api/conversations/<conv_id>/title", methods=["PUT"])
def update_conversation_title(conv_id):
    """Update title of a conversation."""
    data = request.get_json(silent=True) or {}
    new_title = data.get("title", "").strip()
    if not new_title:
        return jsonify({"error": "Title cannot be empty"}), 400
    success = conv_manager.update_title(conv_id, new_title)
    return jsonify({"success": success, "title": new_title})


# ==========================================
# Document Management Endpoints
# ==========================================

@app.route("/api/documents", methods=["GET"])
def list_documents():
    """Return all indexed documents and metadata."""
    docs = []
    for filename, info in vector_store.registry.items():
        docs.append({
            "filename": filename,
            "pages_count": info.get("pages_count", 0),
            "chunks_count": info.get("chunks_count", 0),
            "indexed_at": info.get("indexed_at", ""),
            "hash": info.get("hash", ""),
        })
    return jsonify({
        "documents": docs,
        "total_documents": len(docs),
        "total_vectors": vector_store.count(),
    })


@app.route("/api/documents/<path:filename>", methods=["DELETE"])
def delete_document(filename):
    """Remove a document and its vectors from index."""
    if filename not in vector_store.registry:
        return jsonify({"error": f"Document '{filename}' not found."}), 404

    vector_store.remove_document(filename)
    doc_file = settings.DOCUMENT_DIR / filename
    if doc_file.exists():
        doc_file.unlink(missing_ok=True)

    return jsonify({
        "message": f"Successfully deleted '{filename}'",
        "total_vectors": vector_store.count(),
    })


@app.route("/upload", methods=["POST"])
def upload():
    """Upload and incrementally ingest a PDF study document (~3 chunks/page)."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded.", "status": "error"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename provided.", "status": "error"}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported.", "status": "error"}), 400

    save_path = settings.DOCUMENT_DIR / filename
    try:
        file.save(save_path)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        return jsonify({"error": f"Failed to save file: {e}", "status": "error"}), 500

    file_hash = compute_pdf_hash(save_path)

    # Check for duplicate
    if vector_store.is_document_indexed(filename, file_hash):
        doc_info = vector_store.registry.get(filename, {})
        return jsonify({
            "message": f"Document '{filename}' is already indexed.",
            "filename": filename,
            "pages": doc_info.get("pages_count", 0),
            "chunks": doc_info.get("chunks_count", 0),
            "total_vectors": vector_store.count(),
            "status": "skipped",
        })

    try:
        pages = load_pdf(save_path)
        total_pages = len(pages)
        if total_pages == 0:
            return jsonify({"error": "PDF contains no readable pages.", "status": "error"}), 400

        # Chunk pages using V2 semantic chunking (~3 chunks/page)
        chunks = chunk_documents(
            pages,
            target_chunks=settings.TARGET_CHUNKS_PER_PAGE,
            overlap_words=settings.CHUNK_OVERLAP,
        )
        total_chunks = len(chunks)
        if total_chunks == 0:
            return jsonify({"error": "No text could be chunked from PDF.", "status": "error"}), 400

        # Generate embeddings
        chunk_texts = [c["text"] for c in chunks]
        vectors = embedder.embed_documents(chunk_texts)

        # Store in FAISS
        if filename in vector_store.registry:
            vector_store.remove_document(filename)

        vector_store.add(vectors, chunks)
        vector_store.register_document(
            filename=filename,
            sha256_hash=file_hash,
            pages_count=total_pages,
            chunks_count=total_chunks,
        )

        logger.info(f"Ingested '{filename}' ({total_pages} pages, {total_chunks} chunks). Total store: {vector_store.count()}")

        return jsonify({
            "message": f"Successfully ingested '{filename}'",
            "filename": filename,
            "pages": total_pages,
            "chunks": total_chunks,
            "total_vectors": vector_store.count(),
            "status": "success",
        })

    except Exception as e:
        logger.error(f"Error processing PDF '{filename}': {e}", exc_info=True)
        return jsonify({"error": f"Failed to ingest PDF: {e}", "status": "error"}), 500


# ==========================================
# System Settings & Status Endpoints
# ==========================================

@app.route("/api/status", methods=["GET"])
def api_status():
    """Return comprehensive system and service health status."""
    return jsonify({
        "ollama_available": ollama_client.is_available(),
        "ollama_model": settings.OLLAMA_MODEL,
        "available_models": ollama_client.list_models(),
        "embedding_model": settings.EMBEDDING_MODEL,
        "mongodb_available": mongo_manager.is_available,
        "total_vectors": vector_store.count(),
        "indexed_documents": vector_store.registry,
        "top_k": settings.TOP_K,
        "min_similarity": settings.MIN_SIMILARITY,
        "target_chunks_per_page": settings.TARGET_CHUNKS_PER_PAGE,
    })


@app.route("/api/settings", methods=["POST"])
def update_settings():
    """Update runtime settings."""
    data = request.get_json(silent=True) or {}
    if "top_k" in data:
        settings.TOP_K = int(data["top_k"])
    if "min_similarity" in data:
        settings.MIN_SIMILARITY = float(data["min_similarity"])
    if "model" in data and data["model"]:
        settings.OLLAMA_MODEL = str(data["model"])
        ollama_client.model = settings.OLLAMA_MODEL

    return jsonify({
        "status": "updated",
        "top_k": settings.TOP_K,
        "min_similarity": settings.MIN_SIMILARITY,
        "model": settings.OLLAMA_MODEL,
    })


# ==========================================
# Main Execution & Mode Selection
# ==========================================

def start_server():
    """Start Flask web server."""
    print("\n" + "=" * 60)
    print(f"🚀 Starting StudyRAG V2 Web Interface on http://localhost:{settings.PORT}")
    print(f"   Model: {settings.OLLAMA_MODEL} | DB: MongoDB ({'Online' if mongo_manager.is_available else 'Offline/Memory'})")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=settings.PORT, debug=settings.DEBUG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StudyRAG V2 - Local Offline Study Assistant")
    parser.add_argument("-t", "--terminal", action="store_true", help="Start directly in interactive Terminal Mode")
    parser.add_argument("-w", "--web", action="store_true", help="Start directly in Web UI Mode")
    args = parser.parse_args()

    if args.terminal:
        run_terminal_mode(rag_pipeline, vector_store, embedder, conv_manager)
    elif args.web:
        start_server()
    else:
        # Prompt user to choose mode
        print("\n" + "=" * 54)
        print("╔════════════════════════════════════════════════════╗")
        print("║                   StudyRAG V2                      ║")
        print("║        Offline Local AI Study Assistant            ║")
        print("╚════════════════════════════════════════════════════╝")
        print("=" * 54)
        print("\nSelect mode:")
        print(" [1] Terminal Mode (CLI)")
        print(" [2] Web UI Mode (Browser)")
        print()

        try:
            choice = input("Enter choice [1 or 2] (Default: 2): ").strip()
            if choice == "1":
                run_terminal_mode(rag_pipeline, vector_store, embedder, conv_manager)
            else:
                start_server()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting StudyRAG.")
            sys.exit(0)
