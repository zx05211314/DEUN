"""Build graph from inferred relations with rich edge attributes."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

from modules.config import VERBOSE


def extract_inference_graph(
    input_path: str = "output/inferred_relations.json",
    output_path: str = "output/inference_graph.json",
    node_csv: str = "output/inference_graph_nodes.csv",
    edge_csv: str = "output/inference_graph_edges.csv",
) -> Dict:
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Missing {in_path}")

    data: List[Dict] = json.loads(in_path.read_text(encoding="utf-8"))
    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []

    def add_node(node_id: str, label: str, node_type: str) -> None:
        if not node_id:
            return
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "label": label, "type": node_type}

    for item in data:
        char = item.get("character", "")
        tool = item.get("item", "")
        verb = item.get("verb", "")
        effect = item.get("effect", "未知")
        time_val = item.get("chapter", "未知")
        location = item.get("location", "")
        action_type = item.get("action_type", "未知")
        power = item.get("power_level", "未知")
        exclusive = item.get("exclusive", False)
        sentence = item.get("sentence", "")
        context_before = item.get("context_before", []) or []
        context_after = item.get("context_after", []) or []

        add_node(char, char, "Character")
        add_node(tool, tool, "Item")
        if effect and effect != "未知":
            add_node(effect, effect, "Effect")
        if location:
            add_node(location, location, "Location")
        add_node(time_val, time_val, "Chapter")

        edge = {
            "source": char,
            "target": tool,
            "verb": verb,
            "action_type": action_type,
            "mission_type": item.get("mission_type", "未知"),
            "emotion": item.get("emotion", "無標記"),
            "power_level": power,
            "exclusive": exclusive,
            "effect": effect,
            "time": time_val,
            "location": location,
            "sentence": sentence,
            "context_before": context_before,
            "context_after": context_after,
        }
        edges.append(edge)

    graph = {"nodes": list(nodes.values()), "edges": edges}

    out_path = Path(output_path)
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    export_nodes_edges_csv(graph, node_csv=node_csv, edge_csv=edge_csv)
    if VERBOSE:
        print(f"Graph generated: {len(graph['nodes'])} nodes / {len(graph['edges'])} edges")
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
            "verb",
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

    extract_inference_graph(
        input_path=str(ROOT / "output" / "inferred_relations.json"),
        output_path=str(ROOT / "output" / "inference_graph.json"),
        node_csv=str(ROOT / "output" / "inference_graph_nodes.csv"),
        edge_csv=str(ROOT / "output" / "inference_graph_edges.csv"),
    )


if __name__ == "__main__":
    main()
