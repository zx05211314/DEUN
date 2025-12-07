"""Validate pipeline outputs and report basic stats."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pprint import pprint

OUTPUT_FILES = [
    "output/items.json",
    "output/relations.json",
    "output/relations_with_context.json",
    "output/inferred_relations.json",
    "output/semantic_relations.json",
]

MANDATORY_FIELDS = {
    "items.json": ["name", "score"],
    "relations.json": ["character", "item", "verb", "sentence"],
    "relations_with_context.json": ["character", "item", "verb", "sentence", "context_before", "context_after"],
    "inferred_relations.json": ["character", "item", "verb", "action_type", "power_level", "exclusive"],
    "semantic_relations.json": ["character", "item", "verb", "mission_type", "emotion"],
}


def validate_file(path: str, mandatory_fields):
    if not os.path.exists(path):
        print(f"[❌] File not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:  # noqa: BLE001
            print(f"[❌] Failed to parse {path}: {e}")
            return

    print(f"\n✅ Validating: {path} ({len(data)} records)")
    empty_counter = Counter()
    value_counter = defaultdict(Counter)

    for entry in data:
        for field in mandatory_fields:
            value = entry.get(field, "")
            if value is None or value == "":
                empty_counter[field] += 1
            else:
                value_counter[field][str(value)] += 1

    for field in mandatory_fields:
        print(f" - {field}: {len(value_counter[field])} unique, {empty_counter[field]} empty")

    if "action_type" in value_counter:
        print(" 🔹 action_type 分布：")
        pprint(value_counter["action_type"].most_common())
    if "emotion" in value_counter:
        print(" 🔹 emotion 分布：")
        pprint(value_counter["emotion"].most_common())
    if "mission_type" in value_counter:
        print(" 🔹 mission_type 分布：")
        pprint(value_counter["mission_type"].most_common())


def main():
    print("📊 Pipeline 結果驗證與統計報告")
    for file in OUTPUT_FILES:
        key = os.path.basename(file)
        validate_file(file, MANDATORY_FIELDS.get(key, []))


if __name__ == "__main__":
    main()
