# app/modules/vocab_store.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from app.services.db_supabase import current_user_id

DATA_DIR = (Path(__file__).resolve().parents[1] / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = DATA_DIR / "vocab_store.json"

# { user_id: { word: { "definition": str, "examples": [str] } } }
_vocab_cache: Dict[str, Dict[str, dict]] = {}


def _load() -> None:
    global _vocab_cache
    if DATA_FILE.exists():
        try:
            _vocab_cache = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            _vocab_cache = {}
    else:
        _vocab_cache = {}


def _save() -> None:
    DATA_FILE.write_text(
        json.dumps(_vocab_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


_load()


def _uid_or_default() -> str:
    """Use Supabase user id if present, else a local 'anonymous' id."""
    uid = current_user_id()
    return uid or "anonymous"


def get_user_vocab(user_id: str | None = None) -> Dict[str, dict]:
    if user_id is None:
        user_id = _uid_or_default()
    return _vocab_cache.get(user_id, {})


def get_known_words_set(user_id: str | None = None) -> set[str]:
    return set(get_user_vocab(user_id).keys())


def add_word(
    user_id: str | None,
    word: str,
    definition: str,
    examples: List[str] | None = None,
) -> None:
    if user_id is None:
        user_id = _uid_or_default()
    word = word.lower()
    examples = examples or []
    if user_id not in _vocab_cache:
        _vocab_cache[user_id] = {}
    _vocab_cache[user_id][word] = {
        "definition": definition,
        "examples": examples,
    }
    _save()
