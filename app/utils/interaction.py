from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Dict, Iterable, List, Tuple

CANDIDATE_FIELDS = [
    "speaker",
    "character",
    "target_speaker",
    "target_character",
    "other_speaker",
    "listener",
    "subject",
    "object_character",
    "object_speaker",
    "target",
]


def build_unit_id(rel: Dict[str, Any]) -> str:
    """Return a deterministic interaction unit id.

    Priority: event_id > sentence_id/line_id > (chapter_index + timeline_index)
    > (chapter_index + hash(text_snippet)). Fallback to a stable hash of the
    record content to avoid run-to-run drift. Never use random values.
    """

    for key in ("event_id", "eventId", "id"):
        if key in rel and rel[key] is not None:
            return f"event:{rel[key]}"

    for key in ("sentence_id", "sentence_idx", "line_id", "line_idx"):
        if key in rel and rel[key] is not None:
            return f"sent:{rel[key]}"

    chapter_val = rel.get("chapter_index")
    timeline_val = rel.get("timeline_index") or rel.get("index") or rel.get("order")
    if chapter_val is not None and timeline_val is not None:
        return f"chapter:{chapter_val}-pos:{timeline_val}"

    text_snippet = rel.get("text") or rel.get("content") or rel.get("sentence")
    if text_snippet:
        snippet_hash = hashlib.md5(text_snippet.strip().encode("utf-8")).hexdigest()[:10]
        prefix = f"chapter:{chapter_val}" if chapter_val is not None else "chapter:unknown"
        return f"{prefix}-snippet:{snippet_hash}"

    fallback_val = rel.get("index") or rel.get("order")
    if fallback_val is not None:
        return f"fallback:{fallback_val}"

    serialized = json.dumps(rel, sort_keys=True, ensure_ascii=False)
    stable_hash = hashlib.md5(serialized.encode("utf-8")).hexdigest()[:10]
    return f"fallback:hash-{stable_hash}"


def normalize_role(name: str | None, alias_map: Dict[str, str] | None = None) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"[\s\t\n]+", " ", str(name)).strip()
    cleaned = re.sub(r"[\u3000\s]+", " ", cleaned)
    punctuation_chars = "-—·•・,，。.!！?？；;:'\"()（）[]【】{}"
    cleaned = cleaned.strip(punctuation_chars)
    cleaned = cleaned.lower()
    alias_map = alias_map or {}
    return alias_map.get(cleaned, cleaned)


def extract_characters_from_relation(
    rel: Dict[str, Any], alias_map: Dict[str, str] | None = None
) -> List[str]:
    participants: List[str] = []

    if isinstance(rel.get("participants"), list):
        participants.extend([p for p in rel["participants"] if isinstance(p, str)])

    for field in CANDIDATE_FIELDS:
        val = rel.get(field)
        if isinstance(val, str):
            participants.append(val)

    normalized = [normalize_role(p, alias_map=alias_map) for p in participants]
    return [p for p in normalized if p]


def _pair_value(counts: Dict[str, int], a: str, b: str, mode: str) -> int:
    if mode == "occurrence":
        return min(counts.get(a, 0), counts.get(b, 0)) or 0
    return 1


def _normalize_mode(mode: str) -> str:
    if mode in {"occurrence", "count_occurrences"}:
        return "occurrence"
    return "binary"


def _stable_pairs(roles: Iterable[str]) -> List[Tuple[str, str]]:
    return [(a, b) for a, b in combinations(sorted(roles), 2)]


def count_interactions(
    sem_filtered: List[Dict[str, Any]],
    mode: str = "binary",
    confidence_col: str | None = None,
    min_confidence: float | None = None,
    alias_map: Dict[str, str] | None = None,
) -> Tuple[Counter, Counter, Dict[str, Any]]:
    """Count interactions deterministically using sem_filtered only."""

    normalized_mode = _normalize_mode(mode)
    pair_counts: Counter = Counter()
    character_totals: Counter = Counter()
    unit_to_roles: Dict[str, set[str]] = defaultdict(set)
    unit_role_counts: Dict[str, Counter] = defaultdict(Counter)
    unit_pair_counts: Dict[str, Counter] = defaultdict(Counter)
    diagnostics: Dict[str, Any] = {
        "rows_total": len(sem_filtered),
        "rows": len(sem_filtered),
        "rows_used": 0,
        "units": 0,
        "unit_participant_sizes": {},
        "duplicate_role_mentions": {},
        "below_conf_threshold": 0,
        "dropped": {"no_participants": 0, "invalid_unit": 0},
        "mode": normalized_mode,
        "pair_units": {},
    }

    for rel in sem_filtered:
        if confidence_col and min_confidence is not None:
            try:
                if float(rel.get(confidence_col, 0)) < float(min_confidence):
                    diagnostics["below_conf_threshold"] += 1
            except (TypeError, ValueError):
                diagnostics["below_conf_threshold"] += 1

        unit_id = build_unit_id(rel)
        if not unit_id:
            diagnostics["dropped"]["invalid_unit"] += 1
            continue

        participants = extract_characters_from_relation(rel, alias_map=alias_map)
        unique_participants = set(participants)
        if not unique_participants:
            diagnostics["dropped"]["no_participants"] += 1
            continue

        diagnostics["rows_used"] += 1
        for p in participants:
            unit_role_counts[unit_id][p] += 1
        unit_to_roles[unit_id].update(unique_participants)

    diagnostics["units"] = len(unit_to_roles)
    for unit_id, roles in unit_to_roles.items():
        diagnostics["unit_participant_sizes"][unit_id] = len(roles)
        diagnostics["duplicate_role_mentions"][unit_id] = {
            role: cnt for role, cnt in unit_role_counts[unit_id].items() if cnt > 1
        }

    for unit_id, roles in unit_to_roles.items():
        if len(roles) < 2:
            continue
        role_counts = unit_role_counts[unit_id]
        for a, b in _stable_pairs(roles):
            increment = _pair_value(role_counts, a, b, normalized_mode)
            if increment <= 0:
                continue
            pair_counts[(a, b)] += increment
            character_totals[a] += increment
            character_totals[b] += increment
            unit_pair_counts[unit_id][(a, b)] += increment

    diagnostics["pair_units"] = {
        pair: sorted(
            ((unit_id, cnt) for unit_id, counts in unit_pair_counts.items() if (cnt := counts.get(pair))),
            key=lambda x: (-x[1], x[0]),
        )
        for pair in pair_counts
    }

    return pair_counts, character_totals, diagnostics


__all__ = [
    "build_unit_id",
    "normalize_role",
    "extract_characters_from_relation",
    "count_interactions",
]
