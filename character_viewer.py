"""Streamlit UI for viewing extracted character index (local-only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT_PATH = ROOT / "output" / "characters.json"


@st.cache_data(show_spinner=False)
def load_characters(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    # Flatten sample sentences for nicer display
    rows = []
    for row in data:
        rows.append(
            {
                "name": row.get("name", ""),
                "count": row.get("count", 0),
                "sample_sentences": "\n".join(row.get("sample_sentences", [])),
            }
        )
    return pd.DataFrame(rows, columns=["name", "count", "sample_sentences"])


def main() -> None:
    st.set_page_config(page_title="DEUN Character Viewer", layout="wide")
    st.title("DEUN 角色圖鑑")
    st.caption("檢視 output/characters.json 產出的角色資料")

    if not OUTPUT_PATH.exists():
        st.error(f"找不到檔案：{OUTPUT_PATH}\n請先執行 `python -Xutf8 -m modules.character` 生成角色資料。")
        return

    df = load_characters(OUTPUT_PATH)

    # Filters
    name_query = st.text_input("名稱包含（留空顯示全部）", value="").strip()
    min_count = st.number_input("最少出現次數", min_value=0, value=0, step=1)

    filtered = df
    if name_query:
        mask_name = filtered["name"].str.contains(name_query, case=False, na=False)
        filtered = filtered[mask_name]
    filtered = filtered[filtered["count"] >= min_count]

    st.write(f"顯示 {len(filtered)} / {len(df)} 筆")
    st.dataframe(filtered, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
