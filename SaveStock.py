import os
import clr
import json
import time
import signal
import datetime as dt
import struct
import pathlib
import sys
import csv
import random
from pathlib import Path
import pandas as pd
import asyncio
import logging
from SocketStats import SocketState, EnumLoginStatusType   # ← 只要匯入一次


logger = logging.getLogger(__name__)

#讀取報價50.0.0.16 執行異常，此功能每秒執行超過限制3次,取得昨收價/漲停價/跌停價
#ReadWatchListAll 50.0.0.16 — 取得昨收價/漲停價/跌停價
def ReadWatchListAll_api(yuanta, clien,isLogin):
    loginStatus = SUBSCRIPTION_STATE.get('login_status')
    if (int)(loginStatus.value) <  (int)(EnumLoginStatusType.LOGIN_SUCCESS.value):
        return False
   
    if not client.RqState(EnumLoginStatusType.REQ_WatchlistAll):
        print(
            "Skipping REQ_WatchlistAll_api – waiting for ACK of REQ_WatchlistAll"
        )
        return False
    
    stock_ids = get_watchlist_stocks()
    print(f"[{dt.datetime.now()}] ReadWatchListAll: 查詢 {len(stock_ids)} 檔參考價...")

    for sid in stock_ids:
        dataSetter = YuantaDataHelper(enumLangType.NORMAL)
        dataSetter.SetFunctionID(50, 0, 0, 16)
        dataSetter.SetUInt(1)
        dataSetter.SetByte(1)
        dataSetter.SetTByte(sid, 12)
        acc = RQ_account(False)
        yuanta.RQ(acc, dataSetter) #'S98875005091'
        time.sleep(0.33)
    if isLogin:
        time.sleep(1)
    else:
        time.sleep(0.5)
    return True

def safe_float(value, default=0.0):
    """ 安全轉換浮點數，若遇到亂碼、字串減號或 None 則回傳預設值 """
    if value is None or str(value).strip() in ["", "-", "NaN", "nan"]:
        return default
    try:
        return float(value)
    except ValueError:
        return default

def safe_int(value, default=0):
    """ 安全轉換整數 """
    if value is None or str(value).strip() in ["", "-", "NaN", "nan"]:
        return default
    try:
        return int(value)
    except ValueError:
        return default

# 1. 最新、最完整的標準結構範本（滿足目的 2：自動擴充）
DEFAULT_STOCK_STRUCTURE = {
                'market_no': market_no,
                'stock_name': stock_name,
                'yst_price': yst_price,
                'open_ref': open_ref,
                'up_price': up_price,
                'down_price': down_price,
                'yst_vol': yst_vol,
                'ext_name': ext_name,
                'decimal': decimal,
                'credit_pct': credit_pct,
                'bond_pct': bond_pct,
                # "new_feature_key": "default_value"  <-- 將擴充直接加這               
                'OpenPrice': safe_float(100.0),
                'HighPrice': safe_float(110.0),
                'LowPrice': safe_float(90.0),
                'BuyPrice': safe_float(100.0),
                'TotalOutVol' : safe_float(1000),
                'SellPrice' : safe_float(100.0),
                'TotalInVol' : safe_int(1000),
                'DealPrice' : safe_float(100.0),
                'TotalDealAmt' : safe_int(1000),
                'uintVol' : safe_int(1000),    #單量內外盤標記
                'singleVol' : safe_int(500), #單量
                'TotalVol' : safe_int(10500),   #總成交量
                'ytVolFlag' : safe_int(1) #單量內外盤標記
                }



def _save_stock_ref_json():
    """     
    開盤前後通用：精準更新融資、融券、參考價、成交價
    param SUBSCRIPTION_STATE: 元大 Socket 傳入的當前最新數據 (每秒最多 3 次)
    param force_save: 是否強制即時寫入檔案（盤前初始化與盤後結算時設為 True）
    
    將 SUBSCRIPTION_STATE['stock_ref'] 寫入 stock_ref.json 供 dashboard 讀取，
    同時將參考價寫入 @stockID.csv（若當日尚無記錄）。
    CSV 欄位與 _write_daily_summary() 統一使用中文格式。"""
    ref = SUBSCRIPTION_STATE.get('stock_ref', {})
    if not ref:
        print(f"[{dt.datetime.now()}] stock_ref.json 找不到:{ref}")
        return
    #1 清理 pythonnet 編碼損壞的股名（用 stock_names.json 取代）,stock_names.json為已排名上市股code:name only
    # 讀取正確的股票名稱對照表（確保名稱絕對不含 0xFFFD 亂碼）
    
    try:
        with open("stock_names.json", "r", encoding="utf-8") as nf:
            names_dict = json.load(nf)
        for sid, info in ref.items():
            # ────────────────────────────────────────────────────────
            # 目的 2：如果 key 有缺失，擴充此結構（首次執行自動補齊）
            # ────────────────────────────────────────────────────────
            updated_info = DEFAULT_STOCK_STRUCTURE.copy()
            # ────────────────────────────────────────────────────────
            # 目的 1 & 3：無論如何都要更新股票名稱 Value（同步最新名稱）
            # ────────────────────────────────────────────────────────
            correct_name = names_dict.get(sid, "")
            if correct_name:
                updated_info["stock_name"] = correct_name
            # ────────────────────────────────────────────────────────
            # 目的 3：無論如何都要動態更新 Value（精準處理盤中變動欄位）
            # ────────────────────────────────────────────────────────
            dynamic_data = SUBSCRIPTION_STATE.get(sid, {})
            if dynamic_data:
                updated_info["margin_purchase"] = int(dynamic_data.get("margin_purchase", updated_info["margin_purchase"]))
                updated_info["short_sale"]      = int(dynamic_data.get("short_sale", updated_info["short_sale"]))
                updated_info["reference_price"] = float(dynamic_data.get("reference_price", updated_info["reference_price"]))
                updated_info["current_price"]   = float(dynamic_data.get("current_price", updated_info["current_price"]))

            updated_info.update(info)
            sn = info.get("stock_name", "")
            if sn and len([c for c in sn if ord(c) == 0xFFFD]) > 0:
                correct = names_dict.get(sid, "")
                if correct:
                    info["stock_name"] = correct
    except Exception:
        pass
    
    # 2. 原子寫入 stock_ref.json (避免讀寫衝突)
    print (f'save _save_stock_ref_json temp含漲跌停融資眷: {ref}')
    try:
        tmp_path = "stock_ref.json.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(ref, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, "stock_ref.json")
        print(f"[{dt.datetime.now()}] stock_ref.json 已更新: {len(ref)} 檔 (含完整屬性)")
    except Exception as e:
        print(f"[{dt.datetime.now()}] stock_ref.json 寫入失敗: {e}")

    """ 
    3. 建立今日 CSV 佔位 (保持原樣，僅確保日期正確) :{1} 商品名稱:{2}昨收價:{3}:開盤參考價:{4}漲停價:{5}跌停價:{6}昨量:{7}擴充名:{8}小數位數:{9}融資成數:{10}融券成數:{11}'.
    """
    today = dt.datetime.now().strftime("%Y%m%d")
    fieldnames = ["日期", "stock_id", "開盤價", "最高價", "最低價",
                  "收盤價", "成交股數", "成交金額", "成交筆數",
                  "total_in_volume", "total_out_volume", "estimated_day_volume"]
    for stock_id, info in ref.items():
        filename = f"@{stock_id}.csv"
        # 檢查當日是否已有記錄（中文欄位名）
        skip = False
        if os.path.exists(filename):
            try:
                with open(filename, encoding="utf-8-sig", errors="replace") as f:
                    for row in csv.DictReader(f):
                        d = row.get("日期", row.get("date", ""))
                        if d == today:
                            skip = True
                            break
            except Exception:
                pass
        if skip:
            continue       
     
        stock_id = info.get('ext_name', 0)
        yst_price = info.get("yst_price", 0)
        yst_vol = info.get('yst_vol', 0)
        yesterday_volume = info.get("yesterday_volume",0)
        down_price = info.get("down_price", 0)
        up_price = info.get('up_price', 0)
        open_ref = info.get("open_ref", 0)
        HighPrice = info.get("HighPrice", 0)
        LowPrice = info.get("LowPrice", 0)
        TotalInVol = info.get("TotalInVol", 0)
        TotalDealAmt = info.get("TotalDealAmt", 0)
        TotalOutVol = info.get("TotalOutVol", 0)
        SellPrice = info.get("SellPrice",0)
        DealPrice = info.get("DealPrice",0)
        uintVol = info.get("uintVol",0)
        singleVol = info.get("singleVol")
        TotalVol = info.get("TotalVol")
        try:
            file_exists = os.path.exists(filename)
            with open(filename, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()                   
                writer.writerow({
                    "日期": today,
                    "stock_id": stock_id,
                    "開盤價": open_ref,
                    "最高價": HighPrice,
                    "最低價": LowPrice,
                    "收盤價": yst_price,
                    "成交股數": yst_vol,
                    "成交金額": TotalDealAmt,
                    "成交筆數": TotalVol,
                    "total_in_volume": TotalInVol,
                    "total_out_volume": TotalOutVol,
                    "estimated_day_volume": yesterday_volume
                })
            print(f"[{dt.datetime.now()}] @{stock_id}.csv 已建立今日參考價預留: {yst_price}")
        except Exception as e:
            print(f"[{dt.datetime.now()}] @{stock_id}.csv 寫入失敗: {e}")

