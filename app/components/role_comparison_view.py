from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st


def render_role_comparison(sem_filtered: List[Dict], speaker_summary: Dict) -> None:
    st.subheader("角色比較")
    if not sem_filtered:
        st.info("請先選擇至少一位角色，或調整篩選條件。")
        return

    df = pd.DataFrame(sem_filtered)
    speakers = sorted({s for s in df.get("speaker", []) if s})

    selected = st.multiselect(
        "選擇要比較的角色（最多 3 名）",
        options=speakers,
        max_selections=3,
    )

    if not selected:
        st.info("請先選擇至少一位角色，或調整篩選條件。")
        return

    rows = []
    for name in selected:
        speaker_rows = df[df["speaker"] == name]
        total_rel = len(speaker_rows)
        low_conf_rel = (
            speaker_rows["low_confidence"].fillna(False).sum()
            if "low_confidence" in speaker_rows.columns
            else 0
        )

        emo_values = []
        if "emotion" in speaker_rows.columns:
            emo_values.extend([e for e in speaker_rows["emotion"].dropna()])
        if "emotion_perspective" in speaker_rows.columns:
            emo_values.extend([e for e in speaker_rows["emotion_perspective"].dropna()])

        unique_emotions = len(set(emo_values))
        rows.append(
            {
                "角色": name,
                "語意關聯數量": total_rel,
                "低信度關聯數量": int(low_conf_rel),
                "情緒類型數量": unique_emotions,
            }
        )

    comparison_df = pd.DataFrame(rows)
    st.dataframe(comparison_df, width="stretch")

    chart_df = comparison_df.copy()
    chart_fig = px.bar(
        chart_df,
        x="角色",
        y="語意關聯數量",
        color="低信度關聯數量",
        title="角色語意關聯比較",
    )
    st.plotly_chart(chart_fig, use_container_width=True)

    if speaker_summary:
        with st.expander("語者摘要對照", expanded=False):
            for name in selected:
                if name not in speaker_summary:
                    continue
                st.markdown(f"**{name}**")
                for line, strength in speaker_summary[name]:
                    st.markdown(f"- {line}（強度: {strength}）")
