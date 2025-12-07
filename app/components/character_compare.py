from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def _filter_sem(df: pd.DataFrame, characters: list[str]) -> pd.DataFrame:
    if df.empty or not characters:
        return pd.DataFrame()
    return df[df["character"].isin(characters)]


def mission_by_char(df: pd.DataFrame) -> go.Figure | None:
    if df.empty or "mission_type" not in df.columns:
        return None
    agg = (
        df.groupby(["character", "mission_type"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    if agg.empty:
        return None
    fig = px.bar(
        agg,
        x="mission_type",
        y="count",
        color="character",
        barmode="group",
        title="任務分佈（按角色）",
    )
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def emotion_by_char(df: pd.DataFrame) -> go.Figure | None:
    if df.empty or "emotion" not in df.columns:
        return None
    agg = (
        df.groupby(["character", "emotion"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    if agg.empty:
        return None
    fig = px.bar(
        agg,
        x="emotion",
        y="count",
        color="character",
        barmode="group",
        title="情緒分佈（按角色）",
    )
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def radar_emotion(df: pd.DataFrame, characters: list[str]) -> go.Figure | None:
    if df.empty or "emotion" not in df.columns:
        return None
    fig = go.Figure()
    emotions = sorted(df["emotion"].dropna().unique().tolist())
    if not emotions:
        return None
    for c in characters:
        sub = df[df["character"] == c]
        if sub.empty:
            continue
        counts = sub["emotion"].value_counts()
        values = [counts.get(e, 0) for e in emotions]
        fig.add_trace(go.Scatterpolar(r=values, theta=emotions, fill="toself", name=c))
    if not fig.data:
        return None
    fig.update_layout(title="情緒雷達圖（多角色）", height=400, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def items_by_char(items: list[dict], characters: list[str]) -> pd.DataFrame:
    if not items or not characters:
        return pd.DataFrame()
    rows = [it for it in items if str(it.get("owner", "")) in characters]
    return pd.DataFrame(rows)


# -------- 語者視角統計 --------


def voice_by_char(df: pd.DataFrame) -> go.Figure | None:
    if df.empty or "voice" not in df.columns or "speaker" not in df.columns:
        return None
    agg = (
        df.groupby(["speaker", "voice"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    if agg.empty:
        return None
    fig = px.bar(
        agg,
        x="voice",
        y="count",
        color="speaker",
        barmode="group",
        title="主/被動語態分佈（按語者）",
    )
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def perspective_by_char(df: pd.DataFrame) -> go.Figure | None:
    if df.empty or "emotion_perspective" not in df.columns or "speaker" not in df.columns:
        return None
    agg = (
        df.groupby(["speaker", "emotion_perspective"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    if agg.empty:
        return None
    fig = px.bar(
        agg,
        x="emotion_perspective",
        y="count",
        color="speaker",
        barmode="group",
        title="情緒觀點分佈（按語者）",
    )
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def strength_avg_by_char(df: pd.DataFrame) -> go.Figure | None:
    if df.empty or "emotion_strength" not in df.columns or "speaker" not in df.columns:
        return None
    map_val = {"強": 1.0, "中": 0.5, "弱": 0.2}
    df_tmp = df.copy()
    df_tmp["strength_val"] = df_tmp["emotion_strength"].map(map_val)
    agg = (
        df_tmp.groupby("speaker")["strength_val"]
        .mean()
        .reset_index(name="avg_strength")
        .sort_values("avg_strength", ascending=False)
    )
    if agg.empty:
        return None
    fig = px.bar(
        agg,
        x="speaker",
        y="avg_strength",
        title="平均情緒強度（按語者）",
    )
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def render_character_compare(df_sem: pd.DataFrame, items: list[dict], char_rels: list[dict]) -> None:
    if df_sem.empty or "character" not in df_sem.columns:
        st.info("尚無可比較的語意資料")
        return

    char_options = sorted({c for c in df_sem["character"].dropna().unique().tolist() if c})
    sel_chars = st.multiselect("選取多個角色（2-5）", char_options, max_selections=5)
    if not sel_chars or len(sel_chars) < 2:
        st.info("請至少選兩個角色")
        return

    df_sel = _filter_sem(df_sem, sel_chars)
    if df_sel.empty:
        st.info("無對應角色的語意資料")
        return

    col1, col2 = st.columns(2)
    with col1:
        fig_m = mission_by_char(df_sel)
        st.plotly_chart(fig_m, use_container_width=True) if fig_m else st.info("任務分佈不足")
    with col2:
        fig_e = emotion_by_char(df_sel)
        st.plotly_chart(fig_e, use_container_width=True) if fig_e else st.info("情緒分佈不足")

    fig_radar = radar_emotion(df_sel, sel_chars)
    st.plotly_chart(fig_radar, use_container_width=True) if fig_radar else st.info("情緒雷達圖不足")

    st.subheader("語者視角比較")
    col3, col4 = st.columns(2)
    with col3:
        fig_v = voice_by_char(df_sel)
        st.plotly_chart(fig_v, use_container_width=True) if fig_v else st.info("語態分佈不足")
    with col4:
        fig_p = perspective_by_char(df_sel)
        st.plotly_chart(fig_p, use_container_width=True) if fig_p else st.info("情緒觀點分佈不足")

    fig_s = strength_avg_by_char(df_sel)
    st.plotly_chart(fig_s, use_container_width=True) if fig_s else st.info("情緒強度資料不足")

    st.subheader("道具持有")
    df_items = items_by_char(items, sel_chars)
    st.dataframe(df_items, use_container_width=True) if not df_items.empty else st.info("無道具資料")

    st.subheader("角色互動（character_relations）")
    if char_rels:
        rel_df = pd.DataFrame(char_rels)
        if "source" in rel_df.columns and "target" in rel_df.columns:
            rel_filtered = rel_df[rel_df["source"].isin(sel_chars) | rel_df["target"].isin(sel_chars)]
        else:
            rel_filtered = rel_df
        st.dataframe(rel_filtered, use_container_width=True) if not rel_filtered.empty else st.info("沒有符合的互動關係")
    else:
        st.info("尚未產生角色關係資料")

    st.subheader("語意語句")
    cols = [
        c
        for c in [
            "character",
            "mission_type",
            "action_type",
            "emotion",
            "speaker",
            "voice",
            "emotion_perspective",
            "sentence",
        ]
        if c in df_sel.columns
    ]
    st.dataframe(df_sel[cols], use_container_width=True) if not df_sel.empty else st.info("無語句資料")
