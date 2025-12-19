"""Deterministic causal attribution helpers (additive only).

This module MUST NOT affect counting logic, confidence scoring, or metrics.
It derives attribution weights from already-canonicalized interaction units in
an idempotent, deterministic manner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple

from app.utils.interaction import InteractionUnitRecord, _bucket_confidence


@dataclass(frozen=True)
class CausalEdge:
    """A contributor to an interaction unit.

    source_type: entity | pov | emotion | chapter | semantic
    source_id: canonical identifier for the contributor
    weight: normalized weight within the interaction unit (sums to 1.0)
    """

    source_type: str
    source_id: str
    weight: float


@dataclass(frozen=True)
class CausalAttribution:
    """Attribution summary for a single interaction unit.

    interaction_id ties to the InteractionUnitRecord.unit_id.
    confidence_bucket mirrors the unit bucket; edges capture normalized
    contributors. Diagnostics are informational only.
    """

    interaction_id: str
    confidence_bucket: str
    edges: List[CausalEdge] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


_CAUSAL_SOURCE_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("entity", "entity"),
    ("pov", "pov"),
    ("voice", "pov"),
    ("emotion_perspective", "emotion"),
    ("emotion", "emotion"),
    ("chapter", "chapter"),
    ("chapter_index", "chapter"),
    ("chapter_title", "chapter"),
    ("relation", "semantic"),
    ("relation_type", "semantic"),
    ("predicate", "semantic"),
)


def _collect_contributors(unit: InteractionUnitRecord) -> List[Tuple[str, str]]:
    """Collect deterministic contributor tuples (source_type, source_id)."""

    contributors: List[Tuple[str, str]] = []

    if unit.a:
        contributors.append(("entity", unit.a))
    if unit.b:
        contributors.append(("entity", unit.b))

    for field_name, src_type in _CAUSAL_SOURCE_FIELDS:
        val = None
        if unit.meta:
            val = unit.meta.get(field_name)
        if val is None and field_name in ("entity",):
            # Already handled above.
            continue
        if isinstance(val, str) and val.strip():
            contributors.append((src_type, val.strip()))
        elif isinstance(val, (int, float)) and src_type == "chapter":
            contributors.append((src_type, str(val)))
    return contributors


def _normalize_weights(raw_items: Iterable[Tuple[str, str]]) -> List[CausalEdge]:
    weight_counter: Dict[Tuple[str, str], int] = {}
    for src_type, src_id in raw_items:
        key = (src_type, src_id)
        weight_counter[key] = weight_counter.get(key, 0) + 1

    total = sum(weight_counter.values())
    if total <= 0:
        return []

    edges: List[CausalEdge] = []
    for key, count in sorted(weight_counter.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        src_type, src_id = key
        edges.append(CausalEdge(source_type=src_type, source_id=src_id, weight=count / total))
    return edges


def build_causal_attribution(
    interaction_unit: InteractionUnitRecord, trace: Any | None = None
) -> CausalAttribution:
    """Construct a deterministic attribution for an interaction unit.

    This function is additive and MUST NOT alter counts or thresholds.
    """

    contributors = _collect_contributors(interaction_unit)
    edges = _normalize_weights(contributors)
    diagnostics: Dict[str, Any] = {}

    if trace is not None:
        diagnostics["trace_attached"] = True
    else:
        diagnostics["trace_attached"] = False

    if not edges:
        diagnostics["no_contributors"] = True
        return CausalAttribution(
            interaction_id=interaction_unit.unit_id,
            confidence_bucket=interaction_unit.bucket
            if hasattr(interaction_unit, "bucket")
            else _bucket_confidence(interaction_unit.final_confidence),
            edges=[],
            diagnostics=diagnostics,
        )

    diagnostics["contributor_count"] = len(edges)
    return CausalAttribution(
        interaction_id=interaction_unit.unit_id,
        confidence_bucket=interaction_unit.bucket
        if hasattr(interaction_unit, "bucket")
        else _bucket_confidence(interaction_unit.final_confidence),
        edges=edges,
        diagnostics=diagnostics,
    )


__all__ = [
    "CausalEdge",
    "CausalAttribution",
    "build_causal_attribution",
]
