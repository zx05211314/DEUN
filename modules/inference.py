"""Inference layer: classify action types with rule + optional zero-shot fallback.

Input : output/relations_with_context.json
Output: output/inferred_relations.json

Features
- Load whitelist / blacklist (input/whitelist.json / blacklist.json) to filter/force subjects & objects.
- Load custom vocab (input/vocab_overrides.json) to extend action keywords.
- Rule-based action classification; if still unknown, optional zero-shot (NLI) fallback.
- Robust to malformed rows; missing values default to "未知".
"""

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

# ---- Defaults ----
DEFAULT_ACTION_LABELS = ["攻擊", "支援", "控制", "逃亡", "探索", "談判", "拯救", "守衛", "未知"]

ACTION_KEYWORDS: Dict[str, List[str]] = {
    "攻擊": ["攻擊", "斬", "砍", "刺", "轟", "爆", "擊", "射", "轟炸", "衝鋒"],
    "支援": ["增益", "強化", "保護", "護盾", "遮蔽", "治療", "恢復", "補血"],
    "控制": ["冰凍", "麻痺", "定身", "束縛", "禁錮", "封鎖"],
    "逃亡": ["撤退", "逃離", "逃跑", "脫離", "離開"],
    "探索": ["搜索", "探索", "調查", "尋找"],
    "談判": ["談判", "協商", "交流", "溝通"],
    "拯救": ["救援", "營救", "幫助"],
    "守衛": ["守衛", "防禦", "護送", "守護"],
}


def _extend_with_custom_vocab():
    vocab = load_vocab()
    for lbl, words in (vocab.get("action") or {}).items():
        ACTION_KEYWORDS.setdefault(lbl, []).extend(words)


def _load_llm_classifier():
    if pipeline is None:
        return None
    try:
        return pipeline("zero-shot-classification", model=HF_NLI_MODEL)
    except Exception as e:  # noqa: BLE001
        if VERBOSE:
            print(f"[inference] zero-shot classifier load failed: {e}")
        return None


def classify_rule(sentence: str) -> Tuple[str, float]:
    for label, words in ACTION_KEYWORDS.items():
        if any(w for w in words if w and w in sentence):
            return label, 0.9
    return "未知", 0.0


def classify_llm(sentence: str, labels: List[str], clf=None) -> Tuple[str, float]:
    if clf is None:
        return "未知", 0.0
    try:
        res = clf(sentence, labels)
        if isinstance(res, dict):
            lbls = res.get("labels") or []
            scores = res.get("scores") or []
            if lbls:
                return lbls[0], float(scores[0]) if scores else 0.0
    except Exception as e:  # noqa: BLE001
        if VERBOSE:
            print(f"[inference] llm classify failed: {e}")
    return "未知", 0.0


def _apply_knowledge_filter(subject: str, obj: str, wl: Dict[str, set], bl: Dict[str, set]) -> Tuple[bool, str, str]:
    # blacklist skip
    if subject in bl.get("characters", set()) or obj in bl.get("items", set()):
        return False, subject, obj
    # whitelist reinforce
    if not subject:
        for cand in wl.get("characters", set()):
            subject = cand
            break
    if not obj:
        for cand in wl.get("items", set()):
            obj = cand
            break
    return True, subject, obj


def extract_inferences(
    input_path: str = "output/relations_with_context.json",
    output_path: str = "output/inferred_relations.json",
    allow_zero_shot_action: bool = True,
) -> List[Dict]:
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Missing {in_path}")

    _extend_with_custom_vocab()
    wl = as_sets(load_whitelist())
    bl = as_sets(load_blacklist())

    try:
        rows: List[Dict] = json.loads(in_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to load {in_path}: {e}") from e

    clf = _load_llm_classifier() if allow_zero_shot_action else None

    outputs: List[Dict] = []
    for d in rows:
        subject = d.get("character") or d.get("subject") or ""
        obj = d.get("item") or d.get("object") or ""
        verb = d.get("verb") or ""
        sentence = d.get("sentence") or ""
        ok, subject, obj = _apply_knowledge_filter(subject, obj, wl, bl)
        if not ok:
            continue

        # Rule classification
        act_rule, conf_rule = classify_rule(sentence)

        # LLM fallback
        act_llm, conf_llm = ("未知", 0.0)
        if act_rule == "未知" and allow_zero_shot_action:
            act_llm, conf_llm = classify_llm(sentence, DEFAULT_ACTION_LABELS, clf)

        # Final decision
        if act_rule != "未知":
            action_type = act_rule
            confidence = conf_rule
            source = "rule"
        else:
            action_type = act_llm
            confidence = conf_llm
            source = "llm" if act_llm != "未知" else "unknown"

        out = {
            "character": subject,
            "item": obj,
            "verb": verb or "無明確動詞",
            "sentence": sentence,
            "chapter": d.get("chapter", ""),
            "location": d.get("location", ""),
            "time": d.get("time", ""),
            "context_before": d.get("context_before", []),
            "context_after": d.get("context_after", []),
            "action_type_rule": act_rule,
            "action_type_llm": act_llm,
            "action_type": action_type,
            "action_confidence": confidence,
            "action_source": source,
        }
        outputs.append(out)

    out_path = Path(output_path)
    out_path.parent.mkdir(exist_ok=True, parents=True)
    out_path.write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    if VERBOSE:
        print(f"[inference] saved {len(outputs)} rows -> {out_path}")
    return outputs


if __name__ == "__main__":
    extract_inferences()
