import json
import os

def update_market_no(json_path: str):
    """根據 `TotalDealAmt`（成交金額）對股票進行市值排行，
    並將 `market_no` 欄位更新為排名（1 為最大市值）。
    若缺少 `TotalDealAmt`，則視為 0。"""
    # 讀取 JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 取出所有股票項目（排除 readme）
    stocks = [(sid, info) for sid, info in data.items() if sid != "readme"]

    # 依 TotalDealAmt 降序排序
    def deal_amt(item):
        info = item[1]
        return float(info.get("TotalDealAmt", 0))
    stocks.sort(key=deal_amt, reverse=True)

    # 更新 market_no 為排名
    for rank, (sid, info) in enumerate(stocks, start=1):
        info["market_no"] = str(rank)
        data[sid] = info

    # 寫回檔案
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"已依 TotalDealAmt 更新 market_no，總共 {len(stocks)} 支股票。")

if __name__ == "__main__":
    cwd = os.path.abspath(os.path.dirname(__file__))
    json_file = os.path.join(cwd, "stock_ref.json")
    if not os.path.exists(json_file):
        print(f"找不到 {json_file}")
    else:
        update_market_no(json_file)
