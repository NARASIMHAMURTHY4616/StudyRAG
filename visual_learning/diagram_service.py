"""Dedicated Diagram Generation Service for StudyRAG V2.2."""

import uuid
import logging
from typing import Dict, Any, List, Optional

from config import settings
from core.ollama_client import OllamaClient
from visual_learning.schemas import (
    VisualArtifact,
    GroundingStatus,
    ValidationStatus,
    ArtifactType,
)
from visual_learning.prompt_templates import build_diagram_prompt, build_repair_prompt
from visual_learning.diagram_validator import DiagramValidator
from visual_learning.storage import VisualStorageManager
from visual_learning.exceptions import DiagramGenerationError

logger = logging.getLogger(__name__)


class DiagramService:
    """
    Orchestrates technical diagram generation using local Ollama model,
    grounding against retrieved study materials, validating Mermaid syntax,
    and persisting visual artifacts.
    """

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        storage_manager: Optional[VisualStorageManager] = None,
    ):
        self.ollama_client = ollama_client or OllamaClient()
        self.storage = storage_manager or VisualStorageManager()
        self.validator = DiagramValidator()

    def generate_diagram(
        self,
        question: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        preferred_diagram_type: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
    ) -> VisualArtifact:
        """
        Generate a validated academic Mermaid diagram grounded in retrieved documents.
        """
        query = question.strip()
        if not query:
            raise ValueError("Diagram request prompt cannot be empty.")

        if len(query) > settings.VISUAL_MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt length ({len(query)}) exceeds maximum allowed ({settings.VISUAL_MAX_PROMPT_LENGTH}).")

        artifact_id = str(uuid.uuid4())

        # Determine Grounding Status and verified sources from actual retrieval
        if retrieved_chunks and len(retrieved_chunks) > 0:
            grounding_status = GroundingStatus.GROUNDED.value
            sources = self._extract_sources(retrieved_chunks)
        else:
            grounding_status = GroundingStatus.GENERAL_KNOWLEDGE.value
            sources = []

        # Construct Grounded Prompt
        prompt = build_diagram_prompt(
            question=query,
            retrieved_chunks=retrieved_chunks,
            preferred_diagram_type=preferred_diagram_type,
        )

        logger.info(f"Generating diagram for query: '{query[:60]}...' (grounding: {grounding_status})")

        # Step 1: Initial Generation
        max_tokens = settings.VISUAL_MAX_OUTPUT_TOKENS
        try:
            raw_response = self.ollama_client.generate(prompt, model=model, max_tokens=max_tokens)
        except Exception as e:
            logger.error(f"Error communicating with Ollama for diagram generation: {e}")
            raise DiagramGenerationError(f"Local AI diagram generation failed: {e}") from e

        # Step 2: Parse Response
        parsed = self.validator.parse_model_response(raw_response)
        mermaid_code = parsed.get("mermaid", "")
        title = parsed.get("title") or f"Diagram: {query[:40]}"
        diagram_type = parsed.get("diagram_type") or "flowchart"
        explanation = parsed.get("explanation") or ""
        parse_error = parsed.get("error")

        # Step 3: Validate Mermaid Syntax
        is_valid, sanitized_mermaid, syntax_errors = self.validator.validate_mermaid_syntax(mermaid_code)
        validation_status = ValidationStatus.VALID.value if is_valid else ValidationStatus.INVALID.value

        # Step 4: Bounded Repair Attempt (Max 1 Retry)
        if not is_valid and mermaid_code:
            logger.warning(f"Mermaid validation failed for '{title}': {syntax_errors}. Initiating bounded repair attempt...")
            repair_prompt = build_repair_prompt(query, mermaid_code, syntax_errors)

            try:
                repair_raw = self.ollama_client.generate(repair_prompt, model=model, max_tokens=max_tokens)
                repair_parsed = self.validator.parse_model_response(repair_raw)
                repaired_code = repair_parsed.get("mermaid", "")

                rep_valid, rep_sanitized, rep_errors = self.validator.validate_mermaid_syntax(repaired_code)
                if rep_valid:
                    logger.info(f"Bounded repair succeeded for diagram '{title}'")
                    sanitized_mermaid = rep_sanitized
                    validation_status = ValidationStatus.REPAIRED.value
                    if repair_parsed.get("explanation"):
                        explanation = repair_parsed.get("explanation")
                    if repair_parsed.get("title"):
                        title = repair_parsed.get("title")
                    syntax_errors = []
                else:
                    logger.warning(f"Bounded repair failed. Syntax errors remain: {rep_errors}")
                    validation_status = ValidationStatus.INVALID.value
                    syntax_errors = rep_errors
            except Exception as repair_err:
                logger.warning(f"Error during diagram repair attempt: {repair_err}")
        elif not is_valid and parse_error:
            if not syntax_errors:
                syntax_errors = [parse_error]

        # Step 5: Construct and Persist Visual Artifact
        artifact = VisualArtifact(
            artifact_id=artifact_id,
            title=title,
            prompt=query,
            artifact_type=ArtifactType.DIAGRAM.value,
            diagram_type=diagram_type,
            mermaid_code=sanitized_mermaid,
            explanation=explanation,
            grounding_status=grounding_status,
            source_references=sources,
            validation_status=validation_status,
            error_message="; ".join(syntax_errors) if validation_status == ValidationStatus.INVALID.value else None,
            metadata={
                "model": model or settings.OLLAMA_MODEL,
                "retrieved_chunks_count": len(retrieved_chunks) if retrieved_chunks else 0,
            },
        )

        # Save to disk
        self.storage.save_artifact(artifact)
        return artifact

    def _extract_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract verified, non-hallucinated source metadata from retrieved chunks."""
        seen = set()
        sources: List[Dict[str, Any]] = []

        for chunk in chunks:
            doc = chunk.get("document_name") or chunk.get("source") or "Document"
            page = chunk.get("page_number") or chunk.get("page") or 1
            score = chunk.get("score")
            key = (str(doc), str(page))

            if key not in seen:
                seen.add(key)
                src_item: Dict[str, Any] = {
                    "document": doc,
                    "page": page,
                }
                if score is not None:
                    src_item["score"] = round(float(score), 4)
                sources.append(src_item)

        return sources
