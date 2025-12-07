"""Extract character-to-character relations from novel sentences."""

from __future__ import annotations

import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import jieba.posseg as pseg

from modules.config import MAX_CHAPTERS, MAX_SENTENCES, NOVEL_PATH, VERBOSE
from modules.constants.zh_tokens import ACTION_VERBS, CHARACTER_WHITELIST
from modules.user_knowledge import as_sets, load_blacklist, load_whitelist
from modules.parser import parse_novel

RELATION_RULES: Dict[str, Sequence[str]] = {
    "敵對": ["攻擊", "斬殺", "痛擊", "追殺", "對抗", "仇視"],
    "合作": ["合作", "聯手", "共同", "協力", "結盟"],
    "援助": ["援助", "幫助", "救下", "支援", "治療", "保護", "援護"],
    "衝突": ["衝突", "爭吵", "矛盾", "推搡", "打鬥"],
    "指令": ["命令", "指示", "派遣", "安排"],
    "通報": ["通知", "告知", "報告", "匯報"],
}


def _load_known_characters(output_dir: Path) -> List[str]:
    char_path = output_dir / "characters.json"
    if char_path.exists():
        try:
            data = json.loads(char_path.read_text(encoding="utf-8"))
            names = [row.get("name", "") for row in data if row.get("name")]
            return list(set(names + CHARACTER_WHITELIST))
        except Exception:
            return CHARACTER_WHITELIST
    return CHARACTER_WHITELIST


try:
    from transformers import pipeline
except Exception:  # noqa: BLE001
    pipeline = None  # type: ignore


RELATION_LABELS = list(RELATION_RULES.keys()) + ["互動", "未知"]


def _classify_relation(sentence: str, clf=None, confidence_threshold: float = 0.5) -> Tuple[str, str, float, str]:
    """Return (relation_type, verb_hit/label, confidence, source)."""
    for rel, keywords in RELATION_RULES.items():
        for kw in keywords:
            if kw in sentence:
                return rel, kw, 1.0, "rule"
    for verb in ACTION_VERBS:
        if verb in sentence:
            return "互動", verb, 0.6, "rule"
    if clf is not None and sentence.strip():
        try:
            res = clf(sentence, RELATION_LABELS)
            if res and res.get("labels"):
                label = res["labels"][0]
                score = float(res["scores"][0])
                if score >= confidence_threshold:
                    return label, label, score, "zero-shot"
        except Exception:
            pass
    return "未知", "", 0.0, "rule"


def extract_character_relations(
    novel_path: str | Path = NOVEL_PATH,
    output_path: str = "output/character_relations.json",
    limit_chapters: int | None = MAX_CHAPTERS,
    limit_sentences: int | None = MAX_SENTENCES,
) -> List[Dict]:
    novel_path = Path(novel_path)
    chapters = parse_novel(str(novel_path))

    # apply limits
    limited = {}
    for i, (ch, sentences) in enumerate(chapters.items()):
        if limit_chapters is not None and i >= limit_chapters:
            break
        limited[ch] = sentences if limit_sentences is None else sentences[:limit_sentences]

    output_dir = Path(output_path).parent
    output_dir.mkdir(exist_ok=True)
    known_chars = _load_known_characters(output_dir)
    wl = as_sets(load_whitelist())
    bl = as_sets(load_blacklist())
    known_chars = list(set(known_chars).union(wl.get("characters", set())))

    clf = None
    if pipeline is not None:
        try:
            clf = pipeline("zero-shot-classification", model="MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli")
        except Exception:
            clf = None

    relations: List[Dict] = []
    for chapter, sentences in limited.items():
        for sent in sentences:
            if any(bc for bc in bl.get("characters", set()) if bc and bc in sent):
                continue
            hits = [name for name in known_chars if name and name in sent]
            if len(hits) < 2:
                continue
            # pick all combinations of detected characters in order
            ordered = sorted(set(hits), key=lambda n: sent.index(n))
            for a, b in combinations(ordered, 2):
                rel_type, verb_hit, conf, source = _classify_relation(sent, clf=clf)
                relations.append(
                    {
                        "chapter": chapter,
                        "character_a": a,
                        "character_b": b,
                        "relation_type": rel_type,
                        "verb": verb_hit,
                        "sentence": sent,
                        "relation_confidence": conf,
                        "relation_source": source,
                    }
                )

    Path(output_path).write_text(json.dumps(relations, ensure_ascii=False, indent=2), encoding="utf-8")
    if VERBOSE:
        print(f"[character_relations] extracted {len(relations)} relations -> {output_path}")
    return relations


def __main__():  # noqa: D401 - entrypoint
    extract_character_relations()


if __name__ == "__main__":
    __main__()
