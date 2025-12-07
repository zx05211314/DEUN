"""Character extractor: builds a simple character index with counts and sample sentences."""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path
from typing import DefaultDict, Dict, List, Sequence, Tuple

_ner_pipe = None

try:
    from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline
except Exception:  # noqa: BLE001
    AutoModelForTokenClassification = None  # type: ignore
    AutoTokenizer = None  # type: ignore
    pipeline = None  # type: ignore


ROLE_STOP = {
    "今天",
    "昨天",
    "明天",
    "夜晚",
    "早上",
    "上午",
    "下午",
    "晚上",
    "夜間",
    "時間",
    "房間",
    "房间",
    "房頂",
    "街道",
    "城市",
    "生活",
    "夏天",
    "冬天",
}


def _load_ner_pipeline():
    """Load HF NER pipeline if available; return None on failure."""
    global _ner_pipe
    if _ner_pipe is not None:
        return _ner_pipe
    if pipeline is None or AutoModelForTokenClassification is None or AutoTokenizer is None:
        return None
    try:
        model_name = "ckiplab/bert-base-chinese-ner"
        _ner_pipe = pipeline(
            "ner",
            model=AutoModelForTokenClassification.from_pretrained(model_name),
            tokenizer=AutoTokenizer.from_pretrained(model_name),
            grouped_entities=True,
        )
    except Exception:  # noqa: BLE001
        _ner_pipe = None
    return _ner_pipe


def _clean_name(name: str) -> str:
    name = re.sub(r"\s+", "", name or "")
    # keep only CJK chars
    if not re.fullmatch(r"[一-龥]{1,4}", name):
        return ""
    if name in ROLE_STOP:
        return ""
    return name


def _extract_persons(sentence: str) -> List[str]:
    persons: List[str] = []
    ner = _load_ner_pipeline()
    if ner:
        try:
            ents = ner(sentence)
            for ent in ents:
                label = ent.get("entity_group") or ent.get("entity") or ""
                if "PER" in label:
                    nm = _clean_name(ent.get("word") or "")
                    if nm:
                        persons.append(nm)
        except Exception:  # noqa: BLE001
            pass
    # fallback: simple 2-4 char CJK spans
    if not persons:
        for m in re.finditer(r"[一-龥]{2,4}", sentence):
            nm = _clean_name(m.group(0))
            if nm:
                persons.append(nm)
    # dedupe while preserving order
    seen = set()
    unique: List[str] = []
    for p in persons:
        if p in seen:
            continue
        seen.add(p)
        unique.append(p)
    return unique


def extract_characters(
    chapter_sentences: Dict[str, List[str]],
    top_n: int = 50,
    max_samples_per_character: int = 5,
) -> List[Dict]:
    """
    擷取小說中的主要角色資訊：
    - name: 角色名稱（透過 NER 模型或規則）
    - count: 出現次數（以句為單位）
    - sample_sentences: 出現的代表句（最多 max_samples_per_character 筆）
    """
    role_counter = collections.Counter()
    role_sentences: DefaultDict[str, List[str]] = collections.defaultdict(list)

    for _, sentences in chapter_sentences.items():
        for sentence in sentences:
            if not sentence.strip():
                continue
            names = _extract_persons(sentence)
            for name in names:
                role_counter[name] += 1
                if len(role_sentences[name]) < max_samples_per_character:
                    role_sentences[name].append(sentence)

    result: List[Dict] = []
    for name, count in role_counter.most_common(top_n):
        result.append(
            {
                "name": name,
                "count": count,
                "sample_sentences": role_sentences[name],
            }
        )
    return result


if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from modules.parser import parse_novel

    chapters_full = parse_novel(str(ROOT / "小說資料" / "輪迴樂園.txt"))
    # Limit for quick smoke test to avoid long HF NER runs on full text.
    limited: Dict[str, List[str]] = {}
    for i, (k, v) in enumerate(chapters_full.items()):
        if i >= 2:  # only first 2 chapters for test
            break
        limited[k] = v[:200]  # cap sentences per chapter

    characters = extract_characters(limited, top_n=20, max_samples_per_character=3)

    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    out_path = output_dir / "characters.json"
    out_path.write_text(json.dumps(characters, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved top {len(characters)} characters to {out_path}")
