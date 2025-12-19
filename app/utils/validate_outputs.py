from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.utils.interaction import build_unit_id, extract_characters_from_relation
from app.utils.entity_registry import EntityRegistry
from app.utils.schema import SCHEMAS

REQUIRED_FILES = [
    "items.json",
    "relations.json",
    "semantic_relations.json",
    "timeline.json",
    "speaker_summary.json",
    "graph.json",
    "semantic_graph.json",
    "metadata.json",
    "mission_timeline.json",
]


def _load_json(path: Path) -> Tuple[bool, Any, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - best-effort diagnostics
        return False, None, f"unable to read file: {exc}"

    if text.strip() == "":
        return False, None, "file is empty"

    try:
        return True, json.loads(text), ""
    except Exception as exc:  # pragma: no cover - best-effort diagnostics
        return False, None, f"json parse error: {exc}"


def _type_name(obj: Any) -> str:
    if isinstance(obj, tuple):
        return "/".join(t.__name__ for t in obj)
    return type(obj).__name__


def _validate_dict(data: Dict[str, Any], schema: Dict[str, Any], issues: List[str], prefix: str) -> None:
    for key in schema.get("required_keys", ()):  # type: ignore[arg-type]
        if key not in data:
            issues.append(f"{prefix}: missing key '{key}'")
    for key, expected_type in schema.get("key_types", {}).items():
        if key in data and not isinstance(data[key], expected_type):
            issues.append(
                f"{prefix}: key '{key}' expects {_type_name(expected_type)} but got {_type_name(data[key])}"
            )


def _validate_list_items(
    data: List[Any], schema: Dict[str, Any], issues: List[str], prefix: str, stats: Dict[str, Any]
) -> None:
    required_keys = schema.get("item_required_keys", ())
    optional_keys = schema.get("item_optional_keys", ())
    key_types: Dict[str, Any] = schema.get("item_key_types", {})

    for idx, item in enumerate(data):
        item_prefix = f"{prefix}[{idx}]"
        if not isinstance(item, dict):
            issues.append(f"{item_prefix}: expected dict item but got {_type_name(item)}")
            stats["schema_errors"] += 1
            continue
        for key in required_keys:
            if key not in item:
                issues.append(f"{item_prefix}: missing key '{key}'")
                stats["schema_errors"] += 1
        for key in key_types:
            if key in item and not isinstance(item[key], key_types[key]):
                issues.append(
                    f"{item_prefix}: key '{key}' expects {_type_name(key_types[key])} but got {_type_name(item[key])}"
                )
                stats["schema_errors"] += 1
        for key in item.keys():
            if key not in required_keys and key not in optional_keys and key not in key_types:
                continue  # extra keys are allowed


def _validate_schema(name: str, data: Any, issues: List[str], stats: Dict[str, Any]) -> None:
    schema = SCHEMAS.get(name)
    if not schema:
        return

    expected_type = schema.get("type")
    if expected_type and not isinstance(data, expected_type):
        issues.append(f"{name}: expected {_type_name(expected_type)} but got {_type_name(data)}")
        stats["schema_errors"] += 1
        return

    if isinstance(data, dict):
        _validate_dict(data, schema, issues, name)
        if schema.get("node_schema") and isinstance(data.get("nodes"), list):
            _validate_list_items(data["nodes"], schema["node_schema"], issues, f"{name}.nodes", stats)
        if schema.get("edge_schema") and isinstance(data.get("edges"), list):
            _validate_list_items(data["edges"], schema["edge_schema"], issues, f"{name}.edges", stats)
        if name == "speaker_summary.json":
            for k, v in data.items():
                if not isinstance(v, list):
                    issues.append(f"speaker_summary.json[{k}] should be a list of tuples")
                    stats["schema_errors"] += 1
    elif isinstance(data, list):
        _validate_list_items(data, schema, issues, name, stats)


def _warn_timeline_order(name: str, data: List[Dict[str, Any]], issues: List[str], stats: Dict[str, Any]) -> None:
    order_values: List[float] = []
    for idx, item in enumerate(data):
        for key in ("order", "index", "idx", "time_idx"):
            val = item.get(key)
            if isinstance(val, (int, float)):
                order_values.append(float(val))
                break
        else:
            order_values.append(float(idx))

    for prev, curr in zip(order_values, order_values[1:]):
        if curr < prev:
            issues.append(f"WARN {name}: non-monotonic order detected around values {prev} -> {curr}")
            stats["warnings"] += 1
            break


def _warn_speakers(name: str, data: List[Dict[str, Any]], issues: List[str], stats: Dict[str, Any]) -> None:
    speakers = {item.get("speaker") for item in data if item.get("speaker")}
    if len(speakers) == 0:
        issues.append(f"WARN {name}: no speaker fields found")
        stats["warnings"] += 1


def _check_canonicalization(names: List[str], registry: EntityRegistry, issues: List[str], stats: Dict[str, Any], label: str) -> None:
    for name in names:
        canon = registry.canonicalize(name)
        if canon != registry.canonicalize(canon):
            issues.append(f"{label}: canonicalization not idempotent for '{name}' -> '{canon}'")
            stats["schema_errors"] += 1


def validate_outputs(output_dir: str) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Validate output directory contents for required files and schema alignment."""

    issues: List[str] = []
    stats: Dict[str, Any] = {
        "missing_files": 0,
        "empty_files": 0,
        "parse_errors": 0,
        "schema_errors": 0,
        "warnings": 0,
        "items_loaded": {},
        "interaction_warnings": [],
    }

    registry = EntityRegistry.load()

    base = Path(output_dir)
    if not base.exists():
        issues.append(f"output directory does not exist: {base}")
        stats["missing_files"] = len(REQUIRED_FILES)
        return False, issues, stats

    for filename in REQUIRED_FILES:
        path = base / filename
        if not path.exists():
            issues.append(f"missing required file: {filename}")
            stats["missing_files"] += 1
            continue

        ok, data, error = _load_json(path)
        if not ok:
            if error == "file is empty":
                issues.append(f"{filename} is empty")
                stats["empty_files"] += 1
            else:
                issues.append(f"{filename}: {error}")
                stats["parse_errors"] += 1
            continue

        if isinstance(data, list):
            stats["items_loaded"][filename] = len(data)
        elif isinstance(data, dict):
            stats["items_loaded"][filename] = len(data)
        else:
            stats["items_loaded"][filename] = 1

        _validate_schema(filename, data, issues, stats)

        if filename == "timeline.json" and isinstance(data, list) and data:
            _warn_timeline_order(filename, data, issues, stats)
            _warn_speakers(filename, data, issues, stats)
            _check_canonicalization(
                [item.get("speaker", "") for item in data if isinstance(item, dict)],
                registry,
                issues,
                stats,
                filename,
            )

        if filename == "semantic_relations.json" and isinstance(data, list) and data:
            _warn_speakers(filename, data, issues, stats)
            _, interaction_warnings, interaction_stats = validate_interaction_records(data)
            stats["interaction_warnings"].extend(interaction_warnings)
            stats.update({f"interaction_{k}": v for k, v in interaction_stats.items()})
            _check_canonicalization(
                [item.get("speaker", "") for item in data if isinstance(item, dict)],
                registry,
                issues,
                stats,
                filename,
            )

    error_total = stats["missing_files"] + stats["empty_files"] + stats["parse_errors"] + stats["schema_errors"]
    ok = error_total == 0
    return ok, issues, stats


def validate_interaction_records(records: List[Dict[str, Any]]) -> Tuple[bool, List[str], Dict[str, Any]]:
    warnings: List[str] = []
    stats: Dict[str, Any] = {
        "records": len(records),
        "dropped_no_participants": 0,
        "dropped_invalid_unit": 0,
        "invalid_confidence": 0,
    }

    for idx, rel in enumerate(records):
        if not isinstance(rel, dict):
            warnings.append(f"semantic_relations[{idx}]: not a dict, skipped")
            stats["dropped_invalid_unit"] += 1
            continue

        unit_id = build_unit_id(rel)
        if not unit_id:
            warnings.append(f"semantic_relations[{idx}]: unable to derive unit id")
            stats["dropped_invalid_unit"] += 1
            continue

        participants = extract_characters_from_relation(rel)
        if not participants:
            warnings.append(f"semantic_relations[{idx}]: no participants found")
            stats["dropped_no_participants"] += 1

        if "confidence" in rel:
            conf_val = rel.get("confidence")
            if not isinstance(conf_val, (int, float)) or not (0 <= float(conf_val) <= 1):
                warnings.append(f"semantic_relations[{idx}]: confidence out of bounds")
                stats["invalid_confidence"] += 1

    ok = len(warnings) == 0
    return ok, warnings, stats
