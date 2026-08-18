# AGENTS.md — 待辦工作清單

> 本檔案記錄 Agent 可能接下來要做的工作，依優先級排序。
> 完成一項就勾掉，新增工作加到對應區塊。

## 🔴 高優先（影響正確性）

- [ ] **填入 15 檔近 5 年真實 PE/PBR 區間**
  - 檔案：`valuation_config.json`
  - 目前 `pe_history.min/median/max` 和 `pb_history.min/median/max` 是佔位值（=當前值）
  - 需用戶提供或從歷史數據計算
  - 影響：5 檔價位帶的正確性

- [ ] **補 7 檔 forward_eps / eps_growth_pct**
  - 缺：9907, 6770, 4958, 2337, 4536, 4967, 1522
  - 檔案：`analyst_eps.json` + `fundamentals.json`
  - 影響：PEG 無法計算、成長型估值可能 fallback 到 TTM

- [ ] **下個交易日驗證**
  - `stock_ref.json` 是否拿到真實 API 漲跌停價（up_price ≠ HighPrice）
  - `@*.csv` 是否為真實收盤數據（非模擬器）
  - Dashboard 漲跌停價 + 估值帶 + 技術面顯示正確
  - `technical.py` 量比/大戶判定在真實數據下是否合理

## 🟡 中優先（功能完整性）

- [ ] **技術面整合進 web_dashboard.py**
  - 每張股票卡顯示：MA5/20 位置、MACD 狀態、KDJ、量比、支撐/壓力
  - 讀取 `technical.json`（1hr cache，同 valuation 模式）
  - 目前 `technical.py` 已可獨立產出，但 dashboard 尚未讀取

- [ ] **分K（1分鐘）技術面**
  - 資料來源：`1min/{code}_1min.csv`（由 `resample_1min.py` 從 5 秒 CSV 產生）
  - 用途：盤中卡位、預估量、短線進出場
  - 先確認日K穩定後再動態加入
  - 可能需要在 `technical.py` 加 `--period 1min` 參數

- [ ] **預估量獨立模組**
  - 目前散落在 `YuantaAPI_Pythonnet.py` 的 `_update_estimates()`
  - cStocks README 有完整公式（時間倍數法）
  - 可獨立成 `estimate_volume.py` 供 dashboard + cStocks 共用

- [ ] **EPS 年份選擇邏輯**
  - 目前 `get_consensus_eps()` 優先序可能選到當年 EPS 而非明年
  - 用戶框架：上半年用當年、下半年（7月起）用明年
  - 需加日期判斷或讓 config 明確指定

## 🟢 低優先（改善/研究）

- [ ] **Notebook 研究選股法**
  - 近 5 年 EPS 軌跡視覺化（加速/放緩/轉折）
  - 同業 PE/PBR 對照散佈圖
  - 季 EPS 實際 vs 法人預估偏離度
  - 聯準會利率週期與估值帶關聯
  - 日K趨勢 + 分K進場訊號的組合策略

- [ ] **`all_estimates` 填入實際季 EPS**
  - 目前 15 檔全部為 `[]`
  - 格式：`[{quarter, eps, source}]`
  - 用途：給前瞻指標一個「實際錨點」

- [ ] **資料新鮮度檢查**
  - `fundamentals.json` / `analyst_eps.json` 超過 N 天未更新 → warning
  - 可在 `run.py` 盤前檢查中加入

- [ ] **修 `requirements.txt`**
  - 移除無效的 `mplfonts>=2.4.2`
  - 確認所有相依套件版本正確

- [ ] **cStocks.py 未實現項目**（見 cStocks/README.md）
  - 自訂文字框（指定日期旁加備註）
  - X 軸標籤重疊優化
  - 1 分 K 切換資料來源

## 📋 工作流提醒

- 修改程式碼後：`pre-commit run --all-files` → 全過 → `git add -A && git commit`
- 估值相關改動：改 `valuation_config.json` → 重跑 `python valuation.py` → 驗證 `valuation.json`
- 技術面改動：改 `technical.py` → 重跑 `python technical.py` → 驗證 `technical.json`
- Dashboard 改動：改 `web_dashboard.py` → 重啟 `python web_dashboard.py` → 瀏覽器驗證
- 所有 JSON 輸出檔不要手動編輯（會被程式覆蓋），改設定檔（`*_config.json`）
