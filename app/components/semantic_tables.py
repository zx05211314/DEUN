from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st


def render_detail_panel(selected_item: Dict[str, Any]) -> None:
    """統一顯示詳情卡片（事件或節點）。"""
    if not selected_item:
        return
    with st.expander("詳細資訊", expanded=True):
        if selected_item.get("type") == "node":
            st.markdown(f"**節點：{selected_item.get('name','')}**")
            if selected_item.get("degree") is not None:
                st.caption(f"度數：{selected_item['degree']}")
            rels = selected_item.get("related_relations") or []
            st.markdown(f"關聯語意筆數：{len(rels)}")
            if rels:
                df = pd.DataFrame(rels)
                st.dataframe(df, width="stretch")
        else:
            st.markdown(f"**句子**：{selected_item.get('sentence','')}")
            st.markdown(
                f"語者：{selected_item.get('speaker','')} ｜ 語態：{selected_item.get('voice','')} ｜ "
                f"情緒觀點：{selected_item.get('emotion_perspective','')} ｜ 信度：{'低' if selected_item.get('low_confidence') else '高'}"
            )
            if selected_item.get("time"):
                st.caption(f"時間：{selected_item.get('time')}")


def render_tables(sem_filtered: List[Dict]) -> None:
    st.subheader("語意關聯表")
    if not sem_filtered:
        st.info("目前沒有可用的語意關聯資料。")
        return
    df = pd.DataFrame(sem_filtered)
    if "low_confidence" in df.columns:
        df["信度"] = df["low_confidence"].apply(lambda x: "⚠ 低" if x else "高")
    st.dataframe(df, width="stretch")
