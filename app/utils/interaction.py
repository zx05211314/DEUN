from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class InteractionUnitRecord:
    unit_id: str
    a: str
    b: str
    count: int
    raw_confidence: float
    final_confidence: float
    bucket: str
    reasons: List[str] = field(default_factory=list)
    drop_reason: str | None = None
    meta: Dict[str, Any] = field(default_factory=dict)


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


def _bucket_confidence(score: float) -> str:
    boundaries = [0.2, 0.4, 0.6, 0.8, 1.0]
    for upper in boundaries:
        if score <= upper:
            lower = 0.0 if upper == 0.2 else boundaries[boundaries.index(upper) - 1]
            return f"{lower:.1f}-{upper:.1f}"
    return "unknown"


def compute_interaction_confidence(rel: Dict[str, Any]) -> Tuple[float, float, List[str], Dict[str, Any]]:
    base = 0.5
    reasons: List[str] = ["base:+0.50"]
    meta: Dict[str, Any] = {}

    raw_confidence = rel.get("confidence")
    if isinstance(raw_confidence, (int, float)):
        meta["raw_confidence"] = float(raw_confidence)

    distance_keys = ["distance", "sentence_distance", "mention_distance", "gap"]
    distance_val = None
    for key in distance_keys:
        val = rel.get(key)
        if isinstance(val, (int, float)):
            distance_val = float(val)
            meta["distance"] = distance_val
            break

    if distance_val is not None:
        if distance_val <= 0:
            base += 0.2
            reasons.append("+0.20 distance<=0")
        elif distance_val <= 1:
            base += 0.15
            reasons.append("+0.15 distance<=1")
        elif distance_val <= 3:
            base += 0.1
            reasons.append("+0.10 distance<=3")
        elif distance_val <= 5:
            base += 0.05
            reasons.append("+0.05 distance<=5")
        else:
            penalty = min(0.35, 0.02 * (distance_val - 5))
            base -= penalty
            reasons.append(f"-{penalty:.2f} far_distance({distance_val})")

    same_sentence_flags = ["same_sentence", "same_line", "same_paragraph"]
    for key in same_sentence_flags:
        if isinstance(rel.get(key), bool) and rel.get(key):
            base += 0.1
            reasons.append(f"+0.10 {key}")
            meta[key] = True
            break

    score_keys = ["score", "similarity", "relation_score", "weight", "confidence", "probability"]
    for key in score_keys:
        val = rel.get(key)
        if isinstance(val, (int, float)):
            score_val = float(val)
            normalized = score_val if 0 <= score_val <= 1 else max(0.0, min(1.0, score_val / 2))
            delta = (normalized - 0.5) * 0.4
            base += delta
            reasons.append(f"{delta:+.2f} {key}({score_val})")
            meta[key] = score_val
            break

    text_field = rel.get("text") or rel.get("content") or rel.get("sentence")
    if isinstance(text_field, str):
        lowered = text_field.lower()
        uncertain_patterns = ["rumor", "maybe", "可能", "疑似", "不確定", "傳言", "傳聞", "或許", "未明"]
        neg_patterns = [" not ", " no ", "沒有", "並非"]
        penalty = 0.0
        for pat in uncertain_patterns:
            if pat in lowered:
                penalty += 0.08
                reasons.append(f"-0.08 uncertain({pat})")
        for pat in neg_patterns:
            if pat in lowered:
                penalty += 0.06
                reasons.append(f"-0.06 negation({pat.strip()})")
        if penalty:
            base -= penalty

    final_score = max(0.0, min(1.0, base))
    return float(raw_confidence) if isinstance(raw_confidence, (int, float)) else 0.5, final_score, reasons, meta


def count_interactions(
    sem_filtered: List[Dict[str, Any]],
    mode: str = "binary",
    confidence_col: str | None = None,
    min_confidence: float | None = 0.0,
    alias_map: Dict[str, str] | None = None,
) -> Tuple[Counter, Counter, Dict[str, Any]]:
    """Count interactions deterministically using sem_filtered only."""

    normalized_mode = _normalize_mode(mode)
    pair_counts: Counter = Counter()
    character_totals: Counter = Counter()
    unit_to_roles: Dict[str, set[str]] = defaultdict(set)
    unit_role_counts: Dict[str, Counter] = defaultdict(Counter)
    unit_pair_counts: Dict[str, List[InteractionUnitRecord]] = defaultdict(list)
    diagnostics: Dict[str, Any] = {
        "rows_total": len(sem_filtered),
        "rows_used": 0,
        "rows_dropped": 0,
        "units": 0,
        "unit_participant_sizes": {},
        "duplicate_role_mentions": {},
        "dropped": Counter(),
        "mode": normalized_mode,
        "pair_units": {},
        "confidence_buckets_all": Counter(),
        "confidence_buckets_kept": Counter(),
        "confidence_reasons": Counter(),
        "confidence_drop_reasons": Counter(),
        "confidence_threshold": min_confidence if min_confidence is not None else 0.0,
        "drops": [],
        "unit_confidence": {},
        "unit_raw_confidence": {},
        "unit_reasons": {},
        "unit_meta": {},
        "below_conf_threshold": 0,
    }

    for rel in sem_filtered:
        raw_score, score, reasons, meta = compute_interaction_confidence(rel)
        bucket = _bucket_confidence(score)
        diagnostics["confidence_buckets_all"][bucket] += 1
        for reason in reasons:
            diagnostics["confidence_reasons"][reason] += 1

        unit_id = build_unit_id(rel)
        participants = extract_characters_from_relation(rel, alias_map=alias_map)
        unique_participants = set(participants)

        drop_reason = None
        if min_confidence is not None and score < float(min_confidence):
            drop_reason = "below_confidence"
        elif not unit_id:
            drop_reason = "invalid_unit"
        elif not unique_participants:
            drop_reason = "no_participants"
        elif len(unique_participants) < 2:
            drop_reason = "single_participant"

        if drop_reason:
            diagnostics["rows_dropped"] += 1
            diagnostics["dropped"][drop_reason] += 1
            for reason in reasons:
                diagnostics["confidence_drop_reasons"][reason] += 1
            diagnostics["drops"].append(
                {
                    "unit_id": unit_id or "",
                    "bucket": bucket,
                    "reason": drop_reason,
                    "participants": sorted(unique_participants),
                }
            )
            continue

        if confidence_col:
            try:
                if float(rel.get(confidence_col, 0)) < float(min_confidence or 0):
                    diagnostics["below_conf_threshold"] += 1
            except (TypeError, ValueError):
                diagnostics["below_conf_threshold"] += 1

        diagnostics["rows_used"] += 1
        diagnostics["confidence_buckets_kept"][bucket] += 1
        for p in participants:
            unit_role_counts[unit_id][p] += 1
        unit_to_roles[unit_id].update(unique_participants)
        diagnostics["unit_confidence"][unit_id] = score
        diagnostics["unit_raw_confidence"][unit_id] = raw_score
        diagnostics["unit_reasons"][unit_id] = list(reasons)
        diagnostics["unit_meta"][unit_id] = meta

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
            unit_pair_counts[(a, b)].append(
                InteractionUnitRecord(
                    unit_id=unit_id,
                    a=a,
                    b=b,
                    count=increment,
                    raw_confidence=diagnostics["unit_raw_confidence"].get(unit_id, 0.0),
                    final_confidence=diagnostics["unit_confidence"].get(unit_id, 0.0),
                    bucket=_bucket_confidence(diagnostics["unit_confidence"].get(unit_id, 0.0)),
                    reasons=diagnostics["unit_reasons"].get(unit_id, []),
                    drop_reason=None,
                    meta=diagnostics["unit_meta"].get(unit_id, {}),
                )
            )

    diagnostics["pair_units"] = {
        pair: sorted(
            unit_pair_counts[pair],
            key=lambda rec: (-rec.count, -rec.final_confidence, rec.unit_id),
        )
        for pair in pair_counts
    }

    return pair_counts, character_totals, diagnostics


__all__ = [
    "InteractionUnitRecord",
    "build_unit_id",
    "normalize_role",
    "extract_characters_from_relation",
    "compute_interaction_confidence",
    "count_interactions",
]
