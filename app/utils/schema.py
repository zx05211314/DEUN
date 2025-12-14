from __future__ import annotations

from typing import Any, Dict, Tuple, Type, Union

SchemaSpec = Dict[str, Any]


def make_list_schema(
    *,
    item_required_keys: Tuple[str, ...] = (),
    item_optional_keys: Tuple[str, ...] = (),
    item_key_types: Dict[str, Union[Type, Tuple[Type, ...]]] | None = None,
) -> SchemaSpec:
    return {
        "type": list,
        "item_required_keys": item_required_keys,
        "item_optional_keys": item_optional_keys,
        "item_key_types": item_key_types or {},
    }


TIMELINE_SCHEMA: SchemaSpec = make_list_schema(
    item_required_keys=(),
    item_optional_keys=(
        "order",
        "index",
        "idx",
        "time_idx",
        "time",
        "timestamp",
        "chapter",
        "chapter_title",
        "event",
        "sentence",
        "speaker",
        "voice",
        "emotion",
        "emotion_perspective",
        "low_confidence",
        "display_group",
    ),
    item_key_types={
        "order": (int, float),
        "index": (int, float),
        "idx": (int, float),
        "time_idx": (int, float),
        "time": str,
        "timestamp": (int, float, str),
        "chapter": (str, int),
        "chapter_title": str,
        "event": str,
        "sentence": str,
        "speaker": str,
        "voice": str,
        "emotion": str,
        "emotion_perspective": str,
        "low_confidence": bool,
        "display_group": str,
    },
)


SEMANTIC_RELATIONS_SCHEMA: SchemaSpec = make_list_schema(
    item_required_keys=(),
    item_optional_keys=(
        "speaker",
        "voice",
        "emotion",
        "emotion_perspective",
        "sentence",
        "event",
        "low_confidence",
        "participants",
        "subject",
        "object",
        "item",
        "character",
        "target",
        "target_speaker",
        "target_character",
        "other_speaker",
        "listener",
        "object_character",
        "object_speaker",
    ),
    item_key_types={
        "speaker": str,
        "voice": str,
        "emotion": str,
        "emotion_perspective": str,
        "sentence": str,
        "event": str,
        "low_confidence": bool,
        "participants": list,
        "subject": str,
        "object": str,
        "item": str,
        "character": str,
        "target": str,
        "target_speaker": str,
        "target_character": str,
        "other_speaker": str,
        "listener": str,
        "object_character": str,
        "object_speaker": str,
    },
)


RELATIONS_SCHEMA: SchemaSpec = make_list_schema(
    item_required_keys=(),
    item_optional_keys=("subject", "verb", "object", "sentence", "strength", "low_confidence"),
    item_key_types={
        "subject": str,
        "verb": str,
        "object": str,
        "sentence": str,
        "strength": (int, float, str),
        "low_confidence": bool,
    },
)


SPEAKER_SUMMARY_SCHEMA: SchemaSpec = {
    "type": dict,
    "value_type": list,
}


METADATA_SCHEMA: SchemaSpec = {
    "type": dict,
    "required_keys": ("book",),
    "optional_keys": (
        "chapters_used",
        "sentences_used",
        "zero_shot",
        "enabled_modules",
        "output_stats",
    ),
}


GRAPH_SCHEMA: SchemaSpec = {
    "type": dict,
    "required_keys": ("nodes", "edges"),
    "optional_keys": (),
    "key_types": {"nodes": list, "edges": list},
    "node_schema": make_list_schema(
        item_required_keys=("id",),
        item_optional_keys=("label", "type"),
        item_key_types={"id": (int, str), "label": str, "type": str},
    ),
    "edge_schema": make_list_schema(
        item_required_keys=("source", "target"),
        item_optional_keys=("verb", "label", "low_confidence"),
        item_key_types={
            "source": (int, str),
            "target": (int, str),
            "verb": str,
            "label": str,
            "low_confidence": bool,
        },
    ),
}


SEMANTIC_GRAPH_SCHEMA: SchemaSpec = GRAPH_SCHEMA


SCHEMAS: Dict[str, SchemaSpec] = {
    "timeline.json": TIMELINE_SCHEMA,
    "semantic_relations.json": SEMANTIC_RELATIONS_SCHEMA,
    "relations.json": RELATIONS_SCHEMA,
    "speaker_summary.json": SPEAKER_SUMMARY_SCHEMA,
    "metadata.json": METADATA_SCHEMA,
    "graph.json": GRAPH_SCHEMA,
    "semantic_graph.json": SEMANTIC_GRAPH_SCHEMA,
}
