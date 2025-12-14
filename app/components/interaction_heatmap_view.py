from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.utils.interaction import count_interactions


def render_interaction_heatmap(sem_filtered: List[Dict[str, Any]]) -> None:
    st.subheader("角色互動熱度矩陣")

    if not sem_filtered:
        st.info("目前篩選條件下沒有任何語意關聯資料，無法計算角色互動。")
        return

    mode = st.radio(
        "計數模式",
        options=["binary_per_unit", "count_occurrences"],
        format_func=lambda v: "單一事件計 1" if v == "binary_per_unit" else "依事件內重複次數計算",
        horizontal=True,
    )

    pair_counts, character_totals, diagnostics = count_interactions(
        sem_filtered, mode=mode
    )

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

    with st.expander("計數規則", expanded=False):
        st.markdown(
            """
            * 互動單位：優先使用 event_id / sentence_id，否則以章節與序號或文本摘要組合產生固定 ID。
            * 配對方式：每個互動單位內的角色組合以無序配對計算（A-B 與 B-A 視為同一組）。
            * 預設模式："單一事件計 1" 代表同一事件內的重複只算一次。
            * "依事件內重複次數計算" 會依角色在同一事件內出現的次數取最小值累加。
            """
        )

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

    diagnostics_block = {
        "互動單位數": diagnostics.get("units", 0),
        "語意列數": diagnostics.get("rows", len(sem_filtered)),
        "超過 5 位角色的事件": sum(
            1 for size in diagnostics.get("unit_participant_sizes", {}).values() if size > 5
        ),
        "含重複角色紀錄的事件": sum(
            1
            for dup in diagnostics.get("duplicate_role_mentions", {}).values()
            if dup
        ),
    }

    st.markdown("#### 診斷資訊")
    st.json(diagnostics_block)

    largest_units = sorted(
        diagnostics.get("unit_participant_sizes", {}).items(), key=lambda kv: kv[1], reverse=True
    )[:10]
    if largest_units:
        st.markdown("參與角色最多的事件（前 10 筆）")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "互動單位": unit_id,
                        "角色數": size,
                        "重複角色": ", ".join(
                            f"{role}×{cnt}"
                            for role, cnt in diagnostics.get("duplicate_role_mentions", {})
                            .get(unit_id, {})
                            .items()
                        ),
                    }
                    for unit_id, size in largest_units
                ]
            ),
            width="stretch",
        )
