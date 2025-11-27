# app/engines/pron_eval.py
"""
Minimal stub. Returns "tricky" words from a word-timestamp list if prob is low.
Safe to remove/replace later.
"""
from typing import List, Dict

def flag_tricky_words(words: List[Dict]) -> list[str]:
    out = []
    for w in words or []:
        prob = w.get("prob", 1.0) or 1.0
        token = (w.get("word") or "").strip()
        if token and prob < 0.55:  # low confidence heuristic
            out.append(token)
    return list(dict.fromkeys(out))[:8]
