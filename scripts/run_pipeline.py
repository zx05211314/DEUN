"""End-to-end pipeline runner with skips, zero-shot controls, limits, timeline export, speaker perspective, and metadata."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Callable


def run_pipeline(
    skip_items: bool = False,
    skip_relations: bool = False,
    skip_context: bool = False,
    skip_inference: bool = False,
    skip_graphs: bool = False,
    skip_emotion_strength: bool = False,
    skip_character_rel: bool = False,
    skip_hybrid: bool = False,
    skip_zero_shot_task: bool = False,
    skip_zero_shot_action: bool = False,
    skip_zero_shot_emotion: bool = False,
    skip_zero_shot_emotion_strength: bool = False,
    skip_timeline: bool = False,
    skip_mission_timeline: bool = False,
    skip_speaker: bool = False,
    output_subdir: str | None = None,
    novel_path: str | None = None,
    limit_chapters: int | None = None,
    limit_sentences: int | None = None,
    progress_callback: Callable[[str, int], None] | None = None,
):
    """
    Run the full pipeline. If progress_callback is provided, it will be called with (message, percent).
    """
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from modules import (
        item,
        relations,
        context_window,
        inference,
        semantic_classifier,
        graph_builder,
        inference_graph,
        semantic_graph,
        emotion_strength,
        character_relations,
        hybrid_inference,
        timeline,
        mission_timeline,
        speaker_perspective,
    )
    from modules.config import MAX_CHAPTERS, MAX_SENTENCES, NOVEL_PATH, VERBOSE
    from modules.parser import parse_novel

    def update(msg: str, pct: int):
        if progress_callback:
            try:
                progress_callback(msg, pct)
            except Exception:
                pass

    def enrich_timeline_with_semantics(tl, sem_entries):
        """Attach speaker/voice/emotion_perspective to timeline rows when sentence text matches."""
        if not tl or not sem_entries:
            return tl
        sent_index = {}
        for r in sem_entries:
            sent = r.get("sentence")
            if sent:
                sent_index.setdefault(sent, []).append(r)
        for row in tl:
            sent = row.get("sentence")
            if sent and sent in sent_index:
                src = sent_index[sent][0]
                row.setdefault("speaker", src.get("speaker", ""))
                row.setdefault("voice", src.get("voice", ""))
                row.setdefault("emotion_perspective", src.get("emotion_perspective", ""))
        return tl

    novel_path_use = Path(novel_path) if novel_path else (ROOT / NOVEL_PATH)
    base_out = ROOT / "output"
    base_out.mkdir(exist_ok=True)
    book_dir = base_out / (output_subdir if output_subdir else "")
    book_dir.mkdir(exist_ok=True, parents=True)
    limit_ch = limit_chapters if limit_chapters is not None else MAX_CHAPTERS
    limit_sent = limit_sentences if limit_sentences is not None else MAX_SENTENCES

    # Parse novel
    update("解析小說中...", 10)
    chapters = parse_novel(str(novel_path_use))
    limited = {}
    for i, (k, v) in enumerate(chapters.items()):
        if limit_ch is not None and i >= limit_ch:
            break
        limited[k] = v if limit_sent is None else v[:limit_sent]

    # Items
    items_data = []
    if not skip_items:
        update("擷取道具/能力...", 20)
        items_data = item.extract_items(
            chapter_sentences=limited,
            limit_chapters=limit_ch,
            limit_sentences=limit_sent,
            output_path=str(book_dir / "items.json"),
        )
        if VERBOSE:
            print(f"[items] {len(items_data)}")

    # Relations
    rels = []
    if not skip_relations:
        update("擷取角色-道具關係...", 30)
        items_list = []
        char_list = []
        items_path = book_dir / "items.json"
        chars_path = book_dir / "characters.json"
        if items_path.exists():
            try:
                items_list = [
                    row.get("name", "")
                    for row in json.loads(items_path.read_text(encoding="utf-8"))
                    if row.get("name")
                ]
            except Exception:
                items_list = []
        if chars_path.exists():
            try:
                char_list = [
                    row.get("name", "")
                    for row in json.loads(chars_path.read_text(encoding="utf-8"))
                    if row.get("name")
                ]
            except Exception:
                char_list = []
        rels = relations.extract_relations(
            limited,
            item_list=items_list,
            character_list=char_list,
            strict_mode=False,
        )
        (book_dir / "relations.json").write_text(json.dumps(rels, ensure_ascii=False, indent=2), encoding="utf-8")
        if VERBOSE:
            print(f"[relations] {len(rels)}")

    # Context
    if not skip_context:
        update("補上下文...", 40)
        rel_path = book_dir / "relations.json"
        if rel_path.exists():
            try:
                rels = json.loads(rel_path.read_text(encoding="utf-8"))
            except Exception:
                rels = []
            enriched = context_window.enrich_with_context(rels, limited, window_size=1)
            ctx_path = book_dir / "relations_with_context.json"
            ctx_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
            if VERBOSE:
                print(f"[context] {len(enriched)}")
        else:
            print(f"[context] skip, missing {rel_path}")

    # Inference & semantic
    sem = []
    if not skip_inference:
        update("??/??/????...", 55)
        ctx_book = book_dir / "relations_with_context.json"
        if ctx_book.exists():
            ctx_default = base_out / "relations_with_context.json"
            shutil.copyfile(ctx_book, ctx_default)
            inference.extract_inferences(allow_zero_shot_action=not skip_zero_shot_action)
            if not skip_hybrid:
                hybrid_inference.__main__()
                update("Hybrid/LLM ??...", 60)
            semantic_classifier.extract_semantics(
                allow_zero_shot_task=not skip_zero_shot_task, allow_zero_shot_emotion=not skip_zero_shot_emotion
            )
            if not skip_emotion_strength:
                emotion_strength.annotate_emotion_strength(
                    allow_zero_shot_emotion_strength=not skip_zero_shot_emotion_strength
                )
            if not skip_speaker:
                speaker_perspective.annotate_speaker_perspective(
                    input_path=str(base_out / "semantic_relations.json"),
                    output_path=str(base_out / "semantic_relations.json"),
                )
            # add low-confidence + speaker summaries
            try:
                from modules.semantic_summary import annotate_low_confidence, summarize_by_speaker

                sem_tmp = json.loads((base_out / "semantic_relations.json").read_text(encoding="utf-8"))
                sem_tmp = annotate_low_confidence(sem_tmp)
                (base_out / "semantic_relations.json").write_text(
                    json.dumps(sem_tmp, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                speaker_summary = summarize_by_speaker(sem_tmp, min_conf=0.6, top_n=5)
                (base_out / "speaker_summary.json").write_text(
                    json.dumps(speaker_summary, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass
            # copy outputs back to book_dir
            for fname in [
                "inferred_relations.json",
                "hybrid_relations.json",
                "semantic_relations.json",
                "speaker_summary.json",
            ]:
                src = base_out / fname
                if src.exists():
                    shutil.copyfile(src, book_dir / fname)
            sem_path_local = book_dir / "semantic_relations.json"
            if sem_path_local.exists():
                try:
                    sem = json.loads(sem_path_local.read_text(encoding="utf-8"))
                except Exception:
                    sem = []
        else:
            print("[Pipeline] skip inference: missing relations_with_context.json")

    # Timeline
    timeline_data = None
    if not skip_timeline:
        update("????...", 40)
        try:
            timeline_data = timeline.build_timeline(str(novel_path_use), limit_ch, limit_sent)
            timeline_data = enrich_timeline_with_semantics(timeline_data, sem)
            (book_dir / "timeline.json").write_text(
                json.dumps(timeline_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if VERBOSE:
                print(f"[timeline] saved {len(timeline_data)} -> {book_dir / 'timeline.json'}")
        except Exception as e:
            print(f"[timeline] failed: {e}")

    # Mission timeline
    if not skip_mission_timeline:
        update("????...", 40)
        try:
            sem_path = book_dir / "semantic_relations.json"
            mission_out = book_dir / "mission_timeline.json"
            mission_timeline.extract_mission_timeline(sem_path, mission_out)
        except Exception as e:
            print(f"[mission_timeline] failed: {e}")

    # Metadata
    try:
        items_count = len(items_data) if items_data is not None else None
        relations_count = len(rels) if rels is not None else None
        sem_count = len(sem) if sem else 0 if sem == [] else None
        timeline_count = len(timeline_data) if timeline_data else 0 if timeline_data == [] else None
        mission_count = None
        mt_path = book_dir / "mission_timeline.json"
        if mt_path.exists():
            try:
                mission_count = len(json.loads(mt_path.read_text(encoding="utf-8")))
            except Exception:
                mission_count = None

        metadata = {
            "book": output_subdir or novel_path_use.stem,
            "chapters_used": limit_ch,
            "sentences_used": limit_sent,
            "enabled_modules": {
                "items": not skip_items,
                "relations": not skip_relations,
                "context": not skip_context,
                "inference": not skip_inference,
                "graphs": not skip_graphs,
                "emotion_strength": not skip_emotion_strength,
                "character_rel": not skip_character_rel,
                "hybrid": not skip_hybrid,
                "timeline": not skip_timeline,
                "mission_timeline": not skip_mission_timeline,
                "speaker_perspective": not skip_speaker,
            },
            "zero_shot": {
                "task": not skip_zero_shot_task,
                "action": not skip_zero_shot_action,
                "emotion": not skip_zero_shot_emotion,
                "emotion_strength": not skip_zero_shot_emotion_strength,
            },
            "output_stats": {
                "items": items_count,
                "relations": relations_count,
                "semantic_relations": sem_count,
                "timeline": timeline_count,
                "mission_timeline": mission_count,
            },
        }
        (book_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    # Character relations
    if not skip_character_rel:
        update("????...", 40)
        print("[Pipeline] character-character relations...")
        character_relations.__main__()
        char_rel_src = base_out / "character_relations.json"
        if char_rel_src.exists():
            shutil.copyfile(char_rel_src, book_dir / "character_relations.json")

    # Graphs
    if not skip_graphs:
        update("????...", 40)
        print("[Pipeline] graphs (basic/inference/semantic)...")
        graph_builder.main()
        inference_graph.main()
        semantic_graph.main()
        for fname in [
            "graph.json",
            "inference_graph.json",
            "inference_graph_nodes.csv",
            "inference_graph_edges.csv",
            "semantic_graph.json",
            "semantic_graph_nodes.csv",
            "semantic_graph_edges.csv",
        ]:
            src = base_out / fname
            if src.exists():
                shutil.copyfile(src, book_dir / fname)

        update("????...", 40)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-items", action="store_true")
    parser.add_argument("--skip-relations", action="store_true")
    parser.add_argument("--skip-context", action="store_true")
    parser.add_argument("--skip-inference", action="store_true")
    parser.add_argument("--skip-graphs", action="store_true")
    parser.add_argument("--skip-emotion-strength", action="store_true")
    parser.add_argument("--skip-character-rel", action="store_true")
    parser.add_argument("--skip-hybrid", action="store_true")
    parser.add_argument("--skip-zero-shot-task", action="store_true")
    parser.add_argument("--skip-zero-shot-action", action="store_true")
    parser.add_argument("--skip-zero-shot-emotion", action="store_true")
    parser.add_argument("--skip-zero-shot-emotion-strength", action="store_true")
    parser.add_argument("--skip-timeline", action="store_true")
    parser.add_argument("--skip-mission-timeline", action="store_true")
    parser.add_argument("--skip-speaker", action="store_true", help="Skip speaker/voice/perspective annotation")
    parser.add_argument("--book-name", type=str, default=None, help="Output sub directory name")
    parser.add_argument("--novel-path", type=str, default=None, help="Override novel path")
    parser.add_argument("--limit-chapters", type=int, default=None, help="Limit number of chapters")
    parser.add_argument("--limit-sentences", type=int, default=None, help="Limit sentences per chapter")
    args = parser.parse_args()

    run_pipeline(
        skip_items=args.skip_items,
        skip_relations=args.skip_relations,
        skip_context=args.skip_context,
        skip_inference=args.skip_inference,
        skip_graphs=args.skip_graphs,
        skip_emotion_strength=args.skip_emotion_strength,
        skip_character_rel=args.skip_character_rel,
        skip_hybrid=args.skip_hybrid,
        skip_zero_shot_task=args.skip_zero_shot_task,
        skip_zero_shot_action=args.skip_zero_shot_action,
        skip_zero_shot_emotion=args.skip_zero_shot_emotion,
        skip_zero_shot_emotion_strength=args.skip_zero_shot_emotion_strength,
        skip_timeline=args.skip_timeline,
        skip_mission_timeline=args.skip_mission_timeline,
        skip_speaker=args.skip_speaker,
        output_subdir=args.book_name if args.book_name else None,
        novel_path=args.novel_path,
        limit_chapters=args.limit_chapters,
        limit_sentences=args.limit_sentences,
    )


