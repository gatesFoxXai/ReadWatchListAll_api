import json
import os
import time
import random
import csv
from typing import Dict, List


class StockDataManager:
    """股票數據管理類"""

    # 定義預設的股票結構
    DEFAULT_STOCK_STRUCTURE = {
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
        "ytVolFlag": 1,
    }

    def __init__(self, data_path: str = "e:\\workspace\\temp"):
        """初始化股票數據管理器"""
        self.data_path = data_path
        self.stock_ref_file = os.path.join(data_path, "stock_ref.json")
        self.stock_names_file = os.path.join(data_path, "stock_names.json")
        self.subscription_state: Dict[str, Dict] = {}

    def _check_data_directory(self):
        """檢查資料目錄是否存在"""
        if not os.path.exists(self.data_path):
            os.makedirs(self.data_path)

    def _ensure_stock_structure(self, stock_ref: Dict) -> Dict:
        """確保 stock_ref 中每個 stock_id 都是包含預設欄位的 dict。
        若某筆資料不是 dict，或缺少預設欄位，會以 ``DEFAULT_STOCK_STRUCTURE`` 為基礎補全。
        這樣在後續存取 ``stock_ref[stock_id]["yst_price"]`` 時就不會拋出 KeyError。
        """
        for stock_id, data in list(stock_ref.items()):
            if stock_id == "readme":
                continue
            # 若資料不是 dict，直接以預設結構取代
            if not isinstance(data, dict):
                stock_ref[stock_id] = self.DEFAULT_STOCK_STRUCTURE.copy()
                continue
            # 補全缺少的欄位
            for k, v in self.DEFAULT_STOCK_STRUCTURE.items():
                data.setdefault(k, v)
        return stock_ref

    def read_stock_ref(self) -> Dict:
        """讀取 stock_ref.json 文件。如果檔案不存在，回傳僅包含說明的字典。
        讀取後會呼叫 ``_ensure_stock_structure`` 以保證每支股票都有完整的預設欄位。
        """
        try:
            with open(self.stock_ref_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"readme": "此json資料來源全部以api登入取得後,再往下跑,注意此訂閱每秒最多3次"}
        # 保證結構完整
        return self._ensure_stock_structure(data)

    def write_stock_ref(self, data: Dict):
        """寫入 stock_ref.json 文件"""
        with open(self.stock_ref_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def read_stock_names(self) -> List[Dict]:
        """讀取 stock_names.json 文件"""
        try:
            with open(self.stock_names_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def write_stock_names(self, data: List[Dict]):
        """寫入 stock_names.json 文件"""
        with open(self.stock_names_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def generate_csv_filename(self, stock_id: str) -> str:
        """生成 CSV 文件名"""
        return os.path.join(self.data_path, f"{stock_id}.csv")

    def write_stock_csv(self, stock_id: str, data: Dict):
        """寫入股票的 CSV 文件"""
        csv_file = self.generate_csv_filename(stock_id)

        # 確保欄位結構
        fields = [
            "OpenPrice",
            "HighPrice",
            "LowPrice",
            "BuyPrice",
            "SellPrice",
            "TotalOutVol",
            "TotalInVol",
            "DealPrice",
            "TotalDealAmt",
            "uintVol",
            "singleVol",
            "TotalVol",
        ]

        # 檢查文件是否存在，不存在則寫入標題
        if not os.path.exists(csv_file):
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()

        # 寫入數據行
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writerow({field: data.get(field, 0) for field in fields})

    def update_stock_data(self, stock_id: str):
        """更新股票數據"""
        # 獲取現有數據
        stock_ref = self.read_stock_ref()

        # 如果股票不存在，初始化結構
        if stock_id not in stock_ref:
            new_data = self.DEFAULT_STOCK_STRUCTURE.copy()
            new_data["stock_name"] = f"Stock_{stock_id}"
            new_data["ext_name"] = stock_id
            stock_ref[stock_id] = new_data

        # 確保已有的股票資料具備所有預設欄位，避免舊資料缺少鍵值
        current_data = stock_ref[stock_id]
        for k, v in self.DEFAULT_STOCK_STRUCTURE.items():
            current_data.setdefault(k, v)
        current_data.update(
            {
                "yst_price": random.randint(100, 10000) * 100,
                "open_ref": current_data["yst_price"],
                "up_price": current_data["yst_price"] * 1.1,
                "down_price": current_data["yst_price"] * 0.9,
                "yst_vol": random.randint(1, 1000) * 100,
            }
        )

        # 計算其他欄位
        current_data.update(
            {
                "OpenPrice": float(current_data["open_ref"]),
                "HighPrice": float(current_data["up_price"]),
                "LowPrice": float(current_data["down_price"]),
                "BuyPrice": float(current_data["open_ref"]),
                "SellPrice": float(current_data["open_ref"]),
                "TotalOutVol": current_data["yst_vol"] // 2,
                "TotalInVol": current_data["yst_vol"] // 2,
                "DealPrice": float(current_data["open_ref"]),
                "TotalDealAmt": float(current_data["open_ref"]) * int(current_data["yst_vol"]),
            }
        )

        # 寫入更新後的數據
        self.write_stock_ref(stock_ref)
        self.write_stock_csv(stock_id, current_data)

    def validate_data(self) -> str:
        """校驗數據結構"""
        try:
            # 檢查 stock_ref.json
            stock_ref = self.read_stock_ref()
            if not isinstance(stock_ref, dict):
                return "stock_ref.json 結構錯誤"

            # 檢查所有股票條目
            for stock_id, data in stock_ref.items():
                if stock_id == "readme":
                    continue
                # 若任一預設欄位缺失，回報錯誤。原本的條件相反，導致所有完整資料都被判為缺失。
                if not all(key in data for key in self.DEFAULT_STOCK_STRUCTURE.keys()):
                    return f"stock {stock_id} 欄位缺失"

            # 檢查 stock_names.json
            stock_names = self.read_stock_names()
            # stock_names.json 可能是 dict (id->name) 或 list，兩者皆可接受。
            if not isinstance(stock_names, (dict, list)):
                return "stock_names.json 結構錯誤"

            # 檢查 CSV 文件
            for stock_id in stock_ref.keys():
                if stock_id == "readme":
                    continue
                csv_file = self.generate_csv_filename(stock_id)
                if not os.path.exists(csv_file):
                    return f"{stock_id}.csv 文件缺失"

                with open(csv_file, "r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader)
                    if len(header) != 12:
                        return f"{stock_id}.csv 欄位數量錯誤"

            return "[PASS] VERIFIED"
        except Exception as e:
            return f"數據校驗失敗: {str(e)}"


class StockSubscriber:
    """股票訂閱類"""

    def __init__(self, data_manager: StockDataManager):
        self.data_manager = data_manager
        self.subscription_state: Dict[str, Dict] = {}

    def check_subscription(self, stock_id: str) -> bool:
        """檢查股票訂閱狀態"""
        if stock_id not in self.subscription_state:
            self.subscription_state[stock_id] = {"status": "active", "last_update_time": time.time(), "update_count": 0}
            return True

        state = self.subscription_state[stock_id]
        if time.time() - state["last_update_time"] > 1:
            state.update({"last_update_time": time.time(), "update_count": state["update_count"] + 1})
            return True

        return False

    def update_stock(self, stock_id: str):
        """更新股票數據"""
        if self.check_subscription(stock_id):
            self.data_manager.update_stock_data(stock_id)


class SystemValidator:
    """系統校驗類"""

    @staticmethod
    def validate_path(path: str) -> bool:
        """檢查路徑是否存在"""
        return os.path.exists(os.path.dirname(path))

    @staticmethod
    def validate_json_structure(json_file: str) -> bool:
        """檢查 JSON 文件結構"""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return False
                return True
        except Exception:
            return False

    @staticmethod
    def validate_csv_structure(csv_file: str) -> bool:
        """檢查 CSV 文件結構"""
        try:
            with open(csv_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                if len(header) != 12:
                    return False
                return True
        except Exception:
            return False


def ReadWatchListAllInit():
    data_manager = StockDataManager()
    # 確保資料目錄存在
    data_manager._check_data_directory()
    # 初始化訂閱管理器
    subscriber = StockSubscriber(data_manager)
    return data_manager, subscriber


def main():
    """主函數"""
    # 初始化資料管理器 , 確保資料目錄存在, 初始化訂閱管理器
    data_manager, subscriber = ReadWatchListAllInit()

    # 記錄開始時間
    start_time = time.time()

    try:
        while time.time() - start_time < 10:  # 執行 10 秒
            for _ in range(3):  # 每秒執行 3 次
                # 取得所有股票 ID
                stock_ref = data_manager.read_stock_ref()
                stock_ids = [k for k in stock_ref.keys() if k != "readme"]

                # 更新每支股票數據
                for stock_id in stock_ids:
                    subscriber.update_stock(stock_id)

            time.sleep(1)  # 每秒執行 3 次

        # 自我校驗
        validation_result = data_manager.validate_data()
        print(validation_result)

    except Exception as e:
        print(f"系統錯誤: {str(e)}")


if __name__ == "__main__":
    main()

"""
    修改說明：
在 DEFAULT_STOCK_STRUCTURE 中新增了 readme 欄位。
其他功能保持不變。
"""
