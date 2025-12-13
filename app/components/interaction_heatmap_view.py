from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.utils.interaction import build_pair_counts


def render_interaction_heatmap(sem_filtered: List[Dict[str, Any]]) -> None:
    st.subheader("角色互動熱度矩陣")

    if not sem_filtered:
        st.info("目前篩選條件下沒有任何語意關聯資料，無法計算角色互動。")
        return

    pair_counts, character_totals = build_pair_counts(sem_filtered)

    if not pair_counts:
        st.info("目前角色數量過少，無法繪製互動熱度矩陣。請放寬篩選條件或選擇其他書目。")
        return

    total_interactions = int(sum(pair_counts.values()))
    distinct_pairs = len(pair_counts)
    characters = sorted(character_totals.keys())

    col1, col2, col3 = st.columns(3)
    col1.metric("總互動對數", distinct_pairs)
    col2.metric("總互動次數", total_interactions)
    col3.metric("角色數量", len(characters))

    top_pairs = (
        pd.DataFrame(
            [
                {"角色 A": a, "角色 B": b, "互動次數": cnt}
                for (a, b), cnt in pair_counts.most_common()
            ]
        )
        .sort_values("互動次數", ascending=False)
        .head(20)
    )
    st.dataframe(top_pairs, width="stretch")

    slider_max = max(2, len(characters))
    top_n = st.slider("顯示前 N 位角色", min_value=2, max_value=slider_max, value=min(20, slider_max))

    sorted_chars = [c for c, _ in character_totals.most_common(top_n)]
    if len(sorted_chars) < 2:
        st.info("目前角色數量過少，無法繪製互動熱度矩陣。請放寬篩選條件或選擇其他書目。")
        return

    matrix = pd.DataFrame(0, index=sorted_chars, columns=sorted_chars)
    for (a, b), cnt in pair_counts.items():
        if a in matrix.index and b in matrix.columns:
            matrix.loc[a, b] = cnt
            matrix.loc[b, a] = cnt

    heatmap = go.Figure(
        data=[
            go.Heatmap(
                z=matrix.values,
                x=matrix.columns,
                y=matrix.index,
                colorscale="YlOrRd",
                colorbar=dict(title="互動次數"),
            )
        ]
    )
    heatmap.update_layout(xaxis_title="角色", yaxis_title="角色")
    st.plotly_chart(heatmap, use_container_width=True)
