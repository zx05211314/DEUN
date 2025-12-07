"""Generate simple storyline summaries per chapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from modules.config import MAX_CHAPTERS, MAX_SENTENCES, NOVEL_PATH, VERBOSE
from modules.parser import parse_novel


def summarize_chapter(sentences: List[str], max_sentences: int = 3) -> str:
    # naive summary: take first few sentences concatenated
    picked = [s.strip() for s in sentences[:max_sentences] if s.strip()]
    return " ".join(picked)


def build_story_summary(
    novel_path: str = NOVEL_PATH,
    limit_chapters: int | None = MAX_CHAPTERS,
    limit_sentences: int | None = MAX_SENTENCES,
    output_path: str = "output/storyline_summary.json",
) -> Dict[str, str]:
    chapters = parse_novel(novel_path)
    out: Dict[str, str] = {}
    for idx, (ch, sents) in enumerate(chapters.items()):
        if limit_chapters is not None and idx >= limit_chapters:
            break
        limited = sents if limit_sentences is None else sents[:limit_sentences]
        out[ch] = summarize_chapter(limited)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if VERBOSE:
        print(f"[storyline_summary] saved {len(out)} chapters -> {out_file}")
    return out


if __name__ == "__main__":
    build_story_summary()
