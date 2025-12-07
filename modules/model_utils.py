"""Model loading utilities with simple caching."""

from __future__ import annotations

from typing import Any

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

from modules.config import HF_MODEL_NAME, VERBOSE

_cached_ner: Any = None


def get_ner_pipeline(model_name: str | None = None):
    """Load and cache HF NER pipeline; return None on failure."""
    global _cached_ner
    if _cached_ner is not None:
        return _cached_ner
    try:
        device = 0 if torch.cuda.is_available() else -1
        _cached_ner = pipeline(
            "ner",
            model=AutoModelForTokenClassification.from_pretrained(model_name or HF_MODEL_NAME),
            tokenizer=AutoTokenizer.from_pretrained(model_name or HF_MODEL_NAME),
            aggregation_strategy="simple",
            device=device,
        )
        return _cached_ner
    except Exception as e:  # noqa: BLE001
        if VERBOSE:
            print(f"[NER] pipeline loading failed, fallback to rule-based: {e}")
        _cached_ner = None
        return None
