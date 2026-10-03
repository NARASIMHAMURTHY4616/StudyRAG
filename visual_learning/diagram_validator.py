"""Validation, sanitization, and parsing for model-generated Mermaid diagrams."""

import re
import json
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

# Allowlisted Mermaid diagram types
ALLOWED_DIAGRAM_TYPES = {
    "flowchart",
    "graph",
    "sequencediagram",
    "statediagram",
    "statediagram-v2",
    "classdiagram",
    "erdiagram",
    "gitgraph",
    "journey",
    "mindmap",
    "quadrantchart",
    "pie",
    "timeline",
    "architecture-beta",
    "packet-beta",
}

# Resource limits for modest CPU hardware
MAX_MERMAID_LINES = 150
MAX_MERMAID_CHARS = 6000
MAX_NODES_ESTIMATE = 80


class DiagramValidator:
    """Validates, sanitizes, and repairs Mermaid diagram syntax and structures."""

    @staticmethod
    def strip_markdown_fences(text: str) -> str:
        """Strip markdown code fences (```json, ```mermaid, etc.) from raw model response."""
        if not text:
            return ""
        
        cleaned = text.strip()
        # Remove opening ```json or ```mermaid or ```
        cleaned = re.sub(r"^```(?:json|mermaid|text)?\s*\n?", "", cleaned, flags=re.IGNORECASE)
        # Remove closing ```
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def sanitize_mermaid_text(mermaid_code: str) -> str:
        """
        Sanitize Mermaid definition to prevent XSS, active script injection,
        or malformed HTML tags inside node text.
        """
        if not mermaid_code:
            return ""

        # Remove dangerous tags & attributes
        sanitized = re.sub(r"<\s*script[^>]*>[\s\S]*?<\s*/\s*script\s*>", "", mermaid_code, flags=re.IGNORECASE)
        sanitized = re.sub(r"<\s*iframe[^>]*>[\s\S]*?<\s*/\s*iframe\s*>", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"on\w+\s*=\s*[\"'][^\"']*[\"']", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"javascript\s*:", "", sanitized, flags=re.IGNORECASE)

        # Normalize windows line endings
        sanitized = sanitized.replace("\r\n", "\n").strip()
        return sanitized

    @staticmethod
    def normalize_mermaid_source(mermaid_code: str) -> str:
        """Normalize Mermaid source string, strip fences, and unescape escaped newlines."""
        if not mermaid_code:
            return ""
        
        code = DiagramValidator.strip_markdown_fences(mermaid_code).strip()
        
        # If the string contains literal escaped newlines (e.g. \\n) but few or no actual newlines
        if "\\n" in code and ("\n" not in code or code.count("\\n") > code.count("\n")):
            try:
                # Safely replace escaped newlines and tabs
                code = code.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
            except Exception:
                pass
                
        return code.strip()

    @staticmethod
    def parse_model_response(raw_text: str) -> Dict[str, Any]:
        """
        Parse model output into structured dictionary: title, diagram_type, explanation, mermaid.
        Handles pure JSON, fenced JSON, truncated JSON regex extraction, or raw markdown Mermaid fallback.
        """
        if not raw_text or not raw_text.strip():
            return {
                "title": "Educational Diagram",
                "diagram_type": "flowchart",
                "explanation": "",
                "mermaid": "",
                "is_parsed": False,
                "error": "Empty response received from local model.",
            }

        unfenced = DiagramValidator.strip_markdown_fences(raw_text)

        # 1. Try standard JSON parsing
        try:
            json_match = re.search(r"\{[\s\S]*\}", unfenced)
            candidate_json = json_match.group(0) if json_match else unfenced
            data = json.loads(candidate_json)

            if isinstance(data, dict):
                mermaid_raw = data.get("mermaid") or data.get("diagram") or data.get("code") or ""
                mermaid_code = DiagramValidator.normalize_mermaid_source(str(mermaid_raw))
                explanation = str(data.get("explanation") or "").strip()
                title = str(data.get("title") or "Educational Diagram").strip()
                diag_type = str(data.get("diagram_type") or "flowchart").strip()

                return {
                    "title": title,
                    "diagram_type": diag_type,
                    "explanation": explanation,
                    "mermaid": mermaid_code,
                    "is_parsed": bool(mermaid_code),
                    "error": None if mermaid_code else "Mermaid diagram code is empty in model response.",
                }
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. Try Regex Extraction for embedded JSON fields (handles truncated / unclosed JSON)
        title_m = re.search(r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', raw_text)
        type_m = re.search(r'"diagram_type"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', raw_text)
        expl_m = re.search(r'"explanation"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', raw_text)
        mermaid_m = re.search(r'"mermaid"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)', raw_text)

        if mermaid_m and mermaid_m.group(1).strip():
            raw_val = mermaid_m.group(1).strip()
            # If it had an unescaped trailing quote or escaped chars, normalize
            raw_val = raw_val.rstrip('"')
            try:
                extracted_mermaid = json.loads(f'"{raw_val}"')
            except Exception:
                extracted_mermaid = raw_val.replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t")

            extracted_mermaid = DiagramValidator.normalize_mermaid_source(extracted_mermaid)
            if extracted_mermaid:
                title = title_m.group(1).rstrip('"') if title_m else "Educational Diagram"
                diag_type = type_m.group(1).rstrip('"') if type_m else (DiagramValidator.detect_diagram_type(extracted_mermaid) or "flowchart")
                explanation = ""
                if expl_m:
                    expl_val = expl_m.group(1).rstrip('"')
                    try:
                        explanation = json.loads(f'"{expl_val}"')
                    except Exception:
                        explanation = expl_val.replace("\\n", "\n").replace('\\"', '"')

                return {
                    "title": title.strip(),
                    "diagram_type": diag_type.strip(),
                    "explanation": explanation.strip(),
                    "mermaid": extracted_mermaid,
                    "is_parsed": True,
                    "error": None,
                }

        # 3. Fallback: Extract Mermaid block directly from text if model answered in markdown
        mermaid_match = re.search(r"```(?:mermaid)?\s*\n([\s\S]+?)\n```", raw_text, flags=re.IGNORECASE)
        if mermaid_match:
            mermaid_code = DiagramValidator.normalize_mermaid_source(mermaid_match.group(1))
            explanation = raw_text.replace(mermaid_match.group(0), "").strip()
            # Clean explanation if it contains json-like remnants
            if explanation.startswith("{") and explanation.endswith("}"):
                explanation = ""

            return {
                "title": "Educational Diagram",
                "diagram_type": DiagramValidator.detect_diagram_type(mermaid_code) or "flowchart",
                "explanation": explanation,
                "mermaid": mermaid_code,
                "is_parsed": True,
                "error": None,
            }

        # 4. Direct Mermaid string detection (starts with flowchart/sequenceDiagram etc.)
        detected_type = DiagramValidator.detect_diagram_type(unfenced)
        if detected_type:
            return {
                "title": "Educational Diagram",
                "diagram_type": detected_type,
                "explanation": "",
                "mermaid": DiagramValidator.normalize_mermaid_source(unfenced),
                "is_parsed": True,
                "error": None,
            }

        # 5. Failed Parsing: Never expose raw JSON dump as the user-facing explanation
        is_json_like = bool(re.search(r'^\s*\{|\"mermaid\"\s*:', raw_text))
        safe_explanation = "" if is_json_like else raw_text.strip()

        return {
            "title": "Educational Diagram",
            "diagram_type": "flowchart",
            "explanation": safe_explanation,
            "mermaid": "",
            "is_parsed": False,
            "error": "Could not parse valid Mermaid diagram structure from model response.",
        }

    @staticmethod
    def detect_diagram_type(mermaid_code: str) -> Optional[str]:
        """Detect the header diagram type from the first non-comment line."""
        if not mermaid_code:
            return None

        for line in mermaid_code.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("%%"):
                continue

            first_word = line.split()[0].lower()
            if first_word in ALLOWED_DIAGRAM_TYPES:
                return first_word
            if "sequence" in line.lower():
                return "sequenceDiagram"
            if "state" in line.lower():
                return "stateDiagram-v2"
            if "erdiagram" in line.lower():
                return "erDiagram"
            if "classdiagram" in line.lower():
                return "classDiagram"
            if "flowchart" in line.lower() or "graph" in line.lower():
                return "flowchart"
            break
        return None

    @classmethod
    def validate_mermaid_syntax(cls, mermaid_code: str) -> Tuple[bool, str, List[str]]:
        """
        Validate Mermaid definition syntax, balance, limits, and allowlist.
        Returns: (is_valid, sanitized_code, errors)
        """
        errors: List[str] = []

        if not mermaid_code or not mermaid_code.strip():
            return False, "", ["Mermaid definition is empty."]

        sanitized = cls.sanitize_mermaid_text(mermaid_code)

        # Length and line limit checks
        if len(sanitized) > MAX_MERMAID_CHARS:
            errors.append(f"Diagram length exceeds safe limit ({len(sanitized)} > {MAX_MERMAID_CHARS} chars).")

        lines = [l for l in sanitized.split("\n") if l.strip()]
        if len(lines) > MAX_MERMAID_LINES:
            errors.append(f"Diagram line count exceeds limit ({len(lines)} > {MAX_MERMAID_LINES} lines).")

        # Diagram type validation
        diag_type = cls.detect_diagram_type(sanitized)
        if not diag_type:
            errors.append("Missing valid Mermaid declaration header (e.g. 'flowchart TD', 'sequenceDiagram', 'stateDiagram-v2').")

        # Check balanced brackets/parentheses/quotes
        bracket_pairs = [("[", "]"), ("(", ")"), ("{", "}")]
        for open_b, close_b in bracket_pairs:
            open_count = sanitized.count(open_b)
            close_count = sanitized.count(close_b)
            if open_count != close_count:
                errors.append(f"Mismatched delimiters: {open_count} '{open_b}' vs {close_count} '{close_b}'.")

        # Check quote balance (simple check)
        quote_count = sanitized.count('"')
        if quote_count % 2 != 0:
            errors.append(f"Unclosed quotation mark detected ({quote_count} total double quotes).")

        # Check node estimate
        arrow_count = len(re.findall(r"-->|->|==>|-.->|-->>|->>", sanitized))
        if arrow_count > MAX_NODES_ESTIMATE * 2:
            errors.append(f"Diagram complexity exceeds safe limit ({arrow_count} transitions).")

        is_valid = len(errors) == 0
        return is_valid, sanitized, errors
