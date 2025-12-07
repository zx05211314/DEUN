"""Zero-shot mission classification using multilingual NLI models."""

from __future__ import annotations

from typing import List, Tuple

from modules.config import HF_NLI_MODEL, VERBOSE

try:
    from transformers import pipeline
except Exception:  # noqa: BLE001
    pipeline = None  # type: ignore

# 任務類別
DEFAULT_LABELS = ["擊殺", "逃亡", "探索", "談判", "支援", "控制", "守衛", "拯救", "未知"]

_clf = None


def load_zero_shot_classifier(model_name: str = HF_NLI_MODEL):
    """Load and cache zero-shot-classification pipeline."""
    global _clf
    if _clf is not None:
        return _clf
    if pipeline is None:
        if VERBOSE:
            print("[mission_inference] transformers not available.")
        return None
    try:
        _clf = pipeline("zero-shot-classification", model=model_name)
    except Exception as e:  # noqa: BLE001
        if VERBOSE:
            print(f"[mission_inference] failed to load model {model_name}: {e}")
        _clf = None
    return _clf


def infer_mission(sentence: str, labels: List[str] | None = None, model_name: str = HF_NLI_MODEL) -> Tuple[str, float]:
    """Return (mission_label, confidence)."""
    if not sentence.strip():
        return "未知", 0.0
    labels = labels or DEFAULT_LABELS
    clf = load_zero_shot_classifier(model_name=model_name)
    if clf is None:
        return "未知", 0.0
    try:
        result = clf(sentence, labels)
        if not result or not result.get("labels"):
            return "未知", 0.0
        label = result["labels"][0]
        score = float(result["scores"][0])
        return label, score
    except Exception as e:  # noqa: BLE001
        if VERBOSE:
            print(f"[mission_inference] inference failed: {e}")
        return "未知", 0.0


def __main__():  # noqa: D401 - entrypoint
    sample = "他拔刀衝向敵人，試圖一刀斬下。"
    label, score = infer_mission(sample)
    print(f"sample: {sample}\nmission: {label} ({score:.2f})")


if __name__ == "__main__":
    __main__()
