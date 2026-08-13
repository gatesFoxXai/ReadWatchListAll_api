import json
import os
import time
import random
from pathlib import Path

import httpx
import re
import time

# 定義雙 5090 分流服務端點（對應我們分開開啟的 Port）
'''
PORT_GPU0 = "http://localhost:11434/api/generate"  # GPU 0: Llama 3.3 70B (主架構師)
PORT_GPU1 = "http://localhost:11435/api/generate"  # GPU 1: DeepSeek-R1 32B (慢思考稽核員)
'''
PORT_GPU0 = "http://localhost:11434/api/generate"  # 改為 11434
PORT_GPU1 = "http://localhost:11434/api/generate"  # 也改為 11434


def ask_ollama(url, model, prompt, validator_prompt="", context_length=32768, temperature=0.0):
    """
    呼叫 Ollama API 的核心函式
    - 解放關鍵參數：num_ctx (上下文長度設定為 32K 以上)
    - 寫程式與 Debug 必須設定 temperature=0.0，卡死邏輯、杜絕模型瞎編湊字數
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": context_length,  # ⚡ 挑戰長上下文，讓模型看清複雜 Class 的前後依賴關係
            "temperature": temperature,  # ⚡ 嚴謹模式，拒絕幻覺
            "num_predict": 32768          # 允許生成長篇大論的程式碼或深度報告
        }
    }
    start_time = time.time()
    try:
        response = httpx.post(url, json=payload, timeout=600.0) # 長上下文運算較久，逾時設 10 分鐘
        elapsed = time.time() - start_time
        return response.json()['response'], elapsed
    except Exception as e:
        return f"連線錯誤: {str(e)}", validator_prompt.find("稽核次數") + 1 if "稽核次數" in validator_prompt else 1

# =====================================================================
# 🚀 實戰情境：挑戰複雜系統（純文字邏輯運算版本，免裝 matplotlib）
# =====================================================================

complex_task = """
請改寫一個完整的 Python 物件導向系統 (Class Architecture)。
要求包含全局變量SUBSCRIPTION_STATE,依循你的思考鏈進行推理,並顯示規劃改進框架：
1. 在路徑"E:\\workspace\\temp\\SaveStockRef.py"**此python要能檢查** stock_ref.json,及根據 stock_id 循環首次至stock_names.json取得對應的 stock_name ,的欄位,目前stock_ref.json的有些欄位不存在,並同時更新他的value值,這個行為,也許只會做一次,但update的行為會每秒執行3次,每次呼叫時,還要同時insert一筆對應的stock.csv , csv維持目前的欄位,不需要append其他,請你嘗試,修改,並假設每秒會執行3次,簡單說,第一次模擬一筆資料append stock_ref.json的欄位,並更新value ,同時產生一筆預設欄位的csv.第2次以後,json只需update所有欄位及insert一筆csv資料,連續做10秒,注意目前def ReadWatchListAll_Out():
2. dataGetter="模擬資料不一定正確,請每次根據現有stock_ref.json的stock_id,產生隨機值,唯 market_no=權重市值排名與stock_id=股號,都是不重複的唯一值,stock_name=股名,decimal=小數位數(由股價決定,含幾位小數,通常為2位,但1000元以上1跳5元) 為固定值,大約都違現有stock_ref.json的值,必要時請自行產生需要的技能
3. 最終方案已確保的核心功能.**自我校驗**：程式執行後須檢查 `stock_ref.json` 欄位結構、CSV檔案是否存在且含表頭數據行數，並輸出 `[PASS] VERIFIED` 或失敗原因。  **強制生成測試資料**： `stock_names.json` ，同時開啟含 ID 的模擬檔（如 2330、1036） **路徑檢查**：確保程式有寫入路徑 `E:\\workspace\\temp\\jsonCsvUpdate.py` ，並在控制台顯示錯誤提示。請從構思到程式碼，之後直接保存完整原始碼，不要有任何敷衍、省略或TODO。
4. 核心變數 SUBSCRIPTION_STATE 請在此基礎上增加新的欄位 , DEFAULT_STOCK_STRUCTURE 最完整"stock_ref.json" 的最終結構必要欄位（可自動擴充不可擅自修改及簡化）
"""

print("="*60)
print("🤖 [GPU 0 - Llama 3.3 70B] 正在架構大型程式系統（32K 上下文模式）...")
print("="*60)

coder_prompt = f"你是頂級軟體架構師。請針對以下複雜需求撰寫完美的、可直接執行的 Python 程式碼，輸出純程式碼區:程式內禁用簡體編碼,並且不准簡化 DEFAULT_STOCK_STRUCTURE{{}} 破壞E:\workspace\temp\stock_ref.json已存在的欄位結構,請直接給出完整的原始碼，不要有任何敷衍、省略或TODO。\n{complex_task}"
code_output, t0 = ask_ollama(PORT_GPU0, "llama3.3:latest", coder_prompt)

print(f"✨ GPU 0 生成完畢！耗時: {t0:.2f} 秒。\n")

# 2. 將 GPU 0 寫出來的龐大代碼，丟給 GPU 1 進行高智商推理審查
print("="*60)
print("🧠 [GPU 1 - DeepSeek-R1 32B] 正在啟動『慢思考推理機制』進行深度審查...")
print("="*60)

validator_prompt = f"""
你是一位極度嚴苛的代碼審查與測試專家。
請仔細檢查以下由其他 AI 產生的 Python 程式碼，確認其是否符合物件導向規範、是否有漏寫任何功能、或者後半段有沒有出現無意義的跳針凑字數(Loop)現象。

程式碼內容：
`E:\\workspace\\temp\\jsonCsvUpdate.py`
程式碼引用的 stock_ref.json,stock_names.json,及產生的 stock.csv,請確認其欄位結構是否正確,並且檢查程式碼是否有邏輯錯誤,或是有任何不合理的地方,請依循你的思考鏈進行推理。
程式執行後會檢查 `stock_ref.json` 欄位結構、CSV檔案是否存在且含表頭數據行數，並輸出 `[PASS] VERIFIED` 及失敗原因。  **強制生成測試資料**： `stock_names.json` ，同時開啟含 ID 的模擬檔（如 2330.csv、其他.csv header及資料同2330.csv） **路徑檢查**：確保程式有寫入 `E:\\workspace\\temp\\jsonCsvUpdate.py` ，並在控制台顯示錯誤提示。請從構思到程式碼，並且直接給出完整的原始碼，不要有任何敷衍、結構省略或TODO。

請依循你的思考鏈進行推理，最終在回答的最後一行：
如果完全沒問題，請給出 'VERDICT: PASS'。
如果發現任何程式錯誤、缺少功能或胡言亂語，請給出 'VERDICT: REJECT 並提示哪裡有問題行號'，並在 `<think>` 標籤外列出修正後的完美程式碼:"jsonCsvUpdate1.py"。
"""

review_output, t1 = ask_ollama(PORT_GPU1, "deepseek-r1:32b", validator_prompt)
print(f"✨ GPU 1 推理完畢！耗時: {t1:.2f} 秒。")
t1 = 1
while (t1):
    # 3. 核心技術：提取並展示 DeepSeek-R1 的內心思考世界
    think_match = re.search(r'<think>(.*?)</think>', review_output, re.DOTALL)
    if think_match:
        think_content = think_match.group(1).strip()
        print("\n--- 💡 獨家揭密：GPU 1 的真實思考鏈 (Chain of Thought) ---")
        print(think_content)
        print("-----------------------------------------------------------\n")

    # 4. 去除思考標籤，印出最終審查結果
    final_report = re.sub(r'<think>.*?</think>', '', review_output, flags=re.DOTALL).strip()
    print("--- 📋 GPU 1 最終審查報告 ---")
    print(final_report)
    print("-----------------------------\n")

    # 5. 自動化決策
    if "VERDICT: PASS" in review_output:
        print("✅ 雙 Agent 達成共識！該複雜 Class 程式碼通過硬體稽核，可直接投入生產環境。")
        t1 = 0
    else:
        
        code_output = "⚠️ 稽核失敗第 " + str(t1) + " 次！DeepSeek-R1 抓到了 Llama 3.3 的漏洞或湊字數行為。請根據審查報告進行修正。"
        print(code_output)
        t1 =t1+1
        if t1 > 3:
            print("❌ 稽核失敗超過 3 次，請與Llama 3.3 建立建立討論細節。")
            code_output="⚠️ 稽核失敗第 " + str(t1) + " 次！DeepSeek-R1 抓到了 Llama 3.3 的漏洞或湊字數行為。請根據審查報告進行修正。"
            code_output, t1 = ask_ollama(PORT_GPU0, "llama3.3:latest",coder_prompt,  code_output )
            break
        elif(t1 > 5):
            print("⚠️ 稽核失敗第 " + str(t1) + " 次！DeepSeek-R1 抓到了 Llama 3.3 的漏洞或湊字數行為。請人工介入，檢查程式碼是否有邏輯錯誤或胡言亂語。")
            break
        else:
            code_output, t1 = ask_ollama(PORT_GPU0, "llama3.3:latest",coder_prompt,  code_output )
        
