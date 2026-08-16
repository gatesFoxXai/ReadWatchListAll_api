#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
財務數據更新工具 — 從公開來源取得季度 EPS，計算 PEG。
寫入 stock_financials.json 供 dashboard 顯示 PE/PB/PEG。

資料來源:
  - 近四季 EPS: 從 TWSE 財報頁面估算
  - PE/PB: 從 BWIBBU_ALL (已整合在 market_cap.json)

PEG 公式:
  - 有法人預估值 → PEG = PE / 預估 EPS 成長率
  - 無預估值 → PEG = PE / 近四季 EPS 成長率 ( YoY )
  - 成長率 < 0 → PEG = N/A (負成長無意義)

用法:
  python update_financials.py                # 更新全部
  python update_financials.py --stocks 2330  # 指定股票

排程: 每季財報公布後（5/15, 8/14, 11/14, 3/31 前後）執行
"""
import json
import os
import ssl
import sys
from datetime import datetime
from urllib.request import urlopen, Request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "stock_financials.json")
# ---- 近四季 EPS（手動維護，每季更新） ----
#SUB-AGENTS,_QUARTERLY_EPS 每季設法更新,並註明updated TIME LIKE, python update_financials.py -> stock_financials.json
# 資料來源: 優先TWSE 個股財報 → 基本每股盈餘, 
# 格式: {code: [Q1_EPS, Q2_EPS, Q3_EPS, Q4_EPS]} (最近四季，從最早到最新)
# **此處為 2026Q1 示範值(非實際值)，實際需每季更新,AI TODO RIGHT NOW**
# 一次拿到全市場近四季 EPS 排行200  https://www.wantgoo.com/stock/ranking/trailing-eps?market=Listed
#一次拿到半導體近四季 EPS 排行 https://www.wantgoo.com/stock/ranking/trailing-eps?market=Listed&industry=^024
#一次拿到零組件近四季 EPS 排行https://www.wantgoo.com/stock/ranking/trailing-eps?market=Listed&industry=^028
#一次拿到航運近四季 EPS 排行https://www.wantgoo.com/stock/ranking/trailing-eps?market=Listed&industry=^033
#一次拿到指定個股近四季 EPS https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=IS_M_QUAR_ACC&STOCK_ID=2317
# 請ai代勞,上面方法得到此表取得正確值,並擴充 load_watchlist_stocks.json的所有自選股,去從
# ---- 近四季 EPS（手動維護，每季更新updated TIME2026-07-01）TODO: sub-agent 根據個股財報,取得正確近4季EPS** ----
_QUARTERLY_EPS = {  
    "2330": [22.08, 19.51, 17.44, 15.36],  # 台積電 2025Q2~2026Q1 ✅
    "2317": [2.83, 3.15, 2.98, 3.56],       # 鴻海✅
    "2454": [16.50, 18.20, 17.80, 15.17],   # 聯發科✅
    "2344": [0.35, 0.42, 0.38, 0.45],       # 華邦電✅
    "2356": [0.85, 0.92, 0.88, 0.95],       # 英業達✅
    "2609": [1.20, 1.35, 1.28, 1.42],       # 陽明✅
    "2610": [0.25, 0.28, 0.26, 0.30],       # 華航✅
    "2303": [1.10, 1.18, 1.15, 1.25],       # 聯電✅
    "2412": [1.20, 1.25, 1.22, 1.28],       # 中華電✅y
    "2881": [0.85, 0.92, 0.88, 0.95],       # 富邦金
    "2882": [5.5, 5.76, 4.26, 4.37],       # 國泰金   ✅ 
    "6412": [1.01, 1.18, 1.85, 1.17],       # 群電✅
    "6122": [1.03,1.33,1.23,1.08],       # 6122 擎邦✅
    "6123": [0.7,0.74,0.68,0.7],       # 6123 上奇✅
    "8936": [0.99,1.13,1.34,0.87],       # 國統✅
    "2535": [2.88, 6.5, 4.37, 2.61],         #達欣工✅
    "3019": [1.05, 1.09,1.86, 2.86]        #亞光✅
}


def fetch_eps_from_bwibbu_all(stock_code):
    """嘗試從 BWIBBU_ALL API（例如 https://bwibbu.com/api/v1/stock/{stock_code}/eps）取得近四季 EPS。"""
    url = f"https://bwibbu.com/api/v1/stock/{stock_code}/eps"
    try:
        response = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), context=_ssl_ctx())
        data = json.loads(response.read().decode("utf-8"))
        return {
            "eps": data["data"][0]["eps"],
            "bps": data["data"][0]["eps_bps"],
            "issue_amount": data["data"][0]["issue_amount"],
            "price_per_share": data["data"][0]["price_per_share"],
        }
    except Exception as e:
        print(f"Error fetching EPS for {stock_code} from BWIBBU_ALL: {e}")
        return None

def fetch_eps_from_wantgoo(stock_code):
    """嘗試從 WantGoo API（例如 https://www.wantgoo.com/stock/ranking/trailing-eps?market=Listed）取得近四季 EPS,ROE,ROA,per,pbr,財報三率%,營收成長率%。"""
    url = f"https://www.wantgoo.com/stock/ranking/trailing-eps?market=Listed"
    try:
        response = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), context=_ssl_ctx())
        data = json.loads(response.read().decode("utf-8"))
        eps_list = [stock["trailing_eps"] for stock in data["data"]]
        return {
            "eps": sum(eps_list) / len(eps_list),
            "bps": None,  # 不提供bps数据,但有pbr,成交價;可算出Bps
            "issue_amount": None,  # 不提供issue_amount数据
            "price_per_share": None,  # 不提供price_per_share数据,但有per,成交價;可算出eps
        }
    except Exception as e:
        print(f"Error fetching EPS for {stock_code} from WantGoo: {e}")
        return None


def fetch_eps_from_api(stock_code):
    """嘗試從 reliable API（例如 BWIBBU_ALL）取得近四季 EPS。
    假设 BWIBBU_ALL 返回一个包含eps、bps、發行股數、每股單價的字典。"""
    eps_data = fetch_eps_from_api_bwibbu_all(stock_code)
    if not eps_data:
        eps_data = fetch_eps_from_wantgoo(stock_code)
    return eps_data


def fetch_eps_from_goodInfo(stock_code):
    """嘗試從 goodinfo API（例如 https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=IS_{rpt_cat_suffix}&STOCK_ID={stock_code}取得近四季 EPS。"""
    rpt_cat_suffix = "M_QUAR"
    url_is = f"https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=IS_{rpt_cat_suffix}&STOCK_ID={stock_code}"
    try:        
        resp_is = requests.get(url_is, headers=headers); resp_is.encoding="utf-8"
        soup_is = BeautifulSoup(resp_is.text, "html.parser")
        eps = extract_values(soup_is, "每股稅後盈餘")
        eps_calc_values = eps
        return eps_calc_values[:4]
    except Exception as e:
        print(f"Error fetching EPS for {stock_code} from goodinfo: {e}")
        return None
                
        
def get_quarterly_eps_from_api(stock_code):
    """嘗試從 reliable API（例如 BWIBBU_ALL）取得近四季 EPS。
    假设 BWIBBU_ALL 返回一个包含eps、bps、發行股數、每股單價的字典。"""
    manual_override=load_analyst_eps().get(stock_code)
    eps_data = fetch_eps_from_api(stock_code)
    if not eps_data:       
        eps_data = fetch_eps_from_goodInfo(stock_code)
        if not eps_data:
            return {manual_override}
    return eps_data
    

def calculate_peg(pe, eps_4q):
    """計算 PEG。
    PEG = PE / EPS成長率(%)
    EPS成長率 = (近四季EPS / 前四季EPS - 1) × 100"""
    if not pe or pe <= 0:
        return None
    if not eps_4q or len(eps_4q) < 4:
        return None
    # 近四季 EPS 合計
    ttm_eps = sum(eps_4q)
    if ttm_eps <= 0:
        return None
    # EPS 成長率: 使用最近兩季 vs 去年同期兩季 (YoY)
    # 假設 eps_4q = [Q-3, Q-2, Q-1, Q0]
    recent_half = eps_4q[2] + eps_4q[3] if len(eps_4q) >= 4 else sum(eps_4q[-2:])
    prior_half = eps_4q[0] + eps_4q[1] if len(eps_4q) >= 4 else sum(eps_4q[:2])
    if prior_half <= 0:
        return None
    growth_pct = (recent_half / prior_half - 1) * 100
    if growth_pct <= 0:
        return None  # 負成長不計算 PEG
    peg = round(pe / growth_pct, 2)
    return {"peg": peg, "ttm_eps": round(ttm_eps, 2), "growth_pct": round(growth_pct, 1)}

    
def load_market_cap():
    """從 market_cap.json 讀取百大otc清單。"""    

    try:
        with open(os.path.join(BASE_DIR, "market_cap.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"stocks": {"2330": {}, "2317": {}}}


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx



def load_watchlist_stocks():
    """從 watchlist.json 讀取自選股清單。"""
    try:
        with open(os.path.join(BASE_DIR, "watchlist.json"), encoding="utf-8") as f:
            config = json.load(f)
        return config.get("自選股1", {}).get("stocks", [])
    except Exception:
        return ["2330", "2317", "2344"]

def load_analyst_eps():
    """從 analyst_eps.json manual_eps.eps if "method": "manual_override"=load_analyst_eps()。"""
    try:
        with open(os.path.join(BASE_DIR, "analyst_eps.json"), encoding="utf-8") as f:
            config = json.load(f)
        return config.get("stocks", {})
    except Exception:
        return config.get("stocks",{})

def build_financials(stocks=None):
    """建立財務數據 dict。"""    
    mcap = load_market_cap()
    stocks_data = mcap.get("stocks", {})

    if stocks is None:
        # 優先處理自選股，再補 _QUARTERLY_EPS 中的股票
        stocks = list(set(load_watchlist_stocks()) | set(_QUARTERLY_EPS.keys()))

    result = {"updated": datetime.now().isoformat(), "used" : "update_financials.py" ,"stocks": {}}
    watchlist = load_watchlist_stocks()
    for code in stocks:
        sym_str = str(code).strip()
        # 1. 排除 ETF、主動型型基金、權證與債券期貨邏輯,不同類型TODO:關注不同焦點
        if (
            sym_str.startswith("00") or   # 標準台股 ETF (如 0050)
            sym_str.startswith("01") or   # 不動產投資信託 (REITs)
            sym_str.startswith("03") or   # 權證
            sym_str.startswith("TX") or   # 台指期 期貨型
            sym_str.endswith("A") or      # 主動型 ETF (如 XXXXA) 🌟 新增
            sym_str.endswith("B") or      # 債券型 ETF (如 00679B)
            sym_str.endswith("U") or      # 期貨型 ETF (如 00642U)
            sym_str.endswith("R")         # 反向型 ETF (如 00632R)
        ):
            # print(f"跳過 ETF/主動型/權證: {sym_str}") 
            continue
        entry = stocks_data.get(code, {})   # 2. 獲取該股票的財務原始資料
        pe = entry.get("pe")
        pb = entry.get("pb")
        eps_q = _QUARTERLY_EPS.get(code)

        peg_info = None
        if pe and eps_q:
            peg_info = calculate_peg(pe, eps_q)

        is_watchlist = code in watchlist
        # 若無 PE/PB 且是自選股，從收盤價估算（標記為估算值）
        pe_note = ""
        if pe is None and is_watchlist and entry.get("close"):
            # 無法取得 PE，嘗試從已知 EPS 推算
            if eps_q:
                ttm = sum(eps_q)
                if ttm > 0:
                    pe = round(entry["close"] / ttm, 1)
                    pe_note = " (估算)"

        result["stocks"][code] = {
            "name": entry.get("name", ""),
            "pe": pe,
            "pb": pb,
            "eps_ttm": peg_info["ttm_eps"] if peg_info else (sum(eps_q) if eps_q else None),
            "eps_growth_pct": peg_info["growth_pct"] if peg_info else None,
            "peg": peg_info["peg"] if peg_info else None,
            "eps_quarters": eps_q,
            "peg_note": "近四季EPS (YoY半年成長率)" if peg_info else (
                "負成長，PEG無意義" if eps_q else (
                    "無EPS資料，需手動填入analyst_eps.json" if is_watchlist else "無EPS資料"
                )
            ),
        }
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="財務數據更新工具")
    parser.add_argument("--stocks", default=None, help="指定股票代碼（逗號分隔）")
    args = parser.parse_args()

    stocks = args.stocks.split(",") if args.stocks else None

    data = build_financials(stocks)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"stock_financials.json 已更新 ({len(data['stocks'])} 檔):")
    for code, info in sorted(data["stocks"].items()):
        peg_str = f"PEG={info['peg']}" if info['peg'] else f"({info['peg_note']})"
        print(f"  {code}: PE={info['pe']} PB={info['pb']} EPS_TTM={info['eps_ttm']} {peg_str}")


if __name__ == "__main__":
    main()

'''
taskschd.msc
设置定时任务
建立bat定時每季啟動更新Eps,失敗隔天再試,直到完成
'''
