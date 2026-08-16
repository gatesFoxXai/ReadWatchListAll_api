# OneAPI 專案修復計劃

## 目標
1. 針對 `YuantaAPI_Pythonnet.py`、`sim_run.py`、`web_dashboard.py`、`cStocks.py` 進行問題排查與修復。
2. 保持最小改動、避免盲修、明確區分現貨／期貨／ETF／權證／基金邏輯。
3. 確保 CSV 內價量單位一致，並保留股級資料、僅在呈現時轉換成張。

## 核心原則
- 全程使用繁體中文。
- 先產出：
  - 影響力評估（Impact Analysis）
  - 潛在風險預測（Regression Risk）
  - 最小介入策略（Minimal Intervention）
- 若任何需求不清楚，先問再改。
- 修復後建議同步更新 `AGENTS.md`、`CHANGELOG.md` 或 `README.md`。

## 任務流程
1. 讀取 `AGENTS.md`、`PRD.md`、`SPEC.md`、`README.md`，確認專案要求與現有標準。
2. 定位問題範圍：先排查 `YuantaAPI_Pythonnet.py` 的訂閱、CSV 持久化、日總結與盤後覆蓋邏輯。
3. 檢查 `web_dashboard.py` 的資料讀取、SSE 更新與價格/成交量顯示邏輯。
4. 檢視 `cStocks.py` 中的 1 分 K / 日 K 切換與繪圖資料來源，避免與 API 端邏輯混淆。
5. 若可拆分，規劃子代理：
   - `api` 子代理：API / CSV / snapshot / stock_ref
   - `dashboard` 子代理：SSE /前端顯示 / PE/PB/PEG / watchlist
   - `csv` 子代理：資料分割、去重、日總結、1min 重採樣
6. 形成驗證清單：
   - `python run.py` 開盤日啟動
   - `python sim_run.py` 模擬日驗證
   - 檢查 CSV 是否以股為單位、`@stockID.csv` 日總結是否寫入、`stock_ref.json` 是否正確

## 驗證重點
- 盤中實際成交總量應該來自累積 `in + out`，盤後才使用 `actual_vol` 覆蓋。
- PE 顯示要區分有/無 `forward_eps` 的股票。
- 新增股票時應自動建立 `fundamentals.json` 佔位資料。
- 期貨邏輯與現貨邏輯要拆開，以避免帳號與避險計算錯亂。

## 建議使用示例
- `使用 yuanta-oneapi agent 來排查 YuantaAPI_Pythonnet.py 的 CSV 和盤後日總結問題。`
- `需要修正 web_dashboard.py 的成交量顯示，並保持最小改動。`
- `請先分析 cStocks.py 的 1 分 K/日 K 切換邏輯，列出影響範圍和風險。`
