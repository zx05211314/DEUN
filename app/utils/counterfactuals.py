"""Counterfactual helpers layered on causal attribution (additive only).

This module MUST NOT affect counting logic or confidence scoring. All operations
are deterministic, idempotent, and non-mutating.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from app.utils.causal_attribution import CausalAttribution, CausalEdge, build_causal_attribution
from app.utils.interaction import InteractionUnitRecord

STABLE = "STABLE"
THRESHOLD_CROSSED = "THRESHOLD_CROSSED"
INVALID = "INVALID"


@dataclass(frozen=True)
class CounterfactualResult:
    before: CausalAttribution
    after: CausalAttribution
    delta: Dict[str, Any]
    verdict: str


def _rebuild_attribution(attribution: CausalAttribution, removed_edge_keys: Tuple[str, ...]) -> CausalAttribution:
    filtered_edges = [
        edge for edge in attribution.edges if f"{edge.source_type}:{edge.source_id}" not in removed_edge_keys
    ]
    if not filtered_edges:
        return CausalAttribution(
            interaction_id=attribution.interaction_id,
            confidence_bucket=attribution.confidence_bucket,
            edges=[],
            diagnostics={"removed_all": True},
        )

    total = sum(edge.weight for edge in filtered_edges)
    normalized = [
        CausalEdge(source_type=edge.source_type, source_id=edge.source_id, weight=edge.weight / total)
        for edge in filtered_edges
    ]
    return CausalAttribution(
        interaction_id=attribution.interaction_id,
        confidence_bucket=attribution.confidence_bucket,
        edges=normalized,
        diagnostics=attribution.diagnostics,
    )


def simulate_drop_entity(interaction_unit: InteractionUnitRecord, entity_id: str) -> CounterfactualResult:
    base_attr = build_causal_attribution(interaction_unit)
    key = f"entity:{entity_id}"
    after_attr = _rebuild_attribution(base_attr, (key,))

    verdict = STABLE
    if not base_attr.edges:
        verdict = INVALID
    elif not after_attr.edges:
        verdict = THRESHOLD_CROSSED

    delta = {
        "removed": key,
        "before_edges": [(e.source_type, e.source_id, e.weight) for e in base_attr.edges],
        "after_edges": [(e.source_type, e.source_id, e.weight) for e in after_attr.edges],
    }
    return CounterfactualResult(before=base_attr, after=after_attr, delta=delta, verdict=verdict)


def simulate_confidence_shift(interaction_unit: InteractionUnitRecord, delta: float) -> CounterfactualResult:
    base_attr = build_causal_attribution(interaction_unit)
    adjusted_confidence = max(0.0, min(1.0, interaction_unit.final_confidence + delta))

    after_attr = CausalAttribution(
        interaction_id=base_attr.interaction_id,
        confidence_bucket=base_attr.confidence_bucket,
        edges=deepcopy(base_attr.edges),
        diagnostics={**base_attr.diagnostics, "confidence_shift": delta},
    )

    verdict = STABLE
    if adjusted_confidence != interaction_unit.final_confidence and (
        (interaction_unit.final_confidence < 0.5 <= adjusted_confidence)
        or (interaction_unit.final_confidence >= 0.5 > adjusted_confidence)
    ):
        verdict = THRESHOLD_CROSSED

    delta_summary = {
        "delta": delta,
        "before_confidence": interaction_unit.final_confidence,
        "after_confidence": adjusted_confidence,
    }
    return CounterfactualResult(before=base_attr, after=after_attr, delta=delta_summary, verdict=verdict)


def simulate_edge_removal(interaction_unit: InteractionUnitRecord, edge_id: str) -> CounterfactualResult:
    base_attr = build_causal_attribution(interaction_unit)
    after_attr = _rebuild_attribution(base_attr, (edge_id,))

    if not base_attr.edges:
        verdict = INVALID
    elif not after_attr.edges:
        verdict = THRESHOLD_CROSSED
    else:
        verdict = STABLE

    delta = {
        "removed": edge_id,
        "before_edges": [(e.source_type, e.source_id, e.weight) for e in base_attr.edges],
        "after_edges": [(e.source_type, e.source_id, e.weight) for e in after_attr.edges],
    }
    return CounterfactualResult(before=base_attr, after=after_attr, delta=delta, verdict=verdict)


__all__ = [
    "CounterfactualResult",
    "simulate_drop_entity",
    "simulate_confidence_shift",
    "simulate_edge_removal",
    "STABLE",
    "THRESHOLD_CROSSED",
    "INVALID",
]
