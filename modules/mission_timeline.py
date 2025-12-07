"""
Build a simple mission timeline from semantic_relations.json.

Output fields:
[
  {"chapter": "...", "time": "...", "character": "...", "mission": "...", "sentence": "..."}
]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict


def extract_mission_timeline(semantic_path: Path, output_path: Path) -> List[Dict[str, str]]:
    if not semantic_path.exists():
        return []
    try:
        data = json.loads(semantic_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    timeline: List[Dict[str, str]] = []
    for row in data:
        mission = row.get("mission_type") or ""
        if not mission or mission == "未知":
            continue
        timeline.append(
            {
                "chapter": row.get("chapter") or "",
                "time": row.get("time") or "",
                "character": row.get("character") or row.get("subject") or "",
                "mission": mission,
                "sentence": row.get("sentence") or "",
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    return timeline


if __name__ == "__main__":
    root = Path("output")
    sem_path = root / "semantic_relations.json"
    out_path = root / "mission_timeline.json"
    tl = extract_mission_timeline(sem_path, out_path)
    print(f"[mission_timeline] saved {len(tl)} rows -> {out_path}")
