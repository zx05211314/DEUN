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

## 測試
- 重構後確認 `python -m compileall app` 通過，確保匯入路徑與語法無誤。
