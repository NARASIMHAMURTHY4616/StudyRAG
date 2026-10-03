"""Prompt templates for Technical Diagram Generation and Mermaid Repair."""

from typing import List, Dict, Any, Optional

DIAGRAM_SYSTEM_PROMPT = """You are StudyRAG V2.2's Visual Learning Engine, an expert university-level computer science, engineering, and academic visual educator.

Your task is to generate technically accurate, clean, and locally renderable Mermaid diagrams along with a clear academic explanation.

RULES FOR MERMAID DIAGRAMS:
1. Always choose the most semantically appropriate Mermaid diagram type:
   - Protocols, network handshakes (e.g. TCP 3-way handshake, TLS, OAuth, Authentication): Use `sequenceDiagram`.
   - Process states, DFA/NFA automata, compiler lexical/syntax phases, lifecycle workflows: Use `stateDiagram-v2`.
   - Workflows, architectures, data structures, algorithms, databases, CPU scheduling, ML/RAG pipelines, cyber defense: Use `flowchart TD` or `flowchart LR`.
   - Entity Relationships, relational database schemas: Use `erDiagram`.
   - Object-oriented classes, design patterns: Use `classDiagram`.
2. STRICT SYNTAX REQUIREMENTS:
   - Use clean, standard alphanumeric node IDs without special characters (e.g. `A[Client] -->|SYN| B[Server]`).
   - For labels with spaces or punctuation, enclose them in square brackets `["..."]` or parentheses `("...")`.
   - NEVER use raw `<` or `>` or unescaped quotes inside node text.
   - Do NOT include HTML tags (like `<br>`, `<script>`, `<div>`) or JavaScript inside Mermaid node labels.
   - Ensure all subgraphs, blocks, and quotes are properly closed.
3. OUTPUT FORMAT:
   Return ONLY a valid JSON object matching this exact schema:
   {
     "title": "Short descriptive diagram title",
     "diagram_type": "flowchart | sequenceDiagram | stateDiagram-v2 | classDiagram | erDiagram",
     "explanation": "Clear, step-by-step academic explanation of the visual components and process flow.",
     "mermaid": "The exact valid Mermaid diagram code"
   }
"""


def build_diagram_prompt(
    question: str,
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
    preferred_diagram_type: Optional[str] = None,
    complexity: Optional[str] = "standard",
) -> str:
    """
    Build structured prompt for the LLM to generate a technical diagram.
    Integrates retrieved study material chunks for grounding when available.
    """
    sections: List[str] = [DIAGRAM_SYSTEM_PROMPT.strip()]

    # If preferred diagram type is specified
    if preferred_diagram_type:
        sections.append(f"Student requested diagram format: {preferred_diagram_type}")

    # Grounding study material section
    if retrieved_chunks and len(retrieved_chunks) > 0:
        context_blocks = []
        for idx, chunk in enumerate(retrieved_chunks[:4], start=1):
            source = chunk.get("document_name") or chunk.get("source", "Document")
            page = chunk.get("page_number") or chunk.get("page", "?")
            text = (chunk.get("chunk_text") or chunk.get("text", "")).strip()
            if text:
                context_blocks.append(f"[Source {idx}] {source} (Page {page}):\n{text}")

        if context_blocks:
            sections.append(
                "Grounding Study Materials (Use these technical details to construct the diagram):\n"
                + "\n\n".join(context_blocks)
            )
    else:
        sections.append(
            "Note: No specific textbook passages matched this query. Generate an accurate academic diagram based on foundational university curriculum knowledge."
        )

    sections.append(
        f"Topic / Academic Concept to Visualize:\n{question}\n\nJSON Response (title, diagram_type, explanation, mermaid):"
    )

    return "\n\n".join(sections)


def build_repair_prompt(
    original_prompt: str,
    invalid_mermaid: str,
    syntax_errors: List[str],
) -> str:
    """
    Build bounded repair prompt when generated Mermaid code has syntax errors.
    """
    error_summary = "\n- ".join(syntax_errors) if syntax_errors else "Invalid syntax or unclosed delimiters."
    return f"""The previous Mermaid diagram generated for the topic had syntax errors.
Please fix the Mermaid syntax errors and return ONLY the corrected JSON object.

Topic: {original_prompt}

Invalid Mermaid Code:
```mermaid
{invalid_mermaid}
```

Detected Syntax Issues:
- {error_summary}

Instructions for Fix:
1. Ensure the first line is a valid declaration header (e.g. `flowchart TD`, `sequenceDiagram`, `stateDiagram-v2`).
2. Fix all unclosed brackets, parentheses, quotes, or invalid arrow types.
3. Ensure all node labels avoid unescaped HTML characters or raw angle brackets.
4. Return ONLY the valid JSON object:
{{"title": "...", "diagram_type": "...", "explanation": "...", "mermaid": "..."}}
"""
