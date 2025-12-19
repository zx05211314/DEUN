# 語意圖譜模組化架構（無行為變更）

本次重構將原本集中於 `app/pages/語意圖譜.py` 的邏輯拆分為明確模組，僅調整檔案位置與匯入路徑，未修改任何功能或 UI 文案。

## 模組對照表（舊位置 → 新模組）

| 功能 | 原始位置 | 新位置 |
| --- | --- | --- |
| 載入輸出檔 (`load_outputs`, `load_json`) | `app/pages/語意圖譜.py` | `app/utils/data_loaders.py` |
| 語意過濾 (`apply_semantic_filters`) | `app/pages/語意圖譜.py` | `app/utils/filters.py` |
| 情緒分數／分類 | `app/pages/語意圖譜.py` | `app/utils/emotion.py` |
| 視角分組 | `app/pages/語意圖譜.py` | `app/utils/pov.py` |
| 互動參與者擷取與配對計算 | `app/pages/語意圖譜.py` | `app/utils/interaction.py` |
| 章節事件整理與統計 | `app/pages/語意圖譜.py` | `app/utils/chapter_metrics.py` |
| 分析摘要區塊 | `app/pages/語意圖譜.py` | `app/components/metadata_view.py` |
| 情緒／視角統計卡片 | `app/pages/語意圖譜.py` | `app/components/semantic_overview.py` |
| 詳細資訊卡／語意表格 | `app/pages/語意圖譜.py` | `app/components/semantic_tables.py` |
| 時間線視圖 | `app/pages/語意圖譜.py` | `app/components/timeline_view.py` |
| 圖譜視圖 | `app/pages/語意圖譜.py` | `app/components/semantic_graphs.py` |
| 角色比較 | `app/pages/語意圖譜.py` | `app/components/role_comparison_view.py` |
| 互動熱度矩陣 | `app/pages/語意圖譜.py` | `app/components/interaction_heatmap_view.py` |
| 故事情緒曲線 | `app/pages/語意圖譜.py` | `app/components/story_emotion_arc_view.py` |
| 敘事視角變化圖 | `app/pages/語意圖譜.py` | `app/components/pov_shift_view.py` |
| 章節比較儀表板 | `app/pages/語意圖譜.py` | `app/components/chapter_comparison_view.py` |
| 資料下載 | `app/pages/語意圖譜.py` | `app/components/downloads_view.py` |
| 語者摘要 | `app/pages/語意圖譜.py` | `app/components/speaker_summary_view.py` |

## 主要檔案職責
- `app/pages/語意圖譜.py`：負責側邊欄、分析觸發、資料載入、套用過濾條件，以及串接各渲染模組（膠水層）。
- `app/utils/*`：純計算與資料準備，不含 Streamlit UI。
- `app/components/*`：各分析視圖與 UI 區塊（含圖表、表格、下載）。

## Analytics contract
- 互動計數僅允許透過 `app/utils/interaction.count_interactions` 執行，所有視圖使用同一組計數模式與互動單位推導（event_id/sentence_id → 章節+序號 → 內容雜湊），並共用信心分數與門檻過濾邏輯。
- 輸出驗證由 `app/utils/validate_outputs.validate_outputs` 處理，並針對語意資料呼叫 `validate_interaction_records` 收集警告而不終止流程。
- UI 層不得重新實作計數或解析邏輯，僅消費 utils 的結果並渲染圖表/表格。

### Interaction confidence contract
- 信心分數計算與配對均在 `app/utils/interaction.py` 內集中管理，採用穩定的 unit_id、角色正規化與原因列表，並以 `InteractionUnitRecord` 表示（含 raw/final confidence、bucket、reasons）。
- 所有互動統計需遵守：信心分數落在 [0, 1]、提高 `min_confidence` 不得增加計數、binary 模式結果不得超過 occurrence 模式、drop 項目都附帶 drop_reason 以利診斷。
- Heatmap 僅接受 `sem_filtered` 與上述集中計數結果，可透過信心門檻、bucket 分布、drop 摘要與 pair 來源事件診斷確認計算過程。

### Entity canonicalization contract
- 實體名稱（speaker/角色等）在 `load_outputs` 邊界經由 `app/utils/entity_registry.py` 的 `EntityRegistry` 做決定式正規化，再交給 analytics；analytics 模組本身不做名稱猜測或比對。
- 註冊檔缺失時以身分函式 fallback，並在 UI 顯示警示；canonicalize 需為冪等、排序穩定（`canonical_pair`）。
- `app/utils/consistency_checks.py` 提供跨模組實體集合檢查，協助偵測缺漏、封鎖命中與未註冊名稱，結果於主頁診斷面板呈現。

### Semantic traceability contract
- 互動追蹤資料以 `app/utils/semantic_trace.py` 的 `SemanticTraceRecord` 表示，並透過 `TraceIndex`（`app/utils/trace_index.py`）集中索引、提供 bucket/捨棄摘要與 pair 級樣本。
- 追蹤僅為觀察用途，計數與信心分數維持 Phase 1/2 行為；當 UI 啟用解釋面板時才使用追蹤索引，不影響既有統計。
- 追蹤 ID、pair 索引與信心 bucket 均為決定式；提高 `min_confidence` 僅會縮減（不會增加）保留追蹤。可於 `scripts/selfcheck_interaction.py` 驗證冪等性與界限條件。

## 測試
- 重構後確認 `python -m compileall app` 通過，確保匯入路徑與語法無誤。
