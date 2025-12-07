"""Annotate emotion strength (強/中/弱/未知) with rule + optional zero-shot fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from modules.config import HF_NLI_MODEL, VERBOSE
from modules.custom_vocab import load_vocab
from modules.user_knowledge import as_sets, load_blacklist, load_whitelist

try:
    from transformers import pipeline
except Exception:  # noqa: BLE001
    pipeline = None  # type: ignore

DEFAULT_LEVELS = ["強", "中", "弱", "未知"]

# 修飾詞對應強度
STRONG_MOD = ["非常", "極度", "十分", "極其", "暴躁", "強烈"]
MEDIUM_MOD = ["有些", "有點", "有些許", "稍微"]
WEAK_MOD = ["略", "稍"]


def _extend_vocab():
    vocab = load_vocab()
    # 自訂 emotion 強度修飾詞
    mods = vocab.get("emotion") or {}
    STRONG_MOD.extend(mods.get("strong", []))
    MEDIUM_MOD.extend(mods.get("medium", []))
    WEAK_MOD.extend(mods.get("weak", []))


def _classify_rule(sentence: str) -> Tuple[str, float]:
    if any(m in sentence for m in STRONG_MOD):
        return "強", 0.8
    if any(m in sentence for m in MEDIUM_MOD):
        return "中", 0.6
    if any(m in sentence for m in WEAK_MOD):
        return "弱", 0.4
    return "未知", 0.0


def _load_zero_shot():
    if pipeline is None:
        return None
    try:
        return pipeline("zero-shot-classification", model=HF_NLI_MODEL)
    except Exception as e:  # noqa: BLE001
        if VERBOSE:
            print(f"[emotion_strength] zero-shot load failed: {e}")
        return None


def _classify_llm(sentence: str, clf) -> Tuple[str, float]:
    if clf is None or not sentence.strip():
        return "未知", 0.0
    try:
        res = clf(sentence, DEFAULT_LEVELS)
        lbls = res.get("labels") or []
        scores = res.get("scores") or []
        if lbls:
            return lbls[0], float(scores[0]) if scores else 0.0
    except Exception as e:  # noqa: BLE001
        if VERBOSE:
            print(f"[emotion_strength] llm failed: {e}")
    return "未知", 0.0


def annotate_emotion_strength(
    input_path: str = "output/semantic_relations.json",
    output_path: str = "output/semantic_relations.json",
    allow_zero_shot_emotion_strength: bool = True,
) -> List[Dict]:
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Missing {in_path}")

    _extend_vocab()
    wl = as_sets(load_whitelist())
    bl = as_sets(load_blacklist())

    data: List[Dict] = json.loads(in_path.read_text(encoding="utf-8"))
    clf = _load_zero_shot() if allow_zero_shot_emotion_strength else None

    out_rows: List[Dict] = []
    for d in data:
        subj = d.get("character", "")
        itm = d.get("item", "")
        if subj in bl.get("characters", set()) or itm in bl.get("items", set()):
            continue
        sentence = d.get("sentence", "")
        level_rule, conf_rule = _classify_rule(sentence)
        level = level_rule
        conf = conf_rule
        source = "rule"
        if level_rule == "未知":
            level_llm, conf_llm = _classify_llm(sentence, clf)
            if level_llm != "未知":
                level = level_llm
                conf = conf_llm
                source = "llm"
        d["emotion_strength"] = level
        d["emotion_strength_confidence"] = conf
        d["emotion_strength_source"] = source
        out_rows.append(d)

    out_path = Path(output_path)
    out_path.write_text(json.dumps(out_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if VERBOSE:
        print(f"[emotion_strength] annotated {len(out_rows)} rows -> {out_path}")
    return out_rows


if __name__ == "__main__":
    annotate_emotion_strength()
