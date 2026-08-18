import json
import os


def verify_json_file(file_path):
    try:
        # 使用UTF-8編碼讀取文件
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        print("JSON文件驗證成功！")
        return True

    except json.JSONDecodeError as e:
        print(f"JSON格式錯誤: {e}")
        return False

    except UnicodeDecodeError:
        print("文件編碼錯誤，請確保文件使用UTF-8編碼。")
        return False

    except FileNotFoundError:
        print("指定的JSON文件不存在。")
        return False

    except Exception as e:
        print(f"讀取文件時出錯: {e}")
        return False


if __name__ == "__main__":
    # 指定要驗證的文件路徑
    file_path = "stock_ref.json"

    if os.path.exists(file_path):
        verify_json_file(file_path)
    else:
        print(f"找不到文件：{file_path}")
