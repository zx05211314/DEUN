from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st

from app.utils.chapter_metrics import (
    build_chapter_summary,
    build_ordered_records,
    fill_chapter_labels,
)


def render_chapter_comparison(outputs: Dict[str, Any], sem_filtered: List[Dict]) -> None:
    st.subheader("章節比較")

    timeline_data = outputs.get("timeline") or []
    source_data = timeline_data if timeline_data else sem_filtered

    if not source_data:
        st.info("目前沒有足夠的時間線或章節資訊，無法進行章節比較。")
        return

    records, has_explicit_chapter = build_ordered_records(source_data)
    df_events = fill_chapter_labels(records, has_explicit_chapter)

    if df_events.empty:
        st.info("目前沒有足夠的時間線或章節資訊，無法進行章節比較。")
        return

    available_speakers = sorted({s for s in df_events["speaker"] if s})
    speaker_filter = st.multiselect(
        "可選擇特定角色，只比較其參與的章節統計（可留空顯示全部）",
        options=available_speakers,
    )

    filtered_events = (
        df_events[df_events["speaker"].isin(speaker_filter)] if speaker_filter else df_events
    )

    if filtered_events.empty:
        st.info("目前可比較的章節數量不足，請放寬篩選條件或選擇其他書目。")
        return

    df_chapters = build_chapter_summary(filtered_events)

    if df_chapters.empty:
        st.info("目前可比較的章節數量不足，請放寬篩選條件或選擇其他書目。")
        return

    chapter_options = list(df_chapters["chapter_name"])
    default_selection = chapter_options[: min(3, len(chapter_options))]
    selected_chapters = st.multiselect(
        "選擇要比較的章節（最多 3 個）",
        options=chapter_options,
        default=default_selection,
        max_selections=3,
    )

    if not selected_chapters:
        selected_chapters = default_selection

    selected_df = df_chapters[df_chapters["chapter_name"].isin(selected_chapters)]

    if len(selected_df) < 2:
        st.info("目前可比較的章節數量不足，請放寬篩選條件或選擇其他書目。")
        return

    display_df = selected_df[
        [
            "chapter_name",
            "event_count",
            "unique_speakers",
            "interaction_density",
            "positive_ratio",
            "negative_ratio",
            "neutral_ratio",
            "dominant_pov",
        ]
    ].rename(
        columns={
            "chapter_name": "章節",
            "event_count": "事件數量",
            "unique_speakers": "不同角色數量",
            "interaction_density": "互動密度",
            "positive_ratio": "正向情緒比例",
            "negative_ratio": "負向情緒比例",
            "neutral_ratio": "中性情緒比例",
            "dominant_pov": "優勢視角",
        }
    )

    st.dataframe(display_df, width="stretch")

    fig_event = px.bar(
        selected_df,
        x="chapter_name",
        y="event_count",
        title="章節事件數量",
        labels={"chapter_name": "章節", "event_count": "事件數量"},
    )
    st.plotly_chart(fig_event, use_container_width=True)

    fig_speakers = px.bar(
        selected_df,
        x="chapter_name",
        y="unique_speakers",
        title="章節角色多樣性",
        labels={"chapter_name": "章節", "unique_speakers": "不同角色數量"},
    )
    st.plotly_chart(fig_speakers, use_container_width=True)

    emo_df = selected_df.melt(
        id_vars=["chapter_name"],
        value_vars=["positive_ratio", "negative_ratio", "neutral_ratio"],
        var_name="emotion_type",
        value_name="ratio",
    )
    emo_df["emotion_type"] = emo_df["emotion_type"].map(
        {
            "positive_ratio": "正向情緒比例",
            "negative_ratio": "負向情緒比例",
            "neutral_ratio": "中性情緒比例",
        }
    )
    fig_emo = px.bar(
        emo_df,
        x="chapter_name",
        y="ratio",
        color="emotion_type",
        title="章節情緒比例",
        labels={"chapter_name": "章節", "ratio": "比例", "emotion_type": "情緒類型"},
    )
    st.plotly_chart(fig_emo, use_container_width=True)

    pov_fig = px.bar(
        selected_df,
        x="chapter_name",
        y="dominant_pov",
        title="章節優勢視角",
        labels={"chapter_name": "章節", "dominant_pov": "優勢視角"},
    )
    st.plotly_chart(pov_fig, use_container_width=True)
