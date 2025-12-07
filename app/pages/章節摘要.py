import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "output"


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def ensure_output_root():
    OUTPUT_ROOT.mkdir(exist_ok=True)
    books = []
    for p in OUTPUT_ROOT.iterdir():
        if p.is_dir() and (p / "storyline_summary.json").exists():
            books.append(p.name)
    return sorted(books) or ["."]


st.set_page_config(page_title="章節摘要", layout="wide")
st.sidebar.title("小說章節摘要")

books = ensure_output_root()
selected_book = st.sidebar.selectbox("選擇輸出目錄", books)
base_dir = OUTPUT_ROOT / selected_book
summary_path = base_dir / "storyline_summary.json"

summary = load_json(summary_path)
if not summary:
    st.error(f"找不到 {summary_path}，請先執行 storyline_summary")
    st.stop()

df = pd.DataFrame(list(summary.items()), columns=["章節", "摘要"])
st.subheader("章節簡要摘要")
st.dataframe(df, hide_index=True)

csv = df.to_csv(index=False, encoding="utf-8")
st.download_button("下載摘要 CSV", csv, file_name="storyline_summary.csv", mime="text/csv")
