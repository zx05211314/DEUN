from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple


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


def sanitize_book_name(book_name: str) -> str:
    """Return a filesystem-safer book name by stripping risky characters."""
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "", book_name or "").strip()
    return cleaned


def validate_novel_input(book_name: str, novel_path: Path | None) -> Tuple[bool, str, str, Path | None]:
    """Validate book name safety and novel file availability.

    Returns (is_valid, message, sanitized_book_name, resolved_path).
    """

    sanitized = sanitize_book_name(book_name)
    if not sanitized:
        return False, "書名不可為空且需為有效的資料夾名稱。", "", None

    resolved_path = novel_path or (Path("novels") / f"{sanitized}.txt")
    if not resolved_path.exists():
        return False, f"找不到輸入檔：{resolved_path}", sanitized, resolved_path
    if resolved_path.stat().st_size <= 0:
        return False, "小說檔案為空，請提供含內容的檔案。", sanitized, resolved_path

    return True, "", sanitized, resolved_path
