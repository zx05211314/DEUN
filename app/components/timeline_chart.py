from __future__ import annotations

"""
Timeline chart helper (Plotly).

Expected input: a list of dicts, each containing at least:
    - chapter: str / int (used on y-axis, sorted)
    - time: str (display in hover)
    - event or sentence: str (display text)
    - speaker: str
    - voice: str ("主動" / "被動" / "")
    - emotion_perspective: str
    - low_confidence: bool
Optional:
    - display_group: str (for color grouping; if missing we derive from voice/low_confidence)

Low-confidence events are shown with lighter/outlined markers.
"""

from typing import List, Dict

import pandas as pd
import plotly.express as px


def timeline_bar(timeline_data: List[Dict]):
    if not timeline_data:
        return None

    df = pd.DataFrame(timeline_data)
    if df.empty:
        return None

    # Ensure required columns exist
    for col in [
        "chapter",
        "time",
        "event",
        "sentence",
        "speaker",
        "voice",
        "emotion_perspective",
        "low_confidence",
    ]:
        if col not in df.columns:
            df[col] = "" if col != "low_confidence" else False

    # order for x-axis
    df["order"] = range(1, len(df) + 1)

    # color grouping
    if "display_group" not in df.columns:
        def _group(row):
            voice = row.get("voice") or "未知語態"
            return f"{voice}" + (" (低信度)" if row.get("low_confidence") else "")

        df["display_group"] = df.apply(_group, axis=1)

    # low confidence styling
    df["marker_opacity"] = df["low_confidence"].apply(lambda x: 0.4 if x else 0.9)
    df["marker_symbol"] = df["low_confidence"].apply(lambda x: "circle-open-dot" if x else "circle")

    fig = px.scatter(
        df,
        x="order",
        y="chapter",
        color="display_group",
        symbol="marker_symbol",
        opacity=df["marker_opacity"],
        hover_data={
            "time": True,
            "event": True,
            "sentence": True,
            "speaker": True,
            "voice": True,
            "emotion_perspective": True,
            "low_confidence": True,
        },
        labels={"order": "序號", "chapter": "章節"},
        title="事件時間線",
    )
    fig.update_traces(marker=dict(size=10, line=dict(width=1, color="rgba(60,60,60,0.6)")))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=500, margin=dict(l=10, r=10, t=30, b=10), legend_title_text="語態/信度")
    return fig
