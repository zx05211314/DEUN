from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Tuple

from app.utils.semantic_trace import SemanticTraceRecord


class TraceIndex:
    def __init__(self, records: Iterable[SemanticTraceRecord]):
        self.records: List[SemanticTraceRecord] = list(records)
        self.pair_index: Dict[Tuple[str, str], List[SemanticTraceRecord]] = defaultdict(list)
        self.entity_index: Dict[str, List[SemanticTraceRecord]] = defaultdict(list)
        self.confidence_histogram: Counter = Counter()
        self.drop_reasons: Counter = Counter()

        for rec in self.records:
            pair = self._pair_from_metadata(rec)
            if pair:
                self.pair_index[pair].append(rec)
            self.entity_index[rec.canonical_entity_id].append(rec)
            self.confidence_histogram[rec.confidence_bucket] += 1
            if rec.drop_reason:
                self.drop_reasons[rec.drop_reason] += 1

        for key in self.pair_index:
            self.pair_index[key] = sorted(
                self.pair_index[key],
                key=lambda r: (r.unit_id, r.trace_id),
            )

    @staticmethod
    def _pair_from_metadata(rec: SemanticTraceRecord) -> Tuple[str, str] | None:
        pair_val = rec.source_metadata.get("pair")
        if isinstance(pair_val, (list, tuple)) and len(pair_val) == 2:
            return tuple(sorted(str(x) for x in pair_val))  # type: ignore[return-value]
        return None

    @classmethod
    def from_records(cls, records: Iterable[SemanticTraceRecord]) -> "TraceIndex":
        return cls(records)

    def summary_for_pair(self, pair: Tuple[str, str]) -> Dict[str, Any]:
        normalized = tuple(sorted(pair))
        records = self.pair_index.get(normalized, [])
        kept = [r for r in records if not r.drop_reason]
        buckets = Counter(r.confidence_bucket for r in kept)
        drop_buckets = Counter(r.confidence_bucket for r in records if r.drop_reason)
        drop_reasons = Counter(r.drop_reason for r in records if r.drop_reason)

        top_units = Counter(r.unit_id for r in kept)
        top_entities = Counter()
        for rec in kept:
            participants = rec.source_metadata.get("participants") or []
            for p in participants:
                top_entities[p] += 1

        sample = kept[:10] if kept else records[:10]

        return {
            "pair": normalized,
            "records": len(records),
            "kept_records": len(kept),
            "buckets": dict(buckets),
            "drop_buckets": dict(drop_buckets),
            "drop_reasons": {k: v for k, v in drop_reasons.items() if k},
            "top_units": top_units.most_common(5),
            "top_entities": top_entities.most_common(5),
            "sample_traces": sample,
        }

    def buckets(self) -> Dict[str, int]:
        return dict(self.confidence_histogram)

    def drop_summary(self) -> Dict[str, int]:
        return dict(self.drop_reasons)

    def entities(self) -> List[str]:
        return sorted(self.entity_index.keys())


__all__ = ["TraceIndex"]
