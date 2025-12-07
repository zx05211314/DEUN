"""Load user-provided vocab overrides for actions/emotions/missions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "input"
INPUT_DIR.mkdir(exist_ok=True)
VOCAB_PATH = INPUT_DIR / "vocab_overrides.json"

EMPTY = {"action": {}, "emotion": {}, "mission": {}}


def load_vocab() -> Dict[str, Dict[str, List[str]]]:
    if not VOCAB_PATH.exists():
        return EMPTY.copy()
    try:
        data = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
        out = {"action": {}, "emotion": {}, "mission": {}}
        for key in out.keys():
            section = data.get(key, {}) or {}
            out[key] = {k: v for k, v in section.items() if isinstance(v, list)}
        return out
    except Exception:
        return EMPTY.copy()


def save_vocab(vocab: Dict[str, Dict[str, List[str]]]) -> None:
    VOCAB_PATH.write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")
