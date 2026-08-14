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
支持導出報表（PDF、Excel格式）
告警與通知

支持設置股價波動閾值，觸發時發送電子郵件或手機通知
文件結構
.
├── stock_ref.json          # 股票基礎信息存儲文件
├── *.csv                   # 各股票的歷史數據文件（按stock_id命名）
├── SaveStockRef.py         # 主腳本，負責數據抓取與存儲
├── validate_stock_data.py  # 數據驗證工具
└── README.md               # 項目文檔

使用說明
1. 安裝依賴
pip install requests pandas matplotlib

2. 配置參數
編輯 SaveStockRef.py，設置API密鑰和通知方式：

API_KEY = "your_api_key"
NOTIFICATION_EMAIL = "your@email.com"

3. 執行腳本
python SaveStockRef.py

API 文檔
JSON 文件格式（stock_ref.json）
{
    "readme": "此JSON文件存儲股票基礎信息",
    "timestamp": "2026-08-13 14:30:00",
    "2330": {
        "market_no": "1",
        "stock_name": "台積電",
        "yst_price": 23650000,
        "open_ref": 23650000,
        "up_price": 26000000,
        "down_price": 21300000,
        "yst_vol": 22854,
        "ext_name": "2330",
        "decimal": 4,
        "credit_pct": 0,
        "bond_pct": 0
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
修復 stock_names.json 結構驗證錯誤
優化驗證邏輯，為缺失字段自動添加默認值
改進數據校驗系統，增強代碼穩健性
已知 Bug
CSV 文件命名問題

描述：CSV 文件名稱未按 stock_id 生成，而是產生了 自選股1.csv~自選股3.csv
影響：數據無法正確對應到特定股票
優先級：高
JSON 文件字段缺失

描述：部分 JSON 文件的 Key 遺失，需要手動恢復
影響：數據處理邏輯受阻
優先級：中
API 請求超時問題

描述：在高負載情況下，API 請求可能超時
影響：數據更新延遲
優先級：低

貢獻指南
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
