"""Generate suggested whitelist terms from low-semantic sentences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import jieba.posseg as pseg
from sklearn.feature_extraction.text import TfidfVectorizer

INPUT_ROOT = Path("input")
OUTPUT_ROOT = Path("output")


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_tokens(sentences: list[str], whitelist: set[str], blacklist: set[str], top_n: int = 30):
    if not sentences:
        return []
    vec = TfidfVectorizer(token_pattern=r"(?u)\\b[^\\s]+\\b")
    X = vec.fit_transform(sentences)
    scores = X.sum(axis=0).A1
    tokens = vec.get_feature_names_out()
    ranked = sorted(zip(tokens, scores), key=lambda x: -x[1])
    candidates = []
    for tok, _ in ranked:
        if tok in whitelist or tok in blacklist:
            continue
        if tok.strip():
            candidates.append(tok.strip())
        if len(candidates) >= top_n:
            break
    return candidates


def pos_filter(tokens: Iterable[str], keep_flags={"n", "nr", "ns", "nt", "nz", "vn"}) -> list[str]:
    out = []
    for t in tokens:
        flag = pseg.lcut(t)
        if not flag:
            continue
        if flag[0].flag[:2] in keep_flags or flag[0].flag in keep_flags:
            out.append(t)
    return out


def suggest_for_book(book_dir: Path) -> dict:
    sem = load_json(book_dir / "semantic_relations.json") or []
    relations = load_json(book_dir / "relations.json") or []
    sentences = []
    for r in sem:
        if r.get("sentence"):
            sentences.append(r["sentence"])
    # 若語意為空，嘗試 relations
    if not sentences and relations:
        for r in relations:
            if r.get("sentence"):
                sentences.append(r["sentence"])
    # 若仍空，返回空結果
    if not sentences:
        return {"suggested_characters": [], "suggested_items": [], "suggested_time_terms": []}

    wl = load_json(INPUT_ROOT / "whitelist.json") or {"characters": [], "items": [], "time": []}
    bl = load_json(INPUT_ROOT / "blacklist.json") or {"characters": [], "items": [], "time": []}
    wl_set = set(wl.get("characters", []) + wl.get("items", []) + wl.get("time", []))
    bl_set = set(bl.get("characters", []) + bl.get("items", []) + bl.get("time", []))

    candidates = extract_tokens(sentences, wl_set, bl_set, top_n=50)
    candidates = pos_filter(candidates)

    # 簡易分類：包含“刀/槍/劍/藥/卷/之/核/石”等視為道具，其餘視為角色或時間
    items = [c for c in candidates if any(s in c for s in ["刀", "槍", "劍", "藥", "卷", "核", "石", "裝", "槍", "彈"])]
    times = [c for c in candidates if any(s in c for s in ["天", "夜", "清晨", "傍晚", "日", "時", "前夕", "之後"])]
    chars = [c for c in candidates if c not in items and c not in times]

    return {
        "suggested_characters": list(dict.fromkeys(chars))[:20],
        "suggested_items": list(dict.fromkeys(items))[:20],
        "suggested_time_terms": list(dict.fromkeys(times))[:20],
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--book-name", required=True, help="對應 output/<book-name>")
    args = parser.parse_args()

    book_dir = OUTPUT_ROOT / args.book_name
    if not book_dir.exists():
        print(f"[suggest] missing {book_dir}")
        return
    result = suggest_for_book(book_dir)
    out_path = book_dir / "suggested_whitelist.json"
    save_json(out_path, result)
    print(f"[suggest] saved -> {out_path}")


if __name__ == "__main__":
    main()
