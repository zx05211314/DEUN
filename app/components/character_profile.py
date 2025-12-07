from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components.mission_emotion_charts import emotion_radar


def _bar(series: pd.Series, title: str, top_n: int = 10):
    if series.empty:
        return None
    df = series.value_counts().head(top_n).reset_index()
    df.columns = ["label", "count"]
    fig = px.bar(df, x="label", y="count", title=title)
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def render_character_profile(char_name: str, df_sem: pd.DataFrame, items: list[dict], char_rels: list[dict]) -> None:
    """Render a character overview card."""
    st.subheader(f"角色：{char_name}")
    if df_sem.empty:
        st.info("無語意資料可供分析。")
        return

    # filter semantic rows
    sem_char = df_sem[
        (df_sem.get("character") == char_name)
        | (df_sem.get("subject") == char_name)
        | (df_sem.get("object") == char_name)
    ]
    if sem_char.empty:
        st.info("找不到與該角色相關的語句。")
        return

    # 基本統計
    first_ch = sem_char.get("chapter", pd.Series()).dropna().astype(str).head(1).tolist()
    last_ch = sem_char.get("chapter", pd.Series()).dropna().astype(str).tail(1).tolist()
    st.markdown(
        f"""
        - 出現筆數：{len(sem_char)}
        - 首次出現章節：{first_ch[0] if first_ch else '未知'}
        - 末次出現章節：{last_ch[0] if last_ch else '未知'}
        """
    )

    # 視覺統計
    col_a, col_b = st.columns(2)
    with col_a:
        if "mission_type" in sem_char.columns:
            fig = _bar(sem_char["mission_type"].fillna("未知"), "任務分布 (Top 10)")
            if fig:
                st.plotly_chart(fig)
    with col_b:
        if "action_type" in sem_char.columns:
            fig = _bar(sem_char["action_type"].fillna("未知"), "行為分布 (Top 10)")
            if fig:
                st.plotly_chart(fig)

    if "emotion" in sem_char.columns:
        fig_r = emotion_radar(sem_char, min_conf=0.0)
        if fig_r:
            st.plotly_chart(fig_r)

    # 道具持有
    st.markdown("### 道具 / 能力（持有或相關）")
    item_rows = [it for it in items if str(it.get("owner", "")) == char_name]
    st.dataframe(pd.DataFrame(item_rows)) if item_rows else st.info("無道具資料")

    # 角色互動
    st.markdown("### 角色互動關係")
    rel_rows = [
        r
        for r in char_rels
        if r.get("source") == char_name or r.get("target") == char_name or r.get("character") == char_name
    ]
    st.dataframe(pd.DataFrame(rel_rows)) if rel_rows else st.info("無角色互動資料")

    # 語句列表
    st.markdown("### 語句片段")
    cols = [c for c in ["character", "item", "verb", "action_type", "mission_type", "emotion", "sentence", "context_before", "context_after"] if c in sem_char.columns]
    st.dataframe(sem_char[cols]) if cols else st.info("無可顯示欄位")
