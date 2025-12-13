from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any, Dict, List, Tuple


CANDIDATE_FIELDS = [
    "speaker",
    "character",
    "target_speaker",
    "target_character",
    "other_speaker",
    "listener",
    "subject",
    "object_character",
    "object_speaker",
    "target",
]


def extract_characters_from_relation(rel: Dict[str, Any]) -> List[str]:
    participants = set()

    if isinstance(rel.get("participants"), list):
        for p in rel["participants"]:
            if isinstance(p, str) and p.strip():
                participants.add(p.strip())

    for field in CANDIDATE_FIELDS:
        val = rel.get(field)
        if isinstance(val, str) and val.strip():
            participants.add(val.strip())

    return [p for p in participants if p]


def build_pair_counts(sem_filtered: List[Dict]) -> Tuple[Counter, Counter]:
    pair_counts: Counter = Counter()
    character_totals: Counter = Counter()
    for rel in sem_filtered:
        participants = extract_characters_from_relation(rel)
        if len(participants) < 2:
            continue
        for a, b in combinations(sorted(set(participants)), 2):
            pair_counts[(a, b)] += 1
            character_totals[a] += 1
            character_totals[b] += 1
    return pair_counts, character_totals
