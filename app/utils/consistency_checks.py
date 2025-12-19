from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set, Tuple

from app.utils.entity_registry import EntityRegistry, identity_registry
from app.utils.interaction import count_interactions, extract_characters_from_relation


@dataclass
class ConsistencyFailure:
    check_name: str
    view_a: str
    view_b: str
    metric_key: str
    expected: Any
    actual: Any
    context: Dict[str, Any] = field(default_factory=dict)
    trace_ids: List[str] | None = None


@dataclass
class ConsistencyReport:
    passed: List[str] = field(default_factory=list)
    failed: List[ConsistencyFailure] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:  # pragma: no cover - simple property
        return not self.failed


def _stable_hash(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canon_pair_key(a: str, b: str) -> str:
    return f"{min(a, b)}|{max(a, b)}"


def _extract_interaction_signature(result: Any) -> Dict[str, Any]:
    pair_counts = {}
    diagnostics: Dict[str, Any] = {}

    if isinstance(result, tuple) and len(result) >= 3:
        pair_counts = result[0]
        diagnostics = result[2]
    elif isinstance(result, dict):
        pair_counts = result.get("pair_counts", {})
        diagnostics = result.get("diagnostics", {})

    signature_pairs = {
        _canon_pair_key(a, b): int(count) for (a, b), count in pair_counts.items()
    }
    total_count = sum(signature_pairs.values())

    return {
        "mode": diagnostics.get("mode"),
        "min_confidence": diagnostics.get("confidence_threshold", 0.0),
        "total_pairs": len(signature_pairs),
        "total_count": total_count,
        "pair_counts": signature_pairs,
        "bucket_counts": {
            k: int(v) for k, v in (diagnostics.get("confidence_buckets_kept", {}) or {}).items()
        },
        "drop_reason_counts": {
            k: int(v) for k, v in (diagnostics.get("dropped", {}) or {}).items()
        },
    }


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


def run_entity_consistency_checks(outputs: Dict[str, Any], registry: EntityRegistry) -> Dict[str, Any]:
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


def run_cross_view_checks(
    *,
    data_bundle: Dict[str, Any],
    filters: Dict[str, Any],
    thresholds: List[float],
    counting_modes: List[str],
    trace_enabled: bool = False,
    max_pairs_sample: int = 50,
) -> ConsistencyReport:
    sem_filtered = (data_bundle or {}).get("sem_filtered") or []
    registry = data_bundle.get("entity_registry") if isinstance(data_bundle, dict) else None
    if not isinstance(registry, EntityRegistry):
        registry = identity_registry()

    report = ConsistencyReport(summary={"thresholds": thresholds, "modes": counting_modes})

    signatures: Dict[Tuple[str, float], Dict[str, Any]] = {}

    for mode in counting_modes:
        prev_total = None
        for thr in thresholds:
            result = count_interactions(
                sem_filtered,
                mode=mode,
                min_confidence=thr,
                collect_traces=trace_enabled,
                applied_filters=[f"confidence>={thr}", f"mode={mode}"] + list(filters.values()),
            )
            signature = _extract_interaction_signature(result)
            signatures[(mode, thr)] = signature

            # Determinism: same call twice should hash identically
            result_again = count_interactions(
                sem_filtered,
                mode=mode,
                min_confidence=thr,
                collect_traces=trace_enabled,
                applied_filters=[f"confidence>={thr}", f"mode={mode}"] + list(filters.values()),
            )
            signature_again = _extract_interaction_signature(result_again)
            if _stable_hash(signature) != _stable_hash(signature_again):
                report.failed.append(
                    ConsistencyFailure(
                        check_name="determinism",
                        view_a="interaction",
                        view_b="interaction",
                        metric_key="signature_hash",
                        expected=_stable_hash(signature),
                        actual=_stable_hash(signature_again),
                        context={"mode": mode, "threshold": thr},
                    )
                )
            else:
                report.passed.append(f"determinism:{mode}:{thr}")

            # Monotonicity within mode
            if prev_total is not None and signature["total_count"] > prev_total:
                report.failed.append(
                    ConsistencyFailure(
                        check_name="monotonic_threshold",
                        view_a="interaction",
                        view_b="interaction",
                        metric_key="total_count",
                        expected=prev_total,
                        actual=signature["total_count"],
                        context={"mode": mode, "threshold": thr},
                    )
                )
            else:
                report.passed.append(f"monotonic:{mode}:{thr}")
            prev_total = signature["total_count"]

            # Canonical closure: ensure registry can represent pair ids
            for pair_key in signature["pair_counts"].keys():
                a, b = pair_key.split("|")
                ca = registry.canonicalize(a)
                cb = registry.canonicalize(b)
                if not ca or not cb or ca != a or cb != b:
                    report.failed.append(
                        ConsistencyFailure(
                            check_name="canonical_closure",
                            view_a="interaction",
                            view_b="registry",
                            metric_key="pair",
                            expected="canonicalized ids",
                            actual=pair_key,
                            context={"mode": mode, "threshold": thr},
                        )
                    )
                    break
            else:
                report.passed.append(f"canonical:{mode}:{thr}")

    # binary <= occurrence for same threshold
    for thr in thresholds:
        binary_sig = signatures.get(("binary", thr))
        occ_sig = signatures.get(("occurrence", thr))
        if binary_sig and occ_sig:
            if binary_sig["total_count"] > occ_sig["total_count"]:
                report.failed.append(
                    ConsistencyFailure(
                        check_name="binary_vs_occurrence",
                        view_a="interaction",
                        view_b="interaction",
                        metric_key="total_count",
                        expected=occ_sig["total_count"],
                        actual=binary_sig["total_count"],
                        context={"threshold": thr},
                    )
                )
            else:
                report.passed.append(f"binary<=occurrence:{thr}")

    # Placeholder for future cross-view parity; mark as skipped if not available
    report.passed.append("parity_skipped_semantic_tables")
    report.summary["parity"] = "semantic_tables_skipped"
    report.summary["signatures_tested"] = len(signatures)

    # Add sampled trace ids if available for failures
    if trace_enabled:
        for failure in report.failed:
            # no heavy trace fetch; just placeholder context for now
            failure.trace_ids = failure.trace_ids or []

    return report


__all__ = [
    "ConsistencyFailure",
    "ConsistencyReport",
    "run_cross_view_checks",
    "run_entity_consistency_checks",
]
