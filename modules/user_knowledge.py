"""User-provided whitelist/blacklist loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "input"
INPUT_DIR.mkdir(exist_ok=True)
WL_PATH = INPUT_DIR / "whitelist.json"
BL_PATH = INPUT_DIR / "blacklist.json"

EMPTY = {"characters": [], "items": [], "time": []}


def _load(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        return EMPTY.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "characters": data.get("characters", []) or [],
            "items": data.get("items", []) or [],
            "time": data.get("time", []) or [],
        }
    except Exception:
        return EMPTY.copy()


def load_whitelist() -> Dict[str, List[str]]:
    return _load(WL_PATH)


def load_blacklist() -> Dict[str, List[str]]:
    return _load(BL_PATH)


def save_knowledge(whitelist: Dict[str, List[str]] = None, blacklist: Dict[str, List[str]] = None) -> None:
    if whitelist is not None:
        WL_PATH.write_text(json.dumps(whitelist, ensure_ascii=False, indent=2), encoding="utf-8")
    if blacklist is not None:
        BL_PATH.write_text(json.dumps(blacklist, ensure_ascii=False, indent=2), encoding="utf-8")


def as_sets(data: Dict[str, List[str]]) -> Dict[str, Set[str]]:
    return {k: set(v or []) for k, v in data.items()}
