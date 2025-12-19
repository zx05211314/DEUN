from __future__ import annotations

from typing import Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st


def render_overview_cards(sem_filtered: List[Dict]) -> None:
    total = len(sem_filtered)
    low_conf = sum(1 for r in sem_filtered if r.get("low_confidence"))
    speakers = {r.get("speaker") for r in sem_filtered if r.get("speaker")}

    col1, col2, col3 = st.columns(3)
    col1.metric("語意筆數", f"{total}")
    col2.metric("低信度筆數", f"{low_conf}")
    col3.metric("獨立語者", f"{len(speakers)}")


def render_emotion_charts(sem_filtered: List[Dict]) -> None:
    with st.expander("情緒與視角統計", expanded=False):
        if not sem_filtered:
            st.info("目前篩選條件下沒有任何語意關聯資料。")
            return

        df = pd.DataFrame(sem_filtered)

        total = len(sem_filtered)
        low_conf = sum(1 for r in sem_filtered if r.get("low_confidence"))
        speakers = {r.get("speaker") for r in sem_filtered if r.get("speaker")}

        stat_cols = st.columns(3)
        stat_cols[0].metric("語意筆數", f"{total}")
        stat_cols[1].metric("低信度筆數", f"{low_conf}")
        stat_cols[2].metric("獨立語者", f"{len(speakers)}")

        if "emotion" in df.columns and not df["emotion"].dropna().empty:
            emo_series = df["emotion"].dropna()
        elif "emotion_perspective" in df.columns and not df["emotion_perspective"].dropna().empty:
            emo_series = df["emotion_perspective"].dropna()
        else:
            emo_series = pd.Series(dtype=object)

        if not emo_series.empty:
            emo_counts = emo_series.value_counts().reset_index()
            emo_counts.columns = ["emotion", "count"]
            fig = px.bar(emo_counts, x="emotion", y="count", title="情緒 / 視角分布")
            st.plotly_chart(fig, use_container_width=True)

        if "voice" in df.columns and not df["voice"].dropna().empty:
            voice_counts = df["voice"].dropna().value_counts().reset_index()
            voice_counts.columns = ["voice", "count"]
            voice_fig = px.bar(
                voice_counts, x="voice", y="count", title="語態 / 視角分布", color="voice"
            )
            st.plotly_chart(voice_fig, use_container_width=True)
