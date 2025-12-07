from __future__ import annotations

import pandas as pd
import plotly.express as px


def mission_bar(df: pd.DataFrame, top_n: int = 10, min_conf: float = 0.0, by_character: bool = False):
    if df.empty or "mission_type" not in df.columns:
        return None
    work = df.copy()
    if "confidence" in work.columns:
        work = work[work["confidence"].fillna(0) >= min_conf]
    work["mission_type"] = work["mission_type"].fillna("未知")
    if by_character and "character" in work.columns:
        agg = (
            work.groupby(["character", "mission_type"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(top_n)
        )
        if agg.empty:
            return None
        fig = px.bar(
            agg,
            x="mission_type",
            y="count",
            color="character",
            title="任務分布（依角色）",
        )
    else:
        agg = work["mission_type"].value_counts().reset_index()
        agg.columns = ["mission_type", "count"]
        agg = agg.head(top_n)
        if agg.empty:
            return None
        fig = px.bar(agg, x="mission_type", y="count", title="任務分布")
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def emotion_bar(df: pd.DataFrame, top_n: int = 10, min_conf: float = 0.0):
    if df.empty or "emotion" not in df.columns:
        return None
    work = df.copy()
    if "confidence" in work.columns:
        work = work[work["confidence"].fillna(0) >= min_conf]
    work["emotion"] = work["emotion"].fillna("無標記")
    agg = work["emotion"].value_counts().reset_index()
    agg.columns = ["emotion", "count"]
    agg = agg.head(top_n)
    if agg.empty:
        return None
    fig = px.bar(agg, x="emotion", y="count", title="情緒分布")
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def emotion_radar(df: pd.DataFrame, min_conf: float = 0.0):
    if df.empty or "emotion" not in df.columns:
        return None
    work = df.copy()
    if "confidence" in work.columns:
        work = work[work["confidence"].fillna(0) >= min_conf]
    work["emotion"] = work["emotion"].fillna("無標記")
    agg = work["emotion"].value_counts().reset_index()
    agg.columns = ["emotion", "count"]
    if agg.empty:
        return None
    fig = px.line_polar(agg, r="count", theta="emotion", line_close=True, title="情緒雷達圖")
    fig.update_traces(fill="toself")
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
    return fig
