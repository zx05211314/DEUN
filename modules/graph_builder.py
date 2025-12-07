"""Build a simple graph from relations_with_context.json with knowledge filters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from modules.config import VERBOSE
from modules.constants.zh_tokens import EFFECT_KEYWORDS, ACTION_VERBS
from modules.user_knowledge import as_sets, load_blacklist, load_whitelist


def _clean(text: str) -> str:
    return (text or "").strip()


def _find_effect(texts: List[str]) -> str:
    for t in texts:
        for kw in EFFECT_KEYWORDS:
            if kw in t:
                return kw
    return "未知"


def _gather_texts(rel: Dict) -> List[str]:
    arr: List[str] = []
    for key in ("sentence", "context_before", "context_after"):
        val = rel.get(key)
        if isinstance(val, list):
            arr.extend(val)
        elif isinstance(val, str):
            arr.append(val)
    return arr


def extract_graph(
    relations_with_context_path: str = "output/relations_with_context.json",
    graph_output_path: str = "output/graph.json",
) -> Dict:
    rel_path = Path(relations_with_context_path)
    if not rel_path.exists():
        raise FileNotFoundError(f"Missing {rel_path}")

    wl = as_sets(load_whitelist())
    bl = as_sets(load_blacklist())

    relations = json.loads(rel_path.read_text(encoding="utf-8"))
    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []

    def add_node(node_id: str, ntype: str):
        if not node_id:
            return
        key = f"{ntype}:{node_id}"
        if key not in nodes:
            nodes[key] = {"id": node_id, "type": ntype, "label": node_id}

    for r in relations:
        char = _clean(r.get("character", ""))
        item = _clean(r.get("item", ""))
        if char in bl.get("characters", set()) or item in bl.get("items", set()):
            continue
        texts = _gather_texts(r)
        effect = _find_effect(texts)
        time = _clean(r.get("time", ""))
        loc = _clean(r.get("location", ""))
        verb = _clean(r.get("verb", ""))

        # whitelist reinforcement
        if not char and wl.get("characters"):
            char = next(iter(wl.get("characters")))
        if not item and wl.get("items"):
            item = next(iter(wl.get("items")))

        add_node(char, "character")
        add_node(item, "item")
        add_node(effect, "effect")
        if time:
            add_node(time, "time")
        if loc:
            add_node(loc, "location")

        edges.append(
            {
                "source": char,
                "target": item,
                "verb": verb or "未知",
                "effect": effect,
                "time": time,
                "location": loc,
                "sentence": r.get("sentence", ""),
            }
        )

    graph = {"nodes": list(nodes.values()), "edges": edges}
    out_path = Path(graph_output_path)
    out_path.parent.mkdir(exist_ok=True, parents=True)
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    if VERBOSE:
        print(f"[graph_builder] nodes {len(graph['nodes'])}, edges {len(edges)} -> {out_path}")
    return graph


def main():
    extract_graph()


if __name__ == "__main__":
    main()
