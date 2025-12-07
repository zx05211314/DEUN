"""Streamlit page: DEUN 道具圖鑑."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="DEUN 道具圖鑑", layout="wide")
st.title("🧰 DEUN 道具圖鑑")
st.caption("檢視 output/items.json 產出的道具與能力資料")

ROOT = Path(__file__).resolve().parents[2]
data_path = ROOT / "output" / "items.json"

if not data_path.exists():
    st.error(f"找不到檔案：{data_path}\n請先執行 `python -Xutf8 -m modules.item` 生成 items.json。")
else:
    items = json.loads(data_path.read_text(encoding="utf-8"))
    df = pd.DataFrame(items)

    name_filter = st.text_input("名稱包含（留空顯示全部）", "")
    min_count = st.number_input("最少出現次數", min_value=0, value=0, step=1)

    filtered = df[df["count"] >= min_count]
    if name_filter:
        filtered = filtered[filtered["name"].str.contains(name_filter, case=False, na=False)]

    st.caption(f"顯示 {len(filtered)} / {len(df)} 筆")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
