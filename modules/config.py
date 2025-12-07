"""Centralized configuration for paths and defaults."""

NOVEL_PATH = "小說資料/輪迴樂園.txt"

# Limits for quick runs; set to None for full run
MAX_CHAPTERS = 3
MAX_SENTENCES = 300

HF_MODEL_NAME = "ckiplab/bert-base-chinese-ner"
# Zero-shot NLI model for mission inference
HF_NLI_MODEL = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"

# Verbose logging toggle
VERBOSE = True

# Optional log file path (None = stdout only)
LOG_PATH = None
