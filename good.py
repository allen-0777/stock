import pandas as pd
import numpy as np

# 取得台灣股市所有股票的資料
df = pd.read_csv("https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL.csv")

# 計算每檔股票的EPS、ROE、P/E、P/B
df['EPS'] = df['EPS'].astype(float)
df['ROE'] = df['ROE'].astype(float)
df['P/E'] = df['P/E'].astype(float)
df['P/B'] = df['P/B'].astype(float)

# 篩選出EPS成長率大於10%，ROE大於15%，P/E小於20，P/B小於2的股票
df = df[(df['EPS_growth'] > 0.1) & (df['ROE'] > 0.15) & (df['P/E'] < 20) & (df['P/B'] < 2)]

# 輸出篩選出來的股票清單
print(df)
