#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修復 stock_ref.json 缺失字段的腳本"""

import json
import sys

def fix_stock_ref():
    """為所有 stock 條目添加缺失字段"""
    file_path = "stock_ref.json"
    
    # 定義完整的 stock 結構
    DEFAULT_FIELDS = {
        "market_no": "1",
        "stock_name": "",
        "yst_price": 0,
        "open_ref": 0,
        "up_price": 0,
        "down_price": 0,
        "yst_vol": 0,
        "ext_name": "",
        "decimal": 4,
        "credit_pct": 0,
        "bond_pct": 0,
        "OpenPrice": 0.0,
        "HighPrice": 0.0,
        "LowPrice": 0.0,
        "BuyPrice": 0.0,
        "SellPrice": 0.0,
        "TotalOutVol": 0,
        "TotalInVol": 0,
        "DealPrice": 0.0,
        "TotalDealAmt": 0,
        "uintVol": 0,
        "singleVol": 0,
        "TotalVol": 0,
        "ytVolFlag": 1
    }
    
    # 讀取文件
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"讀取文件失敗: {e}")
        return False
    
    # 計數器
    updated_count = 0
    
    # 為每個 stock 條目添加缺失字段
    for stock_id, stock_data in data.items():
        # 跳過 readme 特殊鍵
        if stock_id == "readme":
            continue
            
        if isinstance(stock_data, dict):
            # 檢查並添加缺失字段
            for field, default_value in DEFAULT_FIELDS.items():
                if field not in stock_data:
                    stock_data[field] = default_value
                    updated_count += 1
    
    # 寫入文件
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"✓ 修復完成：已為 stock 條目添加 {updated_count} 個缺失字段")
        return True
    except Exception as e:
        print(f"寫入文件失敗: {e}")
        return False

if __name__ == "__main__":
    success = fix_stock_ref()
    sys.exit(0 if success else 1)
