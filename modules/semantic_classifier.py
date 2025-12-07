"""Semantic classifier for mission & emotion with custom vocab and zero-shot fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from modules.config import HF_NLI_MODEL, VERBOSE
from modules.custom_vocab import load_vocab
from modules.mission_inference import infer_mission  # zero-shot fallback if available
from modules.user_knowledge import as_sets, load_blacklist, load_whitelist

# Default keyword dictionaries (clean UTF-8)
MISSION_KEYWORDS: Dict[str, List[str]] = {
    "擊殺": ["殺", "斬", "滅", "刺", "擊倒"],
    "守衛": ["守", "保護", "防禦", "護送"],
    "探索": ["找", "探索", "尋", "調查", "搜索"],
    "談判": ["談", "協商", "溝通", "交流"],
    "逃亡": ["逃", "撤退", "離開", "躲避", "脫離"],
    "救援": ["救", "營救", "幫助", "支援"],
}

EMOTION_KEYWORDS: Dict[str, List[str]] = {
    "憤怒": ["怒", "恨", "火", "咆哮"],
    "恐懼": ["怕", "恐", "驚", "顫抖"],
    "冷靜": ["冷靜", "沉著", "淡定"],
    "悲傷": ["悲", "傷", "哭", "淚"],
    "喜悅": ["喜", "樂", "笑", "開心"],
}


def _extend_with_custom_vocab():
    vocab = load_vocab()
    for lbl, words in (vocab.get("mission") or {}).items():
        MISSION_KEYWORDS.setdefault(lbl, []).extend(words)
    for lbl, words in (vocab.get("emotion") or {}).items():
        EMOTION_KEYWORDS.setdefault(lbl, []).extend(words)


def classify_mission_rule(sentence: str) -> str:
    for m_type, keywords in MISSION_KEYWORDS.items():
        if any(kw in sentence for kw in keywords):
            return m_type
    return "未知"


def classify_emotion_rule(sentence: str) -> str:
    for emo, keywords in EMOTION_KEYWORDS.items():
        if any(kw in sentence for kw in keywords):
            return emo
    return "無標記"


def extract_semantics(
    input_path: str = "output/inferred_relations.json",
    output_path: str = "output/semantic_relations.json",
    allow_zero_shot_task: bool = True,
    allow_zero_shot_emotion: bool = False,  # currently unused; placeholder for future emotion llm
) -> List[Dict]:
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Missing {in_path}")

    _extend_with_custom_vocab()
    wl = as_sets(load_whitelist())
    bl = as_sets(load_blacklist())

    rows: List[Dict] = json.loads(in_path.read_text(encoding="utf-8"))
    outputs: List[Dict] = []

    for d in rows:
        subject = d.get("character") or ""
        obj = d.get("item") or ""
        if subject in bl.get("characters", set()) or obj in bl.get("items", set()):
            continue
        # rule classifications
        sentence = d.get("sentence", "")
        mission_rule = classify_mission_rule(sentence)
        emotion_rule = classify_emotion_rule(sentence)

        mission = mission_rule
        mission_conf = 0.0
        mission_source = "rule"

        if mission_rule == "未知" and allow_zero_shot_task:
            mission_llm, conf = infer_mission(sentence, labels=list(MISSION_KEYWORDS.keys()), model_name=HF_NLI_MODEL)
            mission = mission_llm
            mission_conf = conf
            mission_source = "llm" if mission_llm != "未知" else "rule"

        out = {
            **d,
            "mission_type": mission,
            "mission_confidence": mission_conf,
            "mission_source": mission_source,
            "emotion": emotion_rule,
        }
        outputs.append(out)

    out_path = Path(output_path)
    out_path.parent.mkdir(exist_ok=True, parents=True)
    out_path.write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    if VERBOSE:
        print(f"[semantic_classifier] saved {len(outputs)} rows → {out_path}")
    return outputs


if __name__ == "__main__":
    extract_semantics()
