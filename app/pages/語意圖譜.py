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
from collections import Counter
import math
from importlib import util
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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


EMOTION_SCORE_MAP = {
    "極度負向": -2,
    "負向": -1,
    "憤怒": -1,
    "悲傷": -1,
    "害怕": -1,
    "中性": 0,
    "平靜": 0,
    "正向": 1,
    "期待": 1,
    "開心": 1,
    "極度正向": 2,
}

POV_GROUPS = {
    "第一人稱": "第一人稱",
    "我": "第一人稱",
    "我方": "第一人稱",
    "第三人稱": "第三人稱",
    "全知視角": "第三人稱全知",
    "全知": "第三人稱全知",
}


def categorize_emotion_label(value: Optional[Any]) -> str:
    """將情緒標籤分類為正向/負向/中性，未知以中性處理。"""

    score = map_emotion_score(value)
    if score > 0:
        return "正向"
    if score < 0:
        return "負向"
    return "中性"


def map_emotion_score(value: Optional[Any]) -> float:
    """將情緒標籤映射為簡易分數；未命中則視為 0。"""

    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(EMOTION_SCORE_MAP.get(value.strip(), 0))
    return 0.0


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


def extract_characters_from_relation(rel: Dict[str, Any]) -> List[str]:
    participants = set()

    if isinstance(rel.get("participants"), list):
        for p in rel["participants"]:
            if isinstance(p, str) and p.strip():
                participants.add(p.strip())

    candidate_fields = [
        "speaker",
        "character",
        "target_speaker",
        "target_character",
        "other_speaker",
        "listener",
        "subject",
        "object_character",
        "object_speaker",
        "target",
    ]

    for field in candidate_fields:
        val = rel.get(field)
        if isinstance(val, str) and val.strip():
            participants.add(val.strip())

    return [p for p in participants if p]


def render_interaction_heatmap(sem_filtered: List[Dict]):
    st.subheader("角色互動熱度矩陣")

    if not sem_filtered:
        st.info("目前篩選條件下沒有任何語意關聯資料，無法計算角色互動。")
        return

    pair_counts: Counter = Counter()
    character_totals: Counter = Counter()
    for rel in sem_filtered:
        participants = extract_characters_from_relation(rel)
        if len(participants) < 2:
            continue
        for a, b in combinations(sorted(set(participants)), 2):
            pair_counts[(a, b)] += 1
            character_totals[a] += 1
            character_totals[b] += 1

    if not pair_counts:
        st.info("目前角色數量過少，無法繪製互動熱度矩陣。請放寬篩選條件或選擇其他書目。")
        return

    total_interactions = int(sum(pair_counts.values()))
    distinct_pairs = len(pair_counts)
    characters = sorted(character_totals.keys())

    col1, col2, col3 = st.columns(3)
    col1.metric("總互動對數", distinct_pairs)
    col2.metric("總互動次數", total_interactions)
    col3.metric("角色數量", len(characters))

    top_pairs = (
        pd.DataFrame(
            [
                {"角色 A": a, "角色 B": b, "互動次數": cnt}
                for (a, b), cnt in pair_counts.most_common()
            ]
        )
        .sort_values("互動次數", ascending=False)
        .head(20)
    )
    st.dataframe(top_pairs, width="stretch")

    slider_max = max(2, len(characters))
    top_n = st.slider("顯示前 N 位角色", min_value=2, max_value=slider_max, value=min(20, slider_max))

    sorted_chars = [c for c, _ in character_totals.most_common(top_n)]
    if len(sorted_chars) < 2:
        st.info("目前角色數量過少，無法繪製互動熱度矩陣。請放寬篩選條件或選擇其他書目。")
        return

    matrix = pd.DataFrame(0, index=sorted_chars, columns=sorted_chars)
    for (a, b), cnt in pair_counts.items():
        if a in matrix.index and b in matrix.columns:
            matrix.loc[a, b] = cnt
            matrix.loc[b, a] = cnt

    heatmap = go.Figure(
        data=[
            go.Heatmap(
                z=matrix.values,
                x=matrix.columns,
                y=matrix.index,
                colorscale="YlOrRd",
                colorbar=dict(title="互動次數"),
            )
        ]
    )
    heatmap.update_layout(xaxis_title="角色", yaxis_title="角色")
    st.plotly_chart(heatmap, use_container_width=True)


def render_story_emotion_arc(outputs: dict, sem_filtered: List[Dict]):
    st.subheader("故事情緒曲線")

    timeline_data = outputs.get("timeline") or []
    source_data = timeline_data if timeline_data else sem_filtered

    if not source_data:
        st.info("目前沒有可用的時間線或語意資料，無法繪製故事情緒曲線。")
        return

    def order_key(item: Dict[str, Any]):
        for key in ("order", "index", "idx", "position", "sequence", "seq", "id", "time_idx"):
            val = item.get(key)
            if isinstance(val, (int, float)):
                return val
        return None

    ordered_items = sorted(
        enumerate(source_data),
        key=lambda pair: (order_key(pair[1]) if order_key(pair[1]) is not None else pair[0]),
    )

    rows = []
    for pos, (_, item) in enumerate(ordered_items, start=1):
        numeric_score = None
        for cand in ("emotion_score", "sentiment_score", "valence"):
            if cand in item and isinstance(item.get(cand), (int, float)):
                numeric_score = float(item[cand])
                break

        emotion_value = numeric_score
        if emotion_value is None:
            emotion_value = item.get("emotion") or item.get("emotion_perspective")

        rows.append(
            {
                "position": pos,
                "emotion_score": map_emotion_score(emotion_value),
                "speaker": item.get("speaker"),
                "chapter": item.get("chapter"),
            }
        )

    df = pd.DataFrame(rows)
    available_speakers = sorted({s for s in df["speaker"] if s})
    selected_speakers = st.multiselect(
        "僅顯示特定角色的情緒曲線（可留空顯示全部）",
        options=available_speakers,
    )

    if selected_speakers:
        df = df[df["speaker"].isin(selected_speakers)]

    if df.empty:
        st.info("目前資料點數太少，無法繪製有意義的情緒曲線。請放寬篩選條件或選擇其他角色。")
        return

    window = st.select_slider(
        "平滑視窗大小",
        options=[1, 3, 5, 7, 11],
        value=3,
        help="使用移動平均平滑情緒分數，1 為不平滑。",
    )

    if len(df) < 3:
        st.info("目前資料點數太少，無法繪製有意義的情緒曲線。請放寬篩選條件或選擇其他角色。")
        return

    fig = go.Figure()

    if selected_speakers:
        for name in selected_speakers:
            sub = df[df["speaker"] == name].sort_values("position")
            if sub.empty:
                continue
            sub["smoothed"] = sub["emotion_score"].rolling(
                window=window, center=True, min_periods=1
            ).mean()
            fig.add_trace(
                go.Scatter(
                    x=sub["position"],
                    y=sub["smoothed"],
                    mode="lines+markers",
                    name=name,
                )
            )
    else:
        df_sorted = df.sort_values("position")
        df_sorted["smoothed"] = df_sorted["emotion_score"].rolling(
            window=window, center=True, min_periods=1
        ).mean()
        fig.add_trace(
            go.Scatter(
                x=df_sorted["position"],
                y=df_sorted["smoothed"],
                mode="lines+markers",
                name="整體情緒",
            )
        )

    if not fig.data:
        st.info("目前資料點數太少，無法繪製有意義的情緒曲線。請放寬篩選條件或選擇其他角色。")
        return

    fig.update_layout(
        title="故事情緒曲線",
        xaxis_title="故事進程（事件序號）",
        yaxis_title="情緒分數",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("情緒分數為簡化映射，僅供觀察趨勢使用。")


def render_pov_shift_map(outputs: dict, sem_filtered: List[Dict]):
    st.subheader("敘事視角變化圖")

    timeline_data = outputs.get("timeline") or []
    source_data = timeline_data if timeline_data else sem_filtered

    if not source_data:
        st.info("目前沒有可用的時間線或語意資料，無法繪製敘事視角變化圖。")
        return

    def order_key(item: Dict[str, Any]):
        for key in ("order", "index", "idx", "position", "sequence", "seq", "id", "time_idx"):
            val = item.get(key)
            if isinstance(val, (int, float)):
                return val
        return None

    ordered_items = sorted(
        enumerate(source_data),
        key=lambda pair: (order_key(pair[1]) if order_key(pair[1]) is not None else pair[0]),
    )

    records: List[Dict[str, Any]] = []
    for pos, (_, item) in enumerate(ordered_items, start=1):
        voice_val = item.get("voice") or item.get("emotion_perspective")
        records.append(
            {
                "position": pos,
                "voice": voice_val,
                "speaker": item.get("speaker"),
                "chapter": item.get("chapter"),
            }
        )

    df = pd.DataFrame(records)
    if df.empty:
        st.info("目前資料點數太少，無法繪製有意義的視角變化圖。請放寬篩選條件或選擇其他角色。")
        return

    df["pov_group"] = df["voice"].map(POV_GROUPS).fillna(df["voice"].fillna("其他"))

    available_speakers = sorted({s for s in df["speaker"] if s})
    selected_speakers = st.multiselect(
        "僅顯示特定角色的視角變化（可留空顯示全部）",
        options=available_speakers,
    )

    if selected_speakers:
        df = df[df["speaker"].isin(selected_speakers)]

    if len(df) < 3:
        st.info("目前資料點數太少，無法繪製有意義的視角變化圖。請放寬篩選條件或選擇其他角色。")
        return

    window = st.select_slider(
        "視角統計視窗大小",
        options=[1, 5, 10, 20],
        value=1,
        help="可將事件分段後觀察主要敘事視角變化。",
    )

    df_sorted = df.sort_values("position").copy()
    if window > 1:
        df_sorted["window"] = (df_sorted["position"] - 1) // window
        aggregated = (
            df_sorted.groupby("window")
            .agg(
                position_start=("position", "min"),
                position_end=("position", "max"),
                position_mid=("position", "mean"),
                pov_group=("pov_group", lambda s: s.value_counts().idxmax()),
            )
            .reset_index(drop=True)
        )
        plot_df = aggregated.rename(columns={"position_mid": "position"})[["position", "pov_group"]]
    else:
        plot_df = df_sorted[["position", "pov_group"]]

    if len(plot_df) < 3:
        st.info("目前資料點數太少，無法繪製有意義的視角變化圖。請放寬篩選條件或選擇其他角色。")
        return

    pov_categories = sorted(plot_df["pov_group"].dropna().unique())
    pov_to_idx = {p: i for i, p in enumerate(pov_categories)}
    plot_df["pov_idx"] = plot_df["pov_group"].map(pov_to_idx)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df["position"],
            y=plot_df["pov_idx"],
            mode="lines+markers",
            line_shape="hv" if window == 1 else "linear",
            text=plot_df["pov_group"],
            hovertemplate="事件序號: %{x}<br>敘事視角: %{text}<extra></extra>",
            name="敘事視角",
        )
    )

    fig.update_layout(
        title="敘事視角變化圖",
        xaxis_title="故事進程（事件序號）",
        yaxis_title="敘事視角",
        yaxis=dict(tickmode="array", tickvals=list(pov_to_idx.values()), ticktext=pov_categories),
    )
    st.plotly_chart(fig, use_container_width=True)

    if window > 1:
        st.caption("已按視窗大小彙整後顯示主要敘事視角。")


def render_chapter_comparison(outputs: dict, sem_filtered: List[Dict]):
    st.subheader("章節比較")

    timeline_data = outputs.get("timeline") or []
    source_data = timeline_data if timeline_data else sem_filtered

    if not source_data:
        st.info("目前沒有足夠的時間線或章節資訊，無法進行章節比較。")
        return

    def order_key(item: Dict[str, Any]):
        for key in ("order", "index", "idx", "position", "sequence", "seq", "id", "time_idx"):
            val = item.get(key)
            if isinstance(val, (int, float)):
                return val
        return None

    ordered_items = sorted(
        enumerate(source_data),
        key=lambda pair: (order_key(pair[1]) if order_key(pair[1]) is not None else pair[0]),
    )

    records: List[Dict[str, Any]] = []
    has_explicit_chapter = False
    for pos, (_, item) in enumerate(ordered_items, start=1):
        chapter_label: Optional[str] = None
        chapter_index: Optional[int] = None

        # 嘗試從常見欄位取得章節資訊
        for field in ("chapter", "chapter_title"):
            val = item.get(field)
            if isinstance(val, str) and val.strip():
                chapter_label = val.strip()
                break
            if isinstance(val, (int, float)):
                chapter_index = int(val)
                chapter_label = f"第 {chapter_index} 章"
                break

        if chapter_index is None and isinstance(item.get("chapter_index"), (int, float)):
            chapter_index = int(item.get("chapter_index"))
            chapter_label = chapter_label or f"第 {chapter_index} 章"

        if chapter_label or chapter_index is not None:
            has_explicit_chapter = True

        emotion_label = item.get("emotion") or item.get("emotion_perspective")
        voice_val = item.get("voice") or item.get("emotion_perspective")

        records.append(
            {
                "position": pos,
                "chapter": chapter_label,
                "chapter_index": chapter_index,
                "speaker": item.get("speaker"),
                "emotion_label": emotion_label,
                "pov_group": voice_val,
                "low_confidence": bool(item.get("low_confidence")),
            }
        )

    if not records:
        st.info("目前沒有足夠的時間線或章節資訊，無法進行章節比較。")
        return

    # 若缺少章節欄位，以固定分段方式建立章節標籤。
    if not has_explicit_chapter:
        segment_size = max(1, math.ceil(len(records) / 10))
        for idx, rec in enumerate(records):
            segment = idx // segment_size + 1
            rec["chapter"] = f"第 {segment} 段"
            rec["chapter_index"] = segment

    df_events = pd.DataFrame(records)
    if df_events.empty:
        st.info("目前沒有足夠的時間線或章節資訊，無法進行章節比較。")
        return

    df_events["chapter"] = df_events["chapter"].fillna(method="ffill").fillna(method="bfill")
    if df_events["chapter"].isna().any():
        df_events["chapter"] = df_events["chapter"].fillna(
            df_events["position"].apply(lambda p: f"第 {p} 段")
        )

    chapter_order = {name: idx for idx, name in enumerate(df_events["chapter"].unique(), start=1)}
    df_events["chapter_index"] = df_events["chapter_index"].fillna(df_events["chapter"].map(chapter_order))
    df_events["chapter_index"] = df_events["chapter_index"].fillna(df_events["position"]).astype(int)

    df_events["pov_group"] = df_events["pov_group"].map(POV_GROUPS).fillna(
        df_events["pov_group"].fillna("其他")
    )
    df_events["emotion_category"] = df_events["emotion_label"].apply(categorize_emotion_label)

    available_speakers = sorted({s for s in df_events["speaker"] if s})
    speaker_filter = st.multiselect(
        "可選擇特定角色，只比較其參與的章節統計（可留空顯示全部）",
        options=available_speakers,
    )

    filtered_events = (
        df_events[df_events["speaker"].isin(speaker_filter)] if speaker_filter else df_events
    )

    if filtered_events.empty:
        st.info("目前可比較的章節數量不足，請放寬篩選條件或選擇其他書目。")
        return

    chapter_groups = filtered_events.groupby(["chapter", "chapter_index"], sort=False)
    chapter_rows: List[Dict[str, Any]] = []
    for (chapter_name, chapter_idx), grp in chapter_groups:
        event_count = len(grp)
        if event_count == 0:
            continue
        speaker_count = grp["speaker"].dropna().nunique()
        emotion_counts = grp["emotion_category"].value_counts()
        positive_ratio = float(emotion_counts.get("正向", 0) / event_count)
        negative_ratio = float(emotion_counts.get("負向", 0) / event_count)
        neutral_ratio = float(emotion_counts.get("中性", 0) / event_count)
        dominant_pov = grp["pov_group"].dropna().mode().iloc[0] if not grp["pov_group"].dropna().empty else "未知"

        chapter_rows.append(
            {
                "chapter_name": chapter_name,
                "chapter_index": chapter_idx,
                "event_count": event_count,
                "unique_speakers": speaker_count,
                "interaction_density": event_count,
                "positive_ratio": positive_ratio,
                "negative_ratio": negative_ratio,
                "neutral_ratio": neutral_ratio,
                "dominant_pov": dominant_pov,
            }
        )

    df_chapters = pd.DataFrame(chapter_rows).sort_values("chapter_index")

    if df_chapters.empty:
        st.info("目前可比較的章節數量不足，請放寬篩選條件或選擇其他書目。")
        return

    chapter_options = list(df_chapters["chapter_name"])
    default_selection = chapter_options[: min(3, len(chapter_options))]
    selected_chapters = st.multiselect(
        "選擇要比較的章節（最多 3 個）",
        options=chapter_options,
        default=default_selection,
        max_selections=3,
    )

    if not selected_chapters:
        selected_chapters = default_selection

    selected_df = df_chapters[df_chapters["chapter_name"].isin(selected_chapters)]

    if len(selected_df) < 2:
        st.info("目前可比較的章節數量不足，請放寬篩選條件或選擇其他書目。")
        return

    display_df = selected_df[
        [
            "chapter_name",
            "event_count",
            "unique_speakers",
            "interaction_density",
            "positive_ratio",
            "negative_ratio",
            "neutral_ratio",
            "dominant_pov",
        ]
    ].rename(
        columns={
            "chapter_name": "章節",
            "event_count": "事件數量",
            "unique_speakers": "不同角色數量",
            "interaction_density": "互動密度",
            "positive_ratio": "正向情緒比例",
            "negative_ratio": "負向情緒比例",
            "neutral_ratio": "中性情緒比例",
            "dominant_pov": "優勢視角",
        }
    )
    st.dataframe(display_df, width="stretch")

    event_fig = px.bar(
        selected_df,
        x="chapter_name",
        y="event_count",
        title="章節事件數量比較",
        labels={"chapter_name": "章節", "event_count": "事件數量"},
    )
    st.plotly_chart(event_fig, use_container_width=True)

    speaker_fig = px.bar(
        selected_df,
        x="chapter_name",
        y="unique_speakers",
        title="章節角色多樣性比較",
        labels={"chapter_name": "章節", "unique_speakers": "不同角色數量"},
    )
    st.plotly_chart(speaker_fig, use_container_width=True)

    emo_long = selected_df.melt(
        id_vars=["chapter_name"],
        value_vars=["positive_ratio", "negative_ratio", "neutral_ratio"],
        var_name="情緒類型",
        value_name="比例",
    )
    emo_long["情緒類型"] = emo_long["情緒類型"].map(
        {
            "positive_ratio": "正向",
            "negative_ratio": "負向",
            "neutral_ratio": "中性",
        }
    )
    emo_fig = px.bar(
        emo_long,
        x="chapter_name",
        y="比例",
        color="情緒類型",
        title="章節情緒比例比較",
        labels={"chapter_name": "章節"},
        barmode="stack",
    )
    st.plotly_chart(emo_fig, use_container_width=True)

    pov_counts = (
        filtered_events[filtered_events["chapter"].isin(selected_chapters)]
        .groupby(["chapter", "pov_group"])
        .size()
        .reset_index(name="count")
    )
    if not pov_counts.empty:
        pov_fig = px.bar(
            pov_counts,
            x="chapter",
            y="count",
            color="pov_group",
            title="章節視角分布",
            labels={"chapter": "章節", "count": "筆數", "pov_group": "視角"},
            barmode="stack",
        )
        st.plotly_chart(pov_fig, use_container_width=True)

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
    render_interaction_heatmap(sem_filtered)
    render_graphs(outputs, sem_filtered)
    render_story_emotion_arc(outputs, sem_filtered)
    render_pov_shift_map(outputs, sem_filtered)
    render_chapter_comparison(outputs, sem_filtered)
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
