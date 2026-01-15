import json
from pathlib import Path
from typing import List, Dict

BASE_DIR = Path(__file__).resolve().parents[1]   # -> app/
READING_DIR = BASE_DIR / "reading"              # -> app/reading

def list_reading_sets(level: str) -> List[Path]:
    level_dir = READING_DIR / level
    if not level_dir.exists():
        return []
    return sorted(level_dir.glob("*.json"))      # ✅ bu satır şart

def load_reading_set(path: str | Path) -> Dict:
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)