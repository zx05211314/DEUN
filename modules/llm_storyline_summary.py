"""LLM-assisted storyline summarization per chapter."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from modules.config import HF_NLI_MODEL, VERBOSE
from modules.mission_inference import load_zero_shot_classifier
from modules.user_knowledge import as_sets, load_blacklist, load_whitelist


def _collect_by_chapter(relations: List[Dict]) -> Dict[str, List[Dict]]:
    grouped: Dict[str, List[Dict]] = {}
    for r in relations:
        ch = r.get("chapter", "未知")
        grouped.setdefault(ch, []).append(r)
    return grouped


def _simple_summary(chapter_data: List[Dict], clf=None) -> Tuple[str, List[str], str]:
    if not chapter_data:
        return "", [], ""
    # join top sentences
    sentences = [r.get("sentence", "") for r in chapter_data if r.get("sentence")]
    summary = " ".join(sentences[:3])
    # characters
    char_counter = Counter([r.get("character", "") for r in chapter_data if r.get("character")])
    top_chars = [c for c, _ in char_counter.most_common(3) if c]
    # dominant emotion via zero-shot on concatenated text (reuse NLI classifier)
    emotion = "未知"
    if clf:
        try:
            res = clf(summary, ["憤怒", "恐懼", "悲傷", "喜悅", "冷靜", "未知"])
            if res.get("labels"):
                emotion = res["labels"][0]
        except Exception:
            pass
    return summary, top_chars, emotion


def build_llm_storyline(
    input_path: str = "output/relations_with_context.json",
    output_path: str = "output/storyline_llm_summary.json",
    allow_zero_shot: bool = True,
) -> Dict[str, Dict]:
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Missing {in_path}")
    relations = json.loads(in_path.read_text(encoding="utf-8"))

    wl = as_sets(load_whitelist())
    bl = as_sets(load_blacklist())

    # filter blacklist
    filtered = []
    for r in relations:
        if r.get("character", "") in bl.get("characters", set()):
            continue
        filtered.append(r)

    grouped = _collect_by_chapter(filtered)
    clf = load_zero_shot_classifier(HF_NLI_MODEL) if allow_zero_shot else None

    output: Dict[str, Dict] = {}
    for ch, rows in grouped.items():
        summary, chars, emo = _simple_summary(rows, clf)
        output[ch] = {
            "summary": summary,
            "characters": chars,
            "dominant_emotion": emo,
        }

    out_path = Path(output_path)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    if VERBOSE:
        print(f"[llm_storyline_summary] saved {len(output)} chapters -> {out_path}")
    return output


if __name__ == "__main__":
    build_llm_storyline()
