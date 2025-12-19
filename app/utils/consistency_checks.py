from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, Set

from app.utils.interaction import extract_characters_from_relation


def _entities_from_relations(relations: Iterable[Dict[str, Any]]) -> Set[str]:
    entities: Set[str] = set()
    for rel in relations or []:
        entities.update(extract_characters_from_relation(rel))
        speaker = rel.get("speaker")
        if speaker:
            entities.add(str(speaker))
    return {e for e in entities if e}


def _entities_from_timeline(timeline: Iterable[Dict[str, Any]]) -> Set[str]:
    entities: Set[str] = set()
    for item in timeline or []:
        speaker = item.get("speaker")
        if speaker:
            entities.add(str(speaker))
        participants = item.get("participants")
        if isinstance(participants, list):
            entities.update([p for p in participants if isinstance(p, str)])
    return {e for e in entities if e}


def _entities_from_graph(graph: Dict[str, Any]) -> Set[str]:
    nodes = graph.get("nodes") if isinstance(graph, dict) else []
    result: Set[str] = set()
    for node in nodes or []:
        name = node.get("name") or node.get("label")
        if name:
            result.add(str(name))
    return result


def run_entity_consistency_checks(outputs: Dict[str, Any], registry) -> Dict[str, Any]:
    interactions = _entities_from_relations(outputs.get("semantic_relations", []))
    pov_entities = _entities_from_timeline(outputs.get("timeline", []))
    chapter_entities = _entities_from_timeline(outputs.get("mission_timeline", []))
    summary_entities = set(outputs.get("speaker_summary", {}).keys())
    graph_entities = _entities_from_graph(outputs.get("graph", {})) | _entities_from_graph(
        outputs.get("semantic_graph", {})
    )

    module_entities = {
        "interactions": interactions,
        "pov": pov_entities,
        "chapter": chapter_entities,
        "summary": summary_entities,
        "graph": graph_entities,
    }

    all_entities: Set[str] = set().union(*module_entities.values())

    missing: Dict[str, Set[str]] = {
        name: all_entities - ents for name, ents in module_entities.items()
    }

    orphan_aliases = sorted(registry.stats.get("unknown_hits", {}).items(), key=lambda kv: kv[1], reverse=True)
    blocked_hits = sum(registry.stats.get("blocked_hits", {}).values())

    report = {
        "registry_loaded": registry.loaded,
        "registry_path": str(registry.path) if registry.path else "",
        "all_entities": sorted(all_entities),
        "module_entities": {k: sorted(v) for k, v in module_entities.items()},
        "missing": {k: sorted(v) for k, v in missing.items()},
        "orphan_aliases": orphan_aliases,
        "blocked_hits": blocked_hits,
    }
    return report


__all__ = ["run_entity_consistency_checks"]
