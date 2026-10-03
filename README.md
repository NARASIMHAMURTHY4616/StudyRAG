# StudyRAG v2.2 — Local Offline Study Assistant & Visual Learning Engine

**StudyRAG v2.2** is an offline-first, local Retrieval-Augmented Generation (RAG) system engineered for university students and academic researchers. It combines accurate document-grounded text answers with an integrated **Visual Learning Engine** that generates technically accurate Mermaid diagrams and educational illustrations using local AI—with zero reliance on cloud APIs or public CDNs.

---

## 🏗️ Architecture Diagram

```text
                                STUDYRAG v2.2
                        
  Uploaded Academic PDF ──► PyMuPDF Page-Aware Loader
                                    │
                                    ▼
                             Text Chunker (~3 chunks/page)
                                    │
                                    ▼
                   Sentence-Transformers (all-MiniLM-L6-v2)
                                    │
                                    ▼
                    FAISS Local Vector Store (IndexFlatIP)
                                    │
                                    ├──────────────────────────┐
                                    ▼                          ▼
                          Text RAG Stream             Visual Learning Engine
                                    │                          │
                                    ▼                          ▼
   User Question / ──► Semantic Cosine Retrieval ──► Grounded Diagram Prompt
   Diagram Request                  │                          │
                                    ▼                          ▼
                          Grounded Prompt          Local Ollama (Qwen3:1.7B)
                                    │                          │
                                    ▼                          ▼
                       Local Ollama Generation      Diagram Validator & Repair
                                    │                          │
                                    ▼                          ▼
                       Streaming Academic Answer    Validated Mermaid AST & SVG
                                    │                          │
                                    └────────────┬─────────────┘
                                                 ▼
                                     Web UI / Terminal / Export
                             (Interactive Mermaid, Citations, SVG/PNG)
```

---

## 🚀 What's New in V2.2: Visual Learning Engine

1. **Intelligent Diagram Generation (Objective A)**:
   - Request diagrams for university computer science and academic concepts:
     - **Protocols & Networks**: TCP 3-way handshake, OSI model layers, DNS lookup flow (`sequenceDiagram`).
     - **Operating Systems**: Process lifecycle & state transitions, CPU scheduling queues, deadlock conditions (`stateDiagram-v2`, `flowchart`).
     - **Automata & Compilers**: DFA/NFA state-transition machines, compiler pipeline phases (`stateDiagram-v2`, `flowchart`).
     - **Databases & Architecture**: Relational schemas, ER diagrams, Cloud/IoT microservices (`erDiagram`, `flowchart`).
     - **Cybersecurity & AI**: Safe educational attack/defense lifecycles, ML/RAG pipelines (`flowchart`).

2. **RAG-Grounded Visual Explanations (Objective B)**:
   - When study materials match the query, diagrams are generated using exact technical passages and labeled as **"📄 Grounded in Study Material"** with verified document & page citations.
   - When no study materials match, diagrams are generated from foundational curriculum knowledge and labeled as **"🌐 General Academic Knowledge"**.
   - Citations are strictly extracted from verified retrieval chunks and never fabricated by the model.

3. **100% Offline Local Mermaid Rendering (Objective D & E)**:
   - Vendored, MIT-licensed Mermaid.js (`v10.9.1`) served locally—zero CDN dependencies.
   - Runs in strict security mode (`securityLevel: 'strict'`), disabling unsafe HTML execution or scripts.
   - Bounded syntax validator with automatic single-pass repair if the local model outputs malformed syntax.

4. **Diagram Export & Interactive Viewing**:
   - One-click **SVG download** (sanitized server-side) and high-DPI **PNG download** (client-side canvas).
   - One-click **Copy Mermaid code** for use in reports or Markdown notes.
   - Fullscreen **Lightbox Viewer** with zoom-in (+), zoom-out (-), and reset controls.

5. **Optional AI Illustration Abstraction (Objective C)**:
   - Decoupled `ImageGenerationBackend` interface supporting local text-to-image backends (`Diffusers`, `ComfyUI`).
   - Disabled by default with honest diagnostic reporting (`GET /api/visualize/status`).
   - Does not treat text LLMs (`qwen3:1.7b`) as image models and does not download multi-gigabyte models automatically.

6. **Hardware Efficiency**:
   - Operates comfortably on modest hardware (e.g., Intel Core i5-6300U, 8 GB RAM, Integrated GPU).
   - Diagram generation requires zero GPU and adds no second large language model.

---

## 🧠 Model Architecture & Component Roles

| Component | Model / Engine | Host / Location | Purpose |
|---|---|---|---|
| **Embedding Engine** | `all-MiniLM-L6-v2` | Sentence-Transformers (CPU) | Vectorizes chunks and queries into 384-dimensional normalized dense vectors. |
| **Vector Store** | FAISS `IndexFlatIP` | Local Disk (`data/vector_db/`) | High-speed local cosine similarity indexing with SHA-256 duplicate detection. |
| **Generation Model** | `qwen3:1.7b` | Ollama (`http://localhost:11434`) | Generates grounded explanations and Mermaid diagram ASTs. |
| **Visual Renderer** | Mermaid.js `10.9.1` | Local Static Asset (`static/vendor/`) | Client-side strict-mode SVG rendering. |
| **Conversation Store** | MongoDB / Memory | `localhost:27017` / RAM Cache | Stores multi-turn chat threads, diagram artifacts, and citations. |

---

## 📁 Project Structure

```text
StudyRAG/
├── app.py                      # Flask web application entry point with V2.2 visual routes
├── requirements.txt            # Minimal local dependencies
├── README.md                   # Complete documentation
├── .env.example                # Environment variable configuration template
│
├── config/
│   └── settings.py             # Config defaults, visual learning toggles, and directories
│
├── visual_learning/            # Visual Learning Engine Package (V2.2)
│   ├── __init__.py
│   ├── schemas.py              # VisualArtifact, GroundingStatus, ValidationStatus dataclasses
│   ├── exceptions.py           # Custom visual learning exception hierarchy
│   ├── prompt_templates.py     # Diagram generation & bounded repair prompts
│   ├── diagram_validator.py    # AST syntax validation, fence stripping, & sanitization
│   ├── diagram_service.py      # Diagram generation orchestrator & RAG grounding
│   ├── storage.py              # Visual artifact persistence, SVG sanitization, path security
│   ├── image_backends.py       # Extensible image generation backend abstractions
│   └── image_service.py        # Educational illustration service layer
│
├── core/
│   ├── ollama_client.py        # Local Ollama HTTP client with streaming & lock
│   ├── prompts.py              # Grounding prompts & context budgeting
│   └── performance.py          # Latency, TTFT, and metric tracking
│
├── ingestion/
│   ├── pdf_loader.py           # PyMuPDF page-aware loader & SHA-256 hashing
│   ├── text_cleaner.py         # Whitespace normalization
│   └── chunker.py              # Academic chunking (~3 chunks/page)
│
├── embeddings/
│   └── embedder.py             # Sentence-Transformers local embedder
│
├── vectorstore/
│   └── local_store.py          # FAISS local vector store & persistence
│
├── retrieval/
│   └── retriever.py            # Cosine similarity search & threshold filtering
│
├── rag/
│   └── pipeline.py             # End-to-end RAG & visual explanation orchestrator
│
├── database/
│   ├── mongo.py                # MongoDB connection manager with auto-reconnect
│   └── conversations.py        # Multi-turn conversation lifecycle & memory fallback
│
├── static/
│   ├── css/style.css           # Modern ChatGPT-style stylesheet with diagram card UI
│   ├── js/app.js               # Frontend controller, Mermaid rendering, SVG/PNG export
│   └── vendor/                 # 100% Offline Local Libraries (Zero CDN)
│       ├── mermaid/            # Mermaid.js (v10.9.1, MIT)
│       ├── marked/             # Marked.js (v12.0.2, MIT)
│       └── highlight/          # Highlight.js (v11.9.0, BSD-3)
│
├── data/
│   ├── documents/              # Stored PDF study documents
│   ├── vector_db/              # FAISS index, metadata, & registry
│   └── generated_visuals/      # Saved diagram artifacts and exported SVGs
│
└── tests/                      # Comprehensive Unit & Integration Test Suite (61 tests)
    ├── test_diagram_validator.py
    ├── test_diagram_service.py
    ├── test_visual_storage.py
    ├── test_image_service.py
    ├── test_visual_learning_routes.py
    ├── test_visual_rag_integration.py
    ├── test_chat_stream.py
    ├── test_chunker.py
    ├── test_embedder.py
    ├── test_embeddings.py
    ├── test_mongo.py
    ├── test_ollama_client.py
    ├── test_pdf_loader.py
    ├── test_performance.py
    ├── test_pipeline.py
    ├── test_prompt_builder.py
    └── test_retrieval.py
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
* Python 3.10+
* Ollama installed with `qwen3:1.7b`:
  ```bash
  ollama pull qwen3:1.7b
  ollama serve
  ```
* (Optional) MongoDB for persistent conversation storage:
  ```bash
  sudo systemctl start mongod
  ```
  *Note: If MongoDB is not running, StudyRAG operates seamlessly using an in-memory conversation cache.*

### 2. Virtual Environment & Dependencies
```bash
cd StudyRAG
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 📖 Usage Guide

### Starting the Web Interface
```bash
python app.py -w
```
Open [http://localhost:5000](http://localhost:5000) in your browser:
1. **Upload Study PDF**: Drag and drop course PDFs (e.g., `Operating_Systems_Notes.pdf`).
2. **Request Technical Diagrams**:
   - Click the **"Diagram Mode"** button or ask naturally:
     - *"Diagram the TCP three-way handshake and connection teardown"*
     - *"Create a state transition diagram of OS process states"*
     - *"Show a flowchart of CPU Round Robin scheduling"*
3. **Inspect Grounded Citations**: Review exact document and page references (e.g. `OS_Notes.pdf — Page 42`).
4. **Export & View**:
   - Click **SVG** to download clean vector graphics.
   - Click **PNG** for raster images.
   - Click **Fullscreen** to zoom and inspect intricate architectures.
   - Click **Copy Code** to copy raw Mermaid definition.

---

## ⚙️ Configuration Settings

Configure runtime behavior via `.env` or environment variables:

| Setting | Default | Description |
|---|---|---|
| `VISUAL_LEARNING_ENABLED` | `true` | Enables/disables diagram generation routes and UI controls. |
| `VISUAL_IMAGE_GENERATION_ENABLED` | `false` | Enables optional text-to-image AI backends. |
| `IMAGE_GENERATION_BACKEND` | `none` | Active image backend (`none`, `diffusers`). |
| `OLLAMA_MODEL` | `qwen3:1.7b` | Local text LLM for answer synthesis and diagram ASTs. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama HTTP endpoint. |
| `TOP_K` | `4` | Number of relevant chunks retrieved per query. |
| `MIN_SIMILARITY` | `0.25` | Minimum cosine similarity threshold. |
| `GENERATED_VISUALS_DIR` | `data/generated_visuals`| Directory for stored diagram artifacts and SVGs. |

---

## 🧪 Running the Test Suite

Execute the complete 61-test verification suite:
```bash
pytest -v
```

All 61 tests run offline using mocks for Ollama and isolated temporary directories for FAISS/artifacts without requiring GPU or internet access.

---

## 🔒 Security Architecture

1. **Strict Mermaid Sandbox**: Mermaid operates in `securityLevel: 'strict'`, stripping `<script>`, `<iframe>`, `onload`, `onerror`, and inline javascript URIs.
2. **Path Traversal Defense**: All artifact IDs and export filenames are strictly validated against `^[a-zA-Z0-9_-]{8,64}$` and resolved using strict relative subpath verification.
3. **Indirect Prompt Injection Defense**: Retrieved study material is enclosed in strict context delimiters, preventing document text from executing commands or overriding system instructions.
4. **Zero Cloud Inference**: 100% of embeddings, retrieval, LLM generation, AST parsing, and diagram rendering execute locally.

---

## 📋 Changelog — V2.2

* **Visual Learning Engine**: Integrated dedicated `DiagramService`, `DiagramValidator`, `VisualStorageManager`, and `ImageService`.
* **RAG-Grounded Visuals**: Grounding status classification (`grounded` vs `general_knowledge`) with citation integrity.
* **Mermaid Local Vendoring**: Local vendoring of Mermaid.js `v10.9.1`, Marked.js, and Highlight.js for true offline usage without CDNs.
* **Interactive Diagram UI**: Fullscreen modal viewer, SVG/PNG export, copy code, and grounding badges.
* **Bounded Repair Engine**: Automatic one-pass repair loop for invalid Mermaid syntax.
* **Test Suite Expansion**: Added 28 new tests covering validators, diagram generation, SVG sanitization, storage security, RAG integration, and visual API routes (61 total passing tests).
