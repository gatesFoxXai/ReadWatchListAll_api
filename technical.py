#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技術面指標模組（日 K 為主）— 依 cStocks/SPEC.md 的公式實作。

指標:
  - MA5 / MA20 均線 + 乖離
  - 布林通道 (MA20 ± 2σ, 20日)
  - MACD (12/26/9) + 金叉/死叉偵測
  - KDJ (9/3/3) + 超買/超賣
  - 量能: 量比(今日/5日均量)、大戶判定(每筆均量 > MA5×1.2)
  - 支撐/壓力: 近 20 日高低點 + 量能峰

資料來源:
  - @{code}.csv (日總結, 12 欄中文) — 主來源
  - {code}.csv (5 秒) — 盤中即時（後續 1 分 K 衝浪用）

輸出:
  - technical.json (供 dashboard 顯示)

用法:
  python technical.py                 # 全部自選股
  python technical.py --stocks 2330   # 指定
  python technical.py --dry-run       # 僅顯示
"""

import json
import os
from datetime import datetime

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "technical.json")
WATCHLIST_FILE = os.path.join(BASE_DIR, "watchlist.json")

# 預設參數（與 cStocks SPEC 一致）
MA_SHORT = 5
MA_LONG = 20
BOLL_PERIOD = 20
BOLL_STD = 2
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
KDJ_N, KDJ_M1, KDJ_M2 = 9, 3, 3
VOL_MA = 5
WHALE_RATIO = 1.2  # 大戶判定: 每筆均量 > MA5 × 1.2
SR_WINDOW = 20  # 支撐壓力回看天數


def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        return ["2330", "2317"]
    with open(WATCHLIST_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("自選股1", {}).get("stocks", ["2330", "2317"])


def load_daily(code, min_days=30):
    """讀取 @{code}.csv 日 K 資料。回傳 DataFrame 或 None。"""
    path = os.path.join(BASE_DIR, f"@{code}.csv")
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    # 欄位標準化
    colmap = {}
    for c in df.columns:
        cs = str(c).strip()
        if cs == "日期":
            colmap[c] = "date"
        elif cs == "開盤價":
            colmap[c] = "open"
        elif cs == "最高價":
            colmap[c] = "high"
        elif cs == "最低價":
            colmap[c] = "low"
        elif cs == "收盤價":
            colmap[c] = "close"
        elif cs == "成交股數":
            colmap[c] = "volume"
        elif cs == "成交金額":
            colmap[c] = "amount"
        elif cs == "成交筆數":
            colmap[c] = "trades"
    df = df.rename(columns=colmap)
    need = ["open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in need):
        return None
    for c in need:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # 過濾未完成/無效行（收盤價=0 或 成交量=0 代表當日尚未收盤）
    df = df[(df["close"] > 0) & (df["volume"] > 0)]
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(df) < min_days:
        return None
    return df


# ---- 指標計算 ----


def calc_ma(df):
    df["ma5"] = df["close"].rolling(MA_SHORT).mean()
    df["ma20"] = df["close"].rolling(MA_LONG).mean()
    return df


def calc_boll(df):
    mid = df["close"].rolling(BOLL_PERIOD).mean()
    std = df["close"].rolling(BOLL_PERIOD).std()
    df["boll_mid"] = mid
    df["boll_ub"] = mid + BOLL_STD * std
    df["boll_lb"] = mid - BOLL_STD * std
    return df


def calc_macd(df):
    ema_fast = df["close"].ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = df["close"].ewm(span=MACD_SLOW, adjust=False).mean()
    df["macd_dif"] = ema_fast - ema_slow
    df["macd_dea"] = df["macd_dif"].ewm(span=MACD_SIGNAL, adjust=False).mean()
    df["macd_hist"] = (df["macd_dif"] - df["macd_dea"]) * 2
    return df


def calc_kdj(df):
    low_n = df["low"].rolling(KDJ_N).min()
    high_n = df["high"].rolling(KDJ_N).max()
    rng = (high_n - low_n).replace(0, float("nan"))
    rsv = ((df["close"] - low_n) / rng * 100).fillna(50)
    # KDJ 9,3,3: K = EWM(rsv, com=2), D = EWM(K, com=2)
    k = rsv.ewm(com=KDJ_M1 - 1, adjust=False).mean()
    d = k.ewm(com=KDJ_M2 - 1, adjust=False).mean()
    df["kdj_k"] = k
    df["kdj_d"] = d
    df["kdj_j"] = 3 * k - 2 * d
    return df


def calc_volume(df):
    df["vol_ma5"] = df["volume"].rolling(VOL_MA).mean()
    if "trades" in df.columns and "amount" in df.columns:
        trades = pd.to_numeric(df["trades"], errors="coerce").replace(0, float("nan"))
        df["avg_vol_per_trade"] = (df["volume"] / trades).astype(float)
        df["avg_vol_per_trade_ma5"] = df["avg_vol_per_trade"].rolling(VOL_MA, min_periods=1).mean()
    return df


def calc_sr(df):
    """支撐/壓力: 近 SR_WINDOW 日高低點（不含今日）。"""
    recent = df.iloc[-(SR_WINDOW + 1) : -1]
    return {
        "support": round(float(recent["low"].min()), 2),
        "resistance": round(float(recent["high"].max()), 2),
    }


# ---- 訊號判斷 ----


def _macd_signal(df):
    """回傳 (state, cross) state: bullish/bearish, cross: golden/dead/None"""
    dif, dea = df["macd_dif"], df["macd_dea"]
    state = "bullish" if dif.iloc[-1] > dea.iloc[-1] else "bearish"
    cross = None
    if len(dif) >= 2:
        if dif.iloc[-2] <= dea.iloc[-2] and dif.iloc[-1] > dea.iloc[-1]:
            cross = "golden"
        elif dif.iloc[-2] >= dea.iloc[-2] and dif.iloc[-1] < dea.iloc[-1]:
            cross = "dead"
    return state, cross


def _kdj_signal(df):
    k, d, j = df["kdj_k"].iloc[-1], df["kdj_d"].iloc[-1], df["kdj_j"].iloc[-1]
    if j > 100:
        zone = "overbought"
    elif j < 0:
        zone = "oversold"
    else:
        zone = "neutral"
    return zone


def _whale_signal(df):
    """大戶/散戶判定（cStocks SPEC 邏輯）。"""
    if "avg_vol_per_trade" not in df.columns:
        return None
    last = df.iloc[-1]
    if pd.isna(last.get("avg_vol_per_trade")) or pd.isna(last.get("avg_vol_per_trade_ma5")):
        return None
    is_whale = bool(last["avg_vol_per_trade"] > last["avg_vol_per_trade_ma5"] * WHALE_RATIO)
    is_up = bool(last["close"] >= last["open"])
    if is_whale:
        status = "大戶追價" if is_up else "大戶吸收"
    else:
        status = "散戶盤整"
    return {"whale": is_whale, "status": status}


def _vol_signal(df):
    last = df.iloc[-1]
    if pd.isna(last.get("vol_ma5")) or last["vol_ma5"] == 0:
        return None
    ratio = last["volume"] / last["vol_ma5"]
    if ratio > 1.5:
        level = "heavy"
    elif ratio < 0.618:
        level = "light"
    else:
        level = "normal"
    return {"ratio": round(ratio, 2), "level": level}


def _trend_signal(df):
    """均線排列 + 布林位置。"""
    last = df.iloc[-1]
    close = last["close"]
    ma5, ma20 = last.get("ma5"), last.get("ma20")
    if pd.isna(ma5) or pd.isna(ma20):
        return None
    if close > ma5 > ma20:
        alignment = "bullish"  # 多頭排列
    elif close < ma5 < ma20:
        alignment = "bearish"  # 空頭排列
    else:
        alignment = "mixed"
    boll_pos = None
    if not pd.isna(last.get("boll_ub")) and not pd.isna(last.get("boll_lb")):
        width = last["boll_ub"] - last["boll_lb"]
        if width > 0:
            boll_pos = round((close - last["boll_lb"]) / width, 2)  # 0=下軌, 1=上軌
    return {"alignment": alignment, "boll_position": boll_pos}


# ---- 主流程 ----


def compute_stock(code):
    df = load_daily(code)
    if df is None:
        return {"status": "no_data"}
    df = calc_ma(df)
    df = calc_boll(df)
    df = calc_macd(df)
    df = calc_kdj(df)
    df = calc_volume(df)

    last = df.iloc[-1]
    macd_state, macd_cross = _macd_signal(df)
    result = {
        "status": "ok",
        "date": str(last["date"]),
        "close": round(float(last["close"]), 2),
        "ma": {
            "ma5": round(float(last["ma5"]), 2) if not pd.isna(last["ma5"]) else None,
            "ma20": round(float(last["ma20"]), 2) if not pd.isna(last["ma20"]) else None,
        },
        "boll": {
            "lb": round(float(last["boll_lb"]), 2) if not pd.isna(last["boll_lb"]) else None,
            "mid": round(float(last["boll_mid"]), 2) if not pd.isna(last["boll_mid"]) else None,
            "ub": round(float(last["boll_ub"]), 2) if not pd.isna(last["boll_ub"]) else None,
        },
        "macd": {
            "dif": round(float(last["macd_dif"]), 3),
            "dea": round(float(last["macd_dea"]), 3),
            "hist": round(float(last["macd_hist"]), 3),
            "state": macd_state,
            "cross": macd_cross,
        },
        "kdj": {
            "k": round(float(last["kdj_k"]), 1),
            "d": round(float(last["kdj_d"]), 1),
            "j": round(float(last["kdj_j"]), 1),
            "zone": _kdj_signal(df),
        },
        "volume": _vol_signal(df),
        "whale": _whale_signal(df),
        "trend": _trend_signal(df),
        "sr": calc_sr(df),
        "days": len(df),
    }
    return result


def generate(stocks=None, dry_run=False):
    if stocks is None:
        stocks = load_watchlist()
    result = {
        "updated": datetime.now().isoformat(),
        "params": {
            "ma": [MA_SHORT, MA_LONG],
            "boll": [BOLL_PERIOD, BOLL_STD],
            "macd": [MACD_FAST, MACD_SLOW, MACD_SIGNAL],
            "kdj": [KDJ_N, KDJ_M1, KDJ_M2],
        },
        "stocks": {},
    }
    for code in stocks:
        result["stocks"][code] = compute_stock(code)

    if dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] technical.json 已更新 ({len(result['stocks'])} 檔)")
    return result


def _print_summary(result):
    print(f"\n{'=' * 60}")
    print(f"  技術面摘要  (updated: {result['updated'][:10]})")
    print(f"{'=' * 60}")
    for code, v in result["stocks"].items():
        if v.get("status") != "ok":
            print(f"  {code}: {v.get('status')}")
            continue
        macd = v["macd"]
        kdj = v["kdj"]
        trend = v.get("trend") or {}
        vol = v.get("volume") or {}
        whale = v.get("whale") or {}
        sr = v.get("sr") or {}
        cross = f" [{macd['cross']}叉]" if macd.get("cross") else ""
        print(
            f"  {code} 收{v['close']} "
            f"MA5={v['ma']['ma5']} MA20={v['ma']['ma20']} "
            f"MACD={macd['state']}{cross} "
            f"KDJ={kdj['k']}/{kdj['d']}/{kdj['j']}({kdj['zone']}) "
            f"量比={vol.get('ratio')}({vol.get('level')}) "
            f"{whale.get('status', '')} "
            f"排列={trend.get('alignment')} "
            f"S={sr.get('support')} R={sr.get('resistance')}"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="技術面指標（日K）")
    parser.add_argument("--stocks", default=None, help="指定股票代碼（逗號分隔）")
    parser.add_argument("--dry-run", action="store_true", help="僅顯示不寫入")
    args = parser.parse_args()

    stocks = args.stocks.split(",") if args.stocks else None
    res = generate(stocks=stocks, dry_run=args.dry_run)
    _print_summary(res)
