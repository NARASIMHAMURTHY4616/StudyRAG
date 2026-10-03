"""Grounded RAG Prompts and formatting with context budgeting for CPU inference."""

import re
import logging
from typing import List, Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)

NO_CONTEXT_MESSAGE = "I could not find sufficient information in the uploaded study material."

SYSTEM_PROMPT = """You are StudyRAG V2, an intelligent offline academic study assistant.

Instructions:
- Provide a clear, structured, and accurate academic answer grounded in the provided Study Material.
- Use clear Markdown with headings, bullet points, and bold key concepts.
- When referencing facts, mention the document name and page number from the context.
- Keep the explanation direct, comprehensive, and focused without unnecessary preamble.
- If the study material does not contain the answer, state: "I could not find sufficient information in the uploaded study material."
"""


def enrich_query_with_history(query: str, history: Optional[List[Dict[str, Any]]]) -> str:
    """
    Enrich short follow-up queries with recent conversational subject to ensure
    accurate vector retrieval (e.g. 'what are the four conditions?' -> 'deadlock four conditions').
    """
    if not history or len(history) < 1:
        return query

    query_clean = query.strip().lower()
    follow_up_triggers = [
        "second", "third", "fourth", "first", "last", "condition", "algorithm",
        "example", "why", "how", "what about", "explain more", "elaborate",
        "difference", "contrast", "advantage", "disadvantage", "pros", "cons",
        "prevent", "avoid", "detection", "recovery", "them"
    ]

    is_short_follow_up = len(query.split()) <= 7 and any(t in query_clean for t in follow_up_triggers)

    if is_short_follow_up:
        # Find last user question
        for prev_msg in reversed(history):
            if prev_msg.get("role") == "user" and prev_msg.get("content"):
                prev_text = prev_msg.get("content", "").strip()
                prev_keywords = re.sub(
                    r"^(what is|explain|tell me about|how to|describe|what are)\s+",
                    "",
                    prev_text,
                    flags=re.IGNORECASE,
                ).strip()
                if prev_keywords:
                    return f"{prev_keywords} {query}"

    return query


def build_rag_prompt(
    question: str,
    retrieved_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    max_history_turns: int = settings.MAX_HISTORY_MESSAGES,
    max_context_chars: int = settings.MAX_CONTEXT_CHARS,
) -> str:
    """
    Format complete grounded prompt combining:
    1. System Instructions
    2. Recent Conversation History (trimmed to budget)
    3. Retrieved Study Material Chunks (budgeted without splitting chunks mid-text)
    4. Current User Question
    """
    sections: List[str] = [SYSTEM_PROMPT.strip()]

    # Include recent conversation context if present
    history_chars = 0
    if conversation_history:
        recent_msgs = [
            m for m in conversation_history
            if m.get("role") in ("user", "assistant") and m.get("content")
        ][-max_history_turns:]

        if recent_msgs:
            history_blocks = []
            for msg in recent_msgs:
                role_label = "Student" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "").strip()
                if len(content) > 300:
                    content = content[:300] + "..."
                history_blocks.append(f"{role_label}: {content}")

            history_text = "Recent Conversation History:\n" + "\n".join(history_blocks)
            history_chars = len(history_text)
            sections.append(history_text)

    # Grounding Study Material Chunks with Context Budgeting
    context_chars = 0
    selected_chunks_count = 0
    if not retrieved_chunks:
        sections.append("Study Material:\n(No relevant documents found)")
    else:
        context_blocks = []
        accumulated_chars = 0
        seen_texts = set()

        for idx, chunk in enumerate(retrieved_chunks, start=1):
            source = chunk.get("document_name") or chunk.get("source", "Unknown Document")
            page = chunk.get("page_number") or chunk.get("page", "?")
            text = (chunk.get("chunk_text") or chunk.get("text", "")).strip()

            # Deduplicate exact chunk texts within same doc/page
            norm_text = " ".join(text.split())
            dedup_key = (str(source), str(page), norm_text)
            if dedup_key in seen_texts:
                continue
            seen_texts.add(dedup_key)

            block = f"[Source {len(context_blocks) + 1}]\nDocument: {source} (Page {page})\nPage: {page}\nContent:\n{text}"
            block_len = len(block)

            # Check context budget: do not split chunks mid-text if avoidable
            if accumulated_chars + block_len > max_context_chars and len(context_blocks) > 0:
                logger.debug(f"Reached context budget ({accumulated_chars}/{max_context_chars} chars). Stopping at {len(context_blocks)} chunks.")
                break

            context_blocks.append(block)
            accumulated_chars += block_len
            selected_chunks_count += 1

        context_section = "Study Material (Retrieved Context):\n" + "\n\n".join(context_blocks)
        context_chars = len(context_section)
        sections.append(context_section)

    user_section = f"Current Question:\n{question}\n\nAcademic Answer:"
    sections.append(user_section)

    final_prompt = "\n\n".join(sections)

    # Log statistics without exposing full prompt
    logger.info(
        f"RAG prompt statistics: chunks_used={selected_chunks_count}/{len(retrieved_chunks)} | "
        f"context_chars={context_chars} | history_chars={history_chars} | "
        f"question_chars={len(question)} | total_prompt_chars={len(final_prompt)}"
    )

    return final_prompt
