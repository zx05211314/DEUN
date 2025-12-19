from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from app.components.interactive_graph import render_interactive_graph
from app.components.semantic_tables import render_detail_panel


def render_graphs(outputs: Dict[str, Any], sem_filtered: List[Dict]) -> None:
    st.subheader("互動圖譜")
    if not outputs.get("semantic_graph", {}).get("nodes"):
        st.info("目前沒有圖譜資料。")
        return
    selected = render_interactive_graph(outputs.get("semantic_graph", {}), sem_filtered)
    if selected:
        render_detail_panel(selected)
