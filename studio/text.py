"""Unicode-safe, language-agnostic speech chunking with Arabic punctuation."""
from __future__ import annotations

import re
import unicodedata

MAX_SEGMENT_CHARS = 280
MAX_DOCUMENT_CHARS = 6000
_SENTENCE_BREAK = re.compile(r"(?<=[.!?؟؛。])\s+|\n+")


def normalize_text(value: str) -> str:
    """Preserve Arabic tashkeel; strip control characters except whitespace."""
    cleaned = "".join(
        c if c in "\n\t" or unicodedata.category(c)[0] != "C" else " "
        for c in unicodedata.normalize("NFC", value)
    )
    return cleaned.strip()


def split_speech(text: str, max_chars: int = MAX_SEGMENT_CHARS) -> list[str]:
    """Chunk long speech into model-safe parts without dropping words.

    Boundaries favor sentences then spaces; unbroken words are hard-cut.
    This prepares segments only and makes no assertion about audio quality.
    """
    if max_chars < 16:
        raise ValueError("max_chars must be at least 16")
    text = normalize_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    output: list[str] = []
    working = ""
    sentences = _SENTENCE_BREAK.split(text)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars and len(working) + len(sentence) + bool(working) <= max_chars:
            working = f"{working} {sentence}".strip()
            continue
        if working:
            output.append(working)
            working = ""
        if len(sentence) <= max_chars:
            working = sentence
            continue
        for word in sentence.split():
            if len(word) > max_chars:
                if working:
                    output.append(working)
                    working = ""
                while len(word) > max_chars:
                    output.append(word[:max_chars])
                    word = word[max_chars:]
            if not word:
                continue
            if len(working) + len(word) + bool(working) > max_chars:
                output.append(working)
                working = ""
            working = f"{working} {word}".strip()
    if working:
        output.append(working)
    return output
