from __future__ import annotations

import argparse
import shutil
from pathlib import Path

# 根目錄 = scripts 上一層
ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output"


def clean_book_output(book_name: str, *, recreate: bool = True) -> Path:
    """
    清空指定書名的輸出資料夾：
    - 刪除 output/<book_name> 整個資料夾
    - 視 recreate 參數決定是否重建空資料夾
    回傳該書的資料夾路徑（重建後）
    """
    book_dir = OUTPUT_DIR / book_name

    if book_dir.exists():
        shutil.rmtree(book_dir)

    if recreate:
        book_dir.mkdir(parents=True, exist_ok=True)

    print(f"[clean_output] 已清空輸出資料夾：{book_dir}")
    return book_dir


def clean_all_books() -> None:
    """
    一次清空 output/ 底下所有子資料夾（僅子資料夾，不刪掉 output/ 自己）。
    """
    if not OUTPUT_DIR.exists():
        print(f"[clean_output] 找不到 output 目錄：{OUTPUT_DIR}")
        return

    for sub in OUTPUT_DIR.iterdir():
        if sub.is_dir():
            shutil.rmtree(sub)
            print(f"[clean_output] 已刪除書目資料夾：{sub}")


def main() -> None:
    parser = argparse.ArgumentParser(description="清理小說分析輸出資料夾")
    parser.add_argument("--book-name", type=str, help="要清理的書名（對應 output/<book-name>）")
    parser.add_argument("--all-books", action="store_true", help="清空 output/ 底下所有書目的子資料夾")
    parser.add_argument("--no-recreate", action="store_true", help="只刪不重建資料夾（僅在 --book-name 模式有效）")
    args = parser.parse_args()

    if args.all_books:
        clean_all_books()
    elif args.book_name:
        clean_book_output(args.book_name, recreate=not args.no_recreate)
    else:
        parser.error("請指定 --book-name 或 --all-books 其一。")


if __name__ == "__main__":
    main()
