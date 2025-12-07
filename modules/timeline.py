"""Timeline extraction with NER, rule fallbacks, and user knowledge support."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

from modules.config import MAX_CHAPTERS, MAX_SENTENCES, NOVEL_PATH, VERBOSE
from modules.constants.zh_tokens import (
    CHAPTER_PATTERN,
    CHARACTER_WHITELIST,
    LOCATION_LEXICON,
    LOCATION_STOPWORDS,
    PREPOSITION_PATTERNS,
    TIME_PATTERNS,
    TIME_STOPWORDS,
)
from modules.model_utils import get_ner_pipeline
from modules.user_knowledge import as_sets, load_blacklist, load_whitelist

# Optional backends
try:
    from LAC import LAC  # type: ignore
except Exception:  # noqa: BLE001
    LAC = None  # type: ignore

try:
    import spacy
except Exception:  # noqa: BLE001
    spacy = None  # type: ignore

UNK = "未知"
TIME_REGEX = re.compile("|".join(f"({p})" for p in TIME_PATTERNS))
CHAR_STOP = set(TIME_STOPWORDS)
LOC_STOP = set(LOCATION_STOPWORDS)

_hf_pipeline = None
_lac = None
_spacy_nlp = None


def _load_hf_pipeline():
    global _hf_pipeline
    if _hf_pipeline is None:
        _hf_pipeline = get_ner_pipeline()
    return _hf_pipeline


def _load_lac():
    global _lac
    if _lac is None and LAC:
        try:
            _lac = LAC(mode="lac")
        except Exception:  # noqa: BLE001
            _lac = None
    return _lac


def _load_spacy():
    global _spacy_nlp
    if _spacy_nlp is None and spacy:
        try:
            _spacy_nlp = spacy.load("zh_core_web_trf")
        except Exception:  # noqa: BLE001
            _spacy_nlp = None
    return _spacy_nlp


# --- NER helpers ---
def _ner_entities(sentence: str) -> Tuple[List[str], List[str]]:
    persons: List[str] = []
    locations: List[str] = []

    hf_pipe = _load_hf_pipeline()
    if hf_pipe:
        try:
            ents = hf_pipe(sentence)
            for ent in ents:
                label = ent.get("entity_group") or ent.get("entity") or ""
                word = ent.get("word") or ""
                if not word:
                    continue
                if "PER" in label:
                    persons.append(word)
                elif "LOC" in label:
                    locations.append(word)
            persons = list(dict.fromkeys(persons))
            locations = list(dict.fromkeys(locations))
        except Exception:  # noqa: BLE001
            pass

    if not persons or not locations:
        lac = _load_lac()
        if lac:
            try:
                words, tags = lac.run(sentence)
                for w, t in zip(words, tags):
                    if t == "PER" and w not in persons:
                        persons.append(w)
                    if t == "LOC" and w not in locations:
                        locations.append(w)
            except Exception:  # noqa: BLE001
                pass
    return persons, locations


def _filter_names(cands: Sequence[str], stop: set[str], max_len: int = 4) -> List[str]:
    filtered: List[str] = []
    for c in cands:
        c = _clean_field(c)
        if not c or c in stop:
            continue
        if not re.fullmatch(r"[一-龥]{1,%d}" % max_len, c):
            continue
        filtered.append(c)
    return list(dict.fromkeys(filtered))


def _extract_time(sentence: str) -> str:
    m = TIME_REGEX.search(sentence)
    if not m:
        return UNK
    val = m.group(0)
    if val in TIME_STOPWORDS:
        return UNK
    return val


def _extract_character(sentence: str, ner_persons: Sequence[str], wl_chars: set[str]) -> str:
    for name in list(wl_chars) + list(CHARACTER_WHITELIST):
        if name and name in sentence:
            return name
    filtered = _filter_names(ner_persons, CHAR_STOP)
    return filtered[0] if filtered else ""


def _extract_location(sentence: str, ner_locs: Sequence[str]) -> str:
    for loc in _filter_names(ner_locs, LOC_STOP, max_len=6):
        if loc and loc not in LOC_STOP:
            return loc
    for pat in PREPOSITION_PATTERNS:
        m = re.search(pat, sentence)
        if m:
            cand = m.group(1)
            if cand and cand not in LOC_STOP:
                return cand
    for cand in LOCATION_LEXICON:
        if cand in sentence and cand not in LOC_STOP:
            return cand
    m = re.search(r"([一-龥]{2,6})", sentence)
    loc = m.group(1) if m else ""
    return "" if loc in LOC_STOP else loc


def _extract_predicate(sentence: str) -> str:
    nlp = _load_spacy()
    if nlp:
        try:
            doc = nlp(sentence)
            root = next((t for t in doc if t.dep_ == "ROOT"), None)
            if root:
                subj = next((c for c in root.children if c.dep_ in {"nsubj", "nsubjpass"}), None)
                obj = next((c for c in root.children if c.dep_ in {"dobj", "obj"}), None)
                parts = [subj.text if subj else "", root.text, obj.text if obj else ""]
                pred = "".join(p for p in parts if p)
                if pred:
                    return pred
        except Exception:  # noqa: BLE001
            pass
    m = re.search(r"[一-龥]{1,8}(?:了|着|過)?[一-龥]{0,20}", sentence)
    return (m.group(0) if m else sentence).strip()


def _clean_field(text: Optional[str]) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


# --- Public APIs ---
def extract_events(chapter_sentences: Dict[str, List[str]]) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    for chapter, sentences in chapter_sentences.items():
        for sentence in sentences:
            if not sentence.strip():
                continue
            time_expr = _extract_time(sentence)
            persons, locs = _ner_entities(sentence)
            character = _extract_character(sentence, persons, set())
            location = _extract_location(sentence, locs)
            event_summary = _extract_predicate(sentence)
            events.append(
                {
                    "chapter": chapter,
                    "time": _clean_field(time_expr),
                    "character": _clean_field(character),
                    "location": _clean_field(location),
                    "event": _clean_field(event_summary),
                    "sentence": sentence.strip(),
                }
            )
    return events


def extract_events_ner(chapter_sentences: Dict[str, List[str]]) -> List[Dict[str, str]]:
    wl = as_sets(load_whitelist())
    bl = as_sets(load_blacklist())
    wl_time = wl.get("time", set())
    bl_time = bl.get("time", set())
    wl_chars = wl.get("characters", set())

    events: List[Dict[str, str]] = []
    for chapter, sentences in chapter_sentences.items():
        for sentence in sentences:
            if not sentence.strip():
                continue

            # time handling with black/white list
            if any(bt for bt in bl_time if bt in sentence):
                time_expr = UNK
            else:
                time_expr = _extract_time(sentence)
                for wt in wl_time:
                    if wt and wt in sentence:
                        time_expr = wt
                        break

            persons, locs = _ner_entities(sentence)
            character = _extract_character(sentence, persons, wl_chars)
            location = _extract_location(sentence, locs)
            event_summary = _extract_predicate(sentence)
            events.append(
                {
                    "chapter": chapter,
                    "time": _clean_field(time_expr),
                    "character": _clean_field(character),
                    "location": _clean_field(location),
                    "event": _clean_field(event_summary),
                    "sentence": sentence.strip(),
                }
            )
    return events


def build_timeline(
    novel_path: str = NOVEL_PATH,
    limit_chapters: Optional[int] = MAX_CHAPTERS,
    limit_sentences: Optional[int] = MAX_SENTENCES,
) -> List[Dict[str, str]]:
    from modules.parser import parse_novel

    chapters = parse_novel(novel_path)
    limited: Dict[str, List[str]] = {}
    for idx, (k, v) in enumerate(chapters.items()):
        if limit_chapters is not None and idx >= limit_chapters:
            break
        limited[k] = v if limit_sentences is None else v[:limit_sentences]
    return extract_events_ner(limited)


if __name__ == "__main__":
    timeline = build_timeline(novel_path=NOVEL_PATH, limit_chapters=MAX_CHAPTERS, limit_sentences=MAX_SENTENCES)
    if VERBOSE:
        print(timeline[:5])
