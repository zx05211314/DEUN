"""Generate summary reports and charts from pipeline outputs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt


def load_json(path: Path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def summarize_items(items: List[Dict]) -> Dict:
    type_counter = Counter()
    attr_counter = Counter()
    for it in items:
        if it.get("type"):
            type_counter[it["type"]] += 1
        for att in it.get("attribute", []):
            attr_counter[att] += 1
    return {"total": len(items), "types": type_counter, "attributes": attr_counter}


def summarize_relations(relations: List[Dict]) -> Dict:
    by_char = defaultdict(Counter)
    by_item = defaultdict(Counter)
    action_counter = Counter()
    for r in relations:
        c = r.get("character", "")
        i = r.get("item", "")
        a = r.get("action_type", "未知")
        if c and a:
            by_char[c][a] += 1
        if i and c:
            by_item[i][c] += 1
        action_counter[a] += 1
    return {"action_counter": action_counter, "by_char": by_char, "by_item": by_item}


def summarize_semantic(semantic_rel: List[Dict]) -> Dict:
    mission_counter = Counter()
    emotion_counter = Counter()
    strength_counter = Counter()
    for r in semantic_rel:
        mission_counter[r.get("mission_type", "未知")] += 1
        emotion_counter[r.get("emotion", "無標記")] += 1
        strength_counter[r.get("emotion_strength", "無標記")] += 1
    return {"mission": mission_counter, "emotion": emotion_counter, "emotion_strength": strength_counter}


def export_counter_map(counter_map: Dict, path: Path, fieldnames=("key", "count")):
    import csv

    rows = []
    for k, v in counter_map.items():
        rows.append({fieldnames[0]: k, fieldnames[1]: v})
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_bar(counter: Counter, title: str, fname: Path):
    if not counter:
        return
    labels, values = zip(*counter.most_common())
    plt.figure(figsize=(8, 4))
    plt.bar(labels, values)
    plt.title(title)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    fname.parent.mkdir(exist_ok=True, parents=True)
    plt.savefig(fname, dpi=200)
    plt.close()


def save_pie(counter: Counter, title: str, fname: Path):
    if not counter:
        return
    labels, values = zip(*counter.most_common())
    plt.figure(figsize=(6, 6))
    plt.pie(values, labels=labels, autopct="%1.1f%%")
    plt.title(title)
    fname.parent.mkdir(exist_ok=True, parents=True)
    plt.savefig(fname, dpi=200)
    plt.close()


def save_hist(values: List[float], title: str, fname: Path):
    if not values:
        return
    plt.figure(figsize=(6, 4))
    plt.hist(values, bins=10, range=(0, 1))
    plt.title(title)
    plt.xlabel("confidence")
    plt.ylabel("count")
    fname.parent.mkdir(exist_ok=True, parents=True)
    plt.tight_layout()
    plt.savefig(fname, dpi=200)
    plt.close()


def main(by_character: bool = False, by_item: bool = False):
    ROOT = Path(__file__).resolve().parents[1]
    out_dir = ROOT / "output"

    items = load_json(out_dir / "items.json")
    inferred = load_json(out_dir / "inferred_relations.json")
    semantic_rel = load_json(out_dir / "semantic_relations.json")

    report = {
        "items": summarize_items(items),
        "relations": summarize_relations(inferred),
        "semantic": summarize_semantic(semantic_rel),
    }

    # JSON summaries
    (out_dir / "items_summary.json").write_text(json.dumps(report["items"], ensure_ascii=False, indent=2), encoding="utf-8")
    rel_summary = {"action_counter": {k: v for k, v in report["relations"]["action_counter"].items()}}
    if by_character:
        rel_summary["by_character"] = {k: dict(v) for k, v in report["relations"]["by_char"].items()}
    if by_item:
        rel_summary["by_item"] = {k: dict(v) for k, v in report["relations"]["by_item"].items()}
    (out_dir / "relations_summary.json").write_text(json.dumps(rel_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "semantic_summary.json").write_text(
        json.dumps(
            {
                "mission": {k: v for k, v in report["semantic"]["mission"].items()},
                "emotion": {k: v for k, v in report["semantic"]["emotion"].items()},
                "emotion_strength": {k: v for k, v in report["semantic"]["emotion_strength"].items()},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # CSVs
    export_counter_map(report["relations"]["action_counter"], out_dir / "action_type_counts.csv", ("action_type", "count"))
    export_counter_map(report["semantic"]["mission"], out_dir / "mission_counts.csv", ("mission_type", "count"))
    export_counter_map(report["semantic"]["emotion"], out_dir / "emotion_counts.csv", ("emotion", "count"))
    export_counter_map(report["semantic"]["emotion_strength"], out_dir / "emotion_strength_counts.csv", ("emotion_strength", "count"))

    charts_dir = out_dir / "charts"
    save_bar(report["relations"]["action_counter"], "Action Type 分布", charts_dir / "action_type_bar.png")
    save_bar(report["semantic"]["mission"], "Mission Type 分布", charts_dir / "mission_bar.png")
    save_bar(report["semantic"]["emotion"], "Emotion 分布", charts_dir / "emotion_bar.png")
    save_bar(report["semantic"]["emotion_strength"], "Emotion Strength 分布", charts_dir / "emotion_strength_bar.png")

    save_pie(report["semantic"]["mission"], "Mission Type 圓餅圖", charts_dir / "mission_pie.png")
    save_pie(report["semantic"]["emotion"], "Emotion 圓餅圖", charts_dir / "emotion_pie.png")
    save_pie(report["semantic"]["emotion_strength"], "Emotion Strength 圓餅圖", charts_dir / "emotion_strength_pie.png")

    # confidence histogram (action_confidence from inferred_relations)
    confidences = [float(r.get("action_confidence", 0) or 0) for r in inferred if r.get("action_confidence") is not None]
    save_hist(confidences, "Action Confidence 分布", charts_dir / "confidence_histogram.png")

    print("報告輸出完成：")
    print(f"- items_summary.json / relations_summary.json / semantic_summary.json")
    print(f"- action_type_counts.csv / mission_counts.csv / emotion_counts.csv / emotion_strength_counts.csv")
    print(f"- 圖表輸出於 {charts_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--by-character", action="store_true", help="輸出每個角色的行為分布")
    parser.add_argument("--by-item", action="store_true", help="輸出每個道具的使用者分布")
    args = parser.parse_args()
    main(by_character=args.by_character, by_item=args.by_item)
