from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class SemanticTraceRecord:
    trace_id: str
    unit_id: str
    canonical_entity_id: str
    role: str
    count: int
    confidence: float
    confidence_bucket: str
    drop_reason: str | None
    applied_filters: List[str] = field(default_factory=list)
    source_metadata: Dict[str, Any] = field(default_factory=dict)


def build_trace_record(
    *,
    unit_id: str,
    canonical_entity_id: str,
    role: str,
    count: int,
    confidence: float,
    confidence_bucket: str,
    drop_reason: str | None,
    applied_filters: List[str] | None = None,
    source_metadata: Dict[str, Any] | None = None,
) -> SemanticTraceRecord:
    """Build a deterministic trace record without altering the input row."""

    applied_filters = applied_filters or []
    source_metadata = source_metadata or {}

    digest = hashlib.md5()
    digest.update(unit_id.encode("utf-8"))
    digest.update(canonical_entity_id.encode("utf-8"))
    digest.update(role.encode("utf-8"))
    digest.update(str(count).encode("utf-8"))
    digest.update(confidence_bucket.encode("utf-8"))
    digest.update((drop_reason or "").encode("utf-8"))
    trace_id = digest.hexdigest()[:16]

    return SemanticTraceRecord(
        trace_id=trace_id,
        unit_id=unit_id,
        canonical_entity_id=canonical_entity_id,
        role=role,
        count=count,
        confidence=confidence,
        confidence_bucket=confidence_bucket,
        drop_reason=drop_reason,
        applied_filters=applied_filters,
        source_metadata=source_metadata,
    )


__all__ = ["SemanticTraceRecord", "build_trace_record"]
