@echo off
:: ----------------------------------------------------------------------
:: Yuanta OneAPI & Dashboard 自動化整合啟動器 (專業生產環境版)
:: ----------------------------------------------------------------------
chcp 65001 >nul
:: ---（擺脫中文亂碼危機）--chcp 65001 >nu強制將控制台切換為 UTF-8-------
setlocal enabledelayedexpansion

:: ---- 1. 基礎路徑與設定 ----
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "LOG_DIR=%SCRIPT_DIR%logs"
set "PYTHON_EXE=python"

:: 建立日誌資料夾
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: 產生以「日期_時間」命名的專屬日誌檔案 (格式: YYYYMMDD_HHMMSS)動態時間日誌（logs/run_20260621_182000.log）利用 wmic 語法精準抓取系統時間，建立一個絕對不會重複的LOG
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "dt=%%I"
set "YYYY=%dt:~0,4%"
set "MM=%dt:~4,2%"
set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%"
set "MIN=%dt:~10,2%"
set "SEC=%dt:~12,2%"
set "LOG_FILE=%LOG_DIR%\run_%YYYY%%MM%%DD%_%HH%%MIN%%SEC%.log"

echo ============================================================ >> "%LOG_FILE%"
echo  [SYSTEM] 啟動排程任務：%date% %time% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

:: 同時輸出到畫面與日誌 (包裝成巨集)
echo [SYS] 正在啟動 Yuanta 一站式系統，日誌將同步寫入 logs 資料夾...
echo [SYS] 日誌檔案: %LOG_FILE%

:: ---- 2. 環境防禦性檢查 ----
:: 檢查 Python 是否安裝
"%PYTHON_EXE%" --version >nul 2>&1
if %errorlevel% neq 0 (
    set "ERR_MSG=[ERROR] 找不到 Python 執行環境，請檢查環境變數設定！"
    goto :CRITICAL_ERROR
)

:: ---- 3. 核心執行階段 ----
rem  -B:Converts bytes/bytearray to str and issues warnings when comparing bytes/bytearray with str or bytes with int.
echo [SYS] 正在執行 Python 主程式判斷與資料校驗...
echo [INFO] 執行指令: "%PYTHON_EXE%" run.py  >> "%LOG_FILE%"

:: 執行 Python 並將標準輸出 (1) 與錯誤輸出 (2) 全部導向日誌檔(日誌largest??)
:: 為了讓畫面上也能即時看到，如果您想要畫面同步顯示，可以保持目前這樣，若要完全背景執行，則不用加額外設定
"%PYTHON_EXE%" run.py >> "%LOG_FILE%" 2>&1
:: , 改成下面 "%PYTHON_EXE%" run.py test error 才log
::"%PYTHON_EXE%" run.py --skip_close

:: ---- 4. 錯誤層級捕捉 (ErrorLevel) ----
set "EXIT_CODE=%errorlevel%"
echo [INFO] Python 程式退出，結束代碼: %EXIT_CODE% >> "%LOG_FILE%"

:: 根據寫好的 Python 阻斷機制進行判斷
if %EXIT_CODE% equ 0 (
    echo [SUCCESS] 系統已正常啟動，或今日為休市日已安全退出。
::     echo [INFO] 任務正常結束。 >> "%LOG_FILE%"
	echo [INFO] 任務正常結束。
    timeout /t 5 >nul
    exit /b 0
) else if %EXIT_CODE% equ 1 (
    set "ERR_MSG=[ALERT] 偵測到雙開衝突 (PID 旗標存在)，拒絕重複啟動。"
    goto :WARNING_EXIT
) else (
    set "ERR_MSG=[CRITICAL] 程式異常退出，可能是 OHCL 資料有瑕疵遭系統安全阻斷，或是代碼崩潰！"
    goto :CRITICAL_ERROR
)

:: ---- 5. 例外處理區塊 ----

:WARNING_EXIT
echo %ERR_MSG%
echo %ERR_MSG% >> "%LOG_FILE%"
timeout /t 5 >nul
exit /b %EXIT_CODE%

:CRITICAL_ERROR
echo ------------------------------------------------------------
echo %ERR_MSG%
echo ------------------------------------------------------------
echo %ERR_MSG% >> "%LOG_FILE%"
echo [SYS] 請檢查最新日誌檔案內容進行排錯。

:: 如果是在工作排程器執行，不建議暫停；但如果是手動點擊，保持視窗不關閉以便查看錯誤
:: -echo [SYS] 視窗將在 10 秒後自動關閉...
:: -timeout /t 10
exit /b %EXIT_CODE%