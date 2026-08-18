"""Simulation-only launcher — 模擬器 + dashboard 單一進程。
Usage: python sim_run.py [--port 5000] [--interval 5]

  API 優先: 若偵測到 .api_active（UAT 已送來信號），則不啟動。
  啟動前檢查 .dashboard_pid，防止重複啟動。
"""

import argparse
import os
import sys
import threading
import test_simulate
import web_dashboard
from YuantaAPI_Pythonnet import SubscribeWatclistAll_Out
import time

# Helper thread to invoke the mock SubscribeWatclistAll_Out after a short
# delay.


def _mock_subscribe_call():
    """Wait for the API login flag (.api_active) and then invoke the mock
    SubscribeWatclistAll_Out. In simulation mode the API process is not started,
    but the flag may still be created by the test_simulate placeholder or by a
    future implementation. We poll for up to 30 seconds before giving up.
    """
    api_flag = ".api_active"
    waited = 0
    max_wait = 30
    while waited < max_wait:
        if os.path.exists(api_flag):
            break
        time.sleep(1)
        waited += 1
    if not os.path.exists(api_flag):
        print("[SIM] .api_active not detected after login wait; skipping mock subscription call")
        return
    print("[SIM] Detected .api_active – login succeeded; invoking mock SubscribeWatclistAll_Out")
    try:
        dummy_data = b"\x00" * 64
        result = SubscribeWatclistAll_Out(dummy_data)
        print("[SIM] Mock SubscribeWatclistAll_Out result:", result)
    except Exception as e:
        print("[SIM] Mock SubscribeWatclistAll_Out error:", e)
    print("[SIM] Finished mock SubscribeWatclistAll_Out call (thread)")


API_FLAG = ".api_active"
PID_FILE = ".dashboard_pid"


def _check_duplicate():
    """檢查是否已有 dashboard 在運行，避免雙開。"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, encoding="utf-8") as f:
                old_pid = int(f.read().strip())
            import ctypes.wintypes

            SYNCHRONIZE = 0x100000
            PROCESS_QUERY_INFORMATION = 0x0400
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_INFORMATION, False, old_pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return old_pid
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except (ValueError, OSError):
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
    return None


def _write_pid():
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def _cleanup_pid():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except OSError:
        pass


def _check_api_active():
    """檢查 .api_active 是否有效（PID 仍存活），若為僵屍旗標則清除。"""
    if not os.path.exists(API_FLAG):
        return False
    try:
        with open(API_FLAG, encoding="utf-8") as f:
            pid = int(f.read().strip())
        import ctypes.wintypes

        SYNCHRONIZE = 0x100000
        PROCESS_QUERY_INFORMATION = 0x0400
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        # PID 不存在，清除僵屍旗標
        os.remove(API_FLAG)
        print(f"[SIM] 清除僵屍 .api_active (PID {pid} 已不存在)")
        return False
    except (ValueError, OSError):
        if os.path.exists(API_FLAG):
            os.remove(API_FLAG)
        print("[SIM] 清除無效 .api_active")
        return False


def main():
    if _check_api_active():
        print("[SIM] API 信號 active，模擬器不啟動。請使用 run.py 或等待 API 中斷。")
        return

    dup_pid = _check_duplicate()
    if dup_pid is not None:
        print(f"[SIM] Dashboard 已在運行中 (PID {dup_pid})，拒絕重複啟動。")
        print(f"[SIM] 若確定未運行，請手動刪除 {PID_FILE}")
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--stocks", type=str, default=None)
    args = parser.parse_args()

    print("[SIM] 模擬模式啟動 (API 未連線)")

    sim_thread = threading.Thread(target=_run_sim, args=(args,), daemon=True)
    sim_thread.start()

    _write_pid()
    try:
        poll_thread = threading.Thread(target=web_dashboard.poll_worker, daemon=True)
        poll_thread.start()
        print(f"Dashboard -> http://localhost:{args.port}")
        web_dashboard.app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
    finally:
        _cleanup_pid()


def _run_sim(args):
    sys.argv = ["test_simulate.py"]
    if args.stocks:
        sys.argv.extend(["--stocks", args.stocks])
    sys.argv.extend(["--interval", str(args.interval)])
    # Start mock subscription call in a separate daemon thread so it runs
    # concurrently with the (potentially long‑running) simulation.
    threading.Thread(target=_mock_subscribe_call, daemon=True).start()
    test_simulate.simulate()


if __name__ == "__main__":
    main()
