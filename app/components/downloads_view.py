from __future__ import annotations

import io
import json
from typing import Any, Dict, List

import pandas as pd
import streamlit as st


def render_downloads(book_name: str, sem_filtered: List[Dict], speaker_summary: Dict) -> None:
    st.subheader("資料下載")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "下載語意關聯 (JSON)",
            data=json.dumps(sem_filtered, ensure_ascii=False, indent=2),
            file_name=f"{book_name}_semantic_relations.json",
        )
    with col2:
        csv_bytes = io.BytesIO()
        pd.DataFrame(sem_filtered).to_csv(csv_bytes, index=False)
        st.download_button(
            "下載語意關聯 (CSV)",
            data=csv_bytes.getvalue(),
            file_name=f"{book_name}_semantic_relations.csv",
            mime="text/csv",
        )

    if speaker_summary:
        st.download_button(
            "下載語者摘要 (JSON)",
            data=json.dumps(speaker_summary, ensure_ascii=False, indent=2),
            file_name=f"{book_name}_speaker_summary.json",
        )
