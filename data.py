import streamlit as st
import httpx
import asyncio
import requests
import numpy as np
import pandas as pd
import json
from datetime import date, datetime, timedelta
from io import StringIO
import time
from bs4 import BeautifulSoup

async def fetch_data_async(datestr):
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={datestr}&selectType=ALL&response=json&_=1687956428483"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        return data

@st.cache_data(ttl=3600)
def fetch_data(max_attempts=5):
    now = datetime.now()
    for _ in range(max_attempts):
        datestr = now.strftime("%Y%m%d")
        data = asyncio.run(fetch_data_async(datestr))
        if data.get("total", 1) == 0:
            print(f"No data for date {datestr}, trying the previous day.")
            now -= timedelta(days=1)
            continue
        else:
            df = pd.DataFrame(data["data"], columns=data["fields"])
            return df, now.strftime("%Y-%m-%d")
    return pd.DataFrame(), ""

@st.cache_data(ttl=3600)
def three_data():
    response = httpx.get("https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json")
    data = response.json()
    data_list = data["data"]
    data_date = data["date"]
    df = pd.DataFrame(data_list, columns=data["fields"]).drop(columns=['買進金額', '賣出金額'])
    df['買賣差'] = pd.to_numeric(df['買賣差額'].str.replace(',', ''), errors='coerce') / 1e8
    return df[['單位名稱', '買賣差']], data_date

@st.cache_data(ttl=3600)
def turnover():
    now = datetime.now()
    datestr = now.strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={datestr}&response=json&_=1687090997495"
    response = requests.get(url)
    time.sleep(1)
    data = response.json()
    data_list = data["data"]
    df = pd.DataFrame(data_list, columns=data["fields"])
    df_new = df.drop(['成交股數', '成交筆數','發行量加權股價指數'], axis=1)
    df['成交金額'] = df['成交金額'].astype(str)
    df['成交量'] = df['成交金額'].apply(format_number)
    new_df = df[['日期', '成交量','漲跌點數']].copy()

    return new_df

# @st.cache_data
@st.cache_data(ttl=3600)
def for_buy_sell():
    df, data_date = fetch_data()
    df_for = df[['證券代號','證券名稱','外陸資買賣超股數(不含外資自營商)']].copy()
    df_for['外陸資買賣超股數(不含外資自營商)'] = df_for['外陸資買賣超股數(不含外資自營商)'].str.replace(',', '')
    df_for['外陸資買賣超股數(不含外資自營商)'] = pd.to_numeric(df_for['外陸資買賣超股數(不含外資自營商)'], errors='coerce')
    df_for.rename(columns={'外陸資買賣超股數(不含外資自營商)': '外資買賣超股數'}, inplace=True)
    df_for_all = df_for[df_for['外資買賣超股數'].notna() & (df_for['外資買賣超股數'] != 0)]
    df_for_all = df_for_all.sort_values('外資買賣超股數', ascending=False)
    df_for_all2 = df_for_all.sort_values('外資買賣超股數', ascending=True)
    df_buy_top50 = df_for_all.head(50)
    df_sell_top50 = df_for_all2.head(50)
    return df_for_all, df_buy_top50, df_sell_top50, data_date

# @st.cache_data
@st.cache_data(ttl=3600)
def ib_buy_sell():
    df, data_date = fetch_data()
    df_ib = df[['證券代號','證券名稱','投信買賣超股數']].copy()
    df_ib['投信買賣超股數'] = df_ib['投信買賣超股數'].str.replace(',', '')
    df_ib['投信買賣超股數'] = pd.to_numeric(df_ib['投信買賣超股數'], errors='coerce')
    df_ib_all = df_ib[df_ib['投信買賣超股數'].notna() & (df_ib['投信買賣超股數'] != 0)]
    df_ib_all = df_ib_all.sort_values('投信買賣超股數', ascending=False)
    df_ib_all2 = df_ib_all.sort_values('投信買賣超股數', ascending=True)
    df_buy_top50 = df_ib_all.head(50)
    df_sell_top50 = df_ib_all2.head(50)
    return df_ib_all, df_buy_top50, df_sell_top50, data_date

# @st.cache_data
def for_ib_common():
    df_for_all, _, _, data_date = for_buy_sell()
    df_ib_all, _, _, data_date= ib_buy_sell()
    df_com_buy = pd.merge(df_for_all, df_ib_all, on='證券代號')
    df_com_buy.drop('證券名稱_y', axis=1, inplace=True)
    df_com_buy.rename(columns={'證券名稱_x': '證券名稱', '外陸資買賣超股數(不含外資自營商)': '外資買賣超股數'}, inplace=True)
    df_com_buy = df_com_buy[(df_com_buy['外資買賣超股數'] >= 0) & (df_com_buy['投信買賣超股數'] >= 0)]
    df_com_buy = df_com_buy.sort_values(by='投信買賣超股數', ascending=False)
    return df_com_buy, data_date

def exchange_rate():
    # 先到牌告匯率首頁，爬取所有貨幣的種類
    url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
    resp = requests.get(url)
    resp.encoding = 'utf-8'
    html = BeautifulSoup(resp.text, "lxml")
    rate_table = html.find(name='table', attrs={'title':'牌告匯率'}).find(name='tbody').find_all(name='tr')

    # 擷取匯率表格，把美金(也就是匯率表的第一個元素)擷取出來，查詢其歷史匯率
    currency = rate_table[0].find(name='div', attrs={'class':'visible-phone print_hide'})
    # print(currency.get_text().replace(" ", ""))  # 貨幣種類

    buy_rate = rate_table[0].find(name='td', attrs={'data-table':'本行現金買入'})
    sell_rate = rate_table[0].find(name='td', attrs={'data-table':'本行現金賣出'})
    # print("即時現金買入: %s, 即時現金賣出: %s" % (buy_rate.get_text(), sell_rate.get_text()))
    # 針對美金，找到其「歷史匯率」的首頁 
    history_link = rate_table[0].find(name='td', attrs={'data-table':'歷史匯率'})
    # history_rate_link = "https://rate.bot.com.tw" + history_link.a["href"]  # 該貨幣的歷史資料首頁
    history_rate_link = "https://rate.bot.com.tw/xrt/quote/l6m/USD"
    # print(history_rate_link)

    #
    # 到貨幣歷史匯率網頁，選則該貨幣的「歷史區間」，送出查詢後，觀察其網址變化情形，再試著抓取其歷史匯率資料
    #
    # 用「quote/年-月」去取代網址內容，就可以連到該貨幣的歷史資料
    quote_history_url = history_rate_link.replace("history", "quote/2019-08")
    resp = requests.get(quote_history_url)
    resp.encoding = 'utf-8'
    history = BeautifulSoup(resp.text, "lxml")
    history_table = history.find(name='table', attrs={'title':'歷史本行營業時間牌告匯率'}).find(name='tbody').find_all(name='tr')

    #
    # 擷取到歷史匯率資料後，把資料彙整起來並畫出趨勢圖
    #
    date_history = list()
    history_buy = list()
    history_sell = list()

    for history_rate in history_table:
        # 擷取日期資料
        if history_rate.a is None:
            continue
        
        date_string = history_rate.a.get_text()
        date = datetime.strptime(date_string, '%Y/%m/%d').strftime('%Y/%m/%d')  # 轉換日期格式
        date_history.append(date)  # 日期歷史資料

        history_ex_rate = history_rate.find_all(name='td', attrs={'class':'rate-content-cash text-right print_table-cell'})
        history_buy.append(float(history_ex_rate[0].get_text()))  # 歷史買入匯率
        history_sell.append(float(history_ex_rate[1].get_text()))  # 歷史賣出匯率

        # 將匯率資料建成dataframe形式
    History_ExchangeRate = pd.DataFrame({'date': date_history,
                                        'buy_rate':history_buy,
                                        'sell_rate':history_sell})

    History_ExchangeRate = History_ExchangeRate.set_index('date')  # 指定日期欄位為datafram的index
    History_ExchangeRate = History_ExchangeRate.sort_index(ascending=True)

    # print(History_ExchangeRate)
    return History_ExchangeRate

def futures():
    url = 'https://www.taifex.com.tw/cht/3/futContractsDate'

    # 使用read_html解析
    tables = pd.read_html(url)
    df = tables[2]
    df = df.dropna(how='all', axis=0).dropna(how='all', axis=1)

    # 自訂欄位名稱
    headers = [
        "序號", "商品名稱", "身份別",
        "多方口數", "多方交易契約金額",
        "空方口數", "空方契約金額",
        "多空淨額口數", "多空淨額契約金額",
        "多方未平倉口數", "多方未平倉契約金額",
        "空方未平倉口數", "空方未平倉契約金額",
        "多空淨額未平倉口數", "多空淨額未平倉契約金額"
    ]

    df.columns = headers
    df = df[5:].reset_index(drop=True)

    # 使用新的列名稱進行過濾
    df = df[~df['序號'].str.contains('期貨合計|期貨小計|序 號', na=False)]
    df = df[df['商品名稱'] == '臺股期貨']

    selected_columns = ["多空淨額未平倉口數", "多空淨額未平倉契約金額"]
    df = df.loc[:, selected_columns]

    new_index = ["自營商", "投信", "外資"]
    df.index = new_index
    return df

def format_number(num_str):
    num_str = num_str.replace(",", "")
    num_float = float(num_str)
    num_rounded = round(num_float / 1e8, 1)
    return num_rounded
