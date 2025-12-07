from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def summarize_by_speaker(
    semantic_data: List[Dict],
    min_conf: float = 0.6,
    top_n: int = 5,
) -> Dict[str, List[Tuple[str, float]]]:
    """
    Build concise summaries per speaker using high-confidence semantic rows.
    Returns a dict of speaker -> list of (summary_line, emotion_strength).
    """
    summaries: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for row in semantic_data:
        conf = row.get("confidence", 1.0)
        if conf is not None and conf < min_conf:
            continue
        speaker = row.get("speaker") or ""
        if not speaker:
            continue
        voice = row.get("voice", "")
        subject = row.get("subject", "")
        action = row.get("action") or row.get("verb") or row.get("action_type") or ""
        emotion = row.get("emotion", "")
        strength = row.get("emotion_strength") or 0
        summary_line = f"【{voice or '主動'}】{subject or speaker} → {action or '未知行為'}（情緒: {emotion or '無標記'}）"
        summaries[speaker].append((summary_line, strength if isinstance(strength, (int, float)) else 0))
    # keep top_n by emotion_strength
    return {k: sorted(v, key=lambda x: -x[1])[:top_n] for k, v in summaries.items()}


def annotate_low_confidence(semantic_data: List[Dict], threshold: float = 0.5) -> List[Dict]:
    """Mark rows with low confidence for downstream UI filtering."""
    for row in semantic_data:
        conf = row.get("confidence", 1.0)
        try:
            row["low_confidence"] = conf < threshold
        except Exception:
            row["low_confidence"] = False
    return semantic_data


def main(
    input_path: str = "output/semantic_relations.json",
    output_path: str = "output/speaker_summary.json",
    min_conf: float = 0.6,
    top_n: int = 5,
):
    in_path = Path(input_path)
    if not in_path.exists():
        print(f"[semantic_summary] missing {input_path}")
        return
    try:
        data = json.loads(in_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[semantic_summary] failed to load {input_path}: {e}")
        return

    # annotate low confidence in-place (does not rewrite semantic file here)
    annotate_low_confidence(data)
    summary = summarize_by_speaker(data, min_conf=min_conf, top_n=top_n)
    Path(output_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[semantic_summary] saved {len(summary)} speakers -> {output_path}")


if __name__ == "__main__":
    main()
