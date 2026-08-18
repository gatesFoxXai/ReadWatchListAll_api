"""run.py v2 — 每日一站式啟動器。目前可正常啟動,但DASHBOARD無PE/PB/PEG
Usage: python run.py [--port 5000] [--no-api] [--skip-preflight]

  自動化流程:
  1. 雙開防護（PID + API active）
  2. 交易日判斷（週末 / holidays.json）
  3. 盤前檢查（@stockID.csv 昨日資料完整性 + stock_ref.json 涵蓋率）
  4. 啟動 YuantaAPI_Pythonnet.py（API 報價 + CSV 持久化）
  5. 啟動 web_dashboard.py（Flask + SSE 監控面板）

  參數:
  --no-api          僅啟動 dashboard，不啟動 API（非開盤日測試用）
  --skip-preflight  跳過盤前資料檢查
  --port PORT       dashboard port (預設 5000)
  --skip_close     跳過盤後資料檢查
"""

import argparse
import csv
import ctypes
import json
import os
import subprocess
import sys
import threading
import time

from datetime import datetime, date, timedelta

# 確保 console 輸出使用 UTF-8（避免 emoji 等字元在 cp950 環境下報錯）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    try:
        sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)
    except Exception:
        pass

import web_dashboard

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = ".dashboard_pid"
API_FLAG = ".api_active"
HOLIDAYS_FILE = "holidays.json"
WATCHLIST_PATH = "watchlist.json"
STOCK_REF_PATH = "stock_ref.json"

# ---- 工具函數 ----


def load_holidays() -> list:
    if os.path.exists(HOLIDAYS_FILE):
        with open(HOLIDAYS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def is_trading_day(d: date = None) -> bool:
    if d is None:
        d = date.today()
    if d.weekday() >= 5:
        return False
    if d.isoformat() in load_holidays():
        return False
    return True


def market_status() -> str:
    if not is_trading_day():
        return "holiday"
    now = datetime.now()
    t = now.hour * 60 + now.minute
    if t < 8 * 60 + 30:
        return "pre_open"
    if t < 13 * 60 + 30:
        return "trading"
    if t < 14 * 60 + 30:
        return "matching"
    return "closed"


def _try_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _is_process_running(pid: int) -> bool:
    try:
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_INFORMATION = 0x0400
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if handle == 0:
            return False
        kernel32.CloseHandle(handle)
        return True
    except Exception:
        return False


def _check_existing_pid_file(path: str, label: str) -> bool:
    """檢查 PID 檔案是否存在且程序執行中。回傳 True 表示雙開衝突。"""
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            pid = _try_int(f.read().strip())
    except OSError:
        _remove_file(path)
        return False
    if pid is None:
        _remove_file(path)
        return False
    if _is_process_running(pid):
        print(f"[RUN] {label} 已在執行中 (PID={pid})，拒絕雙開。")
        return True
    else:
        print(f"[RUN] 清除殘留 {label} 旗標 (PID={pid} 已不存在)")
        _remove_file(path)
        return False


def _remove_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _write_pid():
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def _cleanup_pid():
    _remove_file(PID_FILE)


# ---- 雙開防護 ----


def check_duplicate() -> bool:
    """檢查所有雙開旗標。回傳 True 表示可以繼續啟動。"""
    # 1) dashboard PID
    if _check_existing_pid_file(PID_FILE, "Dashboard"):
        return False
    # 2) API active flag
    if os.path.exists(API_FLAG):
        try:
            with open(API_FLAG, encoding="utf-8") as f:
                api_pid = _try_int(f.read().strip())
            if api_pid and _is_process_running(api_pid):
                print(f"[RUN] API 已在執行中 (PID={api_pid})，拒絕雙開。")
                print(f"      如需重啟: taskkill /f /pid {api_pid}")
                return False
            else:
                print("[RUN] 清除殘留 .api_active 旗標")
                _remove_file(API_FLAG)
        except OSError:
            _remove_file(API_FLAG)
    return True


# ---- 盤前資料檢查 ----


def _yesterday_str(target_date: date = None) -> str:
    """取得昨日日期字串 YYYYMMDD。"""
    if target_date is None:
        target_date = date.today()
    return (target_date - timedelta(days=1)).strftime("%Y%m%d")


def today_str() -> str:
    return date.today().strftime("%Y%m%d%h%M")


def _get_watchlist_stocks() -> list:
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            config = json.load(f)
        return config.get("自選股1", {}).get("stocks", [])
    except Exception:
        return ["2330", "2317", "2344"]


def get_last_row_optimized(path):
    # 1. 取得今天的日期 (格式為：2026-07-23)
    mtoday = date.today().strftime("%Y%m%d")
    weekday = date.weekday
    # 0~6#返回值是一個整數（0 到 6）。📅 星期代碼對照表 0：星期一 (Monday),4：星期五(Friday)5：星期六
    # (Saturday) 6：星期日 (Sunday)6 ：星期日（星期日）

    # 1. 先讀取 CSV 的第一行，取得欄位名稱 (Header)
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        if not reader:
            return None  # 空檔案
        headers = next(csv.reader(f), None)

        # 2. 極速倒退：直接跳到檔尾抓最後一行,以二進位模式開啟，從檔案末尾往前找最後一行
        if headers:
            with open(path, "rb") as f:
                try:
                    f.seek(-4, os.SEEK_END)
                    while f.read(1) != b"\n":
                        f.seek(-4, os.SEEK_CUR)
                except OSError:
                    f.seek(0)
            last_line = f.readline().decode("utf-8-sig", errors="replace").strip()

            # 3. 動態綁定：用當下抓到的 Header 與最後一行結合成 Dict (JSON)
            if last_line:
                # 使用 csv.reader 解析單行，自動處理可能有引號、逗號的欄位內容
                last_values = next(csv.reader([last_line]))

                # 使用 zip 將 Header 與 數值 1比1 綁定成字典（欄位多或少都能自動對齊）
                last_row_dict = dict(zip(headers, last_values))
                return last_row_dict


def check_yesterday_data() -> list:
    """檢查昨日 @stockID.csv 資料完整性。
    回傳缺少昨收資料的股票代碼清單。
    """
    yesterday = _yesterday_str()
    print(f"[RUN]今天是:{today_str()}  yesterday是:{yesterday}")

    stocks = _get_watchlist_stocks()
    missing = []
    for sid in stocks:
        path = f"@{sid}.csv"
        last_row_dict = get_last_row_optimized(path)
        # 昨日比較
        try:
            # --- 1. 安全且方便的驗證與取值,就算未來欄位順序換了，這樣拿資料依然絕對安全 ---
            if last_row_dict:
                current_date = last_row_dict.get("日期")
                if current_date:
                    # 計算相差天數current_date=CSV 的最後一天
                    days_diff = (today_str() - current_date).days
                    stock_id = sid
                    close_price = last_row_dict.get("收盤價" or 0)
                    open_price = last_row_dict.get("開盤價" or 0)
                    print(f"📊 成功轉換為 JSON 格式：\n{last_row_dict}\n")
                    print(
                        f"📅 檢查csv欄位：日期={current_date}, 股票代碼={stock_id}, 收盤價={close_price} open_price: {open_price}"
                    )
                    # 3. 比對日期邏輯
                    if days_diff == 0:
                        print(f"📊 資料是最新的！最後日期就是今天 ({current_date})。")
                        continue
                    elif days_diff == 1:
                        print(f"⚠️ 昨日是 {current_date}")
                        continue
                    elif days_diff == 2 & today_str().weekday == 0:  # 周一days_diff=2合理,但未考慮特休
                        continue
                    else:
                        print(f"🔮 異常：最後日期 {current_date} 未考慮特休日期或尚未紀錄今日收盤。")
                        missing.append(sid)
                        continue
        except e:
            print(f"❌ 日期格式解析失敗，請檢查 CSV 欄位文字是否為：{current_date}")
            print(f"❌ 無法取得有效的最後一行日期。{e}")
            missing.append(sid)
            continue

        except Exception:
            missing.append(sid)  # except
    return missing


def check_stock_ref_coverage() -> list:
    """檢查 stock_ref.json 是否涵蓋所有自選股且有完整參考價。"""
    stocks = _get_watchlist_stocks()
    try:
        with open(STOCK_REF_PATH, encoding="utf-8") as f:
            ref = json.load(f)
    except Exception:
        return stocks  # 全部缺
    missing = []
    for sid in stocks:
        entry = ref.get(sid, {})
        if not entry.get("yst_price"):
            missing.append(sid)
    return missing


def run_preflight(args, check_date_str: str = None) -> bool:
    """盤前檢查：昨日資料 + stock_ref.json。
    回傳 True 表示檢查通過（或跳過）。"""
    if hasattr(args, "skip_preflight"):
        print("[RUN] 跳過盤前檢查 (--skip-preflight)")
        return True

    print("[RUN] 盤前資料檢查...")

    # 1) 昨日 @stockID.csv
    missing_yesterday = check_yesterday_data(check_date_str)
    if missing_yesterday:
        print(f"[RUN] ⚠ 缺少昨日收盤資料: {missing_yesterday}")
        print(
            "[RUN] 自動執行 fetch_daily_close.py ....從公開資訊站(TWSE/TPEx) 取得每日收盤數據，寫入 @stockID.csv 與 stock_ref.json.."
        )
        try:
            result = subprocess.run(
                [sys.executable, "fetch_daily_close.py"],
                capture_output=True,
                text=True,
                timeout=150,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
            if result.returncode == 0:
                print("[RUN] fetch_daily_close.py 完成")
            else:
                print(f"[RUN] fetch_daily_close.py 失敗: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print("[RUN] fetch_daily_close.py 逾時 (150s)")
        except Exception as e:
            print(f"[RUN] fetch_daily_close.py 執行異常: {e}")

        # 再檢查一次
        still_missing = check_yesterday_data(check_date_str)
        if still_missing:
            print(f"[RUN] ⚠ 仍缺昨日資料: {still_missing}，將使用開盤價作為參考基準")
    else:
        print("[RUN] 昨日 @stockID.csv: OK")

    # 2) stock_ref.json 涵蓋率
    missing_ref = check_stock_ref_coverage()
    if missing_ref:
        print(f"[RUN] ⚠ stock_ref.json 缺少: {missing_ref}")
        still_missing_ref = check_stock_ref_coverage()
        if still_missing_ref:
            print(f"[RUN] ⚠ 仍缺參考價: {still_missing_ref}，漲跌停/顏色可能不準")
    else:
        print("[RUN] stock_ref.json 涵蓋率: OK")

    # 3) PEG 動態更新（需要先有 stock_financials.json + analyst_eps.json）
    _run_financials_update()
    _run_analyst_eps_update()

    print("[RUN] 盤前檢查完成")
    return True


def _run_financials_update():
    """執行 update_financials.py 確保 stock_financials.json 存在且涵蓋所有自選股。"""
    fin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_financials.json")
    stocks = _get_watchlist_stocks()
    need_update = not os.path.exists(fin_path)
    if not need_update:
        try:
            with open(fin_path, encoding="utf-8") as f:
                existing = json.load(f)
            existing_stocks = set(existing.get("stocks", {}).keys())
            missing = set(stocks) - existing_stocks
            if missing:
                print(f"[RUN] stock_financials.json 缺少: {list(missing)}")
                need_update = True
        except Exception:
            need_update = True
    if not need_update:
        print("[RUN] stock_financials.json: OK")
        return
    print("[RUN] 更新 stock_financials.json ...")
    try:
        result = subprocess.run(
            [sys.executable, "update_financials.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0:
            print("[RUN] stock_financials.json 更新完成")
        else:
            print(f"[RUN] update_financials.py 失敗: {result.stderr[:100]}")
    except Exception as e:
        print(f"[RUN] update_financials.py 執行異常: {e}")


def _run_analyst_eps_update():
    """若 analyst_eps.json 存在且有手動 EPS，根據最新收盤價重新計算 PEG。"""
    analyst_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyst_eps.json")
    if not os.path.exists(analyst_path):
        return
    try:
        with open(analyst_path, encoding="utf-8") as f:
            data = json.load(f)
        has_manual = any(s.get("manual_eps") is not None for s in data.get("stocks", {}).values())
        if not has_manual:
            return
    except Exception:
        return

    print("[RUN] 更新 PEG (analyst_eps.json → 根據收盤價)...")
    try:
        result = subprocess.run(
            [sys.executable, "fetch_analyst_eps.py", "--stocks", ",".join(_get_watchlist_stocks())],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0:
            print("[RUN] PEG 更新完成")
        else:
            print(f"[RUN] PEG 更新異常: {result.stderr[:100]}")
    except Exception as e:
        print(f"[RUN] PEG 更新失敗: {e}")


# ---- 主流程 ----


def main():
    parser = argparse.ArgumentParser(description="Yuanta OneAPI 每日一站式啟動器")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--no-api", action="store_true", help="僅啟動 dashboard")
    parser.add_argument("--skip-preflight", action="store_true", help="跳過盤前資料檢查")
    parser.add_argument("--skip_close", action="store_true", help="跳過盤後資料檢查")
    args = parser.parse_args()

    # ---- 雙開防護 ----
    if not check_duplicate():
        sys.exit(1)

    # ---- 交易日判斷 ----
    status = market_status()
    if status == "holiday":
        today = date.today()
        day_names = ["一", "二", "三", "四", "五", "六", "日"]
        reason = "週末" if today.weekday() >= 5 else "休市日"
        print(f"[RUN] 今日 ({today} {day_names[today.weekday()]}) 為{reason}，不啟動")
        return

    if status == "closed" and not args.skip_close:
        print("[RUN] 已收盤 (14:30+)，不啟動。使用 sim_run2.py 進行模擬測試。")
        return

    print(f"[RUN] 市場狀態: {status} args:{args}")
    # ---- 動態決定資料校驗基準日 ----
    # 如果開啟了 skip_closed，代表我們要校驗「今天當天」的收盤資料，否則預設校驗「昨天」
    target_date_str = date.today().strftime("%Y%m%d")
    if hasattr(args, "skip_closed"):
        # args.skip_closed:
        target_date_str = date.today().strftime("%Y%m%d")
    else:
        target_date_str = _yesterday_str()

    # ---- 盤前檢查 ----
    run_preflight(args, check_date_str=target_date_str)

    # ---- 啟動 API (subprocess) ----
    api_proc = None
    if not args.no_api:
        print("[RUN] 啟動 YuantaAPI_Pythonnet.py ...")
        try:
            # 強制子程序使用 UTF-8，避免 cp950 亂碼
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            api_proc = subprocess.Popen(
                [sys.executable, "-B", "-X", "utf8", "YuantaAPI_Pythonnet.py"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            print(f"[RUN] API 子程序已啟動 (PID={api_proc.pid})")

            # 背景讀取 stdout，防止 pipe 緩衝區阻塞子程序
            def _read_api_stdout(proc, label="API"):
                """持續讀取子程序 stdout 並打印到主控台。"""
                try:
                    for line in proc.stdout:
                        print(f"[{label}] {line.rstrip()}")
                except Exception:
                    pass

            reader_thread = threading.Thread(target=_read_api_stdout, args=(api_proc, "API"), daemon=True)
            reader_thread.start()

            # 等待 API 初始化完成（登入 + 首次訂閱），最多等 30 秒
            api_ready = False
            api_flag_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), API_FLAG)
            for _ in range(30):
                time.sleep(1)
                # 檢查子程序是否還活著
                if api_proc.poll() is not None:
                    print(
                        f"[RUN] ⚠ API 子程序已退出 (returncode={
                            api_proc.returncode})"
                    )
                    break
                # 檢查 .api_active 旗標（登入成功後 show() 才會建立）
                if os.path.exists(api_flag_path):
                    api_ready = True
                    print("[RUN] ✅ API 初始化完成（.api_active 已出現）")
                    break
            else:
                print("[RUN] ⚠ API 初始化逾時 (30s)，將繼續啟動 dashboard")
                print("[RUN]    若 CSV 無產出，請手動執行 YuantaAPI_Pythonnet.py")

            if api_ready:
                # 二次驗證：等待 CSV 實際產出
                csv_check_timeout = 10
                csv_confirmed = False
                for _ in range(csv_check_timeout):
                    time.sleep(1)
                    # 檢查任一主要股票的 CSV 是否有寫入（mtime > 30 秒內）? 萬一自選股,沒有2330,2317 ???
                    # ["2330", "2317"]:
                    for test_id in _get_watchlist_stocks():
                        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{test_id}.csv")
                        if os.path.exists(csv_path):
                            csv_age = time.time() - os.path.getmtime(csv_path)
                            if csv_age < 30:
                                csv_confirmed = True
                                break
                    if csv_confirmed:
                        print(f"[RUN] ✅ CSV 資料流已確認（{test_id}.csv 持續更新）")
                        break
                if not csv_confirmed:
                    print(f"[RUN] ⚠ 逾時等待 CSV 產出 ({csv_check_timeout}s)，可能訂閱無資料")
                    print("[RUN]    請檢查帳號登入狀態及網路連線")
            else:
                # 再等 3 秒給登入回應
                print("[RUN] ⚠ 再等 5 秒給登入回應")
                time.sleep(5)
        except Exception as e:
            print(f"[RUN] API 啟動失敗: {e}")
            print("[RUN] 將僅啟動 dashboard（無即時報價）")
    else:
        print("[RUN] --no-api: 跳過 API 啟動")

    # ---- 啟動 Dashboard ----
    print(f"[RUN] 啟動 Dashboard → http://localhost:{args.port}")
    _write_pid()
    try:
        poll_thread = threading.Thread(target=web_dashboard.poll_worker, daemon=True)
        poll_thread.start()
        web_dashboard.app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n[RUN] 收到中斷訊號")
    finally:
        _cleanup_pid()
        # 清理 API 子程序
        if api_proc is not None and api_proc.poll() is None:
            print(f"[RUN] 關閉 API 子程序 (PID={api_proc.pid})...")
            api_proc.terminate()
            try:
                api_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("[RUN] API 未回應，強制關閉")
                api_proc.kill()
            print("[RUN] API 子程序已關閉")

        # ---- 盤後自動轉換 1 分 K（供 cStocks 使用）----
        try:
            print("[RUN] 轉換 5 秒 CSV → 1 分 K (resample_1min.py --all) ...")
            resample_proc = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", "resample_1min.py", "--all"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if resample_proc.returncode == 0:
                print("[RUN] ✅ 1 分 K 轉換完成 → 1min/")
            else:
                print(f"[RUN] ⚠ 1 分 K 轉換有問題 (rc={resample_proc.returncode})")
                if resample_proc.stderr:
                    print(f"[RUN]   {resample_proc.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print("[RUN] ⚠ 1 分 K 轉換逾時 (120s)")
        except Exception as e:
            print(f"[RUN] ⚠ 1 分 K 轉換失敗: {e}")


if __name__ == "__main__":
    main()
