"""Lightweight text cleaning for academic documents."""

import re


def clean_text(text: str) -> str:
    """
    Perform non-destructive cleaning on extracted document text.

    - Normalizes line endings and removes unprintable control characters.
    - Resolves hyphenated word splits at line breaks (e.g. "distri-\\nbuted" -> "distributed").
    - Normalizes excessive horizontal spaces and blank lines.
    - Preserves academic punctuation, letter casing, numbers, and paragraph structure.
    """
    if not text:
        return ""

    # Replace null bytes and non-standard control characters (keep \n and \t)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # Normalize line endings to standard Unix \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Fix hyphenated words broken across line breaks (e.g., "comput-\ner" -> "computer")
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # Replace non-breaking spaces and tabs with standard single space
    text = re.sub(r"[^\S\n]+", " ", text)

    # Remove trailing/leading spaces on each individual line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Collapse 3 or more consecutive newlines into 2 newlines (preserves paragraph boundaries)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
