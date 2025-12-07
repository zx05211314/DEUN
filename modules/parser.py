"""Novel parser: chapter segmentation and sentence splitting."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from modules.constants.zh_tokens import CHAPTER_PATTERN


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences by common Chinese delimiters and newlines."""
    parts = re.split(r"[。！？\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def _read_text(filepath: str, encoding: str | None = None) -> Tuple[str, str]:
    """
    Read a text file trying common Chinese encodings when none is specified.

    Returns (text, chosen_encoding).
    """
    candidates = (
        [encoding]
        if encoding
        else ["utf-8", "utf-16", "utf-16le", "utf-16be", "gb18030", "big5", "cp950"]
    )
    for enc in candidates:
        if not enc:
            continue
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read(), enc
        except (UnicodeDecodeError, LookupError):
            continue

    # Last resort: utf-8 with ignore to avoid crashing, but content may be lossy.
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read(), "utf-8 (errors=ignore)"


def parse_novel(filepath: str, encoding: str | None = None) -> Dict[str, List[str]]:
    """
    Load a Chinese novel txt file and split it into chapters and sentences.

    Args:
        filepath: Path to a UTF-8 (or decodable) txt file.
        encoding: Optional explicit encoding. If None, try common Chinese encodings.

    Returns:
        Mapping of chapter title -> list of sentences.
    """
    raw, chosen_encoding = _read_text(filepath, encoding=encoding)

    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    chapters: Dict[str, List[str]] = {}
    pattern = re.compile(CHAPTER_PATTERN, re.MULTILINE)
    matches = list(pattern.finditer(text))

    if not matches:
        chapters["全書"] = _split_sentences(text)
        return chapters

    for idx, match in enumerate(matches):
        title = match.group(0).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end]
        chapters[title] = _split_sentences(body)

    return chapters


if __name__ == "__main__":
    novel_data = parse_novel("小說資料/輪迴樂園.txt")
    print(list(novel_data.items())[:2])  # 預覽前兩章
