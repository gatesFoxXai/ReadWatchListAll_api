#MACD Parameter Optimization Myths
#Many investors, after adjusting MACD parameters, seem to feel that the data better suits their trading habits, and thus yearn to find the optimal MACD parameters. In reality, this idea easily leads investors to become dependent on MACD because different markets and timeframes vary greatly, and a single parameter can hardly clearly represent market trends in all markets.
#MACD can not only be used to capture trend momentum, but also to determine whether the market is about to reverse.
#For the MACD fast/slow parameter group, choose one. A MACD indicator (Moving Average Convergence/Divergence) is considered a sell signal when the slow line crosses above the fast line (death cross). A golden cross when the MACD line crosses above the signal line is a potential buy signal. Bottom divergence and top divergence, also called bullish and bearish divergence, indicate that the price may gradually correct itself.

## 快速開始

### 1. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 2. 執行程式

```bash
python3 macdbollng.py
```

執行後會顯示圖表視窗。

## 功能
- 預設default_12_26_9 繪製csv檔的標準算法計算macd, 可用key chosen_key = "default_12_26_9"選擇要用的組合
- 上方繪製csv檔依指定顏色的布林帶參數畫出折現圖
- 下方繪製csv檔依指定顏色的macd柱狀圖高度,MACD線（DIF，快線）
- 為x 軸日期美化,每隨標註一次


## 資料
新增以天為單位的可控變數 N_DAYS = 60
考考 `2317.csv` 中的資料：使用pandas as pd 取最近 6 個月資料,改成取最近N_DAYS資料

```python
共用 x 軸，時間同步
上圖：收盤價 + 布林帶 + 布林帶寬(次軸)
下圖：MACD
```

## 調整樣式
共用x軸,日期美化,每個月標註一次

目前可調參數為：
macd_param_sets = {
    "default_12_26_9": (12, 26, 9), #標準預設參數,12 (快線/Short-term EMA): 計算DIF線的短期平均週期（反映短期動能）。
    "3_10_16": (3, 10, 16),
    "5_13_4": (5, 13, 4),
    "8_17_6": (8, 17, 6), #高波動市場8-17-9反應較快，但雜訊較多,適合外匯 1 小時圖、波動稍大的市場12-26-9穩定度最高，
    "19_39_9": (19, 39, 9), #19-39-9偏向中長週期，能有效過濾大部分雜訊
    "5_35_5": (5, 35, 5), #靈敏度穩定性適用情境5-35-5反應最快，雜訊最多，容易捕捉短期趨勢★★★★★★☆☆☆☆適合短線交易者
    "5_13-8": (5,13,8),
    "6-19-9":(6,19,9)    #短線交易 (更敏感): 例如使用 (5, 13, 8) 或 (6, 19, 9)，適用於高頻率交易，能更快發現趨勢反轉但假訊號較多。
}

# 可選擇要用的組合 key
chosen_key = "default_12_26_9"
#根據要計算查詢的資料來源
csv_file = "2317.csv"

#修改bug
1.為了便於bug修改及後續整合,請N_DAYS = 60 # X 軸刻度間隔：每交易日的 N 天,取代
six_months_ago = max_date - pd.DateOffset(months=6) 改成 one_months_ago = max_date - pd.DateOffset(days=N_DAYS)
如此更方便debug
2.將時間的空白空間移出macd的時間軸,可能因plot會自作主張填補數字空白,或許改用排序後的index間接作為x軸.於顯示時再間接印出yy/MM/DD
3. fig, (ax_price, ax_macd) = plt.subplots(2, 1 ....修改成fig, (ax_price, ax_macd) = plt.subplots(3, 1
4. 在第3個subplots 增加kdj功能 , 要求如下
Please integrate and encapsulate MACDBolling and KDJ, and add another KDJ indicator at the bottom, dividing the screen into upper, middle, and lower sections. The default parameters are typically used to determine short-term buy and sell points, but are quite sensitive. In practice, commonly used parameter adjustments are to increase sensitivity, or reduce false signals. The general principle is:
Overbought conditions warrant caution against pullbacks; oversold conditions present opportunities for rebounds.
KDJ Parameter Setting and Adjustment Suggestions

System Default 9,3,3
Suitable for most markets, with frequent fluctuations and many false signals.
Sensitive 5,3,3
Suitable for short-term trading; the indicator is faster, but there are more false signals, requiring the use of other indicators.
Conservative 8,5,3 Or
18,3,3 reduces noise and provides more stable signals, suitable for medium- to short-term traders.

5.Encapsulate into a class
Encapsulate this into a class `cStock` that inherits from `BasicUnit` for easier stock and time management. Try changing the input
data from `2317.csv` to `2317.TW` to easily retrieve the company name: 鴻海. Then, fill in the appropriate parameters of `BasicUnit`,
including at least `2317.TW` and `鴻海`, such as `fullname` or `name`. Importantly, our `BasicUnit` can be month, week, day, hour, minute, or second.
