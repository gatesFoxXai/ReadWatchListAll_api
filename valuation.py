#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
估值引擎 — 依用戶個人投資框架計算 5 檔價位帶（特價/便宜/合理/昂貴/瘋狂）。

兩種模式:
  - growth   (成長/科技): 共識EPS × 自身歷史PE中位數 × (1±聯準會調整)
  - cyclical (景氣循環/房產): 加權BPS × 自身歷史PBR中位數

共用機制:
  - 5 檔倍數 (tiers) 可自訂，錨定在「合理價」上下展開
  - 價位「挑整幾碼」(round_to_nice)
  - 前瞻指標是「假設」→ 用實際季 EPS 軌跡驗證（all_estimates）

資料來源:
  - fundamentals.json   (eps_ttm / bps / forward_eps)
  - analyst_eps.json    (forward_eps 共識值)
  - valuation_config.json (每檔的 type / 歷史倍數區間 / fed調整 / tiers)

輸出:
  - valuation.json (供 dashboard 顯示)

用法:
  python valuation.py                 # 全部自選股
  python valuation.py --stocks 2330   # 指定
  python valuation.py --dry-run       # 僅顯示不寫入
"""

import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "valuation_config.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "valuation.json")
FUNDAMENTALS_FILE = os.path.join(BASE_DIR, "fundamentals.json")
ANALYST_FILE = os.path.join(BASE_DIR, "analyst_eps.json")
WATCHLIST_FILE = os.path.join(BASE_DIR, "watchlist.json")

# 5 檔預設倍數（錨定合理價=1.0）
DEFAULT_TIERS = {
    "special": 0.6,  # 特價
    "cheap": 0.8,  # 便宜
    "fair": 1.0,  # 合理
    "expensive": 1.3,  # 昂貴
    "crazy": 1.6,  # 瘋狂
}

TIER_LABELS = {
    "special": "特價",
    "cheap": "便宜",
    "fair": "合理",
    "expensive": "昂貴",
    "crazy": "瘋狂",
}


# ---- 資料載入 ----


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] 讀取 {os.path.basename(path)} 失敗: {e}")
        return default if default is not None else {}


def load_watchlist():
    cfg = _load_json(WATCHLIST_FILE, {})
    return cfg.get("自選股1", {}).get("stocks", ["2330", "2317", "2344"])


def load_config():
    return _load_json(CONFIG_FILE, {})


# ---- 核心計算 ----


def round_to_nice(price):
    """挑整幾碼：依價位大小取整數價位。
    <10→1, <100→5, <1000→5, <5000→10, 其餘→25。"""
    if price is None or price <= 0:
        return None
    if price < 10:
        step = 1
    elif price < 100:
        step = 5
    elif price < 1000:
        step = 5
    elif price < 5000:
        step = 10
    else:
        step = 25
    return int(round(price / step) * step)


def get_consensus_eps(code, fund, analyst):
    """取得共識 EPS（前瞻優先）。
    優先序: analyst.forward_eps → fund.forward_eps → fund.eps_ttm。
    回傳 (eps, source) source: 'forward'|'ttm'"""
    a = analyst.get(code, {})
    peg = a.get("peg") or {}
    if peg.get("forward_eps"):
        return peg["forward_eps"], "forward"
    if a.get("consensus_eps"):
        return a["consensus_eps"], "forward"
    f = fund.get(code, {})
    if f.get("forward_eps"):
        return f["forward_eps"], "forward"
    if f.get("eps_ttm"):
        return f["eps_ttm"], "ttm"
    return None, None


def get_bps(code, fund, cfg):
    """取得 BPS。
    優先: cfg.bps_history 加權（近期權重高）→ fund.bps。"""
    hist = cfg.get("bps_history")
    if hist and isinstance(hist, list) and len(hist) >= 2:
        n = len(hist)
        # 近期權重高：線性遞增權重 [1,2,...,n]
        weights = list(range(1, n + 1))
        total_w = sum(weights)
        weighted = sum(v * w for v, w in zip(hist, weights)) / total_w
        return round(weighted, 2)
    return fund.get(code, {}).get("bps")


def _apply_tiers(fair_price, tiers):
    """以合理價為錨，展開 5 檔並挑整幾碼。"""
    bands = {}
    for key in ["special", "cheap", "fair", "expensive", "crazy"]:
        mult = tiers.get(key, DEFAULT_TIERS[key])
        raw = fair_price * mult
        bands[key] = round_to_nice(raw)
    return bands


def _current_tier(close, bands):
    """判斷目前股價落在哪一檔。"""
    if close is None:
        return None
    # 由低到高找第一個 >= close 的檔位
    order = ["special", "cheap", "fair", "expensive", "crazy"]
    for i, key in enumerate(order):
        upper = bands.get(key)
        if upper is None:
            continue
        if close <= upper:
            return key
    return "crazy"


def compute_growth(code, close, fund, analyst, cfg):
    """成長/科技股：共識EPS × 自身歷史PE區間 × (1±fed調整)。

    成長型 PE 範圍會隨成長階段移動（與時俱進），
    因此 5 檔帶用該股自身的 pe_history.min~max 定義邊界：
      特價   = eps × pe_min × (1+fed)
      便宜   = eps × (pe_min + pe_median) / 2 × (1+fed)
      合理   = eps × pe_median × (1+fed)
      昂貴   = eps × (pe_median + pe_max) / 2 × (1+fed)
      瘋狂   = eps × pe_max × (1+fed)

    若 min/max 未設定，fallback 到固定倍數 (0.6~1.6)。
    """
    eps, eps_src = get_consensus_eps(code, fund, analyst)
    pe_hist = cfg.get("pe_history") or {}
    pe_median = pe_hist.get("median")
    pe_min = pe_hist.get("min")
    pe_max = pe_hist.get("max")
    if not eps or not pe_median:
        return None
    fed = cfg.get("fed_adjustment", 0.0)
    adj = 1 + fed

    # 成長型：用 min/median/max 定義 5 檔（與時俱進）
    if pe_min and pe_max and pe_min < pe_median < pe_max:
        bands = {
            "special": round_to_nice(eps * pe_min * adj),
            "cheap": round_to_nice(eps * (pe_min + pe_median) / 2 * adj),
            "fair": round_to_nice(eps * pe_median * adj),
            "expensive": round_to_nice(eps * (pe_median + pe_max) / 2 * adj),
            "crazy": round_to_nice(eps * pe_max * adj),
        }
        band_method = "pe_range"
    else:
        # fallback：固定倍數
        fair = eps * pe_median * adj
        tiers = {**DEFAULT_TIERS, **(cfg.get("tiers") or {})}
        bands = _apply_tiers(fair, tiers)
        band_method = "fixed_mult"

    return {
        "mode": "growth",
        "eps": eps,
        "eps_source": eps_src,
        "pe_anchor": pe_median,
        "pe_range": {"min": pe_min, "max": pe_max},
        "fed_adjustment": fed,
        "band_method": band_method,
        "fair_raw": round(eps * pe_median * adj, 2),
        "bands": bands,
        "current_tier": _current_tier(close, bands),
    }


def compute_cyclical(code, close, fund, analyst, cfg):
    """景氣循環/房產：加權BPS × 自身歷史PBR中位數。"""
    bps = get_bps(code, fund, cfg)
    pb = (cfg.get("pb_history") or {}).get("median")
    if not bps or not pb:
        return None
    fair = bps * pb
    tiers = {**DEFAULT_TIERS, **(cfg.get("tiers") or {})}
    bands = _apply_tiers(fair, tiers)
    return {
        "mode": "cyclical",
        "bps": bps,
        "pb_anchor": pb,
        "fair_raw": round(fair, 2),
        "bands": bands,
        "current_tier": _current_tier(close, bands),
    }


def compute_valuation(code, close, fund, analyst, cfg):
    """依 cfg.type 分派。type 缺省時自動判斷（有 pe_history→growth，有 pb_history→cyclical）。"""
    stock_cfg = cfg.get(code, {})
    mtype = stock_cfg.get("type")
    if mtype is None:
        if stock_cfg.get("pe_history"):
            mtype = "growth"
        elif stock_cfg.get("pb_history"):
            mtype = "cyclical"
        else:
            return None
    if mtype == "growth":
        return compute_growth(code, close, fund, analyst, stock_cfg)
    if mtype == "cyclical":
        return compute_cyclical(code, close, fund, analyst, stock_cfg)
    return None


# ---- 主流程 ----


def generate(stocks=None, dry_run=False):
    """計算全部/指定自選股的 5 檔估值帶，寫入 valuation.json。"""
    fund = _load_json(FUNDAMENTALS_FILE, {}).get("stocks", {})
    analyst = _load_json(ANALYST_FILE, {}).get("stocks", {})
    cfg = load_config()

    if stocks is None:
        stocks = load_watchlist()

    result = {
        "updated": datetime.now().isoformat(),
        "used": "valuation.py",
        "tiers_default": DEFAULT_TIERS,
        "stocks": {},
    }

    for code in stocks:
        close = fund.get(code, {}).get("close")
        # close 可能不在 fundamentals，嘗試從 analyst forward_pe 反推
        if close is None:
            peg = (analyst.get(code, {}) or {}).get("peg") or {}
            if peg.get("forward_pe") and peg.get("forward_eps"):
                close = round(peg["forward_pe"] * peg["forward_eps"], 2)
        v = compute_valuation(code, close, fund, analyst, cfg)
        if v is None:
            result["stocks"][code] = {"status": "no_config", "close": close}
            continue
        v["close"] = close
        v["name"] = fund.get(code, {}).get("name", "")
        result["stocks"][code] = v

    if dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] valuation.json 已更新 ({len(result['stocks'])} 檔)")
    return result


def _print_summary(result):
    """簡易文字摘要。"""
    print(f"\n{'='*64}")
    print(f"  估值摘要  (updated: {result['updated'][:10]})")
    print(f"{'='*64}")
    for code, v in result["stocks"].items():
        if v.get("status") == "no_config":
            print(f"  {code}  (未設定)")
            continue
        b = v["bands"]
        tier = TIER_LABELS.get(v.get("current_tier"), "--")
        print(
            f"  {code} {v.get('name',''):<6} "
            f"現{v.get('close')} [{tier}]  "
            f"特價{b['special']} 便宜{b['cheap']} 合理{b['fair']} "
            f"昂貴{b['expensive']} 瘋狂{b['crazy']}"
        )
    print(f"{'='*64}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="估值引擎")
    parser.add_argument("--stocks", help="指定股票，逗號分隔 (ex: 2330,2317)")
    parser.add_argument("--dry-run", action="store_true", help="僅顯示不寫入")
    args = parser.parse_args()

    stocks = args.stocks.split(",") if args.stocks else None
    res = generate(stocks=stocks, dry_run=args.dry_run)
    _print_summary(res)
