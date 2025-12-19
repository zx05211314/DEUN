from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.utils.entity_registry import EntityRegistry
from app.utils.interaction import count_interactions, compute_interaction_confidence



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
    for thr in thresholds:
        pair_counts_binary, _, diag_binary = count_interactions(
            sem_filtered, mode="binary", min_confidence=thr
        )
        pair_counts_occ, _, diag_occ = count_interactions(
            sem_filtered, mode="occurrence", min_confidence=thr
        )
        binary_results.append((pair_counts_binary, diag_binary))
        occ_results.append((pair_counts_occ, diag_occ))

        for pair, count in pair_counts_binary.items():
            assert count <= pair_counts_occ[pair], f"binary greater than occurrence for {pair}"
            assert count >= 0
            assert pair[0] in {"alice", "bob", "carol", "dave"}
            assert pair[1] in {"alice", "bob", "carol", "dave"}
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

    # determinism check
    pair_counts_binary_1, _, diag_binary_1 = count_interactions(
        sem_filtered, mode="binary", min_confidence=0.2
    )
    pair_counts_binary_2, _, diag_binary_2 = count_interactions(
        sem_filtered, mode="binary", min_confidence=0.2
    )
    assert pair_counts_binary_1 == pair_counts_binary_2, "non-deterministic pair counts"
    assert diag_binary_1["units"] == diag_binary_2["units"]

    print("OK")


if __name__ == "__main__":
    main()
