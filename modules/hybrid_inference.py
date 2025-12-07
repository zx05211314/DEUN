"""Hybrid inference: combine rule-based action_type with zero-shot fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence

from transformers import pipeline

from modules.config import HF_NLI_MODEL, VERBOSE

# zero-shot labels for action type
ACTION_LABELS: Sequence[str] = ["攻擊", "治療", "支援", "潛行", "控制", "逃生", "探索", "談判", "未知"]


def _load_classifier(model_name: str = HF_NLI_MODEL):
    try:
        clf = pipeline("zero-shot-classification", model=model_name)
        if VERBOSE:
            print(f"[hybrid] loaded zero-shot model: {model_name}")
        return clf
    except Exception as e:  # noqa: BLE001
        if VERBOSE:
            print(f"[hybrid] failed to load zero-shot model, fallback to rule only: {e}")
        return None


def enrich_actions(
    input_path: str = "output/inferred_relations.json",
    output_path: str = "output/hybrid_relations.json",
    model_name: str = HF_NLI_MODEL,
    confidence_threshold: float = 0.5,
) -> List[Dict]:
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Missing {in_path}")

    data: List[Dict] = json.loads(in_path.read_text(encoding="utf-8"))
    clf = _load_classifier(model_name)

    for row in data:
        rule_label = row.get("action_type", "未知")
        row["action_type_rule"] = rule_label
        row["action_type_llm"] = None
        row["action_source"] = "rule"
        row["action_confidence"] = 1.0 if rule_label != "未知" else 0.0
        # zero-shot classify when rule is unknown
        sentence_parts = [row.get("sentence", "")]
        sentence_parts.extend(row.get("context_before", []) or [])
        sentence_parts.extend(row.get("context_after", []) or [])
        text = " ".join(sentence_parts).strip()
        if clf is None or not text:
            row.setdefault("action_type", rule_label)
            continue

        try:
            result = clf(text, ACTION_LABELS)
            if not result or not result.get("labels"):
                row.setdefault("action_type", rule_label)
                continue
            label = result["labels"][0]
            score = float(result["scores"][0])
            row["action_type_llm"] = label
            row["action_confidence_llm"] = score
            # keep both; choose final
            final_label = label if (rule_label == "未知" and score >= confidence_threshold) else rule_label
            row["action_type"] = final_label
            row["action_source"] = "zero-shot" if final_label == label else "rule"
            row["action_confidence"] = score if final_label == label else row["action_confidence"]
        except Exception as e:  # noqa: BLE001
            if VERBOSE:
                print(f"[hybrid] inference failed: {e}")
            row.setdefault("action_type", rule_label)

    out_path = Path(output_path)
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if VERBOSE:
        print(f"[hybrid] enriched {len(data)} rows -> {out_path}")
    return data


def __main__():  # noqa: D401 - entrypoint
    enrich_actions()


if __name__ == "__main__":
    __main__()
