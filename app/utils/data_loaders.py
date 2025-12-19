from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

from app.utils.entity_registry import EntityRegistry, identity_registry


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _canonicalize_record(data: Dict[str, Any], registry: EntityRegistry, *, string_fields=None, list_fields=None):
    string_fields = string_fields or []
    list_fields = list_fields or []
    for field in string_fields:
        if field in data:
            data[f"raw_{field}"] = data.get(field)
            data[field] = registry.canonicalize(data.get(field))
    for field in list_fields:
        if isinstance(data.get(field), list):
            data[field] = [registry.canonicalize(v) for v in data[field] if v is not None]


def _canonicalize_outputs(data: Dict[str, Any], registry: EntityRegistry) -> None:
    for rel in data.get("semantic_relations", []) or []:
        _canonicalize_record(
            rel,
            registry,
            string_fields=[
                "speaker",
                "target_speaker",
                "other_speaker",
                "subject",
                "object_character",
                "object_speaker",
                "target",
                "character",
                "voice",
            ],
            list_fields=["participants"],
        )

    for rel in data.get("relations", []) or []:
        _canonicalize_record(
            rel,
            registry,
            string_fields=["speaker", "target", "role", "character"],
            list_fields=["participants"],
        )

    for item in data.get("timeline", []) or []:
        _canonicalize_record(item, registry, string_fields=["speaker", "voice"], list_fields=["participants"])

    for item in data.get("mission_timeline", []) or []:
        _canonicalize_record(item, registry, string_fields=["speaker"], list_fields=["participants"])

    if isinstance(data.get("speaker_summary"), dict):
        summary = {}
        for name, entries in data["speaker_summary"].items():
            canonical = registry.canonicalize(name)
            summary.setdefault(canonical, []).extend(entries if isinstance(entries, list) else [])
        data["speaker_summary"] = summary

    for graph_key in ("graph", "semantic_graph"):
        graph = data.get(graph_key)
        if isinstance(graph, dict) and isinstance(graph.get("nodes"), list):
            for node in graph["nodes"]:
                _canonicalize_record(node, registry, string_fields=["name", "label"])


def load_outputs(book_dir: Path, registry: EntityRegistry | None = None) -> Dict[str, Any]:
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

    registry = registry or EntityRegistry.load()
    if not isinstance(registry, EntityRegistry):
        registry = identity_registry()
    _canonicalize_outputs(data, registry)
    data["entity_registry"] = registry
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
