from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.utils.interaction import count_interactions, compute_interaction_confidence



def main() -> None:
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
    ]

    # confidence determinism and bounds
    for row in sem_filtered:
        score1, reasons1, _ = compute_interaction_confidence(row)
        score2, reasons2, _ = compute_interaction_confidence(row)
        assert 0.0 <= score1 <= 1.0
        assert score1 == score2, "confidence not deterministic"
        assert reasons1, "reasons should not be empty"
        assert reasons2, "reasons should not be empty"

    pair_counts_binary, _, diag_binary = count_interactions(sem_filtered, mode="binary", min_confidence=0.0)
    pair_counts_occ, _, diag_occ = count_interactions(sem_filtered, mode="occurrence", min_confidence=0.0)
    pair_counts_strict, _, diag_strict = count_interactions(sem_filtered, mode="binary", min_confidence=0.6)

    assert pair_counts_binary[("alice", "bob")] == 1, pair_counts_binary
    assert pair_counts_binary[("alice", "carol")] == 1, pair_counts_binary
    assert pair_counts_binary[("bob", "carol")] == 1, pair_counts_binary
    assert pair_counts_binary[("carol", "dave")] == 1, pair_counts_binary
    assert diag_binary["units"] == 4, diag_binary

    assert pair_counts_occ[("alice", "bob")] == 2, pair_counts_occ
    assert pair_counts_occ[("alice", "carol")] == 1, pair_counts_occ
    assert pair_counts_occ[("bob", "carol")] == 1, pair_counts_occ
    assert pair_counts_occ[("carol", "dave")] == 1, pair_counts_occ
    assert diag_occ["units"] == 4, diag_occ

    for pair, count in pair_counts_binary.items():
        assert count <= pair_counts_occ[pair], f"binary greater than occurrence for {pair}"
        assert count <= diag_binary["units"], f"binary count exceeds unit total for {pair}"
        assert count >= 0

    for pair, count in pair_counts_occ.items():
        assert count >= 0
        assert count <= diag_occ["units"] * max(diag_occ.get("unit_participant_sizes", {}).values() or [1])

    # determinism check
    pair_counts_binary_2, _, diag_binary_2 = count_interactions(
        sem_filtered, mode="binary", min_confidence=0.0
    )
    assert pair_counts_binary == pair_counts_binary_2, "non-deterministic pair counts"
    assert diag_binary["units"] == diag_binary_2["units"]

    # stricter confidence should not increase totals
    assert sum(pair_counts_strict.values()) <= sum(pair_counts_binary.values())
    assert diag_strict.get("dropped", {}).get("below_confidence", 0) >= 0

    print("OK")


if __name__ == "__main__":
    main()
