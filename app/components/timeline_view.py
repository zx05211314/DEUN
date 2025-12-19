from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from app.components.semantic_tables import render_detail_panel
from app.components.timeline_chart import timeline_bar


def render_timeline(
    timeline_data: List[Dict[str, Any]],
    sem_filtered: List[Dict[str, Any]],
    plotly_events_available: bool,
    plotly_events: Optional[Any],
) -> None:
    st.subheader("時間線")
    if not plotly_events_available:
        st.caption("未安裝 streamlit_plotly_events，點擊圖表以檢視事件詳情的功能已停用。")
    if not timeline_data:
        st.info("尚無時間線資料。")
        return None
    fig = timeline_bar(timeline_data)
    selected = None
    if fig is not None and plotly_events:
        clicked = plotly_events(fig, click_event=True, hover_event=False)
        if clicked:
            idx = clicked[0].get("pointIndex", 0)
            if idx < len(timeline_data):
                item = timeline_data[idx]
                selected = {
                    "type": "event",
                    "sentence": item.get("sentence") or item.get("event"),
                    "speaker": item.get("speaker"),
                    "voice": item.get("voice"),
                    "emotion_perspective": item.get("emotion_perspective"),
                    "low_confidence": item.get("low_confidence"),
                    "time": item.get("time"),
                }
    if fig is not None:
        st.plotly_chart(fig, width="stretch")
    if selected:
        render_detail_panel(selected)
