from __future__ import annotations

from typing import Dict

import streamlit as st


def render_speaker_summary(speaker_summary: Dict) -> None:
    if not speaker_summary:
        return
    with st.expander("語者摘要（高情緒強度 Top N）", expanded=False):
        for name, entries in speaker_summary.items():
            st.markdown(f"**{name}**")
            for line, strength in entries:
                st.markdown(f"- {line}（強度: {strength}）")
