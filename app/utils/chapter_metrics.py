from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.utils.emotion import categorize_emotion_label
from app.utils.pov import map_pov_group


ORDER_FIELDS = ("order", "index", "idx", "position", "sequence", "seq", "id", "time_idx")


def _order_key(item: Dict[str, Any]) -> Optional[float]:
    for key in ORDER_FIELDS:
        val = item.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def build_ordered_records(source_data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    ordered_items = sorted(
        enumerate(source_data),
        key=lambda pair: (_order_key(pair[1]) if _order_key(pair[1]) is not None else pair[0]),
    )

    records: List[Dict[str, Any]] = []
    has_explicit_chapter = False
    for pos, (_, item) in enumerate(ordered_items, start=1):
        chapter_label: Optional[str] = None
        chapter_index: Optional[int] = None

        for field in ("chapter", "chapter_title"):
            val = item.get(field)
            if isinstance(val, str) and val.strip():
                chapter_label = val.strip()
                break
            if isinstance(val, (int, float)):
                chapter_index = int(val)
                chapter_label = f"第 {chapter_index} 章"
                break

        if chapter_index is None and isinstance(item.get("chapter_index"), (int, float)):
            chapter_index = int(item.get("chapter_index"))
            chapter_label = chapter_label or f"第 {chapter_index} 章"

        if chapter_label or chapter_index is not None:
            has_explicit_chapter = True

        emotion_label = item.get("emotion") or item.get("emotion_perspective")
        voice_val = item.get("voice") or item.get("emotion_perspective")

        records.append(
            {
                "position": pos,
                "chapter": chapter_label,
                "chapter_index": chapter_index,
                "speaker": item.get("speaker"),
                "emotion_label": emotion_label,
                "pov_group": voice_val,
                "low_confidence": bool(item.get("low_confidence")),
            }
        )
    return records, has_explicit_chapter


def fill_chapter_labels(records: List[Dict[str, Any]], has_explicit_chapter: bool) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    if not has_explicit_chapter:
        segment_size = max(1, math.ceil(len(records) / 10))
        for idx, rec in enumerate(records):
            segment = idx // segment_size + 1
            rec["chapter"] = f"第 {segment} 段"
            rec["chapter_index"] = segment

    df_events = pd.DataFrame(records)
    if df_events.empty:
        return df_events

    df_events["chapter"] = df_events["chapter"].fillna(method="ffill").fillna(method="bfill")
    if df_events["chapter"].isna().any():
        df_events["chapter"] = df_events["chapter"].fillna(
            df_events["position"].apply(lambda p: f"第 {p} 段")
        )

    chapter_order = {name: idx for idx, name in enumerate(df_events["chapter"].unique(), start=1)}
    df_events["chapter_index"] = df_events["chapter_index"].fillna(df_events["chapter"].map(chapter_order))
    df_events["chapter_index"] = df_events["chapter_index"].fillna(df_events["position"]).astype(int)
    df_events["pov_group"] = df_events["pov_group"].apply(map_pov_group)
    df_events["emotion_category"] = df_events["emotion_label"].apply(categorize_emotion_label)
    return df_events


def build_chapter_summary(df_events: pd.DataFrame) -> pd.DataFrame:
    if df_events.empty:
        return pd.DataFrame()

    chapter_groups = df_events.groupby(["chapter", "chapter_index"], sort=False)
    chapter_rows: List[Dict[str, Any]] = []
    for (chapter_name, chapter_idx), grp in chapter_groups:
        event_count = len(grp)
        if event_count == 0:
            continue
        speaker_count = grp["speaker"].dropna().nunique()
        emotion_counts = grp["emotion_category"].value_counts()
        positive_ratio = float(emotion_counts.get("正向", 0) / event_count)
        negative_ratio = float(emotion_counts.get("負向", 0) / event_count)
        neutral_ratio = float(emotion_counts.get("中性", 0) / event_count)
        dominant_pov = (
            grp["pov_group"].dropna().mode().iloc[0]
            if not grp["pov_group"].dropna().empty
            else "未知"
        )

        chapter_rows.append(
            {
                "chapter_name": chapter_name,
                "chapter_index": chapter_idx,
                "event_count": event_count,
                "unique_speakers": speaker_count,
                "interaction_density": event_count,
                "positive_ratio": positive_ratio,
                "negative_ratio": negative_ratio,
                "neutral_ratio": neutral_ratio,
                "dominant_pov": dominant_pov,
            }
        )

    return pd.DataFrame(chapter_rows).sort_values("chapter_index")
