# 股票數據管理系統（OneAP_Python）

## 現況（2026-08-18）

### 系統架構（現行）

```
YuantaOneAPI.dll (元大 API)
    │ pythonnet
    ▼
YuantaAPI_Pythonnet.py   ← 即時報價訂閱 + 5秒 CSV + 預估量 + 快照
    ├── {code}.csv            5秒 OHLCV
    ├── @{code}.csv          日總結（日K主來源）
    ├── snapshot/{code}.json  Dashboard 0.5s 快照
    └── stock_ref.json        漲跌停價（API 權威值）

web_dashboard.py          ← Flask + SSE 即時面板 (port 5000)
    顯示: 價格/漲跌停/PE/PB/PEG/主力散戶/估值帶(5檔)

run.py                    ← 每日啟動器（API + Dashboard + 盤前檢查）
sim_run.py                ← 非交易日模擬器
```

### 估值框架（個人投資方法，2026-08-18 實作）

**核心原則：**
- 前瞻指標是「假設」不是「事實」→ 用實際季 EPS 軌跡驗證
- 倍數以「自己近 5 年歷史」為主（高權重），同業對照為輔
- 聯準會升息/降息作為微調項
- 價位「挑整幾碼」
- **成長/成熟不是固定標籤**：成熟股可能因技術突破或換領導者而變成長股

**兩種模式：**

| 模式 | 公式 | 5 檔帶定義 |
|------|------|-----------|
| 成長型 (growth) | 共識EPS × PE中位數 × (1±fed) | 用 PE min~max 區間（與時俱進） |
| 循環/成熟型 (cyclical) | 加權BPS × PBR中位數 | 固定倍數 0.6/0.8/1.0/1.3/1.6 |

**5 檔：特價 / 便宜 / 合理 / 昂貴 / 瘋狂**

**資料鏈：**
```
update_market_cap.py  → market_cap.json   (PE/PB/市值/分類 + 估值帶合併)
update_financials.py  → stock_financials.json (近四季EPS/PEG)
fetch_analyst_eps.py  → analyst_eps.json  (法人預估EPS)
                        ↓
              fundamentals.json (整合)
                        ↓
valuation.py          → valuation.json    (5檔價位帶)
technical.py          → technical.json    (日K技術面指標)
                        ↓
              web_dashboard.py 顯示
```

### 技術面（日K為主，2026-08-18 實作）

`technical.py` 依 `cStocks/SPEC.md` 公式：
- MA5/MA20 + 多頭/空頭排列
- 布林通道 (20日 ± 2σ)
- MACD (12/26/9) + 金叉/死叉
- KDJ (9/3/3) + 超買/超賣
- 量比 + 大戶/散戶判定（每筆均量 > MA5×1.2）
- 支撐/壓力（近 20 日高低點）

**雙層架構：**
- 日K = 決定「要不要做」（趨勢/估值帶位置）
- 分K = 決定「什麼時候做」（盤中卡位/預估量）← 尚未整合

### 已知限制

1. `valuation_config.json` 的 pe_history/pb_history 是**佔位值**（當前 PE/PB），需填近 5 年真實區間
2. 7 檔缺 forward_eps/eps_growth_pct → PEG 無法計算
3. `@*.csv` 目前為模擬器資料，需真實盤中驗證
4. `requirements.txt` 有無效的 `mplfonts>=2.4.2`
5. 分K（1分鐘）技術面尚未整合

---

## 版本記錄

v1.3.0 - 2026-08-18
- 新增估值引擎 valuation.py（5檔價位帶：特價/便宜/合理/昂貴/瘋狂）
- 成長型改用 PE min~max 區間定義 5 檔帶（與時俱進）
- 新增技術面模組 technical.py（日K：MA/布林/MACD/KDJ/量比/支撐壓力）
- update_market_cap.py 合併估值帶到 market_cap.json
- Dashboard 顯示 5 檔估值帶
- Agent渡 移至 .github/agents/agent-du.agent.md

v1.2.0 - 2026-08-17
- 新增前瞻 EPS、前瞻 PE、前瞻殖利率計算
- 改善市值排名演算法，加入 Tier 分類與 Rank
- 更新 market_cap.json 輸出結構，包含 forward_pe、forward_yield

v1.1.1 - 2026-08-13 (修復版本)
- 修復 JSON 文件字段缺失：為 readme 字段添加 timestamp
- 修復 stock_names.json 結構驗證錯誤
- 優化驗證邏輯，為缺失字段自動添加默認值
- 改進數據校驗系統，增強代碼穩健性

已知 Bug
CSV 文件命名問題

描述：CSV 文件名稱未按 stock_id 生成，而是產生了 自選股1.csv~自選股3.csv--ok
影響：數據無法正確對應到特定股票
優先級：高
股票數據管理系統
項目概述
本項目是一個股票數據管理系統，主要功能包括：

實時股價數據更新
歷史數據存儲
數據可視化與分析
自動化報表生成
功能特性
實時數據抓取

支持多線程API請求，每秒最多3次（符合API限制）
支持股票基本信息和實時行情數據的抓取
數據存儲

JSON文件存儲股票基礎信息
CSV文件存儲歷史市場數據
數據可視化

支持生成交互式圖表（K線圖、成交量圖等）

├── stock\_ref.json          # 股票基礎信息存儲文件
├── \*.csv                   # 各股票的歷史數據文件（按stock\_id命名）
├── YuantaAPI_Pythonnet.py   # 主腳本，負責數據抓取與存儲（原文件名有拼寫錯誤 “Jasov”）
├── validate\_stock\_data.py  # 數據驗證工具
└── README.md               # 項目文檔

使用說明

1. 安裝依賴
pip install requests pandas matplotlib



todo:配置參數,計畫整合修改流程
jsonCsvUpdate.py，

&#x20;├─── 第一步先整合 1.YuantaAPI\_Pythonnet.py,  2.jsonCsvUpdate.py 與 3. SocketStats.py

&#x20;├─── 建議移除YuantaAPI\_Pythonnet.py 的 DEFAULT\_STOCK\_STRUCTURE and def \_save\_stock\_ref\_json():(1.的上方 3416行) 將被jsonCsvUpdate.py 取代

&#x20;├─── 請了解YuantaAPI\_Pythonnet.py的 def SubscribeWatclistAll\_Out移植重點 與 jsonCsvUpdate.py 的main() , 取代方式參考SubscribeWatclistAll\_Out

&#x20; ├─── 主程式發送登入後 ,會先收到證卷ack登入成功,這時 asyc show() 將進入等待至少1秒,接收執行續會繼續->期貨登入->海外證卷期貨登入只少3-5秒,才能完成登入

&#x20;├─── 國內證卷登入成功要等收到回應ack才叫登入成功,(至少有3秒時間後台還繼續其他還內外期貨需要登入,)我們至少等一秒以後,可利用這段期間初始化 jsonCsvUpdate.PY ,至  SubscribeWatchlistAll\_api證卷訂閱 ->到確認 ReadWatchListAll\_Out() \*\* 重點取代部分,ps:太快請求server可能容易異常

&#x20;├── \*\* 重點取代部分 a. 初始化時將\_save\_stock\_ref\_json()首次擴充,並初始化,保存至全局變數 SUBSCRIPTION\_STATE

&#x20; ├── \*\* api 回應SubscribeWatchlistAll\_api 取得文整擴充資料,並保存至 json 及 csv ,請注意,此request 每秒最多只能訂閱3次

&#x20;├── \*\* 之後有分3個時段盤前,盤中,盤後,需輪番訂閱各種命令,且須登到確認收到ack才能,下一個訂閱,所以 所有命令完成一輪每秒最多為3次,

&#x20; ├── ### 後續還會有權證分析,期貨,海外期貨的擴充輪巡 , 暫時知道就好
NOTIFICATION\_EMAIL = "your@email.com"

執行腳本
python 1.YuantaAPI\_Pythonnet.py,  2.jsonCsvUpdate.py 與 3. SocketStats.py 須確保成功編譯

{
"readme": "此JSON文件存儲股票基礎信息",
"timestamp": "2026-08-13 14:30:00",
"2330": {
"market\_no": "1",
"stock\_name": "台積電",
"yst\_price": 23650000,
"open\_ref": 23650000,
"up\_price": 26000000,
"down\_price": 21300000,
"yst\_vol": 22854,
"ext\_name": "2330",
"decimal": 4,
"credit\_pct": 0,
"bond\_pct": 0
......
},
// 其他股票信息...
}



版本記錄
v1.0.0 - 2026-08-13
初始版本發布
支持基本的股票數據抓取和存儲功能
實時數據更新功能上線

v1.1.0 - 2026-08-14
新增數據可視化功能
增加API請求限流機制（每秒3次）
支持電子郵件告警通知

v1.1.1 - 2026-08-13 (修復版本)
修復 JSON 文件字段缺失：為 readme 字段添加 timestamp
修復 stock\_names.json 結構驗證錯誤
優化驗證邏輯，為缺失字段自動添加默認值
改進數據校驗系統，增強代碼穩健性
已知 Bug
CSV 文件命名問題

描述：CSV 文件名稱未按 stock\_id 生成，而是產生了 自選股1.csv\~自選股3.csv--ok
影響：數據無法正確對應到特定股票
優先級：高



JSON 文件字段缺失 -- ok

描述：部分 JSON 文件的 Key 遺失，需要手動恢復
影響：數據處理邏輯受阻
優先級：中



API 請求超時問題

描述：在高負載情況下，API 請求可能超時
影響：數據更新延遲
優先級：低



貢獻指南 ,

1. 創建分支
為每個新功能或修復創建一個新的分支：
git commit -m "新增數據可視化功能: 支持生成交互式K線圖"
2. 提交更改
每次提交時，請附帶清晰的提交信息，例如
3. 創建 Pull Request (PR)
在 GitHub 上創建 PR 時，請填寫以下內容：
標題：清晰描述更改內容（例如 新增數據可視化功能）
描述：詳細說明更改的目的、實現方式以及測試結果。
檢查清單：
確保代碼風格符合項目規範
添加相應的測試用例
更新文檔（如有需要）
4. Code Review 流程
提交 PR 後，會有至少一名開發者進行審查。
审查人員會提出改进建議或疑問。
根據反饋修改代碼，並重新提交更改。
確保所有測試用例通過後，PR 將被合併到主分支。
5. 注意事項
請勿直接向 main 分支推送更改。
請在 PR 中提及相關的 Issues（例如 #123）以便追溯。

This function is used by the Yuanta Python API to interpret detailed dynamic information of individual stocks and permanently save it to a CSV file. It also generates corresponding JSON and CSV files based on the selected stocks. You need to apply for a Yuanta API membership to obtain login privileges.
