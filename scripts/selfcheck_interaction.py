from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.utils.entity_registry import EntityRegistry
from app.utils.interaction import count_interactions, compute_interaction_confidence
from app.utils.trace_index import TraceIndex



def main() -> None:
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

    # canonicalization idempotence
    names = ["Ally", "ally", "alice", "b0b"]
    for name in names:
        first = registry.canonicalize(name)
        second = registry.canonicalize(first)
        assert first == second, f"canonicalization not idempotent for {name} -> {first} -> {second}"
    pair_order = registry.canonical_pair("Bob", "ally")
    assert pair_order == tuple(sorted(pair_order)), "canonical_pair must sort deterministically"

    # confidence determinism and bounds
    for row in sem_filtered:
        raw1, score1, reasons1, _ = compute_interaction_confidence(row)
        raw2, score2, reasons2, _ = compute_interaction_confidence(row)
        assert 0.0 <= score1 <= 1.0
        assert 0.0 <= score2 <= 1.0
        assert score1 == score2, "confidence not deterministic"
        assert raw1 == raw2, "raw confidence not deterministic"
        assert reasons1, "reasons should not be empty"
        assert reasons2, "reasons should not be empty"

    thresholds = [0.0, 0.2, 0.5, 0.8]
    binary_results = []
    occ_results = []
    trace_results = []
    for thr in thresholds:
        pair_counts_binary, _, diag_binary = count_interactions(
            sem_filtered, mode="binary", min_confidence=thr, collect_traces=True
        )
        pair_counts_occ, _, diag_occ = count_interactions(
            sem_filtered, mode="occurrence", min_confidence=thr, collect_traces=True
        )
        binary_results.append((pair_counts_binary, diag_binary))
        occ_results.append((pair_counts_occ, diag_occ))
        trace_results.append(diag_binary.get("trace_records", []))

        for pair, count in pair_counts_binary.items():
            assert count <= pair_counts_occ[pair], f"binary greater than occurrence for {pair}"
            assert count >= 0
            assert pair[0] in {"alice", "bob", "carol", "dave"}
            assert pair[1] in {"alice", "bob", "carol", "dave"}
            trace_index = TraceIndex.from_records(diag_binary.get("trace_records", []))
            pair_summary = trace_index.summary_for_pair(pair)
            if count > 0:
                assert pair_summary["kept_records"] >= 1, "missing kept traces for counted pair"
        for pair, count in pair_counts_occ.items():
            assert count >= 0
        assert diag_binary["rows_used"] + diag_binary["rows_dropped"] == diag_binary["rows_total"]
        assert diag_occ["rows_used"] + diag_occ["rows_dropped"] == diag_occ["rows_total"]

        pair_units = diag_binary.get("pair_units", {})
        for records in pair_units.values():
            for rec in records:
                assert 0.0 <= rec.final_confidence <= 1.0
                assert rec.reasons == diag_binary["unit_reasons"].get(rec.unit_id, [])

    # monotonicity: higher thresholds cannot increase counts
    prev_total_binary = None
    prev_total_occ = None
    for (pair_counts_binary, _), (pair_counts_occ, _) in zip(binary_results, occ_results):
        total_binary = sum(pair_counts_binary.values())
        total_occ = sum(pair_counts_occ.values())
        if prev_total_binary is not None:
            assert total_binary <= prev_total_binary, "binary counts increased with higher threshold"
        if prev_total_occ is not None:
            assert total_occ <= prev_total_occ, "occurrence counts increased with higher threshold"
        prev_total_binary = total_binary
        prev_total_occ = total_occ

    # confidence buckets and traces should stay within bounds and deterministic
    for records in trace_results:
        trace_index = TraceIndex.from_records(records)
        for rec in records:
            assert 0.0 <= rec.confidence <= 1.0, "trace confidence out of bounds"
            assert trace_index._pair_from_metadata(rec) is None or len(trace_index._pair_from_metadata(rec)) == 2
        # determinism
        again = TraceIndex.from_records(records)
        assert trace_index.buckets() == again.buckets(), "trace index histogram not deterministic"

    # monotonicity on traces: higher threshold cannot add more kept records
    prev_kept = None
    for records in trace_results:
        idx = TraceIndex.from_records(records)
        kept_count = sum(1 for rec in idx.records if not rec.drop_reason)
        if prev_kept is not None:
            assert kept_count <= prev_kept, "trace kept records increased with higher threshold"
        prev_kept = kept_count

    # determinism check
    pair_counts_binary_1, _, diag_binary_1 = count_interactions(
        sem_filtered, mode="binary", min_confidence=0.2, collect_traces=True
    )
    pair_counts_binary_2, _, diag_binary_2 = count_interactions(
        sem_filtered, mode="binary", min_confidence=0.2, collect_traces=True
    )
    assert pair_counts_binary_1 == pair_counts_binary_2, "non-deterministic pair counts"
    assert diag_binary_1["units"] == diag_binary_2["units"]
    traces_1 = TraceIndex.from_records(diag_binary_1.get("trace_records", []))
    traces_2 = TraceIndex.from_records(diag_binary_2.get("trace_records", []))
    assert traces_1.buckets() == traces_2.buckets(), "trace buckets not deterministic"

    print("OK")


if __name__ == "__main__":
    main()
