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

1. 支持生成交互式圖表（K線圖、成交量圖等）

├── stock\_ref.json          # 股票基礎信息存儲文件
├── \*.csv                   # 各股票的歷史數據文件（按stock\_id命名）
├── jsonCsvUpdate.py        # 存儲主腳本，負責數據抓取與存儲
├── validate\_stock\_data.py  # 數據驗證工具
└── READMEGTp4oss120b.md    # 由單大模型gtp4全程+copiler獨立製作
pip install requests pandas matplotlib



todo:配置參數,計畫整合修改流程
jsonCsvUpdate.py，

&#x20;├─── 第一步先整合 1.YuantaAPI\_Pythonnet.py,  2.jsonCsvUpdate.py 與 3. SocketStats.py 

&#x20;├─── 建議移除YuantaAPI\_Pythonnet.py 的 DEFAULT\_STOCK\_STRUCTURE and def \_save\_stock\_ref\_json():(1.的上方 3416行) 將被jsonCsvUpdate.py 取代

&#x20;├─── 請了解YuantaAPI\_Pythonnet.py的 def SubscribeWatclistAll\_Out移植重點 與 jsonCsvUpdate.py 的main() , 取代方式參考SubscribeWatclistAll\_Out

&#x20; ├─── 主程式發送登入後 ,會先收到證卷ack登入成功,這時 asyc show() 將進入等待至少1秒,接收執行續會繼續->期貨登入->海外證卷期貨登入只少3-5秒,才能完成登入

&#x20;├─── 國內證卷登入成功一秒後,可利用這段期間初始化 jsonCsvUpdate.PY ,至  SubscribeWatchlistAll\_api證卷訂閱 ->到確認 ReadWatchListAll\_Out() \*\* 重點取代部分

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

