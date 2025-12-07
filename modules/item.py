"""Extract items/abilities from novel text with whitelist/blacklist support."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Sequence

import jieba.posseg as pseg

from modules.constants.zh_tokens import ACTION_VERBS, SUFFIX_WHITELIST
from modules.custom_vocab import load_vocab
from modules.user_knowledge import as_sets, load_blacklist, load_whitelist

# Basic keyword hints for item detection
ITEM_KEYWORDS = ["能力", "技能", "道具", "裝備", "武器", "效果", "獲得", "發動", "使用", "卡牌", "卷軸", "藥", "劑", "模組"]

# Type inference heuristics
TYPE_KEYWORDS = {
    "武器": ["刀", "劍", "槍", "斧", "錘", "盾", "弓", "箭", "刃"],
    "藥劑": ["藥", "劑", "瓶", "丹", "藥水", "注射"],
    "卷軸": ["卷軸", "卷"],
    "裝備": ["裝備", "護臂", "盔甲", "護盾", "護具"],
    "能力": ["能力", "技能", "模組", "核心", "卡牌"],
}

ATTRIBUTE_KEYWORDS = {
    "火焰": ["火", "焰", "燃燒", "熔"],
    "冰霜": ["冰", "寒", "霜", "凍"],
    "雷電": ["雷", "電", "閃電"],
    "毒": ["毒", "腐蝕"],
    "治療": ["治療", "回復", "恢復", "治癒"],
    "暗": ["暗", "影"],
    "光": ["光", "聖"],
    "風": ["風", "颶"],
    "水": ["水", "浪", "潮"],
}


def _load_known_characters(output_dir: Path) -> List[str]:
    path = output_dir / "characters.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [row.get("name", "") for row in data if row.get("name")]
        except Exception:
            return []
    return []


def _extract_candidates(sentence: str, wl_items: Sequence[str]) -> List[str]:
    candidates: List[str] = []
    # 《名稱》樣式
    candidates.extend(re.findall(r"《(.{2,12}?)》", sentence))
    # 以「XX能力/武器/裝備」結尾
    tail_match = re.findall(r"([一-龥A-Za-z0-9]{2,12})(?:的)?(?:能力|技能|武器|裝備|道具)", sentence)
    candidates.extend(tail_match)
    # 白名單強制加入
    candidates.extend([w for w in wl_items if w in sentence])
    return candidates


def _passes_filters(name: str, sentence: str, wl_items: Sequence[str], bl_items: Sequence[str]) -> bool:
    if any(b in name for b in bl_items):
        return False
    if name in wl_items:
        return True
    if len(name) < 2:
        return False
    if len(name) < 3 and not any(name.endswith(suf) for suf in SUFFIX_WHITELIST):
        return False
    words = list(pseg.cut(name))
    if not words or not words[0].flag.startswith("n"):
        return False
    if not any(k in sentence for k in ACTION_VERBS + ITEM_KEYWORDS):
        return False
    return True


def _infer_type(name: str, sentence: str) -> str:
    for t, kws in TYPE_KEYWORDS.items():
        if any(k in name for k in kws) or any(k in sentence for k in kws):
            return t
    return "未知"


def _infer_attribute(name: str, sentence: str) -> str:
    for attr, kws in ATTRIBUTE_KEYWORDS.items():
        if any(k in name for k in kws) or any(k in sentence for k in kws):
            return attr
    return "未知"


def extract_items(
    chapter_sentences: Dict[str, List[str]] | None = None,
    novel_path: str | None = None,
    top_n: int = 50,
    max_samples_per_item: int = 5,
    limit_chapters: int | None = None,
    limit_sentences: int | None = None,
    output_path: str = "output/items.json",
) -> List[Dict[str, object]]:
    """
    Extract possible items/abilities from sentences.
    """
    from modules.parser import parse_novel

    if chapter_sentences is None:
        if novel_path is None:
            from modules.config import NOVEL_PATH

            novel_path = NOVEL_PATH
        chapter_sentences = parse_novel(novel_path)

    wl_sets = as_sets(load_whitelist())
    bl_sets = as_sets(load_blacklist())
    vocab = load_vocab()
    # allow custom action verbs expansion
    action_custom = []
    for arr in vocab.get("action", {}).values():
        action_custom.extend(arr)

    wl_items = list(wl_sets.get("items", set()))
    bl_items = list(bl_sets.get("items", set()))

    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True)
    known_chars = _load_known_characters(output_dir)

    counter: Counter[str] = Counter()
    item_sentences: defaultdict[str, List[str]] = defaultdict(list)
    item_type: Dict[str, str] = {}
    item_attr: Dict[str, str] = {}
    owners: defaultdict[str, set] = defaultdict(set)

    action_verbs = ACTION_VERBS + action_custom

    for idx, (chapter, sentences) in enumerate(chapter_sentences.items()):
        if limit_chapters is not None and idx >= limit_chapters:
            break
        for s_idx, sent in enumerate(sentences):
            if limit_sentences is not None and s_idx >= limit_sentences:
                break
            if any(b in sent for b in bl_items):
                continue
            candidates = _extract_candidates(sent, wl_items)
            for name in candidates:
                name = name.strip()
                if not _passes_filters(name, sent, wl_items, bl_items):
                    continue
                counter[name] += 1
                if len(item_sentences[name]) < max_samples_per_item:
                    item_sentences[name].append(sent)
                item_type[name] = item_type.get(name) or _infer_type(name, sent)
                item_attr[name] = item_attr.get(name) or _infer_attribute(name, sent)
                for ch in known_chars:
                    if ch and ch in sent:
                        owners[name].add(ch)

    results: List[Dict[str, object]] = []
    for name, count in counter.most_common(top_n):
        # simple scoring heuristic
        score = 1.0
        if name in wl_items:
            score += 0.5
        if any(name.endswith(suf) for suf in SUFFIX_WHITELIST):
            score += 0.3
        if any(v in "".join(item_sentences[name]) for v in action_verbs):
            score += 0.2
        results.append(
            {
                "name": name,
                "count": count,
                "sample_sentences": item_sentences[name],
                "type": item_type.get(name, "未知"),
                "attribute": item_attr.get(name, "未知"),
                "owner": sorted(list(owners.get(name, set()))),
                "score": round(score, 2),
            }
        )

    Path(output_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    extract_items()
