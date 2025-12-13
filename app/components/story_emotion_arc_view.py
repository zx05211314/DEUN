from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.utils.emotion import map_emotion_score


def render_story_emotion_arc(outputs: Dict[str, Any], sem_filtered: List[Dict]) -> None:
    st.subheader("故事情緒曲線")

    timeline = outputs.get("timeline") or []
    source = timeline if timeline else sem_filtered

    if not source:
        st.info("目前沒有可用的時間線或語意資料，無法繪製故事情緒曲線。")
        return

    records = []
    for idx, item in enumerate(source, start=1):
        order_val = item.get("order") or item.get("index") or item.get("idx") or idx
        emotion_label = (
            item.get("emotion")
            or item.get("emotion_perspective")
            or item.get("emotion_label")
        )
        records.append(
            {
                "position": order_val if isinstance(order_val, (int, float)) else idx,
                "emotion_score": map_emotion_score(emotion_label),
                "raw_emotion": emotion_label,
                "speaker": item.get("speaker"),
            }
        )

    df = pd.DataFrame(records)
    if df.empty:
        st.info("目前沒有可用的時間線或語意資料，無法繪製故事情緒曲線。")
        return

    available_speakers = sorted({s for s in df["speaker"] if s})
    selected_speakers = st.multiselect(
        "僅顯示特定角色的情緒曲線（可留空顯示全部）",
        options=available_speakers,
    )

    if selected_speakers:
        df = df[df["speaker"].isin(selected_speakers)]

    if len(df) < 3:
        st.info("目前資料點數太少，無法繪製有意義的情緒曲線。請放寬篩選條件或選擇其他角色。")
        return

    df_sorted = df.sort_values("position").reset_index(drop=True)
    window = st.select_slider(
        "平滑視窗大小",
        options=[1, 3, 5, 7, 11],
        value=3,
        help="視窗越大，情緒曲線越平滑。",
    )

    df_sorted["smoothed_score"] = (
        df_sorted["emotion_score"].rolling(window=window, center=True, min_periods=1).mean()
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_sorted["position"],
            y=df_sorted["emotion_score"],
            mode="lines",
            name="原始情緒分數",
            line=dict(color="#a0aec0", width=1),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_sorted["position"],
            y=df_sorted["smoothed_score"],
            mode="lines+markers",
            name="平滑後情緒分數",
            line=dict(color="#3182ce", width=3),
        )
    )

    fig.update_layout(
        title="故事情緒曲線",
        xaxis_title="故事進程（事件序號）",
        yaxis_title="情緒分數",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("情緒分數為簡化映射，僅供觀察趨勢使用。")
