"""Enrich relations with surrounding context sentences."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List


def enrich_with_context(relations: List[Dict], chapter_sentences: Dict[str, List[str]], window_size: int = 1) -> List[Dict]:
    """Add context_before/context_after around each relation sentence."""
    enriched: List[Dict] = []
    for rel in relations:
        chapter = rel.get("chapter")
        sentence = rel.get("sentence")
        if not chapter or not sentence:
            continue
        sentences = chapter_sentences.get(chapter)
        if not sentences:
            continue
        try:
            idx = sentences.index(sentence)
        except ValueError:
            continue
        before = sentences[max(0, idx - window_size) : idx]
        after = sentences[idx + 1 : idx + 1 + window_size]
        rel = dict(rel)
        rel["context_before"] = before
        rel["context_after"] = after
        enriched.append(rel)
    return enriched


def main():
    """Standalone runner: load output/relations.json, parse novel, save relations_with_context.json."""
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from modules.config import NOVEL_PATH, MAX_CHAPTERS, MAX_SENTENCES
    from modules.parser import parse_novel

    rel_path = ROOT / "output" / "relations.json"
    if not rel_path.exists():
        print(f"Missing {rel_path}, please run modules.relations first.")
        return
    try:
        relations = json.loads(rel_path.read_text(encoding="utf-8"))
    except Exception:
        print(f"Failed to load {rel_path}")
        return

    chapters_full = parse_novel(str(ROOT / NOVEL_PATH))
    limited: Dict[str, List[str]] = {}
    for idx, (k, v) in enumerate(chapters_full.items()):
        if MAX_CHAPTERS is not None and idx >= MAX_CHAPTERS:
            break
        limited[k] = v if MAX_SENTENCES is None else v[:MAX_SENTENCES]

    enriched = enrich_with_context(relations, limited, window_size=1)

    out_path = ROOT / "output" / "relations_with_context.json"
    out_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(enriched)} enriched relations to {out_path}")


if __name__ == "__main__":
    main()
