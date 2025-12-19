from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import streamlit as st


def render_metadata(metadata: Dict[str, Any], output_dir: Path) -> None:
    if not metadata:
        st.info("尚未找到 metadata.json，可重新執行分析。")
        return
    st.subheader("分析摘要")
    book = metadata.get("book", "")
    lc = metadata.get("chapters_used")
    ls = metadata.get("sentences_used")
    zero = metadata.get("zero_shot", {})
    enabled = metadata.get("enabled_modules", {})
    stats = metadata.get("output_stats", {})

    st.markdown(
        f"""
**書名**：{book}
**章節/句數限制**：{lc} / {ls}
**Zero-shot**：行為 {zero.get('action')}、任務 {zero.get('task')}、情緒 {zero.get('emotion')}、情緒強度 {zero.get('emotion_strength')}
**啟用模組**：{', '.join([k for k, v in enabled.items() if v])}
**產出統計**：{json.dumps(stats, ensure_ascii=False)}
**輸出目錄**：{output_dir}
"""
    )
