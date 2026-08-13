import json
import os
import time
import random
from pathlib import Path

# 定義全局變量
SUBSCRIPTION_STATE = {
    "market_no": None,
    "stock_id": None,
    "stock_name": None,
    "decimal": 2,
    "last_price": 0.0,
    "change": 0.0,
    "volume": 0,
    "timestamp": None
}

# 完整的股票結構範本
DEFAULT_STOCK_STRUCTURE = {
    "market_no": "",
    "stock_name": "",
    "yst_price": 0.0,
    "open_ref": 0.0,
    "up_price": 0.0,
    "down_price": 0.0,
    "yst_vol": 0,
    "ext_name": "",
    "decimal": 2,
    "credit_pct": 0.0,
    "bond_pct": 0.0,
    "open_price": 0.0,
    "high_price": 0.0,
    "low_price": 0.0,
    "close_price": 0.0,
    "in_volume": 0,
    "out_volume": 0,
    "single_volume": 0,
    "total_vol": 0
}

CSV_HEADERS = [
    "timestamp", "id_no", "market_no", "stock_id",
    "stock_name", "decimal", "last_price", "change", "volume"
]

def check_dependencies():
    """檢查依賴文件是否存在"""
    required_files = [
        "watchlist.json",
        "stock_names.json"
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"Error: 依賴文件 {file} 不存在。")
            return False
    return True

def read_watchlist():
    """讀取 watchlist.json 文件"""
    try:
        with open("watchlist.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: watchlist.json 文件未找到。")
        return {}
    except json.JSONDecodeError:
        print("Error: watchlist.json 文件格式錯誤。")
        return {}

def initialize_stock_ref():
    """初始化 stock_ref.json 文件結構"""
    # 讀取股票清單
    watchlist = read_watchlist()
    if not watchlist:
        return []
    
    data = []
    for stock_id, entry in watchlist.items():
        new_entry = DEFAULT_STOCK_STRUCTURE.copy()
        new_entry.update({
            "market_no": str(random.randint(1, 100)),
            "stock_id": stock_id,
            "stock_name": entry.get("name", ""),
            "decimal": entry.get("decimal", 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        data.append(new_entry)
    
    return data

def save_stock_ref_json(data):
    """保存數據到 stock_ref.json 文件"""
    try:
        with open("stock_ref.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("股票參考數據已成功保存到 stock_ref.json")
    except Exception as e:
        print(f"Error: 保存失敗：{str(e)}")

def append_csv_record(stock_id, data):
    """將數據追加到 CSV 文件"""
    csv_path = f"{stock_id}.csv"
    
    # 確保 CSV 文件存在
    if not os.path.exists(csv_path):
        try:
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(",".join(CSV_HEADERS) + "\n")
        except Exception as e:
            print(f"Error: 創建 CSV 文件失敗：{str(e)}")
            return
    
    # 確保所有字段都存在
    try:
        record = [
            data.get("timestamp", ""),
            data.get("id_no", ""),
            str(data.get("market_no", "")),
            str(data.get("stock_id", "")),
            data.get("stock_name", ""),
            str(data.get("decimal", 2)),
            "{0:.{1}f}".format(data.get("last_price", 0.0), data.get("decimal", 2)),
            "{0:.2f}".format(data.get("change", 0.0), 2),
            str(data.get("volume", 0))
        ]
        
        with open(csv_path, "a", encoding="utf-8") as f:
            f.write(",".join(record) + "\n")
    except Exception as e:
        print(f"Error: 追加數據到 CSV 文件失敗：{str(e)}")

def verify_data_integrity():
    """驗證數據完整性"""
    try:
        # 验證 stock_ref.json
        with open("stock_ref.json", "r", encoding="utf-8") as f:
            ref_data = json.load(f)
        
        if not isinstance(ref_data, list):
            raise ValueError("stock_ref.json 內容不正確，應為列表。")
        
        for entry in ref_data:
            if set(DEFAULT_STOCK_STRUCTURE.keys()).issubset(entry.keys()):
                stock_id = entry["stock_id"]
                csv_path = f"{stock_id}.csv"
                
                # 验證 CSV 文件
                if not os.path.exists(csv_path):
                    raise FileNotFoundError(f"CSV 文件 {csv_path} 不存在。")
                
                with open(csv_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if len(lines) < 2 or lines[0].strip() != ",".join(CSV_HEADERS):
                        raise ValueError(f"CSV 文件 {csv_path} 結構不正確。")
            else:
                raise ValueError(f"股票條目缺少必要字段：{entry}")
        
        print("[PASS] VERIFIED: 所有文件結構正常，數據完整")
        return True
    except Exception as e:
        print(f"[ERROR] 驗證失敗：{str(e)}")
        return False

def main():
    """主程序"""
    # 檢查依賴文件
    if not check_dependencies():
        return
    
    # 初始化股票參考數據
    data = initialize_stock_ref()
    if not data:
        print("Error: 初始化 stock_ref.json 失敗。")
        return
    
    # 保存到 JSON 文件
    save_stock_ref_json(data)
    
    # 更新模擬數據並保存到 CSV
    updated_data = []
    for entry in data:
        new_entry = {
            "market_no": entry["market_no"],
            "stock_id": entry["stock_id"],
            "stock_name": entry["stock_name"],
            "decimal": entry.get("decimal", 2),
            "last_price": round(random.uniform(50.0, 3000.0), entry.get("decimal", 2)),
            "change": round(random.uniform(-100.0, 100.0), 2),
            "volume": random.randint(1000, 1000000),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "id_no": str(random.randint(1, 100))
        }
        updated_data.append(new_entry)
        
        # 將數據追加到 CSV
        append_csv_record(entry["stock_id"], new_entry)
    
    print("模擬數據已成功保存到 CSV 文件")
    
    # 驗證數據完整性
    verify_data_integrity()

if __name__ == "__main__":
    main()
    