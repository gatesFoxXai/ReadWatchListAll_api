\# Markdown 中正確顯示 Windows 路徑的技巧



\## 為什麼會只看到一個 `\\`？



| 寫法 | 顯示結果 |

|------|----------|

| `C:\\Users\\user\\.vscode`（普通文字） | \*\*C:\\Users\\user\\.vscode\*\* |

| ``C\\\\Users\\\\user\\\\.vscode``（行內程式碼） | \*\*C:\\Users\\user\\.vscode\*\* |

| ```\\nC\\\\Users\\\\user\\\\.vscode\\n```（程式碼區塊） | \*\*C\\\\Users\\\\user\\\\.vscode\*\*（保留兩個 `\\`） |



\## 使用說明（自動產生範例）



以下 Python 程式會根據你提供的 Windows 路徑，產生三種常見的 Markdown 表示方式，直接貼到文件裡即可。



```python

\# ------------------------------------------------------------

\# markdown\_backslash\_helper.py

\# ------------------------------------------------------------

\# 目的：產生在 Markdown 中正確顯示 Windows 路徑的範例文字

\# ------------------------------------------------------------



def generate\_markdown\_examples(win\_path: str) -> str:

&#x20;   """

&#x20;   依傳入的 Windows 路徑，回傳一段完整的 Markdown 範例文字。

&#x20;   會自動把單一反斜線、雙反斜線、以及程式碼區塊三種寫法全部列出。



&#x20;   範例：

&#x20;       win\_path = r"C:\\\\Users\\\\user\\\\.vscode"

&#x20;   """

&#x20;   # 1. 普通文字（直接寫入）

&#x20;   normal = f"`{win\_path.replace('\\\\\\\\', '\\\\')}`"



&#x20;   # 2. 行內程式碼（使用 `` 包住，必須寫成雙反斜線）

&#x20;   inline\_code = f"``{win\_path}``"



&#x20;   # 3. 程式碼區塊（保留雙反斜線）

&#x20;   code\_block = f"```\\n{win\_path}\\n```"



&#x20;   md = (

&#x20;       "## 範例：在 Markdown 中顯示 Windows 路徑\\n\\n"

&#x20;       f"- 普通文字：{normal}\\n"

&#x20;       f"- 行內程式碼：{inline\_code}\\n"

&#x20;       f"- 程式碼區塊：\\n{code\_block}\\n"

&#x20;   )

&#x20;   return md





if \_\_name\_\_ == "\_\_main\_\_":

&#x20;   sample\_path = r"C:\\\\Users\\\\user\\\\.vscode"

&#x20;   print(generate\_markdown\_examples(sample\_path))
