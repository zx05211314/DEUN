from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_outputs(book_dir: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    data["items"] = load_json(book_dir / "items.json", [])
    data["relations"] = load_json(book_dir / "relations.json", [])
    data["semantic_relations"] = load_json(book_dir / "semantic_relations.json", [])
    data["speaker_summary"] = load_json(book_dir / "speaker_summary.json", {})
    data["character_relations"] = load_json(book_dir / "character_relations.json", [])
    data["graph"] = load_json(book_dir / "graph.json", {"nodes": [], "edges": []})
    data["semantic_graph"] = load_json(book_dir / "semantic_graph.json", {"nodes": [], "edges": []})
    data["timeline"] = load_json(book_dir / "timeline.json", [])
    data["mission_timeline"] = load_json(book_dir / "mission_timeline.json", [])
    data["metadata"] = load_json(book_dir / "metadata.json", {})
    return data
