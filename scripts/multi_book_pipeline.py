"""Run pipeline for all novels under novels/ directory, each outputs to output/{book}/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from modules import character, item, relations, context_window, inference, semantic_classifier, graph_builder, inference_graph, semantic_graph
from modules.parser import parse_novel


def limited_chapters(chapters: Dict[str, List[str]], limit_chapters: int | None, limit_sentences: int | None) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for i, (k, v) in enumerate(chapters.items()):
        if limit_chapters is not None and i >= limit_chapters:
            break
        out[k] = v if limit_sentences is None else v[:limit_sentences]
    return out


def run_for_book(novel_path: Path, output_dir: Path, limit_chapters: int | None, limit_sentences: int | None, skip_items: bool, skip_inference: bool):
    print(f"\n[Book] {novel_path.name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    chapters_full = parse_novel(str(novel_path))
    chapters = limited_chapters(chapters_full, limit_chapters, limit_sentences)

    # Characters
    chars = character.extract_characters(chapters, top_n=50, max_samples_per_character=5)
    (output_dir / "characters.json").write_text(json.dumps(chars, ensure_ascii=False, indent=2), encoding="utf-8")

    # Items
    if skip_items:
        items = []
    else:
        items = item.extract_items_v2(
            chapters,
            known_characters=[c.get("name", "") for c in chars],
            top_n=50,
            max_samples_per_item=5,
            score_threshold=0.3,
            require_action_verbs=False,
        )
        (output_dir / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    # Relations
    rels = relations.extract_relations(
        chapters,
        item_list=[i.get("name", "") for i in items],
        character_list=[c.get("name", "") for c in chars],
        strict_mode=False,
    )
    (output_dir / "relations.json").write_text(json.dumps(rels, ensure_ascii=False, indent=2), encoding="utf-8")

    # Context
    enriched = context_window.enrich_with_context(rels, chapters, window_size=1)
    (output_dir / "relations_with_context.json").write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    if skip_inference:
        return

    # Inference
    inf_out = output_dir / "inferred_relations.json"
    inference.extract_inferences(
        input_path=str(output_dir / "relations_with_context.json"),
        output_path=str(inf_out),
    )

    # Semantic
    semantic_classifier.extract_semantics(
        input_path=str(inf_out),
        output_path=str(output_dir / "semantic_relations.json"),
    )

    # Graphs
    graph = graph_builder.extract_graph(
        relations_with_context_path=str(output_dir / "relations_with_context.json"),
        graph_output_path=str(output_dir / "graph.json"),
    )
    graph_builder.export_nodes_edges_csv(graph, str(output_dir / "graph_nodes.csv"), str(output_dir / "graph_edges.csv"))

    igraph = inference_graph.extract_inference_graph(
        input_path=str(output_dir / "inferred_relations.json"),
        output_path=str(output_dir / "inference_graph.json"),
        node_csv=str(output_dir / "inference_graph_nodes.csv"),
        edge_csv=str(output_dir / "inference_graph_edges.csv"),
    )

    sgraph = semantic_graph.extract_semantic_graph(
        input_path=str(output_dir / "semantic_relations.json"),
        output_path=str(output_dir / "semantic_graph.json"),
        node_csv=str(output_dir / "semantic_graph_nodes.csv"),
        edge_csv=str(output_dir / "semantic_graph_edges.csv"),
    )

    print(f"[Book] {novel_path.name} done. Nodes/Edges: basic {len(graph['nodes'])}/{len(graph['edges'])}, semantic {len(sgraph['nodes'])}/{len(sgraph['edges'])}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--novels-dir", default="novels", help="Directory containing txt novels")
    parser.add_argument("--skip-items", action="store_true")
    parser.add_argument("--skip-inference", action="store_true")
    parser.add_argument("--limit-chapters", type=int, default=None)
    parser.add_argument("--limit-sentences", type=int, default=None)
    args = parser.parse_args()

    novels_dir = Path(args.novels_dir)
    txt_files = sorted(novels_dir.glob("*.txt"))
    if not txt_files:
        print(f"No txt files found in {novels_dir}")
        return

    root_output = Path("output")
    for f in txt_files:
        book_name = f.stem
        out_dir = root_output / book_name
        run_for_book(
            novel_path=f,
            output_dir=out_dir,
            limit_chapters=args.limit_chapters,
            limit_sentences=args.limit_sentences,
            skip_items=args.skip_items,
            skip_inference=args.skip_inference,
        )


if __name__ == "__main__":
    main()
