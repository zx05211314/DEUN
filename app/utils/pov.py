from __future__ import annotations

from typing import Any, Optional

POV_GROUPS = {
    "第一人稱": "第一人稱",
    "我": "第一人稱",
    "我方": "第一人稱",
    "第三人稱": "第三人稱",
    "他": "第三人稱",
    "她": "第三人稱",
    "他們": "第三人稱",
    "她們": "第三人稱",
    "第三人稱全知": "第三人稱全知",
    "全知視角": "第三人稱全知",
    "全知": "第三人稱全知",
}


def map_pov_group(value: Optional[Any]) -> str:
    return POV_GROUPS.get(value, value or "其他")
