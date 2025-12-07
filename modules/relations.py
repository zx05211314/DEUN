"""Extract character-item relations with verb detection and knowledge filters."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

try:
    import jieba.posseg as pseg  # type: ignore
except Exception:  # noqa: BLE001
    pseg = None  # type: ignore

from modules.config import MAX_CHAPTERS, MAX_SENTENCES, NOVEL_PATH, VERBOSE
from modules.constants.zh_tokens import ACTION_VERBS
from modules.custom_vocab import load_vocab
from modules.parser import parse_novel
from modules.user_knowledge import as_sets, load_blacklist, load_whitelist


VERB_PATTERNS = [
    r"(使用|啟動|裝備|持有|投擲|釋放|揮舞|開啟)",
    r"([一-龥]{0,4}擊殺)",
    r"([一-龥]{0,4}攻擊)",
]


def _extend_verbs(base: List[str]) -> List[str]:
    vocab = load_vocab()
    extra = vocab.get("action") or {}
    for _, words in extra.items():
        base.extend(words)
    # deduplicate
    return list(dict.fromkeys([v for v in base if v]))


def _load_json_list(path: Path, key: str = "name") -> List[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [row.get(key, "") if isinstance(row, dict) else str(row) for row in data]
    except Exception:  # noqa: BLE001
        return []
    return []


def _detect_verbs(sentence: str, verbs: Iterable[str]) -> List[str]:
    hits: List[str] = []
    for v in verbs:
        if v and v in sentence:
            hits.append(v)
    if pseg:
        try:
            for w, flag in pseg.lcut(sentence):
                if flag.startswith("v") and w not in hits:
                    hits.append(w)
        except Exception:  # noqa: BLE001
            pass
    for pat in VERB_PATTERNS:
        m = re.search(pat, sentence)
        if m:
            val = m.group(1) if m.lastindex else m.group(0)
            if val and val not in hits:
                hits.append(val)
    return hits


def extract_relations(
    chapter_sentences: Dict[str, List[str]],
    item_list: Sequence[str],
    character_list: Sequence[str],
    strict_mode: bool = False,
) -> List[Dict]:
    verbs = _extend_verbs(list(ACTION_VERBS))
    wl = as_sets(load_whitelist())
    bl = as_sets(load_blacklist())

    item_set = {i for i in item_list if i}
    item_set |= wl.get("items", set())
    char_set = {c for c in character_list if c}
    char_set |= wl.get("characters", set())

    relations: List[Dict] = []
    for chapter, sentences in chapter_sentences.items():
        for sent in sentences:
            if not sent.strip():
                continue
            # blacklist skip
            if any(bi in sent for bi in bl.get("items", set())) or any(bc in sent for bc in bl.get("characters", set())):
                continue

            matched_chars = [c for c in char_set if c in sent]
            matched_items = [i for i in item_set if i in sent]
            if not matched_chars or not matched_items:
                continue

            verb_hits = _detect_verbs(sent, verbs)
            if strict_mode and not verb_hits:
                continue

            for ch in matched_chars:
                for it in matched_items:
                    verb_value = verb_hits[0] if verb_hits else "未標記"
                    relations.append(
                        {
                            "chapter": chapter,
                            "character": ch,
                            "item": it,
                            "verb": verb_value,
                            "sentence": sent,
                        }
                    )
    return relations


def main():
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    novel_path = ROOT / NOVEL_PATH
    chapters_full = parse_novel(str(novel_path))

    limited: Dict[str, List[str]] = {}
    for i, (k, v) in enumerate(chapters_full.items()):
        if MAX_CHAPTERS is not None and i >= MAX_CHAPTERS:
            break
        limited[k] = v if MAX_SENTENCES is None else v[:MAX_SENTENCES]

    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)

    characters = _load_json_list(output_dir / "characters.json", key="name")
    items = _load_json_list(output_dir / "items.json", key="name")

    relations = extract_relations(
        limited,
        item_list=items,
        character_list=characters,
        strict_mode=False,
    )

    out_path = output_dir / "relations.json"
    out_path.write_text(json.dumps(relations, ensure_ascii=False, indent=2), encoding="utf-8")
    if VERBOSE:
        print(f"[relations] extracted {len(relations)} -> {out_path}")


if __name__ == "__main__":
    main()
