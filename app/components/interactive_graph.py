from __future__ import annotations

"""
Interactive graph rendering with low-confidence styling.

Edges are built from the already-filtered semantic relations (sem_filtered) to
ensure consistency across table/graph/timeline.

Low-confidence edges are drawn lighter/dashed. Node click returns a structured
dict for the shared detail panel.
"""

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

try:
    from streamlit_plotly_events import plotly_events
except Exception:
    plotly_events = None


def _build_graph(graph_data: dict, semantic_data: list[dict]) -> nx.Graph:
    G = nx.Graph()
    id_to_label = {}
    for n in graph_data.get("nodes", []):
        nid = n.get("id")
        label = n.get("label", str(nid))
        ntype = n.get("type", "")
        if nid is None:
            continue
        id_to_label[nid] = label
        G.add_node(nid, label=label, type=ntype)

    # low-confidence pairs from semantic data
    low_pairs = set()
    for r in semantic_data or []:
        if r.get("low_confidence"):
            subj = r.get("subject") or r.get("character")
            obj = r.get("object") or r.get("item")
            if subj and obj:
                low_pairs.add((subj, obj))
                low_pairs.add((obj, subj))

    for e in graph_data.get("edges", []):
        src = e.get("source")
        tgt = e.get("target")
        if src is None or tgt is None:
            continue
        verb = e.get("verb") or e.get("label") or ""
        low = bool(e.get("low_confidence", False))
        s_label = id_to_label.get(src, src)
        t_label = id_to_label.get(tgt, tgt)
        if (s_label, t_label) in low_pairs:
            low = True
        G.add_edge(src, tgt, verb=verb, low_confidence=low)
    return G


def _plot_graph(G: nx.Graph) -> go.Figure:
    pos = nx.spring_layout(G, k=0.4, seed=42)
    edge_traces = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        low = data.get("low_confidence", False)
        edge_traces.append(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(
                    width=0.8 if low else 1.6,
                    color="#b0b0b0" if low else "#888",
                    dash="dot" if low else "solid",
                ),
                hoverinfo="text",
                hovertext=f"{data.get('verb','')}｜信度：{'低' if low else '高'}",
            )
        )

    node_x, node_y, text, colors = [], [], [], []
    for node, data in G.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        text.append(data.get("label", str(node)))
        ntype = (data.get("type") or "").lower()
        colors.append("#1f77b4" if ntype == "character" else "#2ca02c")

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=text,
        textposition="top center",
        hoverinfo="text",
        marker=dict(color=colors, size=12, line=dict(width=1, color="#333")),
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        showlegend=False,
        height=600,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_interactive_graph(graph_data: dict, semantic_data: list[dict]):
    """
    Render graph with low-confidence styling. Returns a selected_item dict on node click:
        {
          "type": "node",
          "name": <label>,
          "degree": <int>,
          "related_relations": [...semantic rows...]
        }
    """
    if plotly_events is None:
        st.info("請先安裝 streamlit-plotly-events 套件以啟用互動圖。")
        return None
    if not graph_data or not graph_data.get("nodes"):
        st.info("目前沒有可顯示的圖譜資料。")
        return None

    G = _build_graph(graph_data, semantic_data)
    fig = _plot_graph(G)
    st.caption("低信度邊以虛線/淡色顯示；點擊節點可查看相關語意。")
    clicked = plotly_events(fig, click_event=True, hover_event=False, select_event=False)

    if not clicked:
        return None

    label = clicked[0].get("text", "")
    node_id = None
    for n, data in G.nodes(data=True):
        if data.get("label") == label:
            node_id = n
            break
    related = [
        r
        for r in semantic_data or []
        if label
        and (
            label == r.get("character")
            or label == r.get("item")
            or label == r.get("subject")
            or label == r.get("object")
            or label == r.get("speaker")
        )
    ]
    return {
        "type": "node",
        "name": label,
        "degree": G.degree(node_id) if node_id is not None else None,
        "related_relations": related,
    }
