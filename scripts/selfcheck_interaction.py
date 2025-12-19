from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.utils.interaction import count_interactions



def main() -> None:
    sem_filtered = [
        {"event_id": 1, "speaker": "Alice", "target_speaker": "Bob"},
        {"event_id": 1, "speaker": "alice", "other_speaker": "Bob"},
        {"sentence_id": 5, "participants": ["Alice", "Carol"]},
        {"chapter_index": 1, "timeline_index": 1, "speaker": "Bob", "target_speaker": "Carol"},
    ]

    pair_counts_binary, _, diag_binary = count_interactions(sem_filtered, mode="binary")
    pair_counts_occ, _, diag_occ = count_interactions(sem_filtered, mode="occurrence")

    assert pair_counts_binary[("alice", "bob")] == 1, pair_counts_binary
    assert pair_counts_binary[("alice", "carol")] == 1, pair_counts_binary
    assert pair_counts_binary[("bob", "carol")] == 1, pair_counts_binary
    assert diag_binary["units"] == 3

    assert pair_counts_occ[("alice", "bob")] == 2, pair_counts_occ
    assert pair_counts_occ[("alice", "carol")] == 1, pair_counts_occ
    assert pair_counts_occ[("bob", "carol")] == 1, pair_counts_occ
    assert diag_occ["units"] == 3

    for pair, count in pair_counts_binary.items():
        assert count <= pair_counts_occ[pair], f"binary greater than occurrence for {pair}"
        assert count <= diag_binary["units"], f"binary count exceeds unit total for {pair}"
        assert count >= 0

    for pair, count in pair_counts_occ.items():
        assert count >= 0
        assert count <= diag_occ["units"] * max(diag_occ.get("unit_participant_sizes", {}).values() or [1])

    # determinism check
    pair_counts_binary_2, _, diag_binary_2 = count_interactions(sem_filtered, mode="binary")
    assert pair_counts_binary == pair_counts_binary_2, "non-deterministic pair counts"
    assert diag_binary["units"] == diag_binary_2["units"]

    print("OK")


if __name__ == "__main__":
    main()
