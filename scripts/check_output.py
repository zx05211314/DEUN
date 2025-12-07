"""Quick output completeness checker."""

import argparse
from pathlib import Path


REQUIRED = [
    "items.json",
    "relations.json",
    "semantic_relations.json",
    "timeline.json",
]

OPTIONAL_WARN = ["speaker_summary.json"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-name", required=True, help="Book/output subdir name")
    args = parser.parse_args()

    base = Path("output") / args.book_name
    missing = []
    warn = []
    for fname in REQUIRED:
        if not (base / fname).exists():
            missing.append(fname)
    for fname in OPTIONAL_WARN:
        if not (base / fname).exists():
            warn.append(fname)

    if missing:
        print(f"[ERROR] 缺少必要檔案：{', '.join(missing)} 於 {base}")
        exit(1)
    if warn:
        print(f"[WARN] 以下檔案未找到（可選）：{', '.join(warn)}")
    print(f"[OK] {args.book_name} 輸出檢查完成，必需檔案齊全。")
    exit(0)


if __name__ == "__main__":
    main()
