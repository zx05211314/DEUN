# DEUN Concept & Architecture (Logic Only)

Goal: capture how the planned system ingests novels (local `.txt`/`.epub` or web sources), extracts timeline/characters/items/relations, stores structured results (SQLite first, optional Neo4j), and presents them via a desktop UI. No coding yet—only logic and design notes.

## Layered Modules (clear separation of concerns)
- Data acquisition (crawler/ingester): load local files; crawl supported fiction sites; output raw plain text per chapter/volume.
- Preprocessing: clean line breaks, split chapters/paragraphs/sentences, traditional/simplified conversion; optional tokenization/POS tagging via `jieba`/`HanLP`.
- NLP extraction core:
  - Timeline event extractor: when/where/what; normalize time (JioNLP/Time-NLP), detect locations; summarize events per chapter; maintain sequence if absolute time is missing.
  - Character extractor: detect names (NER), merge aliases, gather personality/ability descriptors, compute co-occurrence stats for prominence and relations.
  - Special nouns/items: detect weapons/skills/pills/beasts/plants via POS tags (`nz`, `nw`), custom dictionaries, and context rules; capture attributes/levels/effects.
  - Relation & sentiment: co-occurrence graph + sentiment/relationship classifier (BERT-style if available) to infer friend/foe/mentor, etc.
  - Summarization & motivation hints: chapter/event summaries; LLM-assisted reasoning for hidden motives (local LLMs like ChatGLM if offline).
- Storage: SQLite as primary (embedded, simple deploy). Optional Neo4j for richer graph queries. Raw text stored as files; DB keeps paths/offsets.
- Application UI: desktop (Electron or PyQt) with timeline view, tables, filters, and detail panes; export to CSV/JSON/Markdown.

## Processing Flow (happy path)
1) Ingest source → dedupe/clean → persist raw text + metadata (title, author, chapter order).
2) Preprocess → sentence/paragraph/chapter segmentation → traditional/simplified normalization → tokenization/POS/NER (if using HanLP/`jieba`+dicts).
3) Timeline pass → extract time expressions, normalize/sequence → detect locations → summarize events per segment (dependency parse or key-sentence extraction).
4) Character pass → collect names (NER/POS `nr`) → alias merging → pull nearby descriptive spans for personality/abilities → co-occurrence stats → optional relation classifier.
5) Item/special-term pass → candidate nouns via POS/custom dict → context rules or classifier to label type (weapon/skill/pill/creature/plant) → extract attributes (pattern-based on `：`, `【】`, brackets, numbers).
6) Persist structured results to SQLite tables; keep chapter offsets for context lookup.
7) UI/query layer reads DB → timeline visualization (zoom/filter), tables with column filters, detail pop-ups linking back to source text; exports.

## Data Model (SQLite first)
- `chapters(chapter_id, title, order_idx, file_path, offset_start, offset_end, summary)`
- `events(event_id, chapter_id, time_norm, time_text, location, description, characters_json)` — `time_norm` sortable; use chapter order if absolute time absent.
- `characters(char_id, name, aliases_json, personality, abilities, relations_json)` — relations can move to a join table if needed.
- `relations(relation_id, char_a, char_b, type, sentiment, evidence_ref)` — optional normalized table.
- `items(item_id, name, type, description, attributes_json, owner_char_id, first_seen_event_id)`
- `meta(key, value)` — config, versioning, source info.

## Tooling Options
- Tokenization/POS/NER: HanLP 2.x (multi-task), or `jieba` (+ custom dicts for domain terms).
- Time/Location parsing: JioNLP or Time-NLP for normalization; JioNLP location parser for province/city/district standardization.
- Summaries/relations/motives: LLMs (GPT-family via API; or local ChatGLM/FastChat). Use chunked prompts per chapter; merge.
- Search/index (optional): lightweight inverted index or Elasticsearch if full-text search is needed in UI.

## UI Ideas (desktop)
- Timeline: vertical or horizontal axis; zoom by chapter range or normalized time; click to reveal event details and source snippet.
- Tables: filterable grids for events (time/location/people), characters (personality/abilities/relations), items (type/attributes/owner).
- Relation view: simple list in v1; graph view later (Neo4j or client-side graph lib).
- Exports: CSV/JSON for tables; Markdown/plain-text for summaries; ensure easy copy/paste.

## Open Questions / Assumptions
- Target fiction sites and anti-scraping constraints?
- Accepted input formats beyond `.txt/.epub` (e.g., `.mobi`/`.pdf`)?
- Required offline-only mode vs. API use allowed?
- Precision vs. recall priorities for NER/relations (tuning thresholds)?
- Language variant: default to simplified internally; preserve original for display?

## Near-Term Validation Steps (no coding yet)
- Fix scope: pick first novel/corpus for a pilot and list target sites for crawling.
- Choose baseline NLP stack (HanLP vs. `jieba`+addons) and time parser (JioNLP/Time-NLP).
- Lock initial DB schema (tables above) and required exports (CSV/JSON/Markdown).
- Sketch UI wireframes for timeline/table interactions and detail drill-down.
- Define evaluation criteria: timeline coverage, character recall, item precision, relation accuracy, summary readability.
