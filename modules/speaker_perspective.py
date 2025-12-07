"""Annotate speaker / voice / emotion perspective for semantic_relations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

# Common passive markers
PASSIVE_PAT = re.compile(r"(被|遭|受到|被迫|挨打)")


def guess_subject(sentence: str) -> str:
    """A lightweight subject guess: take first token before punctuation."""
    if not sentence:
        return "未知"
    seg = re.split(r"[，。、！!？?\s]", sentence)
    for part in seg:
        if part:
            return part[:4]
    return "未知"


def annotate_speaker_perspective_list(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Annotate a list of semantic relation entries in-place."""
    for entry in data:
        sentence = entry.get("sentence", "") or ""
        subject = entry.get("subject") or entry.get("character") or entry.get("actor") or ""
        emotion = entry.get("emotion", "")

        speaker = subject if subject else guess_subject(sentence)
        voice = "被動" if PASSIVE_PAT.search(sentence) else "主動"

        if emotion:
            # if speaker name appears early in the sentence, assume subjective
            emotion_perspective = "主觀" if speaker and speaker in sentence[:10] else "客觀"
        else:
            emotion_perspective = ""

        entry["speaker"] = speaker or "未知"
        entry["voice"] = voice
        entry["emotion_perspective"] = emotion_perspective
    return data


def annotate_speaker_perspective(
    input_path: str = "output/semantic_relations.json",
    output_path: str | None = None,
) -> List[Dict[str, Any]]:
    src = Path(input_path)
    if not src.exists():
        print(f"[speaker] missing {src}")
        return []
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[speaker] parse error: {e}")
        return []

    enriched = annotate_speaker_perspective_list(data)

    dest = Path(output_path) if output_path else src
    dest.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[speaker] annotated {len(enriched)} rows -> {dest}")
    return enriched


if __name__ == "__main__":
    annotate_speaker_perspective()
