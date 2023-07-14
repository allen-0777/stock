import streamlit as st
import requests
import numpy as np
import pandas as pd
import json
from datetime import date, datetime, timedelta
from io import StringIO
import time

# def data():
#     # 打算要取得的股票代碼
#     stock_list_tse = ['0050', '0056', '2330', '2317','2303','2002']
#     stock_list_otc = ['6547', '6180']
        
#     # 組合API需要的股票清單字串
#     stock_list1 = '|'.join('tse_{}.tw'.format(stock) for stock in stock_list_tse) 

#     # 6字頭的股票參數不一樣
#     stock_list2 = '|'.join('otc_{}.tw'.format(stock) for stock in stock_list_otc) 
#     stock_list = stock_list1 + '|' + stock_list2
#     # print(stock_list)
#     #　組合完整的URL
#     query_url = f'http://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={stock_list}'
#     time.sleep(5)
    
#     # 呼叫股票資訊API
#     response1 = requests.get(query_url)

#     # 將回傳的JSON格式資料轉成Python的dictionary
#     data = json.loads(response1.text)
#     # 過濾出有用到的欄位
#     columns = ['c','n','z','tv','v','o','h','l','y', 'tlong']
#     df = pd.DataFrame(data['msgArray'], columns=columns)
#     df.columns = ['股票代號','公司簡稱','成交價','成交量','累積成交量','開盤價','最高價','最低價','昨收價', '資料更新時間']
#     return df

# @st.cache_data
def get_data(max_attempts=5):
    # 獲取今天的日期
    now = datetime.now()
    # 格式化日期
    for _ in range(max_attempts):
        datestr = now.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={datestr}&selectType=ALL&response=json&_=1687956428483"
        response = requests.get(url)
        data = response.json()
        time.sleep(2)
        if data.get("total", 1) == 0:
            print(f"No data for date {datestr}, trying the previous day.")
            now -= timedelta(days=1)
            continue
        else:
            df = pd.DataFrame(data["data"], columns=data["fields"])
            break  # 成功获取数据后跳出循环
    return df

# @st.cache_data
def three_data():
    # 發送GET請求到URL並獲取JSON回應
    response = requests.get("https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&_=1687055087413")
    time.sleep(5)
    # 將JSON回應轉換成Python字典
    data = response.json()

    # 從字典中取出"data"鍵的值，該值是一個二維列表
    data_list = data["data"]

    # 將二維列表轉換成pandas DataFrame
    df = pd.DataFrame(data_list, columns=data["fields"])
    df_new = df.drop(['買進金額', '賣出金額'], axis=1)
    df['買賣差額'] = df['買賣差額'].astype(str)

    # Apply the function to the '買賣差額' column
    df['買賣差'] = df['買賣差額'].apply(format_number)

    # Create a new DataFrame
    new_df = df[['單位名稱', '買賣差']].copy()

    # 顯示DataFrame
    # print(df)
    return new_df

# @st.cache_data
def turnover():
    now = datetime.now()
    datestr = now.strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={datestr}&response=json&_=1687090997495"
    response = requests.get(url)
    # 將JSON回應轉換成Python字典
    time.sleep(2)
    data = response.json()

    # 從字典中取出"data"鍵的值，該值是一個二維列表
    data_list = data["data"]

    # 將二維列表轉換成pandas DataFrame
    df = pd.DataFrame(data_list, columns=data["fields"])
    df_new = df.drop(['成交股數', '成交筆數','發行量加權股價指數'], axis=1)
    df['成交金額'] = df['成交金額'].astype(str)

    # Apply the function to the '買賣差額' column
    df['成交量'] = df['成交金額'].apply(format_number)

    # Create a new DataFrame
    new_df = df[['日期', '成交量','漲跌點數']].copy()

    return new_df

# @st.cache_data
def for_buy_sell():
    df = get_data()
    df_for = df[['證券代號','證券名稱','外陸資買賣超股數(不含外資自營商)']].copy()
    df_for['外陸資買賣超股數(不含外資自營商)'] = df_for['外陸資買賣超股數(不含外資自營商)'].str.replace(',', '')
    df_for['外陸資買賣超股數(不含外資自營商)'] = pd.to_numeric(df_for['外陸資買賣超股數(不含外資自營商)'], errors='coerce')
    df_for_all = df_for[df_for['外陸資買賣超股數(不含外資自營商)'].notna() & (df_for['外陸資買賣超股數(不含外資自營商)'] != 0)]
    df_for_all = df_for_all.sort_values('外陸資買賣超股數(不含外資自營商)', ascending=False)
    df_for_all2 = df_for_all.sort_values('外陸資買賣超股數(不含外資自營商)', ascending=True)
    df_buy_top50 = df_for_all.head(50)
    df_sell_top50 = df_for_all2.head(50)
    return df_for_all, df_buy_top50, df_sell_top50

# @st.cache_data
def ib_buy_sell():
    df = get_data()
    df_ib = df[['證券代號','證券名稱','投信買賣超股數']].copy()
    df_ib['投信買賣超股數'] = df_ib['投信買賣超股數'].str.replace(',', '')
    df_ib['投信買賣超股數'] = pd.to_numeric(df_ib['投信買賣超股數'], errors='coerce')
    df_ib_all = df_ib[df_ib['投信買賣超股數'].notna() & (df_ib['投信買賣超股數'] != 0)]
    df_ib_all = df_ib_all.sort_values('投信買賣超股數', ascending=False)
    df_ib_all2 = df_ib_all.sort_values('投信買賣超股數', ascending=True)
    df_buy_top50 = df_ib_all.head(50)
    df_sell_top50 = df_ib_all2.head(50)
    return df_ib_all, df_buy_top50, df_sell_top50

# @st.cache_data
def for_ib_common():
    df_for_all, _, _ = for_buy_sell()
    df_ib_all, _, _ = ib_buy_sell()
    # _, _, df_sell_top50_1 = for_buy_sell()
    # _, _, df_sell_top50_2, = ib_buy_sell()
    # 使用"證券代號"列合并两个DataFrame
    df_com_buy = pd.merge(df_for_all, df_ib_all, on='證券代號')
    df_com_buy.drop('證券名稱_y', axis=1, inplace=True)
    df_com_buy.rename(columns={'證券名稱_x': '證券名稱'}, inplace=True)
    df_com_buy = df_com_buy[(df_com_buy['外陸資買賣超股數(不含外資自營商)'] >= 0) & (df_com_buy['投信買賣超股數'] >= 0)]
    df_com_buy = df_com_buy.sort_values(by='投信買賣超股數', ascending=False)
    return df_com_buy

def format_number(num_str):
    # remove commas
    num_str = num_str.replace(",", "")

    # convert to float
    num_float = float(num_str)

    # divide by 10^8, round to 1 decimal place
    num_rounded = round(num_float / 1e8, 1)

    return num_rounded