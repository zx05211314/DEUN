"""Build a semantic graph that includes mission and emotion annotations."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

from modules.config import VERBOSE


def extract_semantic_graph(
    input_path: str = "output/semantic_relations.json",
    output_path: str = "output/semantic_graph.json",
    node_csv: str = "output/semantic_graph_nodes.csv",
    edge_csv: str = "output/semantic_graph_edges.csv",
) -> Dict:
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Missing {in_path}")

    relations: List[Dict] = json.loads(in_path.read_text(encoding="utf-8"))

    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []
    node_id_counter = 0

    def get_or_create_node(label: str, ntype: str) -> int:
        nonlocal node_id_counter
        if not label:
            label = "未知"
        key = f"{ntype}:{label}"
        if key not in nodes:
            nodes[key] = {"id": node_id_counter, "label": label, "type": ntype}
            node_id_counter += 1
        return nodes[key]["id"]

    for rel in relations:
        cid = get_or_create_node(rel.get("character", ""), "character")
        iid = get_or_create_node(rel.get("item", ""), "item")
        mid = get_or_create_node(rel.get("mission_type", "未知"), "mission")
        eid = get_or_create_node(rel.get("emotion", "無標記"), "emotion")

        edges.append(
            {
                "source": cid,
                "target": iid,
                "label": rel.get("verb", ""),
                "action_type": rel.get("action_type", "未知"),
                "mission_type": rel.get("mission_type", "未知"),
                "emotion": rel.get("emotion", "無標記"),
                "power_level": rel.get("power_level", "未知"),
                "exclusive": rel.get("exclusive", False),
                "effect": rel.get("effect", ""),
                "time": rel.get("time", ""),
                "location": rel.get("location", ""),
                "sentence": rel.get("sentence", ""),
            }
        )

        edges.append({"source": cid, "target": mid, "label": "參與任務"})
        edges.append({"source": cid, "target": eid, "label": "表現情緒"})

    graph = {"nodes": list(nodes.values()), "edges": edges}

    out_path = Path(output_path)
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    export_nodes_edges_csv(graph, node_csv=node_csv, edge_csv=edge_csv)
    if VERBOSE:
        print(f"圖建構完成：{len(graph['nodes'])} 節點，{len(graph['edges'])} 邊 -> {out_path}")
    return graph


def export_nodes_edges_csv(graph: Dict, node_csv: str, edge_csv: str) -> None:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    Path(node_csv).parent.mkdir(exist_ok=True)
    with open(node_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "label", "type"])
        writer.writeheader()
        writer.writerows(nodes)

    with open(edge_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "source",
            "target",
            "label",
            "action_type",
            "mission_type",
            "emotion",
            "power_level",
            "exclusive",
            "effect",
            "time",
            "location",
            "sentence",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for edge in edges:
            row = {k: edge.get(k, "") for k in fieldnames}
            writer.writerow(row)


def main():
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    extract_semantic_graph(
        input_path=str(ROOT / "output" / "semantic_relations.json"),
        output_path=str(ROOT / "output" / "semantic_graph.json"),
        node_csv=str(ROOT / "output" / "semantic_graph_nodes.csv"),
        edge_csv=str(ROOT / "output" / "semantic_graph_edges.csv"),
    )


if __name__ == "__main__":
    main()
