"""End-to-End RAG Pipeline orchestrating retrieval, grounding, conversation context, and Ollama generation."""

import re
import time
import logging
from typing import Dict, Any, List, Optional, Generator
from config import settings
from core.ollama_client import OllamaClient
from core.prompts import build_rag_prompt, enrich_query_with_history, NO_CONTEXT_MESSAGE
from core.performance import PerformanceTracker
from retrieval.retriever import Retriever

logger = logging.getLogger(__name__)


def detect_conversational_intent(query: str) -> Optional[str]:
    """
    Detect lightweight conversational queries (greetings, acknowledgements, farewells)
    so they are answered immediately without unnecessary vector search.
    """
    q = query.strip().lower()
    q_clean = re.sub(r"[^\w\s]", "", q).strip()

    greetings = ["hi", "hello", "hii", "heyy", "hey", "hola", "greetings", "good morning", "good afternoon", "good evening"]
    if q_clean in greetings:
        return (
            "Hello! 👋 I'm **StudyRAG V2**, your offline academic study assistant.\n\n"
            "I'm ready to answer questions grounded in your uploaded study materials. "
            "Ask me about any concept, algorithm, or topic from your notes!"
        )

    gratitude = ["thanks", "thank you", "thx", "thank you so much", "thanks a lot", "appreciate it"]
    if q_clean in gratitude:
        return "You're very welcome! 😊 Feel free to ask if you need more explanations from your study materials."

    farewells = ["bye", "goodbye", "see you", "cya", "exit"]
    if q_clean in farewells:
        return "Goodbye! 👋 Happy studying, and come back whenever you have questions."

    meta_questions = ["who are you", "what are you", "what can you do", "help me"]
    if q_clean in meta_questions:
        return (
            "I am **StudyRAG V2**, an offline local AI study assistant.\n\n"
            "Here is what I can do for you:\n"
            "- 📄 **Grounded Academic Answers**: Explain concepts strictly from your indexed study PDFs.\n"
            "- 🔍 **Page Citations**: Show verified sources and page numbers for every explanation.\n"
            "- 🧠 **Multi-turn Context**: Answer follow-up questions in the ongoing study session.\n"
            "- 💻 **Code & Diagrams**: Format code blocks with syntax highlighting and render diagrams.\n\n"
            "Ask me anything about your uploaded study materials to get started!"
        )

    return None


def extract_images_from_text(text: str) -> List[str]:
    """Extract Markdown images, HTML images, and inline SVGs from text."""
    if not text:
        return []
    md_images = re.findall(r"!\[.*?\]\((.*?)\)", text)
    html_images = re.findall(r'<img[^>]+src=["\'](.*?)["\']', text, flags=re.IGNORECASE)
    svg_blocks = re.findall(r"(<svg[\s\S]*?<\/svg>)", text, flags=re.IGNORECASE)
    return list(dict.fromkeys(md_images + html_images + svg_blocks))


class RAGPipeline:
    """Offline RAG Pipeline connecting local Retriever with local Ollama LLM."""

    def __init__(
        self,
        retriever: Optional[Retriever] = None,
        ollama_client: Optional[OllamaClient] = None,
        diagram_service: Optional[Any] = None,
    ):
        self.retriever = retriever or Retriever()
        self.ollama_client = ollama_client or OllamaClient()
        self._diagram_service = diagram_service

    @property
    def diagram_service(self):
        """Lazy-loaded DiagramService singleton."""
        if self._diagram_service is None:
            from visual_learning.diagram_service import DiagramService
            self._diagram_service = DiagramService(ollama_client=self.ollama_client)
        return self._diagram_service

    def generate_visual_explanation(
        self,
        question: str,
        preferred_diagram_type: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        top_k: int = settings.TOP_K,
        min_similarity: float = settings.MIN_SIMILARITY,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an educational diagram grounded in retrieved study material passages.
        """
        query = question.strip()
        if not query:
            return {
                "error": "Question is required.",
                "status": "error",
            }

        enriched_search_query = enrich_query_with_history(query, conversation_history)
        retrieved_chunks = self.retriever.retrieve(
            query=enriched_search_query,
            top_k=top_k,
            min_similarity=min_similarity,
        )

        artifact = self.diagram_service.generate_diagram(
            question=query,
            retrieved_chunks=retrieved_chunks,
            preferred_diagram_type=preferred_diagram_type,
            conversation_history=conversation_history,
            model=model,
        )
        return artifact.to_dict()

    def _extract_sources(self, retrieved_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract unique verified source citations from retrieved chunks."""
        unique_sources: List[Dict[str, Any]] = []
        seen = set()
        for chunk in retrieved_chunks:
            doc = chunk.get("document_name") or chunk.get("source")
            page = chunk.get("page_number") or chunk.get("page")
            if doc and (doc, page) not in seen:
                seen.add((doc, page))
                unique_sources.append({
                    "document": doc,
                    "source": doc,
                    "page": page,
                    "page_number": page,
                    "score": chunk.get("score", 0.0),
                })
        return unique_sources

    def answer_question(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        top_k: int = settings.TOP_K,
        min_similarity: float = settings.MIN_SIMILARITY,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute full synchronous RAG flow with conversation context and timing instrumentation.
        """
        perf = PerformanceTracker()
        query = question.strip()
        if not query:
            return {
                "answer": "Please enter a valid question.",
                "sources": [],
                "retrieved_chunks": [],
                "images": [],
                "status": "error",
            }

        # Conversational Intent Check
        conversational_reply = detect_conversational_intent(query)
        if conversational_reply:
            return {
                "answer": conversational_reply,
                "sources": [],
                "retrieved_chunks": [],
                "images": [],
                "status": "conversational",
            }

        logger.info(f"Processing question (Top-K={top_k}, MinSim={min_similarity}): '{query}'")

        # Step 1: Query Enrichment
        enriched_search_query = enrich_query_with_history(query, conversation_history)

        # Step 2: Semantic Retrieval
        perf.start_timer("retrieval")
        retrieved_chunks = self.retriever.retrieve(
            query=enriched_search_query,
            top_k=top_k,
            min_similarity=min_similarity,
        )
        perf.stop_timer("retrieval")
        perf.record_meta("chunks_retrieved", len(retrieved_chunks))

        # Optional debug logging of retrieved chunks
        if settings.DEBUG_RAG:
            for idx, ch in enumerate(retrieved_chunks, start=1):
                preview_str = ch.get('text', '')[:100].replace('\n', ' ')
                logger.info(
                    f"[DEBUG_RAG] Chunk #{idx}: score={ch.get('score')} | "
                    f"doc={ch.get('source')} (p.{ch.get('page')}) | "
                    f"preview={preview_str}"
                )

        # Step 3: No-Context Validation
        if not retrieved_chunks:
            logger.info("No chunks exceeded similarity threshold.")
            perf.log_summary()
            return {
                "answer": NO_CONTEXT_MESSAGE,
                "sources": [],
                "retrieved_chunks": [],
                "images": [],
                "status": "no_context",
            }

        # Step 4: Grounded Prompt Construction
        perf.start_timer("prompt_build")
        prompt = build_rag_prompt(
            question=query,
            retrieved_chunks=retrieved_chunks,
            conversation_history=conversation_history,
        )
        perf.stop_timer("prompt_build")
        perf.record_meta("prompt_chars", len(prompt))

        # Step 5: Local Ollama Generation
        perf.start_timer("ollama_generation")
        try:
            raw_answer = self.ollama_client.generate(prompt, model=model)
            answer = raw_answer if raw_answer.strip() else NO_CONTEXT_MESSAGE
            status = "success"
        except ConnectionError as e:
            logger.error(f"Ollama connection error: {e}")
            return {
                "answer": "Ollama is not running. Please start Ollama (`ollama serve`) and try again.",
                "sources": [],
                "retrieved_chunks": retrieved_chunks,
                "images": [],
                "status": "ollama_error",
            }
        except Exception as e:
            logger.error(f"Error generating answer via Ollama: {e}")
            return {
                "answer": f"Error communicating with local LLM: {e}",
                "sources": [],
                "retrieved_chunks": retrieved_chunks,
                "images": [],
                "status": "ollama_error",
            }
        finally:
            perf.stop_timer("ollama_generation")
            perf.log_summary()

        # Step 6: Extract unique source citations & detected images
        unique_sources = self._extract_sources(retrieved_chunks)
        images = extract_images_from_text(answer)

        return {
            "answer": answer,
            "sources": unique_sources,
            "retrieved_chunks": retrieved_chunks,
            "images": images,
            "status": status,
            "perf_metrics": perf.to_dict(),
        }

    def answer_question_stream(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        top_k: int = settings.TOP_K,
        min_similarity: float = settings.MIN_SIMILARITY,
        model: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Execute streaming RAG flow yielding events:
        1. {"event": "retrieval", "retrieved_chunks": [...], "sources": [...]}
        2. {"event": "token", "token": "..."}
        3. {"event": "done", "answer": "...", "sources": [...], "images": [...], "status": "success"}
        """
        perf = PerformanceTracker()
        query = question.strip()
        if not query:
            yield {
                "event": "error",
                "answer": "Please enter a valid question.",
                "sources": [],
                "retrieved_chunks": [],
                "images": [],
            }
            return

        # Conversational Intent Check
        conversational_reply = detect_conversational_intent(query)
        if conversational_reply:
            yield {"event": "retrieval", "retrieved_chunks": [], "sources": []}
            yield {"event": "token", "token": conversational_reply}
            yield {
                "event": "done",
                "answer": conversational_reply,
                "sources": [],
                "retrieved_chunks": [],
                "images": [],
                "status": "conversational",
            }
            return

        # Step 1: Query Enrichment
        enriched_search_query = enrich_query_with_history(query, conversation_history)

        # Step 2: Semantic Retrieval
        perf.start_timer("retrieval")
        retrieved_chunks = self.retriever.retrieve(
            query=enriched_search_query,
            top_k=top_k,
            min_similarity=min_similarity,
        )
        perf.stop_timer("retrieval")
        sources = self._extract_sources(retrieved_chunks)
        perf.record_meta("chunks_retrieved", len(retrieved_chunks))

        # Optional debug logging
        if settings.DEBUG_RAG:
            for idx, ch in enumerate(retrieved_chunks, start=1):
                preview_str = ch.get('text', '')[:100].replace('\n', ' ')
                logger.info(
                    f"[DEBUG_RAG] Chunk #{idx}: score={ch.get('score')} | "
                    f"doc={ch.get('source')} (p.{ch.get('page')}) | "
                    f"preview={preview_str}"
                )

        # Emit retrieval event early so UI displays source documents immediately
        yield {
            "event": "retrieval",
            "retrieved_chunks": retrieved_chunks,
            "sources": sources,
        }

        # Step 3: Handle No-Context
        if not retrieved_chunks:
            yield {"event": "token", "token": NO_CONTEXT_MESSAGE}
            yield {
                "event": "done",
                "answer": NO_CONTEXT_MESSAGE,
                "sources": [],
                "retrieved_chunks": [],
                "images": [],
                "status": "no_context",
            }
            perf.log_summary()
            return

        # Step 4: Build Prompt with context budgeting
        perf.start_timer("prompt_build")
        prompt = build_rag_prompt(
            question=query,
            retrieved_chunks=retrieved_chunks,
            conversation_history=conversation_history,
        )
        perf.stop_timer("prompt_build")
        perf.record_meta("prompt_chars", len(prompt))

        # Step 5: Stream Tokens from Ollama
        full_tokens = []
        perf.start_timer("ollama_streaming")
        first_token_seen = False

        try:
            for token in self.ollama_client.generate_stream(prompt, model=model):
                if not first_token_seen:
                    first_token_seen = True
                    perf.record_metric("ttft_approx", perf.get_total_elapsed())
                full_tokens.append(token)
                yield {"event": "token", "token": token}
        except ConnectionError:
            err_msg = "Ollama is not running. Please start Ollama (`ollama serve`) and try again."
            yield {"event": "token", "token": err_msg}
            yield {
                "event": "done",
                "answer": err_msg,
                "sources": [],
                "retrieved_chunks": retrieved_chunks,
                "images": [],
                "status": "ollama_error",
            }
            return
        except Exception as e:
            err_msg = f"\n\n[Error communicating with local LLM: {e}]"
            yield {"event": "token", "token": err_msg}
            yield {
                "event": "done",
                "answer": "".join(full_tokens) + err_msg,
                "sources": sources,
                "retrieved_chunks": retrieved_chunks,
                "images": [],
                "status": "ollama_error",
            }
            return
        finally:
            perf.stop_timer("ollama_streaming")
            perf.log_summary()

        complete_answer = "".join(full_tokens).strip() or NO_CONTEXT_MESSAGE
        images = extract_images_from_text(complete_answer)

        yield {
            "event": "done",
            "answer": complete_answer,
            "sources": sources,
            "retrieved_chunks": retrieved_chunks,
            "images": images,
            "status": "success",
        }
