from __future__ import annotations

from typing import Any, Optional

EMOTION_SCORE_MAP = {
    "極度負向": -2,
    "負向": -1,
    "憤怒": -1,
    "悲傷": -1,
    "害怕": -1,
    "中性": 0,
    "平靜": 0,
    "正向": 1,
    "期待": 1,
    "開心": 1,
    "極度正向": 2,
}


def map_emotion_score(value: Optional[Any]) -> float:
    """將情緒標籤映射為簡易分數；未命中則視為 0。"""

    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(EMOTION_SCORE_MAP.get(value.strip(), 0))
    return 0.0


def categorize_emotion_label(value: Optional[Any]) -> str:
    """將情緒標籤分類為正向/負向/中性，未知以中性處理。"""

    score = map_emotion_score(value)
    if score > 0:
        return "正向"
    if score < 0:
        return "負向"
    return "中性"
