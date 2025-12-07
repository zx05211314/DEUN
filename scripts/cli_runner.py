"""CLI wrapper for running the pipeline with common flags."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run DEUN pipeline")
    parser.add_argument("--book-name", type=str, default=None, help="Output subdir name (for multi-book)")
    parser.add_argument("--limit-chapters", type=int, default=None, help="Limit chapters")
    parser.add_argument("--limit-sentences", type=int, default=None, help="Limit sentences per chapter")
    parser.add_argument("--skip-llm", action="store_true", help="Skip zero-shot steps")
    parser.add_argument("--skip-emotion-strength", action="store_true", help="Skip emotion strength step")
    parser.add_argument("--skip-zero-shot-task", action="store_true", help="Skip zero-shot task inference")
    parser.add_argument("--skip-zero-shot-action", action="store_true", help="Skip zero-shot action inference")
    parser.add_argument("--skip-zero-shot-emotion", action="store_true", help="Skip zero-shot emotion inference")
    parser.add_argument("--skip-zero-shot-emotion-strength", action="store_true", help="Skip zero-shot emotion strength")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    args = parser.parse_args()

    cmd = [
        sys.executable,
        "-m",
        "scripts.run_pipeline",
    ]
    if args.skip_llm:
        cmd.append("--skip-expensive")
    if args.skip_emotion_strength:
        cmd.append("--skip-emotion-strength")
    if args.skip_zero_shot_task:
        cmd.append("--skip-zero-shot-task")
    if args.skip_zero_shot_action:
        cmd.append("--skip-zero-shot-action")
    if args.skip_zero_shot_emotion:
        cmd.append("--skip-zero-shot-emotion")
    if args.skip_zero_shot_emotion_strength:
        cmd.append("--skip-zero-shot-emotion-strength")
    if args.limit_chapters is not None:
        cmd.extend(["--chapters", str(args.limit_chapters)])
    if args.limit_sentences is not None:
        cmd.extend(["--sentences", str(args.limit_sentences)])
    if args.book_name:
        cmd.extend(["--book-name", args.book_name])
    if args.output_dir:
        cmd.extend(["--output-dir", args.output_dir])

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
