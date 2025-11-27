# app/modules/vocab_utils.py
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Set

# Very small demo list - extend if you like
COMMON_WORDS: Set[str] = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it",
    "for", "not", "on", "with", "he", "as", "you", "do", "at", "this",
    "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
    "an", "will", "my", "one", "all", "would", "there", "their", "is", "are"
}

WORD_RE = re.compile(r"[A-Za-z\-']+")


def tokenize(text: str) -> list[str]:
    """Simple word tokenizer."""
    return [w for w in WORD_RE.findall(text)]


def find_new_vocabulary(
    text: str,
    known_words: Iterable[str] | None = None,
    min_length: int = 6,
) -> Set[str]:
    """
    Heuristic detection of 'new/complex' words in the given text.

    A word is considered new if:
    - length >= min_length
    - not in COMMON_WORDS
    - not in known_words (user's word list)
    """
    known = {w.lower() for w in (known_words or [])}
    tokens = [t.lower() for t in tokenize(text)]
    counts = Counter(tokens)

    new_words: Set[str] = set()
    for word, _freq in counts.items():
        if (
            len(word) >= min_length
            and word.isalpha()
            and word not in COMMON_WORDS
            and word not in known
        ):
            new_words.add(word)

    return new_words
