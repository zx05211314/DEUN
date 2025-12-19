"""
小說語意圖譜主頁
Contract:
 - Input:  novels/<book_name>.txt  (上傳或既有檔，書名即檔名 stem)
 - Output: output/<book_name>/ 下列檔案：
     items.json, relations.json, relations_with_context.json, semantic_relations.json,
     timeline.json(含 speaker/voice/emotion_perspective/low_confidence),
     speaker_summary.json(若啟用), semantic_graph.json, graph.json,
     mission_timeline.json(若啟用), metadata.json, 其他推論檔。
 UI 僅讀取 output/<book_name>/，不讀取 output 根目錄。
"""
from __future__ import annotations

import subprocess
from importlib import util
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st
from scripts.clean_output import clean_book_output

from app.components.chapter_comparison_view import render_chapter_comparison
from app.components.downloads_view import render_downloads
from app.components.interaction_heatmap_view import render_interaction_heatmap
from app.components.metadata_view import render_metadata
from app.components.pov_shift_view import render_pov_shift_map
from app.components.role_comparison_view import render_role_comparison
from app.components.semantic_graphs import render_graphs
from app.components.semantic_overview import render_emotion_charts, render_overview_cards
from app.components.semantic_tables import render_tables
from app.components.speaker_summary_view import render_speaker_summary
from app.components.story_emotion_arc_view import render_story_emotion_arc
from app.components.timeline_view import render_timeline
from app.utils.consistency_checks import run_entity_consistency_checks
from app.utils.data_loaders import (
    load_outputs,
    sanitize_book_name,
    validate_novel_input,
)
from app.utils.filters import apply_semantic_filters
from app.utils.validate_outputs import validate_outputs

plotly_events_available = util.find_spec("streamlit_plotly_events") is not None
plotly_events = None
if plotly_events_available:
plotly_events = None
if util.find_spec("streamlit_plotly_events"):
    from streamlit_plotly_events import plotly_events


EXPECTED_OUTPUT_FILES = [
    "items.json",
    "relations.json",
    "semantic_relations.json",
    "timeline.json",
    "speaker_summary.json",
    "graph.json",
    "semantic_graph.json",
    "metadata.json",
    "mission_timeline.json",
]


# ----------------------------------------------------------------------
# Pipeline helpers
# ----------------------------------------------------------------------


def run_pipeline_inline(
    book_name: str,
    novel_path: Path,
    limit_chapters: int,
    limit_sentences: int,
    zero_action: bool,
    zero_task: bool,
    zero_emotion: bool,
    zero_strength: bool,
    skip_items: bool,
    skip_relations: bool,
    skip_context: bool,
    skip_inference: bool,
    skip_graphs: bool,
    skip_emotion_strength: bool,
    skip_character_rel: bool,
    skip_timeline: bool,
    skip_mission_timeline: bool,
    skip_speaker: bool,
    progress_callback=None,
):
    cmd = [
        "python",
        "-m",
        "scripts.run_pipeline",
        f"--book-name={book_name}",
        f"--novel-path={str(novel_path)}",
        f"--limit-chapters={limit_chapters}",
        f"--limit-sentences={limit_sentences}",
    ]
    if not zero_action:
        cmd.append("--skip-zero-shot-action")
    if not zero_task:
        cmd.append("--skip-zero-shot-task")
    if not zero_emotion:
        cmd.append("--skip-zero-shot-emotion")
    if not zero_strength:
        cmd.append("--skip-zero-shot-emotion-strength")
    if skip_items:
        cmd.append("--skip-items")
    if skip_relations:
        cmd.append("--skip-relations")
    if skip_context:
        cmd.append("--skip-context")
    if skip_inference:
        cmd.append("--skip-inference")
    if skip_graphs:
        cmd.append("--skip-graphs")
    if skip_emotion_strength:
        cmd.append("--skip-emotion-strength")
    if skip_character_rel:
        cmd.append("--skip-character-rel")
    if skip_timeline:
        cmd.append("--skip-timeline")
    if skip_mission_timeline:
        cmd.append("--skip-mission-timeline")
    if skip_speaker:
        cmd.append("--skip-speaker")

    if progress_callback:
        progress_callback("啟動分析流程", 5)

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pipeline 執行失敗")
    if progress_callback:
        progress_callback("分析完成", 100)
    return result.stdout


# ----------------------------------------------------------------------
# Sidebar controls
# ----------------------------------------------------------------------


def sidebar_controls():
    st.sidebar.title("小說語意圖譜")
    st.sidebar.checkbox("Dark Mode", value=True, disabled=True)

    st.sidebar.subheader("選擇既有小說（novels/.txt）")
    novels_dir = Path("novels")
    existing_novels = (
        [p.stem for p in novels_dir.glob("*.txt")] if novels_dir.exists() else []
    )
    selected_novel = st.sidebar.selectbox("既有小說", options=[""] + existing_novels)

    st.sidebar.subheader("上傳新小說")
    uploaded_file = st.sidebar.file_uploader("📘 上傳小說 (.txt)", type=["txt"])
    book_name_input = st.sidebar.text_input("書名（亦作輸出資料夾名）", value=selected_novel or "")
    sanitized_book_name = sanitize_book_name(book_name_input)
    if book_name_input and sanitized_book_name != book_name_input:
        st.sidebar.info(f"已移除不支援的符號，改為：{sanitized_book_name}")

    novel_path = None
    if selected_novel:
        novel_path_candidate = novels_dir / f"{selected_novel}.txt"
        if novel_path_candidate.exists():
            novel_path = novel_path_candidate

    if uploaded_file and book_name_input:
        if not sanitized_book_name:
            st.sidebar.error("書名不可為空且需為有效的檔名。")
        else:
            novels_dir.mkdir(exist_ok=True)
            novel_path = novels_dir / f"{sanitized_book_name}.txt"
            novel_path.write_bytes(uploaded_file.getvalue())
            st.sidebar.success(f"已儲存至 {novel_path}")

    with st.sidebar.expander("分析選項", expanded=True):
        limit_chapters = st.number_input("限制章節數", min_value=1, max_value=2000, value=100)
        limit_sentences = st.number_input("限制句子數", min_value=50, max_value=50000, value=10000, step=50)

        zero_action = st.checkbox("啟用 zero-shot 行為", value=True)
        zero_task = st.checkbox("啟用 zero-shot 任務", value=True)
        zero_emotion = st.checkbox("啟用 zero-shot 情緒", value=True)
        zero_strength = st.checkbox("啟用 zero-shot 情緒強度", value=True)

        st.markdown("模組開關")
        skip_items = not st.checkbox("道具/能力", value=True)
        skip_relations = not st.checkbox("角色-道具關係", value=True)
        skip_context = not st.checkbox("上下文補充", value=True)
        skip_inference = not st.checkbox("行為推論", value=True)
        skip_graphs = not st.checkbox("圖譜", value=True)
        skip_emotion_strength = not st.checkbox("情緒強度", value=True)
        skip_character_rel = not st.checkbox("角色-角色關係", value=True)
        skip_timeline = not st.checkbox("事件時間線", value=True)
        skip_mission_timeline = not st.checkbox("任務時間線", value=True)
        skip_speaker = not st.checkbox("語者視角", value=True)

    output_root = Path("output")
    existing_outputs = [p.name for p in output_root.iterdir() if p.is_dir()] if output_root.exists() else []
    selected_output_book = st.sidebar.selectbox("已產出書目 (output/)", options=[""] + existing_outputs)

    dry_run = st.sidebar.checkbox("Dry run (validate + show planned outputs only)", value=False)

    return (
        sanitized_book_name,
        novel_path,
        selected_output_book,
        limit_chapters,
        limit_sentences,
        zero_action,
        zero_task,
        zero_emotion,
        zero_strength,
        skip_items,
        skip_relations,
        skip_context,
        skip_inference,
        skip_graphs,
        skip_emotion_strength,
        skip_character_rel,
        skip_timeline,
        skip_mission_timeline,
        skip_speaker,
        dry_run,
    )


# ----------------------------------------------------------------------
# Semantic filters
# ----------------------------------------------------------------------


def semantic_filters(semantic_data):
    speakers = sorted({r.get("speaker", "") for r in semantic_data if r.get("speaker")})
    voices = sorted({r.get("voice", "") for r in semantic_data if r.get("voice")})
    perspectives = sorted(
        {r.get("emotion_perspective", "") for r in semantic_data if r.get("emotion_perspective")}
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        speaker_sel = st.selectbox("語者", options=["全部"] + speakers, index=0)
    with col2:
        voice_sel = st.selectbox("語態", options=["全部"] + voices, index=0)
    with col3:
        persp_sel = st.selectbox("情緒來源", options=["全部"] + perspectives, index=0)
    keyword = st.text_input("句子/事件關鍵字過濾", value="")
    low_conf_only = st.checkbox("只顯示低信度項目", value=False)
    return speaker_sel, voice_sel, persp_sel, keyword, low_conf_only


def apply_semantic_filters(
    sem: List[Dict],
    speaker_sel: str,
    voice_sel: str,
    persp_sel: str,
    keyword: str,
    low_conf_only: bool,
):
    filtered = []
    keyword_lower = (keyword or "").strip().lower()
    for r in sem or []:
        if speaker_sel != "全部" and r.get("speaker") != speaker_sel:
            continue
        if voice_sel != "全部" and r.get("voice") != voice_sel:
            continue
        if persp_sel != "全部" and r.get("emotion_perspective") != persp_sel:
            continue
        if low_conf_only and not r.get("low_confidence"):
            continue
        if keyword_lower:
            sentence = (r.get("sentence") or r.get("event") or "").lower()
            if keyword_lower not in sentence:
                continue
        filtered.append(r)
    return filtered


def render_overview_cards(sem_filtered: List[Dict]):
    total = len(sem_filtered)
    low_conf = sum(1 for r in sem_filtered if r.get("low_confidence"))
    speakers = {r.get("speaker") for r in sem_filtered if r.get("speaker")}

    col1, col2, col3 = st.columns(3)
    col1.metric("語意筆數", f"{total}")
    col2.metric("低信度筆數", f"{low_conf}")
    col3.metric("獨立語者", f"{len(speakers)}")


def render_emotion_charts(sem_filtered: List[Dict]):
    if not sem_filtered:
        return

    df = pd.DataFrame(sem_filtered)
    with st.expander("情緒分布圖表", expanded=False):
        if "emotion" in df.columns and not df["emotion"].dropna().empty:
            emo_counts = df["emotion"].value_counts().reset_index()
            emo_counts.columns = ["emotion", "count"]
            fig = px.bar(emo_counts, x="emotion", y="count", title="情緒類別分布")
            st.plotly_chart(fig, use_container_width=True)

        if "emotion_perspective" in df.columns and not df["emotion_perspective"].dropna().empty:
            persp_counts = df["emotion_perspective"].value_counts().reset_index()
            persp_counts.columns = ["perspective", "count"]
            fig2 = px.bar(
                persp_counts,
                x="perspective",
                y="count",
                title="情緒觀點分布",
                color="perspective",
            )
            st.plotly_chart(fig2, use_container_width=True)


def render_detail_panel(selected_item: Dict[str, Any]):
    """統一顯示詳情卡片（事件或節點）。"""
    if not selected_item:
        return
    with st.expander("詳細資訊", expanded=True):
        if selected_item.get("type") == "node":
            st.markdown(f"**節點：{selected_item.get('name','')}**")
            if selected_item.get("degree") is not None:
                st.caption(f"度數：{selected_item['degree']}")
            rels = selected_item.get("related_relations") or []
            st.markdown(f"關聯語意筆數：{len(rels)}")
            if rels:
                df = pd.DataFrame(rels)
                st.dataframe(df, width="stretch")
        else:
            st.markdown(f"**句子**：{selected_item.get('sentence','')}")
            st.markdown(
                f"語者：{selected_item.get('speaker','')} ｜ 語態：{selected_item.get('voice','')} ｜ "
                f"情緒觀點：{selected_item.get('emotion_perspective','')} ｜ 信度：{'低' if selected_item.get('low_confidence') else '高'}"
            )
            if selected_item.get("time"):
                st.caption(f"時間：{selected_item.get('time')}")


def render_tables(sem_filtered: List[Dict]):
    st.subheader("語意關聯表")
    if not sem_filtered:
        st.info("目前沒有可用的語意關聯資料。")
        return
    df = pd.DataFrame(sem_filtered)
    if "low_confidence" in df.columns:
        df["信度"] = df["low_confidence"].apply(lambda x: "⚠ 低" if x else "高")
    st.dataframe(df, width="stretch")


def render_timeline(timeline_data: List[Dict], sem_filtered: List[Dict]):
    st.subheader("時間線")
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


def render_graphs(outputs: dict, sem_filtered: List[Dict]):
    st.subheader("互動圖譜")
    if not outputs.get("semantic_graph", {}).get("nodes"):
        st.info("目前沒有圖譜資料。")
        return
    selected = render_interactive_graph(outputs.get("semantic_graph", {}), sem_filtered)
    if selected:
        render_detail_panel(selected)


def render_io_contract():
    st.subheader("Input / Output Contract")
    st.markdown(
        """
        **輸入資料夾（novels/）**：放置待分析的小說文字檔，預設支援 `.txt`。
        
        **選擇方式**：可從左側下拉選取現有檔案，或上傳檔案並指定書名（亦作輸出資料夾名）。
        
        **輸出資料夾（output/<book_name>/）**：分析後將產生下列主要檔案：
        - items.json
        - relations.json
        - semantic_relations.json
        - timeline.json
        - speaker_summary.json
        - graph.json / semantic_graph.json
        - metadata.json
        - mission_timeline.json
        - 其他衍生匯出（CSV/HTML，如有）
        
        每次執行前會先清空對應的 `output/<book_name>/`（`scripts/clean_output.py`）。
        """
    )


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def main():
    (
        book_name,
        novel_path,
        selected_output_book,
        limit_chapters,
        limit_sentences,
        zero_action,
        zero_task,
        zero_emotion,
        zero_strength,
        skip_items,
        skip_relations,
        skip_context,
        skip_inference,
        skip_graphs,
        skip_emotion_strength,
        skip_character_rel,
        skip_timeline,
        skip_mission_timeline,
        skip_speaker,
        dry_run,
    ) = sidebar_controls()

    render_io_contract()

    if st.sidebar.button("🚀 分析此小說", type="primary"):
        is_valid, msg, sanitized_book_name, resolved_path = validate_novel_input(
            book_name, novel_path
        )
        if not is_valid or not resolved_path:
            st.sidebar.error(msg)
        else:
            output_dir = Path("output") / sanitized_book_name
            planned_outputs = "\n".join(f"- {name}" for name in EXPECTED_OUTPUT_FILES)

            if dry_run:
                st.sidebar.info("Dry run：僅檢查輸入與預期輸出，未執行分析流程。")
                st.info(
                    "\n".join(
                        [
                            "Dry run：將不執行 pipeline。",
                            f"小說路徑：`{resolved_path}`",
                            f"輸出資料夾：`{output_dir}`",
                            "預期產物：",
                            planned_outputs,
                            f"清理步驟：正式執行前會清空 `{output_dir}`。",
                        ]
                    )
                )
                st.session_state["selected_book"] = sanitized_book_name
                return

            progress_bar = st.sidebar.progress(0, text="開始分析...")

            def update_progress(msg, pct):
                progress_bar.progress(min(max(int(pct), 0), 100), text=msg)

            try:
                clean_book_output(sanitized_book_name)
                run_pipeline_inline(
                    book_name=sanitized_book_name,
                    novel_path=resolved_path,
                    limit_chapters=limit_chapters,
                    limit_sentences=limit_sentences,
                    zero_action=zero_action,
                    zero_task=zero_task,
                    zero_emotion=zero_emotion,
                    zero_strength=zero_strength,
                    skip_items=skip_items,
                    skip_relations=skip_relations,
                    skip_context=skip_context,
                    skip_inference=skip_inference,
                    skip_graphs=skip_graphs,
                    skip_emotion_strength=skip_emotion_strength,
                    skip_character_rel=skip_character_rel,
                    skip_timeline=skip_timeline,
                    skip_mission_timeline=skip_mission_timeline,
                    skip_speaker=skip_speaker,
                    progress_callback=update_progress,
                )
                st.sidebar.success("分析完成")
                st.session_state["selected_book"] = sanitized_book_name
            except Exception as e:
                st.sidebar.error(f"分析失敗：{e}")

    current_book = st.session_state.get("selected_book") or selected_output_book or book_name
    if not current_book:
        st.warning("請選擇或上傳一本小說。")
        return

    book_dir = Path("output") / current_book
    input_path = Path("novels") / f"{current_book}.txt"
    if not input_path.exists():
        st.warning(f"找不到小說輸入檔：{input_path}，請先上傳或放入 novels/。")
    if not book_dir.exists():
        st.warning(f"找不到分析輸出資料夾：{book_dir}，請先執行分析。")
        return

    validation_ok, validation_issues, validation_stats = validate_outputs(str(book_dir))

    st.subheader("Output Validation")
    if validation_ok:
        st.success("Output validation passed.")
    else:
        st.error("Output validation found issues.")
    st.json({"stats": validation_stats})

    if validation_issues:
        with st.expander("Validation issues (showing up to 20)", expanded=not validation_ok):
            st.write("\n".join(validation_issues[:20]))
        if not st.checkbox("Continue even if issues exist", value=False):
            st.info("Rendering stopped because validation issues were detected.")
            return

    outputs = load_outputs(book_dir)
    registry = outputs.get("entity_registry")
    consistency = run_entity_consistency_checks(outputs, registry)

    with st.expander("實體正規化診斷", expanded=False):
        st.markdown(
            f"註冊檔載入狀態：{'已載入' if consistency.get('registry_loaded') else '未載入（使用原始名稱）'}"
        )
        st.markdown(f"註冊檔路徑：{consistency.get('registry_path', '')}")
        st.markdown(f"被封鎖的名稱筆數：{consistency.get('blocked_hits', 0)}")
        orphan = consistency.get("orphan_aliases", [])
        if orphan:
            st.write("未在註冊檔中的名稱（前 50 筆）：")
            st.dataframe(orphan[:50], use_container_width=True)
        st.write({"缺漏實體": consistency.get("missing", {})})

    st.title(f"語意關聯表 - {current_book}")
    render_metadata(outputs.get("metadata", {}), book_dir)

    speaker_sel, voice_sel, persp_sel, keyword, low_conf_only = semantic_filters(
        outputs.get("semantic_relations", [])
    )
    speaker_sel, voice_sel, persp_sel, keyword, low_conf_only = semantic_filters(outputs.get("semantic_relations", []))
    sem_filtered = apply_semantic_filters(
        outputs.get("semantic_relations", []),
        speaker_sel,
        voice_sel,
        persp_sel,
        keyword,
        low_conf_only,
    )

    render_overview_cards(sem_filtered)
    render_tables(sem_filtered)
    render_emotion_charts(sem_filtered)
    render_role_comparison(sem_filtered, outputs.get("speaker_summary", {}))
    render_interaction_heatmap(sem_filtered, registry=registry)
    render_graphs(outputs, sem_filtered)
    render_story_emotion_arc(outputs, sem_filtered)
    render_pov_shift_map(outputs, sem_filtered)
    render_chapter_comparison(outputs, sem_filtered)
    render_timeline(outputs.get("timeline", []), sem_filtered, plotly_events_available, plotly_events)
    render_speaker_summary(outputs.get("speaker_summary", {}))
    render_downloads(current_book, sem_filtered, outputs.get("speaker_summary", {}))

    st.subheader("其他分析結果")
    st.markdown("道具/能力")
    items = outputs.get("items", [])
    if items:
        st.dataframe(pd.DataFrame(items), width="stretch")
    else:
        st.info("尚無道具資料。")

    st.markdown("角色關係")
    if outputs.get("character_relations"):
        st.dataframe(pd.DataFrame(outputs.get("character_relations")), width="stretch")
    else:
        st.info("尚無角色關係資料。")


if __name__ == "__main__":
    main()
