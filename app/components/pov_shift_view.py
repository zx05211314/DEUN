from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.utils.pov import map_pov_group


def render_pov_shift_map(outputs: Dict[str, Any], sem_filtered: List[Dict]) -> None:
    st.subheader("敘事視角變化圖")

    timeline = outputs.get("timeline") or []
    source = timeline if timeline else sem_filtered

    if not source:
        st.info("目前沒有可用的時間線或語意資料，無法繪製敘事視角變化圖。")
        return

    records = []
    for idx, item in enumerate(source, start=1):
        order_val = item.get("order") or item.get("index") or item.get("idx") or idx
        records.append(
            {
                "position": order_val if isinstance(order_val, (int, float)) else idx,
                "voice": item.get("voice") or item.get("emotion_perspective"),
                "speaker": item.get("speaker"),
            }
        )

    df = pd.DataFrame(records)
    df["pov_group"] = df["voice"].apply(map_pov_group)

    available_speakers = sorted({s for s in df["speaker"] if s})
    selected_speakers = st.multiselect(
        "僅顯示特定角色的視角變化（可留空顯示全部）",
        options=available_speakers,
    )

    if selected_speakers:
        df = df[df["speaker"].isin(selected_speakers)]

    if len(df) < 3:
        st.info("目前資料點數太少，無法繪製有意義的視角變化圖。請放寬篩選條件或選擇其他角色。")
        return

    window = st.select_slider(
        "視角統計視窗大小",
        options=[1, 5, 10, 20],
        value=1,
        help="可將事件分段後觀察主要敘事視角變化。",
    )

    df_sorted = df.sort_values("position").copy()
    if window > 1:
        df_sorted["window"] = (df_sorted["position"] - 1) // window
        aggregated = (
            df_sorted.groupby("window")
            .agg(
                position_start=("position", "min"),
                position_end=("position", "max"),
                position_mid=("position", "mean"),
                pov_group=("pov_group", lambda s: s.value_counts().idxmax()),
            )
            .reset_index(drop=True)
        )
        plot_df = aggregated.rename(columns={"position_mid": "position"})[["position", "pov_group"]]
    else:
        plot_df = df_sorted[["position", "pov_group"]]

    if len(plot_df) < 3:
        st.info("目前資料點數太少，無法繪製有意義的視角變化圖。請放寬篩選條件或選擇其他角色。")
        return

    pov_categories = sorted(plot_df["pov_group"].dropna().unique())
    pov_to_idx = {p: i for i, p in enumerate(pov_categories)}
    plot_df["pov_idx"] = plot_df["pov_group"].map(pov_to_idx)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df["position"],
            y=plot_df["pov_idx"],
            mode="lines+markers",
            line_shape="hv" if window == 1 else "linear",
            text=plot_df["pov_group"],
            hovertemplate="事件序號: %{x}<br>敘事視角: %{text}<extra></extra>",
            name="敘事視角",
        )
    )

    fig.update_layout(
        title="敘事視角變化圖",
        xaxis_title="故事進程（事件序號）",
        yaxis_title="敘事視角",
        yaxis=dict(tickmode="array", tickvals=list(pov_to_idx.values()), ticktext=pov_categories),
    )
    st.plotly_chart(fig, use_container_width=True)

    if window > 1:
        st.caption("已按視窗大小彙整後顯示主要敘事視角。")
