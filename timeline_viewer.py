"""Streamlit UI for viewing extracted timeline events (local-only)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Ensure imports work when running via `streamlit run timeline_viewer.py`.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.parser import parse_novel  # type: ignore
from modules.timeline import extract_events  # type: ignore

TXT_PATH = ROOT / "小說資料" / "輪迴樂園.txt"


@st.cache_data(show_spinner=False)
def load_events(
    txt_path: Path,
    max_chapters: int = 3,
    max_sentences: int = 200,
    limit: int = 100,
) -> pd.DataFrame:
    chapters = parse_novel(str(txt_path))
    limited: dict[str, list[str]] = {}
    for idx, (title, sentences) in enumerate(chapters.items()):
        if idx >= max_chapters:
            break
        limited[title] = sentences[:max_sentences]

    events = extract_events(limited)[:limit]
    df = pd.DataFrame(events, columns=["chapter", "time", "character", "location", "event", "sentence"])
    return df


def main() -> None:
    st.set_page_config(page_title="DEUN Timeline Viewer", layout="wide")
    st.title("DEUN Timeline Viewer")
    st.caption("展示從小說萃取的事件時間軸（本地測試）")

    if not TXT_PATH.exists():
        st.error(f"找不到測試檔案：{TXT_PATH}")
        return

    df = load_events(TXT_PATH)

    # Filters
    time_query = st.text_input("時間詞篩選（模糊匹配，留空顯示全部）", value="").strip()
    chapter_options = ["全部"] + list(dict.fromkeys(df["chapter"].tolist()))
    selected_chapter = st.selectbox("章節", options=chapter_options, index=0)

    filtered = df
    if selected_chapter != "全部":
        filtered = filtered[filtered["chapter"] == selected_chapter]
    if time_query:
        mask_time = filtered["time"].str.contains(time_query, case=False, na=False)
        mask_event = filtered["event"].str.contains(time_query, case=False, na=False)
        filtered = filtered[mask_time | mask_event]

    st.write(f"顯示 {len(filtered)} / {len(df)} 筆（前 {len(df)} 筆已載入）")
    st.dataframe(filtered[["chapter", "time", "character", "location", "event"]], hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
