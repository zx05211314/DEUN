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

import json
import subprocess
from importlib import util
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st
from app.components.interactive_graph import render_interactive_graph
from app.components.timeline_chart import timeline_bar
from scripts.clean_output import clean_book_output

plotly_events_available = util.find_spec("streamlit_plotly_events") is not None
plotly_events = None
if plotly_events_available:
    from streamlit_plotly_events import plotly_events


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


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

    novel_path = None
    # 若選擇既有小說且檔案存在，直接設為 canonical path
    if selected_novel:
        novel_path_candidate = novels_dir / f"{selected_novel}.txt"
        if novel_path_candidate.exists():
            novel_path = novel_path_candidate

    # 若上傳新檔，且填了書名，寫入 novels/<book>.txt
    if uploaded_file and book_name_input:
        novels_dir.mkdir(exist_ok=True)
        novel_path = novels_dir / f"{book_name_input}.txt"
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

    # 現有分析結果的書目（output 子資料夾）
    output_root = Path("output")
    existing_outputs = [p.name for p in output_root.iterdir() if p.is_dir()] if output_root.exists() else []
    selected_output_book = st.sidebar.selectbox("已產出書目 (output/)", options=[""] + existing_outputs)

    return (
        book_name_input,
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
    )


# ----------------------------------------------------------------------
# Load & render
# ----------------------------------------------------------------------


def load_outputs(book_dir: Path):
    data: Dict[str, Any] = {}
    data["items"] = load_json(book_dir / "items.json", [])
    data["relations"] = load_json(book_dir / "relations.json", [])
    data["semantic_relations"] = load_json(book_dir / "semantic_relations.json", [])
    data["speaker_summary"] = load_json(book_dir / "speaker_summary.json", {})
    data["character_relations"] = load_json(book_dir / "character_relations.json", [])
    data["graph"] = load_json(book_dir / "graph.json", {"nodes": [], "edges": []})
    data["semantic_graph"] = load_json(book_dir / "semantic_graph.json", {"nodes": [], "edges": []})
    data["timeline"] = load_json(book_dir / "timeline.json", [])
    data["mission_timeline"] = load_json(book_dir / "mission_timeline.json", [])
    data["metadata"] = load_json(book_dir / "metadata.json", {})
    return data


def render_metadata(metadata: dict, output_dir: Path):
    if not metadata:
        st.info("尚未找到 metadata.json，可重新執行分析。")
        return
    st.subheader("分析摘要")
    book = metadata.get("book", "")
    lc = metadata.get("chapters_used")
    ls = metadata.get("sentences_used")
    zero = metadata.get("zero_shot", {})
    enabled = metadata.get("enabled_modules", {})
    stats = metadata.get("output_stats", {})

    st.markdown(
        f"""
**書名**：{book}  
**章節/句數限制**：{lc} / {ls}  
**Zero-shot**：行為 {zero.get('action')}、任務 {zero.get('task')}、情緒 {zero.get('emotion')}、情緒強度 {zero.get('emotion_strength')}  
**啟用模組**：{", ".join([k for k, v in enabled.items() if v])}  
**產出統計**：{json.dumps(stats, ensure_ascii=False)}  
**輸出目錄**：{output_dir}
"""
    )


def semantic_filters(semantic_data):
    speakers = sorted({r.get("speaker", "") for r in semantic_data if r.get("speaker")})
    voices = sorted({r.get("voice", "") for r in semantic_data if r.get("voice")})
    perspectives = sorted({r.get("emotion_perspective", "") for r in semantic_data if r.get("emotion_perspective")})

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
    with st.expander("情緒與視角統計", expanded=False):
        if not sem_filtered:
            st.info("目前篩選條件下沒有任何語意關聯資料。")
            return

        df = pd.DataFrame(sem_filtered)

        total = len(sem_filtered)
        low_conf = sum(1 for r in sem_filtered if r.get("low_confidence"))
        speakers = {r.get("speaker") for r in sem_filtered if r.get("speaker")}

        stat_cols = st.columns(3)
        stat_cols[0].metric("語意筆數", f"{total}")
        stat_cols[1].metric("低信度筆數", f"{low_conf}")
        stat_cols[2].metric("獨立語者", f"{len(speakers)}")

        if "emotion" in df.columns and not df["emotion"].dropna().empty:
            emo_series = df["emotion"].dropna()
        elif "emotion_perspective" in df.columns and not df["emotion_perspective"].dropna().empty:
            emo_series = df["emotion_perspective"].dropna()
        else:
            emo_series = pd.Series(dtype=object)

        if not emo_series.empty:
            emo_counts = emo_series.value_counts().reset_index()
            emo_counts.columns = ["emotion", "count"]
            fig = px.bar(emo_counts, x="emotion", y="count", title="情緒 / 視角分布")
            st.plotly_chart(fig, use_container_width=True)

        if "voice" in df.columns and not df["voice"].dropna().empty:
            voice_counts = df["voice"].dropna().value_counts().reset_index()
            voice_counts.columns = ["voice", "count"]
            voice_fig = px.bar(
                voice_counts, x="voice", y="count", title="語態 / 視角分布", color="voice"
            )
            st.plotly_chart(voice_fig, use_container_width=True)


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


def render_graphs(outputs: dict, sem_filtered: List[Dict]):
    st.subheader("互動圖譜")
    if not outputs.get("semantic_graph", {}).get("nodes"):
        st.info("目前沒有圖譜資料。")
        return
    selected = render_interactive_graph(outputs.get("semantic_graph", {}), sem_filtered)
    if selected:
        render_detail_panel(selected)


def render_speaker_summary(speaker_summary: dict):
    if not speaker_summary:
        return
    with st.expander("語者摘要（高情緒強度 Top N）", expanded=False):
        for name, entries in speaker_summary.items():
            st.markdown(f"**{name}**")
            for line, strength in entries:
                st.markdown(f"- {line}（強度: {strength}）")


def render_role_comparison(sem_filtered: List[Dict], speaker_summary: dict):
    st.subheader("角色比較")
    if not sem_filtered:
        st.info("請先選擇至少一位角色，或調整篩選條件。")
        return

    df = pd.DataFrame(sem_filtered)
    speakers = sorted({s for s in df.get("speaker", []) if s})

    selected = st.multiselect(
        "選擇要比較的角色（最多 3 名）",
        options=speakers,
        max_selections=3,
    )

    if not selected:
        st.info("請先選擇至少一位角色，或調整篩選條件。")
        return

    rows = []
    for name in selected:
        speaker_rows = df[df["speaker"] == name]
        total_rel = len(speaker_rows)
        low_conf_rel = (
            speaker_rows["low_confidence"].fillna(False).sum()
            if "low_confidence" in speaker_rows.columns
            else 0
        )

        emo_values = []
        if "emotion" in speaker_rows.columns:
            emo_values.extend([e for e in speaker_rows["emotion"].dropna()])
        if "emotion_perspective" in speaker_rows.columns:
            emo_values.extend([e for e in speaker_rows["emotion_perspective"].dropna()])

        unique_emotions = len(set(emo_values))
        rows.append(
            {
                "角色": name,
                "語意關聯數量": total_rel,
                "低信度關聯數量": int(low_conf_rel),
                "情緒類型數量": unique_emotions,
            }
        )

    comparison_df = pd.DataFrame(rows)
    st.dataframe(comparison_df, width="stretch")

    chart_df = comparison_df.copy()
    chart_fig = px.bar(
        chart_df,
        x="角色",
        y="語意關聯數量",
        color="低信度關聯數量",
        title="角色語意關聯比較",
    )
    st.plotly_chart(chart_fig, use_container_width=True)

    if speaker_summary:
        with st.expander("語者摘要對照", expanded=False):
            for name in selected:
                if name not in speaker_summary:
                    continue
                st.markdown(f"**{name}**")
                for line, strength in speaker_summary[name]:
                    st.markdown(f"- {line}（強度: {strength}）")


def render_downloads(book_name: str, sem_filtered: List[Dict], speaker_summary: dict):
    st.subheader("下載")
    low_rows = [r for r in sem_filtered if r.get("low_confidence")]
    if low_rows:
        df_low = pd.DataFrame(low_rows)
        st.download_button(
            "下載低信度 CSV",
            df_low.to_csv(index=False).encode("utf-8"),
            file_name=f"{book_name}_low_confidence.csv",
        )

    emo_dist = pd.Series([r.get("emotion") for r in sem_filtered if r.get("emotion")]).value_counts()
    perspective_dist = pd.Series([r.get("emotion_perspective") for r in sem_filtered if r.get("emotion_perspective")]).value_counts()
    low_count = len(low_rows)
    top_speakers = list(speaker_summary.items())[:3] if speaker_summary else []

    md_parts = [
        f"# {book_name} 分析報告",
        "## 總覽",
        f"- 關係筆數：{len(sem_filtered)}",
        f"- 低信度筆數：{low_count}",
        "## 情緒分布",
        emo_dist.to_markdown() if not emo_dist.empty else "無",
        "## 情緒觀點分布",
        perspective_dist.to_markdown() if not perspective_dist.empty else "無",
        "## 語者摘要 Top N",
    ]
    for name, entries in top_speakers:
        md_parts.append(f"- {name}")
        for line, strength in entries:
            md_parts.append(f"  - {line}（強度: {strength}）")
    md_content = "\n\n".join(md_parts)
    st.download_button("匯出分析報告（Markdown）", md_content.encode("utf-8"), file_name=f"{book_name}_report.md")


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
    ) = sidebar_controls()

    # 分析按鈕
    if st.sidebar.button("🚀 分析此小說", type="primary"):
        if not book_name:
            st.sidebar.error("請先輸入書名。")
        else:
            # 確認 canonical input 在 novels/<book>.txt
            novel_path_use = Path("novels") / f"{book_name}.txt"
            if novel_path:
                novel_path_use = novel_path  # 上傳時已寫入
            if not novel_path_use.exists():
                st.sidebar.error(f"找不到輸入檔：{novel_path_use}")
            else:
                progress_bar = st.sidebar.progress(0, text="開始分析...")

                def update_progress(msg, pct):
                    progress_bar.progress(min(max(int(pct), 0), 100), text=msg)

                try:
                    clean_book_output(book_name)
                    run_pipeline_inline(
                        book_name=book_name,
                        novel_path=novel_path_use,
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
                    st.session_state["selected_book"] = book_name
                except Exception as e:
                    st.sidebar.error(f"分析失敗：{e}")

    # 決定當前顯示的書名
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

    outputs = load_outputs(book_dir)

    st.title(f"語意關聯表 - {current_book}")
    render_metadata(outputs.get("metadata", {}), book_dir)

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
    render_graphs(outputs, sem_filtered)
    render_timeline(outputs.get("timeline", []), sem_filtered)
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
