from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.utils.validate_outputs import validate_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate DEUN output directory")
    parser.add_argument("output_dir", type=Path, help="Path to output directory (e.g., output/)")
    args = parser.parse_args()

    ok, issues, stats = validate_outputs(str(args.output_dir))

    print(json.dumps({"ok": ok, "stats": stats}, ensure_ascii=False, indent=2))
    if issues:
        print("Issues:")
        for msg in issues:
            print(f"- {msg}")


if __name__ == "__main__":
    main()
