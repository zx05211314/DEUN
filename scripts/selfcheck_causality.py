from __future__ import annotations

"""Self-check for causal attribution and counterfactual stability.

This script MUST NOT change metrics or counts; it only validates deterministic
behavior of causal attribution helpers.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.utils.causal_attribution import build_causal_attribution
from app.utils.counterfactuals import (
    INVALID,
    STABLE,
    THRESHOLD_CROSSED,
    simulate_confidence_shift,
    simulate_drop_entity,
    simulate_edge_removal,
)
from app.utils.entity_registry import EntityRegistry
from app.utils.interaction import InteractionUnitRecord, count_interactions



def _build_fixture(registry: EntityRegistry) -> list[dict]:
    sem_filtered = [
        {"event_id": 1, "speaker": "Alice", "target_speaker": "Bob", "distance": 0},
        {"sentence_id": 2, "speaker": "alice", "other_speaker": "Carol", "distance": 2},
        {"chapter_index": 1, "timeline_index": 3, "speaker": "Bob", "target_speaker": "Carol"},
        {"chapter_index": 1, "timeline_index": 4, "speaker": "Ally", "target_speaker": "b0b"},
        {
            "event_id": 5,
            "speaker": "Carol",
            "target_speaker": "Dave",
            "distance": 10,
            "text": "rumor about Carol and Dave",
        },
    ]
    for row in sem_filtered:
        for key in ["speaker", "target_speaker", "other_speaker"]:
            if key in row:
                row[key] = registry.canonicalize(row[key])
    return sem_filtered


def main() -> None:
    registry = EntityRegistry(
        canonical={"alice", "bob", "carol", "dave"},
        aliases={"ally": "alice", "b0b": "bob"},
        blocked=set(),
    )

    sem_filtered = _build_fixture(registry)

    pair_counts, _, diag = count_interactions(sem_filtered, mode="binary", min_confidence=0.2, collect_traces=True)
    assert diag["rows_total"] == len(sem_filtered)

    # determinism of attribution
    any_pair = next(iter(pair_counts)) if pair_counts else None
    unit: InteractionUnitRecord | None = None
    if any_pair:
        unit = diag["pair_units"][any_pair][0]
    else:
        raise AssertionError("No interaction units available for testing")

    attr1 = build_causal_attribution(unit)
    attr2 = build_causal_attribution(unit)
    assert attr1 == attr2, "Attribution not deterministic"

    # idempotence: rebuild on the same unit should not change
    attr3 = build_causal_attribution(unit)
    assert attr1 == attr3, "Attribution not idempotent"

    # monotonic: dropping a contributor eliminates its weight
    drop_result = simulate_drop_entity(unit, unit.a)
    for edge in drop_result.after.edges:
        assert edge.source_id != unit.a, "Dropped entity still present"
    if drop_result.verdict == THRESHOLD_CROSSED:
        assert not drop_result.after.edges

    # counterfactual determinism
    drop_again = simulate_drop_entity(unit, unit.a)
    assert drop_result.delta == drop_again.delta, "Counterfactual not deterministic"

    # confidence shift stability
    shift_result = simulate_confidence_shift(unit, -0.3)
    assert 0.0 <= shift_result.delta["after_confidence"] <= 1.0
    assert shift_result.verdict in {STABLE, THRESHOLD_CROSSED}

    # edge removal stability
    if attr1.edges:
        first_edge_id = f"{attr1.edges[0].source_type}:{attr1.edges[0].source_id}"
        removal = simulate_edge_removal(unit, first_edge_id)
        if removal.verdict == INVALID:
            assert not attr1.edges
        else:
            assert removal.after.edges or removal.verdict == THRESHOLD_CROSSED

    # isolation: counterfactuals must not affect counts
    pair_counts_again, _, diag_again = count_interactions(
        sem_filtered, mode="binary", min_confidence=0.2, collect_traces=True
    )
    assert pair_counts == pair_counts_again, "Counterfactual path mutated counts"
    assert diag["pair_units"] == diag_again["pair_units"], "Diagnostics mutated"

    # monotonic thresholds on attribution availability
    _, _, diag_high = count_interactions(sem_filtered, mode="binary", min_confidence=0.8, collect_traces=True)
    kept_low = sum(len(units) for units in diag.get("pair_units", {}).values())
    kept_high = sum(len(units) for units in diag_high.get("pair_units", {}).values())
    assert kept_high <= kept_low, "Higher threshold produced more units"

    print("OK")


if __name__ == "__main__":
    main()
