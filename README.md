# StudyRAG v1.1 — Local Offline PDF RAG Pipeline

**StudyRAG v1.1** is an offline-first, local Retrieval-Augmented Generation (RAG) system engineered for academic study materials. It enables students and researchers to query textbook PDFs with strictly grounded answers, exact page citations, and zero reliance on cloud APIs.

---

## 🏗️ Architecture Diagram

```text
                  STUDYRAG v1.1

                     PDF
                      │
                      ▼
                PyMuPDF Loader
                      │
                      ▼
                 Text Cleaner
                      │
                      ▼
                 Chunker
                      │
                      ▼
             Local Embedding Model (all-MiniLM-L6-v2)
                      │
                      ▼
              Local Vector Store (FAISS IndexFlatIP)
                      │
                      │
User Question ──► Question Embedding
                      │
                      ▼
                Cosine Similarity Search
                      │
                      ▼
                Top-K Chunks (min_similarity filter)
                      │
                      ▼
               Grounded Security Prompt
                      │
                      ▼
                 Local Ollama (http://localhost:11434)
                      │
                      ▼
                Qwen3 1.7B
                      │
                      ▼
              Grounded Academic Answer
                      │
                      ▼
             Source Documents + Page Citations
```

---

## 🚀 What Changed from v1.0

* **v1.0**: Proved basic direct chat connectivity between Python and local Ollama (`qwen3:1.7b`).
* **v1.1**: Implements a complete end-to-end local RAG pipeline:
  1. **Page-Aware PDF Ingestion**: PyMuPDF loader extracts text while retaining original 1-indexed page numbers.
  2. **Academic Chunking**: Paragraph- and sentence-boundary chunking (~500–800 words, ~100-word overlap) without breaking sentences.
  3. **Local CPU Embeddings**: 384-dimensional normalized vectors via Sentence-Transformers (`all-MiniLM-L6-v2`).
  4. **Persistent Local Vector Store**: FAISS `IndexFlatIP` with JSON chunk metadata and SHA-256 duplicate document prevention.
  5. **Filtered Retrieval**: Cosine similarity search with configurable `TOP_K` and `MIN_SIMILARITY` threshold.
  6. **Indirect Prompt Injection Defense**: Treats retrieved context as raw untrusted data inside delimited boundaries.
  7. **Grounded Citations & No-Context Defense**: Explicit source & page citations, returning an explicit message (`"I could not find sufficient information in the uploaded study material."`) rather than hallucinating when no context matches.
  8. **Full UI + CLI Tooling**: Flask web interface with drag-and-drop ingestion, interactive retrieval debugger, chunk inspector, and batch ingestion scripts.

---

## 🧠 Embedding Model vs. Generation Model

| Component | Model | Engine | Purpose |
|---|---|---|---|
| **Embedding Model** | `all-MiniLM-L6-v2` | Sentence-Transformers (CPU) | Converts text chunks and questions into 384-dimensional dense vectors for semantic similarity. |
| **Generation Model** | `qwen3:1.7b` | Ollama (`localhost:11434`) | Synthesizes answers based strictly on retrieved context chunks. |

---

## 💻 Hardware Suitability

Tailored for CPU-only, low-RAM environments (e.g., Intel Core i5-6300U, ~7.4 GB RAM):
* **CPU-optimized PyTorch**: Uses CPU inference wheels to avoid multi-gigabyte GPU bloat.
* **Batch Embedding**: Batches chunk processing to minimize memory pressure.
* **FAISS IndexFlatIP**: Instant, low-footprint vector calculations with zero background daemon overhead.
* **Lightweight LLM**: `qwen3:1.7b` operates smoothly within available system memory.

---

## 📁 Project Structure

```text
StudyRAG/
├── app.py                      # Flask web application entry point
├── requirements.txt            # Minimal, strictly local dependencies
├── README.md                   # Full documentation & architecture
├── .env.example                # Environment variable configuration template
├── .gitignore                  # Git ignore rules for virtualenvs and vector data
│
├── config/
│   ├── __init__.py
│   └── settings.py             # Config defaults, environment loading, directory setup
│
├── core/
│   ├── __init__.py
│   ├── ollama_client.py        # Local Ollama HTTP API client with error handling
│   └── prompts.py              # Grounding prompts & prompt injection defenses
│
├── ingestion/
│   ├── __init__.py
│   ├── pdf_loader.py           # PyMuPDF page-aware loader & SHA-256 hash
│   ├── text_cleaner.py         # Whitespace & line-break normalization
│   └── chunker.py              # Page-aware academic text chunker
│
├── embeddings/
│   ├── __init__.py
│   └── embedder.py             # Sentence-Transformers local embedder
│
├── vectorstore/
│   ├── __init__.py
│   └── local_store.py          # FAISS local vector store & persistence
│
├── retrieval/
│   ├── __init__.py
│   └── retriever.py            # Cosine similarity search & threshold filter
│
├── rag/
│   ├── __init__.py
│   └── pipeline.py             # End-to-end RAG orchestrator & citation builder
│
├── data/
│   ├── documents/              # Stored PDF study documents
│   ├── chunks/                 # Processed chunk cache
│   ├── embeddings/             # Embedding checkpoints
│   └── vector_db/              # FAISS index, metadata, & document registry
│
├── scripts/
│   ├── __init__.py
│   ├── ingest.py               # CLI PDF ingestion tool with duplicate detection
│   ├── inspect_chunks.py       # CLI chunk & document inspector
│   └── test_retrieval.py       # Interactive CLI retrieval debugger
│
├── templates/
│   └── index.html              # Web interface template
│
├── static/
│   ├── css/
│   │   └── style.css           # Modern, responsive stylesheet
│   └── js/
│       └── app.js              # Frontend upload and RAG query interactions
│
└── tests/
    ├── __init__.py
    ├── test_pdf_loader.py      # Unit tests for PyMuPDF extraction & hashing
    ├── test_chunker.py         # Unit tests for text cleaning and chunking
    ├── test_embeddings.py      # Unit tests for embeddings & vector normalization
    └── test_retrieval.py       # Unit tests for FAISS persistence, retrieval, & no-context
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
* Python 3.10+
* Ollama installed and running with `qwen3:1.7b`:
  ```bash
  ollama pull qwen3:1.7b
  ollama serve
  ```

### 2. Setup Virtual Environment
```bash
cd StudyRAG
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 📖 Usage Guide

### Starting the Web UI
```bash
python app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser:
1. **Upload Study PDF**: Drag and drop your academic PDF. The system extracts pages, cleans text, creates chunks, embeds them, and updates the local FAISS index.
2. **Ask Question**: Type your study question (e.g., *"What causes deadlock?"*).
3. **Inspect Grounded Answer & Citations**: View the synthesized answer along with exact document and page citations (e.g., `Operating Systems.pdf — Page 42`).
4. **Inspect Chunks**: Expand the *"Inspect Retrieved Context Chunks"* drawer to review exact excerpts and similarity scores.

---

### Command-Line Tools

#### 1. Ingest PDF Documents
Ingest a specific PDF or scan the entire `data/documents/` folder:
```bash
# Ingest single file
python scripts/ingest.py path/to/Operating_Systems_Notes.pdf

# Or ingest all PDFs in data/documents/
python scripts/ingest.py
```
*Note: Duplicate files with matching SHA-256 hashes are automatically skipped.*

#### 2. Test & Debug Retrieval (Without LLM)
Test semantic retrieval and similarity scores directly:
```bash
python scripts/test_retrieval.py
```
```text
Enter query > deadlock prevention
Retrieved chunks:
[1] Score: 0.8241 | Chunk: os_notes_p0042_c001
    Source: Operating_Systems_Notes.pdf (Page 42)
    Text:
      Deadlock prevention is a set of methods for ensuring that at least one of the necessary conditions cannot hold...
```

#### 3. Inspect Stored Chunks
Inspect chunk quality, word counts, and page mappings:
```bash
python scripts/inspect_chunks.py
```

---

## 🧪 Running Unit Tests

```bash
pytest -v
```

---

## 🔒 Security & Prompt Injection Defenses

* **Untrusted Data Boundary**: All text extracted from PDFs is treated as untrusted data and wrapped in `<retrieved_study_material>` containers.
* **System Prompt Hardening**: Explicit rules command the model to ignore instruction overrides, role-play commands, or system prompt leaks embedded inside PDF text.
* **No-Context Safeguard**: If no retrieved chunk exceeds `MIN_SIMILARITY` (default 0.30), the LLM is not called with empty context; instead, a safe fallback message is returned directly.

*Limitation Note: Prompt engineering reduces risk but does not guarantee 100% defense against sophisticated indirect prompt injection. PDF documents should come from trustworthy academic sources.*
