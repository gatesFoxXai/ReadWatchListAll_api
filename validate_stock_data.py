import json
import csv
import os
import random

def validate_json_file(json_path):
    """驗證並修復 JSON 文件結構"""  
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 確保每個股票都有完整的字段
    for stock in data:
        required_fields = [
            "symbol", "name", "market_cap",
            "52_week_high", "52_week_low",
            "avg_volume", "price", "change",
            "percent_change"
        ]
        
        # 補充缺失的字段
        for field in required_fields:
            if field not in stock:
                # 生成合理的默認值
                if field == "market_cap":
                    stock[field] = random.randint(10**6, 10**9)
                elif field in ["52_week_high", "52_week_low"]:
                    stock[field] = round(random.uniform(10, 1000), 2)
                elif field == "avg_volume":
                    stock[field] = random.randint(1000, 10**6)
                elif field in ["price", "change"]:
                    stock[field] = round(random.uniform(10, 1000), 2)
                elif field == "percent_change":
                    stock[field] = round(random.uniform(-20, 20), 2)
                else:
                    stock[field] = stock[field] = round(random.uniform(60, 40), 2)
    
    # 寫回文件
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def check_csv_files(csv_folder):
    """檢查並修復所有 CSV 文件格式"""
    csv_files = [f for f in os.listdir(csv_folder) if f.endswith('.csv')]
    
    # 確保所有文件有相同的列頭
    expected_headers = [
        "symbol", "name", "market_cap",
        "52_week_high", "52_week_low",
        "avg_volume", "price", "change",
        "percent_change"
    ]
    
    for csv_file in csv_files:
        file_path = os.path.join(csv_folder, csv_file)
        
        # 讀取文件內容
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            
            # 檢查列頭是否正確
            if headers != expected_headers:
                print(f"修復 CSV 文件格式：{csv_file}")
                
                # 重新生成文件內容
                new_content = []
                new_content.append(expected_headers)
                
                for row in reader:
                    # 確保每行有足夠的字段
                    while len(row) < len(expected_headers):
                        row.append("N/A")
                    
                    new_content.append(row[:len(expected_headers)])
                
                # 寫回文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(new_content)

def simulate_market_data(json_path):
    """模擬現實市場數據"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for stock in data:
        # 確保價格在 52周高低之間
        if "price" not in stock or \
           stock["price"] < stock["52_week_low"] or \
           stock["price"] > stock["52_week_high"]:
            stock["price"] = round(random.uniform(
                stock["52_week_low"], 
                stock["52_week_high"]
            ), 2)
        
        # 確保變化幅度合理
        if "percent_change" not in stock or \
           abs(stock["percent_change"]) > 20:
            stock["percent_change"] = round(random.uniform(-10, 10), 2)
        
        # 確保平均成交量為正數
        if "avg_volume" not in stock or stock["avg_volume"] <= 0:
            stock["avg_volume"] = random.randint(1000, 10**6)
    
    # 寫回文件
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    # 設置工作目錄
    current_folder = os.path.dirname(os.path.abspath(__file__))
    
    # 1. 驗證 JSON 文件結構
    print("開始驗證 JSON 文件結構...")
    json_path = os.path.join(current_folder, "stock_ref.json")
    validate_json_file(json_path)
    print("JSON 文件結構驗證完成！")
    
    # 2. 檢查 CSV 文件格式
    print("\n開始檢查 CSV 文件格式...")
    csv_folder = current_folder
    check_csv_files(csv_folder)
    print("CSV 文件格式檢查完成！")
    
    # 3. 模擬市場數據
    print("\n開始模擬市場數據...")
    simulate_market_data(json_path)
    print("市場數據模擬完成！")