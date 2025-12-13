from __future__ import annotations

from typing import Dict, List


def apply_semantic_filters(
    sem: List[Dict],
    speaker_sel: str,
    voice_sel: str,
    persp_sel: str,
    keyword: str,
    low_conf_only: bool,
):
    filtered = []
    keyword_lower = (keyword or "").strip().lower()
    for r in sem or []:
        if speaker_sel != "全部" and r.get("speaker") != speaker_sel:
            continue
        if voice_sel != "全部" and r.get("voice") != voice_sel:
            continue
        if persp_sel != "全部" and r.get("emotion_perspective") != persp_sel:
            continue
        if low_conf_only and not r.get("low_confidence"):
            continue
        if keyword_lower:
            sentence = (r.get("sentence") or r.get("event") or "").lower()
            if keyword_lower not in sentence:
                continue
        filtered.append(r)
    return filtered
