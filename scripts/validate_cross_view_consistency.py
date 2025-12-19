from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.utils.consistency_checks import run_cross_view_checks
from app.utils.entity_registry import EntityRegistry


def build_fixture():
    registry = EntityRegistry(
        canonical={"alice", "bob", "carol", "dave"},
        aliases={"ally": "alice", "b0b": "bob"},
        blocked=set(),
    )
    sem_filtered = [
        {"event_id": 1, "speaker": "Alice", "target_speaker": "Bob", "distance": 0},
        {"event_id": 1, "speaker": "alice", "other_speaker": "Bob", "distance": 1},
        {"sentence_id": 5, "participants": ["Alice", "Carol"], "sentence_distance": 0},
        {
            "chapter_index": 1,
            "timeline_index": 1,
            "speaker": "Bob",
            "target_speaker": "Carol",
            "distance": 8,
            "text": "rumor about Bob and Carol",
        },
        {
            "chapter_index": 1,
            "timeline_index": 2,
            "speaker": "Carol",
            "target_speaker": "Dave",
            "distance": 10,
        },
        {"event_id": 9, "speaker": "ally", "target_speaker": "b0b", "distance": 0},
    ]
    for row in sem_filtered:
        for key in ["speaker", "target_speaker", "other_speaker"]:
            if key in row:
                row[key] = registry.canonicalize(row[key])
    return {"sem_filtered": sem_filtered, "entity_registry": registry}


def main() -> int:
    data_bundle = build_fixture()
    thresholds = [0.0, 0.3, 0.6, 0.9]
    modes = ["binary", "occurrence"]
    report = run_cross_view_checks(
        data_bundle=data_bundle,
        filters={},
        thresholds=thresholds,
        counting_modes=modes,
        trace_enabled=True,
    )

    if report.ok:
        print("PASS")
        print(report.summary)
        return 0

    print("FAIL")
    for failure in report.failed:
        print(
            f"[{failure.check_name}] {failure.metric_key} expected={failure.expected} actual={failure.actual} "
            f"context={failure.context}"
        )
        if failure.trace_ids:
            print(f"  traces: {failure.trace_ids[:5]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
