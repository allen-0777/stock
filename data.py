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
import warnings
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple, List, Dict, Any, Optional
import yfinance as yf

# 忽略不安全請求的警告
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# 共用的 HTTP 請求函數，增加重試機制
def make_request(url: str, max_retries: int = 3, backoff_factor: float = 0.5) -> requests.Response:
    """帶有重試機制的 HTTP 請求函數
    
    Args:
        url: 請求的 URL
        max_retries: 最大重試次數
        backoff_factor: 重試延遲因子
        
    Returns:
        HTTP 響應對象
    """
    for i in range(max_retries):
        try:
            response = requests.get(url, verify=False, timeout=10)
            response.raise_for_status()  # 如果響應包含錯誤代碼則拋出異常
            return response
        except requests.RequestException as e:
            if i == max_retries - 1:  # 最後一次重試
                print(f"獲取數據失敗: {url}, 錯誤: {e}")
                raise
            wait_time = backoff_factor * (2 ** i)  # 指數退避策略
            time.sleep(wait_time)

async def fetch_data_async(datestr):
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={datestr}&selectType=ALL&response=json&_=1687956428483"
    for _ in range(3):  # 最多重試 3 次
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                response = await client.get(url)
                response.raise_for_status()  # 檢查響應狀態碼
                data = response.json()
                return data
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            print(f"非同步請求失敗: {url}, 錯誤: {e}, 稍後重試...")
            await asyncio.sleep(1)  # 重試前等待 1 秒
    
    # 如果所有重試都失敗，返回空數據結構
    return {"data": [], "fields": [], "total": 0}

@st.cache_data(ttl=3600)
def fetch_data(max_attempts=5) -> Tuple[pd.DataFrame, str]:
    """獲取股票數據，帶有日期回退機制和錯誤處理
    
    Returns:
        DataFrame: 股票數據
        str: 數據日期
    """
    now = datetime.now()
    for attempt in range(max_attempts):
        try:
            datestr = now.strftime("%Y%m%d")
            data = asyncio.run(fetch_data_async(datestr))
            
            if data.get("total", 1) == 0 or not data.get("data"):
                print(f"日期 {datestr} 沒有數據，嘗試前一天。")
                now -= timedelta(days=1)
                continue
            
            df = pd.DataFrame(data["data"], columns=data["fields"])
            return df, now.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"獲取數據時出錯: {e}, 嘗試前一天數據。")
            now -= timedelta(days=1)
    
    # 如果所有嘗試都失敗，返回空 DataFrame
    print("警告：所有數據獲取嘗試都失敗了")
    return pd.DataFrame(), ""

@st.cache_data(ttl=3600)
def three_data() -> Tuple[pd.DataFrame, str]:
    """獲取三大法人數據
    
    Returns:
        DataFrame: 三大法人數據
        str: 數據日期
    """
    try:
        response = httpx.get("https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json", verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("data"):
            print("警告：三大法人數據為空")
            # 返回空的 DataFrame 但保持正確的結構
            return pd.DataFrame(columns=['單位名稱', '買賣差']), data.get("date", "")
        
        data_list = data["data"]
        data_date = data["date"]
        df = pd.DataFrame(data_list, columns=data["fields"]).drop(columns=['買進金額', '賣出金額'])
        df['買賣差'] = pd.to_numeric(df['買賣差額'].str.replace(',', ''), errors='coerce') / 1e8
        return df[['單位名稱', '買賣差']], data_date
    except Exception as e:
        print(f"獲取三大法人數據時出錯: {e}")
        # 返回空的 DataFrame
        return pd.DataFrame(columns=['單位名稱', '買賣差']), ""

@st.cache_data(ttl=3600)
def turnover() -> pd.DataFrame:
    """獲取成交量數據
    
    Returns:
        DataFrame: 成交量數據
    """
    try:
        now = datetime.now()
        datestr = now.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={datestr}&response=json&_=1687090997495"
        
        response = make_request(url)
        data = response.json()
        
        if not data.get("data"):
            print("警告：成交量數據為空")
            return pd.DataFrame(columns=['日期', '成交量', '漲跌點數'])
        
        data_list = data["data"]
        df = pd.DataFrame(data_list, columns=data["fields"])
        df_new = df.drop(['成交股數', '成交筆數','發行量加權股價指數'], axis=1)
        df['成交金額'] = df['成交金額'].astype(str)
        df['成交量'] = df['成交金額'].apply(format_number)
        new_df = df[['日期', '成交量','漲跌點數']].copy()

        return new_df
    except Exception as e:
        print(f"獲取成交量數據時出錯: {e}")
        return pd.DataFrame(columns=['日期', '成交量', '漲跌點數'])

@st.cache_data(ttl=3600)
def for_buy_sell() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """獲取外資買賣超數據
    
    Returns:
        DataFrame: 所有外資買賣超數據
        DataFrame: 外資買超前 50
        DataFrame: 外資賣超前 50
        str: 數據日期
    """
    try:
        df, data_date = fetch_data()
        
        if df.empty:
            # 如果沒有數據，返回空的 DataFrame
            empty_df = pd.DataFrame(columns=['證券代號', '證券名稱', '外資買賣超股數'])
            return empty_df, empty_df, empty_df, data_date
        
        df_for = df[['證券代號','證券名稱','外陸資買賣超股數(不含外資自營商)']].copy()
        df_for['外陸資買賣超股數(不含外資自營商)'] = df_for['外陸資買賣超股數(不含外資自營商)'].str.replace(',', '')
        df_for['外陸資買賣超股數(不含外資自營商)'] = pd.to_numeric(df_for['外陸資買賣超股數(不含外資自營商)'], errors='coerce')
        df_for.rename(columns={'外陸資買賣超股數(不含外資自營商)': '外資買賣超股數'}, inplace=True)
        df_for_all = df_for[df_for['外資買賣超股數'].notna() & (df_for['外資買賣超股數'] != 0)]
        
        # 使用 copy() 避免 SettingWithCopyWarning
        df_for_all = df_for_all.copy()
        
        # 排序和獲取前 50 名
        df_for_all_buy = df_for_all.sort_values('外資買賣超股數', ascending=False).copy()
        df_for_all_sell = df_for_all.sort_values('外資買賣超股數', ascending=True).copy()
        df_buy_top50 = df_for_all_buy.head(50)
        df_sell_top50 = df_for_all_sell.head(50)
        
        return df_for_all, df_buy_top50, df_sell_top50, data_date
    except Exception as e:
        print(f"獲取外資買賣超數據時出錯: {e}")
        # 返回空的 DataFrame
        empty_df = pd.DataFrame(columns=['證券代號', '證券名稱', '外資買賣超股數'])
        return empty_df, empty_df, empty_df, ""

@st.cache_data(ttl=3600)
def ib_buy_sell() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """獲取投信買賣超數據
    
    Returns:
        DataFrame: 所有投信買賣超數據
        DataFrame: 投信買超前 50
        DataFrame: 投信賣超前 50
        str: 數據日期
    """
    try:
        df, data_date = fetch_data()
        
        if df.empty:
            # 如果沒有數據，返回空的 DataFrame
            empty_df = pd.DataFrame(columns=['證券代號', '證券名稱', '投信買賣超股數'])
            return empty_df, empty_df, empty_df, data_date
            
        df_ib = df[['證券代號','證券名稱','投信買賣超股數']].copy()
        df_ib['投信買賣超股數'] = df_ib['投信買賣超股數'].str.replace(',', '')
        df_ib['投信買賣超股數'] = pd.to_numeric(df_ib['投信買賣超股數'], errors='coerce')
        df_ib_all = df_ib[df_ib['投信買賣超股數'].notna() & (df_ib['投信買賣超股數'] != 0)].copy()
        
        # 排序和獲取前 50 名
        df_ib_all_buy = df_ib_all.sort_values('投信買賣超股數', ascending=False).copy()
        df_ib_all_sell = df_ib_all.sort_values('投信買賣超股數', ascending=True).copy()
        df_buy_top50 = df_ib_all_buy.head(50)
        df_sell_top50 = df_ib_all_sell.head(50)
        
        return df_ib_all, df_buy_top50, df_sell_top50, data_date
    except Exception as e:
        print(f"獲取投信買賣超數據時出錯: {e}")
        # 返回空的 DataFrame
        empty_df = pd.DataFrame(columns=['證券代號', '證券名稱', '投信買賣超股數'])
        return empty_df, empty_df, empty_df, ""

@st.cache_data(ttl=3600)
def for_ib_common() -> Tuple[pd.DataFrame, str]:
    """獲取外資和投信同時買超的股票
    
    Returns:
        DataFrame: 外資投信同買股票
        str: 數據日期
    """
    try:
        df_for_all, _, _, data_date = for_buy_sell()
        df_ib_all, _, _, _ = ib_buy_sell()
        
        if df_for_all.empty or df_ib_all.empty:
            # 如果任一數據為空，返回空的 DataFrame
            return pd.DataFrame(columns=['證券代號', '證券名稱', '外資買賣超股數', '投信買賣超股數']), data_date
            
        # 合併數據
        df_com_buy = pd.merge(df_for_all, df_ib_all, on='證券代號', how='inner')
        
        # 處理合併後的列名
        if '證券名稱_x' in df_com_buy.columns and '證券名稱_y' in df_com_buy.columns:
            df_com_buy.drop('證券名稱_y', axis=1, inplace=True)
            df_com_buy.rename(columns={'證券名稱_x': '證券名稱'}, inplace=True)
        
        if '外陸資買賣超股數(不含外資自營商)' in df_com_buy.columns:
            df_com_buy.rename(columns={'外陸資買賣超股數(不含外資自營商)': '外資買賣超股數'}, inplace=True)
            
        # 篩選外資和投信同時買超的股票
        df_com_buy = df_com_buy[(df_com_buy['外資買賣超股數'] > 0) & (df_com_buy['投信買賣超股數'] > 0)]
        df_com_buy = df_com_buy.sort_values(by='投信買賣超股數', ascending=False)
        
        return df_com_buy, data_date
    except Exception as e:
        print(f"獲取外資投信同買數據時出錯: {e}")
        # 返回空的 DataFrame
        return pd.DataFrame(columns=['證券代號', '證券名稱', '外資買賣超股數', '投信買賣超股數']), ""

@st.cache_data(ttl=3600)
def exchange_rate() -> pd.DataFrame:
    """獲取匯率數據
    
    Returns:
        DataFrame: 匯率歷史數據
    """
    try:
        # 先到牌告匯率首頁，爬取所有貨幣的種類
        url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
        resp = make_request(url)
        resp.encoding = 'utf-8'
        html = BeautifulSoup(resp.text, "lxml")
        rate_table = html.find(name='table', attrs={'title':'牌告匯率'})
        
        if not rate_table:
            print("警告：匯率表格未找到")
            # 返回空的 DataFrame 但保持正確的結構
            return pd.DataFrame(columns=['buy_rate', 'sell_rate'])
            
        rate_table = rate_table.find(name='tbody').find_all(name='tr')
        
        if not rate_table:
            print("警告：匯率表格行未找到")
            return pd.DataFrame(columns=['buy_rate', 'sell_rate'])

        # 直接使用美金匯率歷史資料的 URL
        history_rate_link = "https://rate.bot.com.tw/xrt/quote/l6m/USD"
        
        resp = make_request(history_rate_link)
        resp.encoding = 'utf-8'
        history = BeautifulSoup(resp.text, "lxml")
        history_table = history.find(name='table', attrs={'title':'歷史本行營業時間牌告匯率'})
        
        if not history_table:
            print("警告：歷史匯率表格未找到")
            return pd.DataFrame(columns=['buy_rate', 'sell_rate'])
            
        history_table = history_table.find(name='tbody').find_all(name='tr')
        
        if not history_table:
            print("警告：歷史匯率表格行未找到")
            return pd.DataFrame(columns=['buy_rate', 'sell_rate'])

        # 擷取歷史匯率數據
        date_history = []
        history_buy = []
        history_sell = []

        for history_rate in history_table:
            # 擷取日期資料
            if history_rate.a is None:
                continue
            
            date_string = history_rate.a.get_text()
            date = datetime.strptime(date_string, '%Y/%m/%d').strftime('%Y/%m/%d')  # 轉換日期格式
            date_history.append(date)  # 日期歷史資料

            history_ex_rate = history_rate.find_all(name='td', attrs={'class':'rate-content-cash text-right print_table-cell'})
            if len(history_ex_rate) >= 2:
                try:
                    history_buy.append(float(history_ex_rate[0].get_text()))  # 歷史買入匯率
                    history_sell.append(float(history_ex_rate[1].get_text()))  # 歷史賣出匯率
                except (ValueError, IndexError) as e:
                    print(f"解析匯率數據時出錯: {e}")
                    continue

        # 如果沒有獲取到任何數據，返回空的 DataFrame
        if not date_history:
            print("警告：未獲取到任何匯率歷史數據")
            return pd.DataFrame(columns=['buy_rate', 'sell_rate'])

        # 將匯率資料建成 DataFrame
        History_ExchangeRate = pd.DataFrame({
            'date': date_history,
            'buy_rate': history_buy,
            'sell_rate': history_sell
        })

        History_ExchangeRate = History_ExchangeRate.set_index('date')  # 指定日期欄位為 DataFrame 的 index
        History_ExchangeRate = History_ExchangeRate.sort_index(ascending=True)

        return History_ExchangeRate
    except Exception as e:
        print(f"獲取匯率數據時出錯: {e}")
        # 返回空的 DataFrame
        return pd.DataFrame(columns=['buy_rate', 'sell_rate'])

@st.cache_data(ttl=3600)
def futures() -> pd.DataFrame:
    """獲取期貨數據
    
    Returns:
        DataFrame: 期貨未平倉數據
    """
    url = 'https://www.taifex.com.tw/cht/3/futContractsDate'

    try:
        # 使用 requests 先獲取內容
        response = make_request(url)
        
        # 使用 read_html 解析
        tables = pd.read_html(StringIO(response.text))
        
        # 打印找到的表格數量和每個表格的形狀，幫助調試
        print(f"找到 {len(tables)} 個表格")
        for i, table in enumerate(tables):
            print(f"表格 {i} 形狀: {table.shape}")
        
        # 檢查表格數量並處理不同情況
        if len(tables) <= 2:
            print(f"警告：只找到 {len(tables)} 個表格，嘗試從現有表格提取數據")
            
            # 嘗試從第一個表格提取數據
            if len(tables) >= 1:
                # 獲取第一個表格
                df = tables[0]
                print(f"使用表格 0，形狀: {df.shape}")
                
                # 從輸出中看出這是一個多層級 header 的表格
                try:
                    # 檢查表格是否包含必要的數據
                    if df.shape[0] > 2 and df.shape[1] > 10:
                        # 根據輸出了解到表格包含 '臺股期貨' 和 '自營商'、'投信'、'外資' 等關鍵字
                        
                        # 嘗試找出自營商、投信和外資的行
                        filtered_rows = []
                        
                        # 遍歷 DataFrame 尋找關鍵字
                        for i, row in df.iterrows():
                            row_values = row.astype(str).values
                            row_text = ' '.join(row_values)
                            
                            # 檢查行是否為臺股期貨加上身份別
                            if '臺股期貨' in row_text:
                                if '自營商' in row_text:
                                    filtered_rows.append(('自營商', row))
                                elif '投信' in row_text:
                                    filtered_rows.append(('投信', row))
                                elif '外資' in row_text:
                                    filtered_rows.append(('外資', row))
                        
                        # 如果找到了所有三種身份別
                        if len(filtered_rows) > 0:
                            # 創建新的 DataFrame
                            result_data = []
                            
                            # 遍歷找到的行
                            for identity, row in filtered_rows:
                                # 從右側開始查找未平倉數據
                                # 根據表格預覽，多空淨額的數據位於最後兩列
                                positions_value = row.iloc[-2]  # 多空淨額口數
                                contract_value = row.iloc[-1]   # 多空淨額契約金額
                                
                                # 轉換為數值型別
                                try:
                                    positions_value = float(positions_value)
                                except (ValueError, TypeError):
                                    positions_value = 0
                                    
                                try:
                                    contract_value = float(contract_value)
                                except (ValueError, TypeError):
                                    contract_value = 0
                                
                                result_data.append([positions_value, contract_value])
                            
                            # 建立結果 DataFrame
                            identities = [item[0] for item in filtered_rows]
                            result_df = pd.DataFrame(
                                result_data, 
                                index=identities,
                                columns=["多空淨額未平倉口數", "多空淨額未平倉契約金額"]
                            )
                            
                            # 確保包含自營商、投信和外資
                            for identity in ["自營商", "投信", "外資"]:
                                if identity not in result_df.index:
                                    # 添加缺失的身份別
                                    result_df.loc[identity] = [0, 0]
                            
                            # 重新排序索引
                            result_df = result_df.reindex(["自營商", "投信", "外資"])
                            
                            return result_df
                
                except Exception as e:
                    print(f"直接處理表格時出錯: {e}")
                    # 繼續使用其他方法嘗試
                
                try:
                    # 第二種方法：直接按位置提取
                    dealer_row = None
                    invest_row = None
                    foreign_row = None
                    
                    # 尋找包含關鍵字的行
                    for i, row in df.iterrows():
                        row_str = ' '.join(row.astype(str).values)
                        if '臺股期貨' in row_str:
                            if '自營商' in row_str:
                                dealer_row = row
                            elif '投信' in row_str:
                                invest_row = row
                            elif '外資' in row_str:
                                foreign_row = row
                    
                    # 如果找到了至少一個關鍵行
                    if dealer_row is not None or invest_row is not None or foreign_row is not None:
                        # 創建結果 DataFrame
                        data = {
                            "多空淨額未平倉口數": [0, 0, 0],
                            "多空淨額未平倉契約金額": [0, 0, 0]
                        }
                        result_df = pd.DataFrame(data, index=["自營商", "投信", "外資"])
                        
                        # 填充找到的數據
                        if dealer_row is not None:
                            try:
                                result_df.loc["自營商", "多空淨額未平倉口數"] = float(dealer_row.iloc[-2])
                                result_df.loc["自營商", "多空淨額未平倉契約金額"] = float(dealer_row.iloc[-1])
                            except:
                                pass
                        
                        if invest_row is not None:
                            try:
                                result_df.loc["投信", "多空淨額未平倉口數"] = float(invest_row.iloc[-2])
                                result_df.loc["投信", "多空淨額未平倉契約金額"] = float(invest_row.iloc[-1])
                            except:
                                pass
                        
                        if foreign_row is not None:
                            try:
                                result_df.loc["外資", "多空淨額未平倉口數"] = float(foreign_row.iloc[-2])
                                result_df.loc["外資", "多空淨額未平倉契約金額"] = float(foreign_row.iloc[-1])
                            except:
                                pass
                        
                        return result_df
                
                except Exception as e:
                    print(f"按位置提取數據時出錯: {e}")
                
                # 從表格預覽看到的結構是有多層級的欄位名稱
                try:
                    df_cols = df.columns.tolist()
                    print(f"列名: {df_cols}")
                    
                    # 找出包含 '臺股期貨' 和各個身份別的行
                    taiwan_futures = df[df.iloc[:, 1].astype(str).str.contains('臺股期貨')]
                    
                    if not taiwan_futures.empty:
                        print(f"找到 {len(taiwan_futures)} 行臺股期貨數據")
                        
                        # 識別包含自營商、投信和外資的行
                        dealer = taiwan_futures[taiwan_futures.iloc[:, 2].astype(str).str.contains('自營商')]
                        invest = taiwan_futures[taiwan_futures.iloc[:, 2].astype(str).str.contains('投信')]
                        foreign = taiwan_futures[taiwan_futures.iloc[:, 2].astype(str).str.contains('外資')]
                        
                        # 創建結果 DataFrame
                        data = {
                            "多空淨額未平倉口數": [0, 0, 0],
                            "多空淨額未平倉契約金額": [0, 0, 0]
                        }
                        result_df = pd.DataFrame(data, index=["自營商", "投信", "外資"])
                        
                        # 填充找到的數據
                        if not dealer.empty:
                            try:
                                result_df.loc["自營商", "多空淨額未平倉口數"] = dealer.iloc[0, -2]
                                result_df.loc["自營商", "多空淨額未平倉契約金額"] = dealer.iloc[0, -1]
                            except:
                                pass
                            
                        if not invest.empty:
                            try:
                                result_df.loc["投信", "多空淨額未平倉口數"] = invest.iloc[0, -2]
                                result_df.loc["投信", "多空淨額未平倉契約金額"] = invest.iloc[0, -1]
                            except:
                                pass
                            
                        if not foreign.empty:
                            try:
                                result_df.loc["外資", "多空淨額未平倉口數"] = foreign.iloc[0, -2]
                                result_df.loc["外資", "多空淨額未平倉契約金額"] = foreign.iloc[0, -1]
                            except:
                                pass
                            
                        return result_df
                
                except Exception as e:
                    print(f"處理多層級表頭時出錯: {e}")
            
            # 如果所有嘗試都失敗，返回空的 DataFrame
            print("所有嘗試均失敗，返回預設數據")
            data = {
                "多空淨額未平倉口數": [0, 0, 0],
                "多空淨額未平倉契約金額": [0, 0, 0]
            }
            return pd.DataFrame(data, index=["自營商", "投信", "外資"])
            
        # 原來的邏輯，處理找到三個或以上表格的情況
        df = tables[2]
        df = df.dropna(how='all', axis=0).dropna(how='all', axis=1)

        # 檢查 DataFrame 是否為空
        if df.empty:
            print("警告：期貨數據表格為空")
            data = {
                "多空淨額未平倉口數": [0, 0, 0],
                "多空淨額未平倉契約金額": [0, 0, 0]
            }
            return pd.DataFrame(data, index=["自營商", "投信", "外資"])

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

        # 檢查 DataFrame 列數是否與標頭數量匹配
        if len(df.columns) != len(headers):
            print(f"警告：期貨表格列數 ({len(df.columns)}) 與標頭數量 ({len(headers)}) 不匹配")
            headers = headers[:len(df.columns)] if len(df.columns) < len(headers) else headers + [f"未知列{i}" for i in range(len(headers), len(df.columns))]

        df.columns = headers
        
        # 檢查是否有足夠的行數
        if len(df) <= 5:
            print(f"警告：期貨表格只有 {len(df)} 行，期望更多行")
            data = {
                "多空淨額未平倉口數": [0, 0, 0],
                "多空淨額未平倉契約金額": [0, 0, 0]
            }
            return pd.DataFrame(data, index=["自營商", "投信", "外資"])
            
        df = df[5:].reset_index(drop=True)

        # 安全地處理字符串操作
        if '序號' in df.columns:
            # 首先檢查 '序號' 列是否包含字符串類型的值
            if df['序號'].dtype == 'object':
                mask = ~df['序號'].str.contains('期貨合計|期貨小計|序 號', na=False)
                df = df[mask]
            else:
                print(f"警告：'序號' 列不是字符串類型，而是 {df['序號'].dtype}")
        else:
            print("警告：DataFrame 中沒有 '序號' 列")

        # 檢查 '商品名稱' 列是否存在
        if '商品名稱' in df.columns:
            if not df.empty:
                df = df[df['商品名稱'] == '臺股期貨']
        else:
            print("警告：DataFrame 中沒有 '商品名稱' 列")

        # 檢查所需的列是否都存在
        needed_columns = ["多空淨額未平倉口數", "多空淨額未平倉契約金額"]
        if all(col in df.columns for col in needed_columns):
            df = df.loc[:, needed_columns]
        else:
            missing_cols = [col for col in needed_columns if col not in df.columns]
            print(f"警告：缺少必要列：{missing_cols}")
            data = {
                "多空淨額未平倉口數": [0, 0, 0],
                "多空淨額未平倉契約金額": [0, 0, 0]
            }
            return pd.DataFrame(data, index=["自營商", "投信", "外資"])

        # 檢查是否有足夠的行數來設置索引
        if len(df) >= 3:
            new_index = ["自營商", "投信", "外資"]
            df = df.head(3)  # 只取前三行
            df.index = new_index
        else:
            print(f"警告：期貨表格只有 {len(df)} 行，無法設置 3 個索引")
            # 不足 3 行時，創建一個新的 DataFrame
            data = {
                "多空淨額未平倉口數": [0, 0, 0],
                "多空淨額未平倉契約金額": [0, 0, 0]
            }
            return pd.DataFrame(data, index=["自營商", "投信", "外資"])
            
        return df
    except Exception as e:
        print(f"獲取期貨數據時發生錯誤: {e}")
        # 返回一個包含數據的 DataFrame
        data = {
            "多空淨額未平倉口數": [0, 0, 0],
            "多空淨額未平倉契約金額": [0, 0, 0]
        }
        return pd.DataFrame(data, index=["自營商", "投信", "外資"])

def format_number(num_str: str) -> float:
    """格式化數字字符串為浮點數
    
    Args:
        num_str: 數字字符串
        
    Returns:
        格式化後的浮點數
    """
    try:
        num_str = num_str.replace(",", "")
        num_float = float(num_str)
        num_rounded = round(num_float / 1e8, 1)
        return num_rounded
    except (ValueError, AttributeError) as e:
        print(f"格式化數字時出錯: {e}, 輸入: {num_str}")
        return 0.0

@st.cache_data(ttl=86400)
def get_stock_history(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """獲取指定股票的歷史行情數據，使用yfinance庫
    
    Args:
        stock_id: 股票代碼，例如 "2330"
        start_date: 開始日期，格式為 "YYYY-MM-DD"
        end_date: 結束日期，格式為 "YYYY-MM-DD"
        
    Returns:
        DataFrame: 股票歷史數據，包含日期、開盤價、最高價、最低價、收盤價、成交量等
    """
    try:
        print(f"使用yfinance獲取 {stock_id} 從 {start_date} 到 {end_date} 的歷史數據")
        
        # 轉換台灣股票代碼為Yahoo格式 (添加.TW後綴)
        yahoo_stock_id = f"{stock_id}.TW"
        
        # 使用yfinance下載數據
        stock_data = yf.download(
            tickers=yahoo_stock_id,
            start=start_date,
            end=end_date,
            progress=False
        )
        
        # 檢查是否成功獲取數據
        if stock_data.empty:
            print(f"無法從yfinance獲取 {stock_id} 的數據")
            return pd.DataFrame()
        
        # 重命名列以匹配原有函數的輸出格式
        stock_data.rename(columns={
            'Open': '開盤價',
            'High': '最高價',
            'Low': '最低價',
            'Close': '收盤價',
            'Volume': '成交股數',
            'Adj Close': '調整後收盤價'
        }, inplace=True)
        
        # 添加一些原始函數可能返回的其他列
        stock_data['成交金額'] = stock_data['收盤價'] * stock_data['成交股數']
        stock_data['成交筆數'] = np.nan  # yfinance沒有提供這一數據
        
        # 按日期排序
        stock_data.sort_index(inplace=True)
        
        return stock_data
    
    except Exception as e:
        print(f"使用yfinance獲取 {stock_id} 的歷史數據時發生錯誤: {e}")
        
        # 如果yfinance失敗，嘗試使用原始的獲取方法
        print("嘗試使用原始方法獲取數據...")
        try:
            # 轉換日期格式從 "YYYY-MM-DD" 到 "YYYYMMDD"
            start_date_fmt = start_date.replace("-", "")
            end_date_fmt = end_date.replace("-", "")
            
            # 計算時間範圍內的月份列表
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            
            # 初始化一個空的 DataFrame 用於存儲結果
            result_df = pd.DataFrame()
            
            # 按月請求數據
            current_date = start_date_obj
            while current_date <= end_date_obj:
                year = current_date.year
                month = current_date.month
                
                # 構建月份的數據請求
                url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={year}{month:02d}01&stockNo={stock_id}&response=json"
                print(f"請求月度數據: {url}")
                
                try:
                    response = make_request(url)
                    data = response.json()
                    
                    if data["stat"] == "OK" and "data" in data:
                        # 將月度數據添加到結果中
                        month_df = pd.DataFrame(data["data"], columns=data["fields"])
                        result_df = pd.concat([result_df, month_df])
                    else:
                        print(f"無法獲取 {year}年{month}月 的數據，狀態: {data.get('stat', 'N/A')}")
                    
                    # 每次請求後等待一下，避免頻繁請求被封
                    time.sleep(0.5)
                
                except Exception as e:
                    print(f"獲取 {year}年{month}月 的數據時出錯: {e}")
                
                # 移動到下一個月
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                current_date = datetime(year, month, 1)
            
            # 處理數據格式
            if not result_df.empty:
                # 將日期列轉換為西元格式
                result_df['日期'] = result_df['日期'].apply(lambda x: convert_tw_date(x))
                
                # 確保數據按日期排序
                result_df = result_df.sort_values('日期')
                
                # 將數值型列轉換為數值類型
                numeric_columns = ['開盤價', '最高價', '最低價', '收盤價', '成交股數', '成交金額', '成交筆數']
                for col in numeric_columns:
                    if col in result_df.columns:
                        result_df[col] = result_df[col].str.replace(',', '').astype(float)
                
                # 設置日期為索引
                result_df.set_index('日期', inplace=True)
                
                # 過濾指定日期範圍內的數據
                result_df = result_df[(result_df.index >= start_date) & (result_df.index <= end_date)]
                
                return result_df
            else:
                print(f"獲取 {stock_id} 的歷史數據時未返回任何結果")
                return pd.DataFrame()
                
        except Exception as backup_error:
            print(f"備用方法也失敗: {backup_error}")
            return pd.DataFrame()

def convert_tw_date(tw_date: str) -> str:
    """將台灣日期格式 (民國年/月/日) 轉換為西元年格式 (YYYY-MM-DD)
    
    Args:
        tw_date: 台灣日期格式，例如 "112/01/04"
        
    Returns:
        str: 西元年日期格式，例如 "2023-01-04"
    """
    try:
        parts = tw_date.split('/')
        if len(parts) == 3:
            year = int(parts[0]) + 1911  # 民國年轉換為西元年
            month = parts[1].zfill(2)  # 確保月份為兩位數
            day = parts[2].zfill(2)  # 確保日期為兩位數
            return f"{year}-{month}-{day}"
        return tw_date
    except Exception as e:
        print(f"日期轉換錯誤: {e}, 輸入: {tw_date}")
        return tw_date

@st.cache_data(ttl=86400)
def get_stock_info(stock_id: str) -> dict:
    """獲取股票的基本信息
    
    Args:
        stock_id: 股票代碼，例如 "2330"
        
    Returns:
        dict: 股票基本信息，包含名稱、產業別等
    """
    try:
        # 從台灣證交所獲取股票基本信息
        url = f"        https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20240301&stockNo={stock_id}"
        response = make_request(url)
        data = response.json()
        
        if data["stat"] == "OK" and "data" in data:
            info = data["data"][0]
            stock_info = {
                "股票代號": stock_id,
                "股票名稱": info[1] if len(info) > 1 else "未知",
                "產業別": info[2] if len(info) > 2 else "未知",
                "上市日期": info[3] if len(info) > 3 else "未知"
            }
            return stock_info
        else:
            print(f"無法獲取股票 {stock_id} 的基本信息")
            return {"股票代號": stock_id, "股票名稱": "未知", "產業別": "未知", "上市日期": "未知"}
    
    except Exception as e:
        print(f"獲取股票 {stock_id} 的基本信息時發生錯誤: {e}")
        return {"股票代號": stock_id, "股票名稱": "未知", "產業別": "未知", "上市日期": "未知"}

@st.cache_data(ttl=86400)
def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """計算技術指標
    
    Args:
        df: 股票歷史數據 DataFrame
        
    Returns:
        DataFrame: 添加了技術指標的股票數據
    """
    if df.empty:
        return df
    
    result_df = df.copy()
    
    try:
        # 計算移動平均線
        result_df['MA5'] = result_df['收盤價'].rolling(window=5).mean()
        result_df['MA10'] = result_df['收盤價'].rolling(window=10).mean()
        result_df['MA20'] = result_df['收盤價'].rolling(window=20).mean()
        result_df['MA60'] = result_df['收盤價'].rolling(window=60).mean()
        
        # 計算RSI (相對強弱指標)
        def calculate_rsi(prices, period=14):
            delta = prices.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()
            
            rs = avg_gain / avg_loss
            return 100 - (100 / (1 + rs))
        
        result_df['RSI14'] = calculate_rsi(result_df['收盤價'], 14)
        
        # 計算MACD
        def calculate_macd(prices, fast=12, slow=26, signal=9):
            ema_fast = prices.ewm(span=fast, adjust=False).mean()
            ema_slow = prices.ewm(span=slow, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()
            histogram = macd_line - signal_line
            return macd_line, signal_line, histogram
        
        result_df['MACD'], result_df['MACD_Signal'], result_df['MACD_Hist'] = calculate_macd(result_df['收盤價'])
        
        # 計算布林帶 (Bollinger Bands)
        def calculate_bollinger_bands(prices, period=20, std_dev=2):
            sma = prices.rolling(window=period).mean()
            std = prices.rolling(window=period).std()
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            return upper_band, sma, lower_band
        
        result_df['BB_Upper'], result_df['BB_Middle'], result_df['BB_Lower'] = calculate_bollinger_bands(result_df['收盤價'])
        
        # 計算KD指標
        def calculate_kd(df, period=9):
            df = df.copy()
            low_min = df['最低價'].rolling(window=period).min()
            high_max = df['最高價'].rolling(window=period).max()
            
            df['RSV'] = 100 * ((df['收盤價'] - low_min) / (high_max - low_min))
            df['K'] = df['RSV'].rolling(window=3).mean()
            df['D'] = df['K'].rolling(window=3).mean()
            
            return df['K'], df['D']
        
        result_df['K'], result_df['D'] = calculate_kd(result_df)
        
        # 計算成交量平均
        result_df['Volume_MA5'] = result_df['成交股數'].rolling(window=5).mean()
        result_df['Volume_MA20'] = result_df['成交股數'].rolling(window=20).mean()
        
        return result_df
    
    except Exception as e:
        print(f"計算技術指標時發生錯誤: {e}")
        return df

@st.cache_data(ttl=86400)
def backtest_strategy(df: pd.DataFrame, strategy: str, params: dict, initial_capital: float = 100000.0, 
                      fee_rate: float = 0.001425, tax_rate: float = 0.003, stop_loss: float = 0.05, 
                      take_profit: float = 0.2) -> tuple:
    """執行交易策略回測
    
    Args:
        df: 股票歷史數據 DataFrame (含技術指標)
        strategy: 策略名稱
        params: 策略參數
        initial_capital: 初始資金
        fee_rate: 交易手續費率
        tax_rate: 交易稅率 (賣出時收取)
        stop_loss: 停損比例
        take_profit: 停利比例
        
    Returns:
        tuple: (交易紀錄DataFrame, 回測結果指標dict, 淨值序列DataFrame)
    """
    if df.empty:
        return pd.DataFrame(), {}, pd.DataFrame()
    
    # 添加技術指標（如果還沒添加）
    if 'MA5' not in df.columns:
        df = calculate_technical_indicators(df)
    
    # 創建回測結果的數據結構
    trades = []  # 交易記錄
    positions = 0  # 持倉數量
    cash = initial_capital  # 現金
    buy_price = 0  # 買入價格
    portfolio_value = []  # 每日投資組合價值
    
    # 實現各種交易策略
    if strategy == "ma_cross":
        short_period = params.get('short_ma', 5)
        long_period = params.get('long_ma', 20)
        
        # 確保必要的移動平均線已被計算
        if f'MA{short_period}' not in df.columns:
            df[f'MA{short_period}'] = df['收盤價'].rolling(window=short_period).mean()
        if f'MA{long_period}' not in df.columns:
            df[f'MA{long_period}'] = df['收盤價'].rolling(window=long_period).mean()
        
        # 生成交易信號
        df['signal'] = 0
        # 買入信號: 短期均線上穿長期均線
        df['signal'] = np.where((df[f'MA{short_period}'] > df[f'MA{long_period}']) & 
                               (df[f'MA{short_period}'].shift(1) <= df[f'MA{long_period}'].shift(1)), 1, df['signal'])
        # 賣出信號: 短期均線下穿長期均線
        df['signal'] = np.where((df[f'MA{short_period}'] < df[f'MA{long_period}']) & 
                               (df[f'MA{short_period}'].shift(1) >= df[f'MA{long_period}'].shift(1)), -1, df['signal'])
    
    elif strategy == "rsi":
        period = params.get('rsi_period', 14)
        overbought = params.get('rsi_overbought', 70)
        oversold = params.get('rsi_oversold', 30)
        
        # 確保 RSI 已被計算
        if f'RSI{period}' not in df.columns:
            df[f'RSI{period}'] = calculate_rsi(df['收盤價'], period)
        
        # 生成交易信號
        df['signal'] = 0
        # 買入信號: RSI 從超賣區上穿
        df['signal'] = np.where((df[f'RSI{period}'] > oversold) & (df[f'RSI{period}'].shift(1) <= oversold), 1, df['signal'])
        # 賣出信號: RSI 從超買區下穿
        df['signal'] = np.where((df[f'RSI{period}'] < overbought) & (df[f'RSI{period}'].shift(1) >= overbought), -1, df['signal'])
    
    elif strategy == "macd":
        fast = params.get('macd_fast', 12)
        slow = params.get('macd_slow', 26)
        signal_period = params.get('macd_signal', 9)
        
        # 確保 MACD 已被計算
        if 'MACD' not in df.columns or 'MACD_Signal' not in df.columns:
            df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = calculate_macd(df['收盤價'], fast, slow, signal_period)
        
        # 生成交易信號
        df['signal'] = 0
        # 買入信號: MACD 線上穿 Signal 線
        df['signal'] = np.where((df['MACD'] > df['MACD_Signal']) & (df['MACD'].shift(1) <= df['MACD_Signal'].shift(1)), 1, df['signal'])
        # 賣出信號: MACD 線下穿 Signal 線
        df['signal'] = np.where((df['MACD'] < df['MACD_Signal']) & (df['MACD'].shift(1) >= df['MACD_Signal'].shift(1)), -1, df['signal'])
    
    elif strategy == "bollinger":
        period = params.get('bollinger_period', 20)
        std_dev = params.get('bollinger_std', 2.0)
        
        # 確保布林帶已被計算
        if 'BB_Upper' not in df.columns or 'BB_Lower' not in df.columns:
            df['BB_Upper'], df['BB_Middle'], df['BB_Lower'] = calculate_bollinger_bands(df['收盤價'], period, std_dev)
        
        # 生成交易信號
        df['signal'] = 0
        # 買入信號: 價格接近下軌 (距離下軌不超過1%的距離)
        df['signal'] = np.where(df['收盤價'] <= df['BB_Lower'] * 1.01, 1, df['signal'])
        # 賣出信號: 價格接近上軌 (距離上軌不超過1%的距離)
        df['signal'] = np.where(df['收盤價'] >= df['BB_Upper'] * 0.99, -1, df['signal'])
    
    elif strategy == "foreign_buy":
        threshold = params.get('foreign_buy_threshold', 1000)
        # 這個策略需要外資買賣超資料，但我們目前沒有每日的外資數據
        # 這裡僅作為示範，使用成交量作為替代
        
        # 生成交易信號 (使用成交量相對於平均的變化作為代理)
        df['signal'] = 0
        df['Volume_Ratio'] = df['成交股數'] / df['Volume_MA20']
        # 買入信號: 成交量顯著高於平均 (假設這表示外資買超)
        df['signal'] = np.where(df['Volume_Ratio'] > 1.5, 1, df['signal'])
        # 賣出信號: 成交量顯著低於平均 (假設這表示外資賣超)
        df['signal'] = np.where(df['Volume_Ratio'] < 0.5, -1, df['signal'])
    
    else:
        # 如果策略不匹配，則沒有交易信號
        df['signal'] = 0
    
    # 執行回測
    for i, (index, row) in enumerate(df.iterrows()):
        # 修改 NaN 檢查方式，避免 Series 的真值模糊錯誤
        if isinstance(row['signal'], pd.Series):
            if row['signal'].isna().any():
                continue
        else:
            if pd.isna(row['signal']):
                continue
            
        # 記錄當前組合價值
        current_value = cash
        if positions > 0:
            # 確保收盤價是數值而不是Series
            current_price = row['收盤價']
            if isinstance(current_price, pd.Series):
                current_price = current_price.iloc[0] if len(current_price) > 0 else 0
            current_value += positions * current_price
        portfolio_value.append((index, current_value))
        
        # 根據交易信號執行交易
        # 使用更安全的比較方式，避免與 Series 比較時的模糊性
        is_buy_signal = False
        is_sell_signal = False
        
        if isinstance(row['signal'], pd.Series):
            # 如果是 Series，檢查第一個元素
            if len(row['signal']) > 0:
                is_buy_signal = row['signal'].iloc[0] == 1
                is_sell_signal = row['signal'].iloc[0] == -1
        else:
            # 如果是純量值
            is_buy_signal = row['signal'] == 1
            is_sell_signal = row['signal'] == -1
        
        # 檢查停損/停利條件 (如果有持倉)
        if positions > 0:
            # 確保收盤價是數值
            current_price = row['收盤價']
            if isinstance(current_price, pd.Series):
                current_price = current_price.iloc[0] if len(current_price) > 0 else 0
                
            price_change = (current_price - buy_price) / buy_price
            if price_change <= -stop_loss:
                # 觸發停損
                sell_amount = positions * current_price
                fee = sell_amount * fee_rate
                tax = sell_amount * tax_rate
                cash += sell_amount - fee - tax
                
                trades.append({
                    "日期": index,
                    "類型": "停損賣出",
                    "價格": current_price,
                    "數量": positions,
                    "交易額": sell_amount,
                    "手續費": fee,
                    "稅額": tax,
                    "淨利": (current_price - buy_price) * positions - fee - tax
                })
                
                positions = 0
                buy_price = 0
                continue
            
            if price_change >= take_profit:
                # 觸發停利
                sell_amount = positions * current_price
                fee = sell_amount * fee_rate
                tax = sell_amount * tax_rate
                cash += sell_amount - fee - tax
                
                trades.append({
                    "日期": index,
                    "類型": "停利賣出",
                    "價格": current_price,
                    "數量": positions,
                    "交易額": sell_amount,
                    "手續費": fee,
                    "稅額": tax,
                    "淨利": (current_price - buy_price) * positions - fee - tax
                })
                
                positions = 0
                buy_price = 0
                continue
        
        # 根據交易信號執行交易
        if is_buy_signal and positions == 0:
            # 買入信號
            # 確保收盤價是數值
            current_price = row['收盤價']
            if isinstance(current_price, pd.Series):
                current_price = current_price.iloc[0] if len(current_price) > 0 else 0
                
            max_shares = int(cash / (current_price * (1 + fee_rate)))
            if max_shares > 0:
                positions = max_shares
                buy_price = current_price
                buy_amount = positions * buy_price
                fee = buy_amount * fee_rate
                cash -= (buy_amount + fee)
                
                trades.append({
                    "日期": index,
                    "類型": "買入",
                    "價格": buy_price,
                    "數量": positions,
                    "交易額": buy_amount,
                    "手續費": fee,
                    "稅額": 0,
                    "淨利": 0
                })
        
        elif is_sell_signal and positions > 0:
            # 賣出信號
            # 確保收盤價是數值
            current_price = row['收盤價']
            if isinstance(current_price, pd.Series):
                current_price = current_price.iloc[0] if len(current_price) > 0 else 0
                
            sell_amount = positions * current_price
            fee = sell_amount * fee_rate
            tax = sell_amount * tax_rate
            cash += sell_amount - fee - tax
            
            trades.append({
                "日期": index,
                "類型": "賣出",
                "價格": current_price,
                "數量": positions,
                "交易額": sell_amount,
                "手續費": fee,
                "稅額": tax,
                "淨利": (current_price - buy_price) * positions - fee - tax
            })
            
            positions = 0
            buy_price = 0
    
    # 如果結束時還有持倉，則進行平倉
    if positions > 0 and len(df) > 0:
        # 確保最後的收盤價是純量值
        last_price = df['收盤價'].iloc[-1]
        if isinstance(last_price, pd.Series):
            last_price = last_price.iloc[0] if len(last_price) > 0 else 0
            
        sell_amount = positions * last_price
        fee = sell_amount * fee_rate
        tax = sell_amount * tax_rate
        cash += sell_amount - fee - tax
        
        trades.append({
            "日期": df.index[-1],
            "類型": "平倉賣出",
            "價格": last_price,
            "數量": positions,
            "交易額": sell_amount,
            "手續費": fee,
            "稅額": tax,
            "淨利": (last_price - buy_price) * positions - fee - tax
        })
    
    # 創建交易記錄 DataFrame
    trades_df = pd.DataFrame(trades)
    
    # 創建資產淨值序列 DataFrame
    portfolio_df = pd.DataFrame(portfolio_value, columns=['日期', '淨值'])
    if not portfolio_df.empty:
        portfolio_df.set_index('日期', inplace=True)
    
    # 計算回測結果指標
    backtest_results = {}
    
    if not trades_df.empty:
        # 總收益
        total_profit = trades_df['淨利'].sum()
        total_return = total_profit / initial_capital
        
        # 交易次數
        num_trades = len(trades_df[trades_df['類型'].isin(['買入', '賣出', '停損賣出', '停利賣出', '平倉賣出'])])
        win_trades = len(trades_df[trades_df['淨利'] > 0])
        
        # 勝率
        win_rate = win_trades / num_trades if num_trades > 0 else 0
        
        # 盈虧比
        avg_profit = trades_df[trades_df['淨利'] > 0]['淨利'].mean() if len(trades_df[trades_df['淨利'] > 0]) > 0 else 0
        avg_loss = abs(trades_df[trades_df['淨利'] < 0]['淨利'].mean()) if len(trades_df[trades_df['淨利'] < 0]) > 0 else 1
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        
        # 最大回撤
        if not portfolio_df.empty:
            portfolio_df['累計最大值'] = portfolio_df['淨值'].cummax()
            portfolio_df['回撤'] = (portfolio_df['淨值'] - portfolio_df['累計最大值']) / portfolio_df['累計最大值']
            max_drawdown = portfolio_df['回撤'].min()
        else:
            max_drawdown = 0
            
        # 回測持續時間（天）
        if len(df) >= 2:
            first_date = pd.to_datetime(df.index[0])
            last_date = pd.to_datetime(df.index[-1])
            duration_days = (last_date - first_date).days
            
            # 年化收益率
            annual_return = ((1 + total_return) ** (365 / duration_days)) - 1 if duration_days > 0 else 0
        else:
            duration_days = 0
            annual_return = 0
        
        # 填充結果
        backtest_results = {
            "總報酬率": f"{total_return:.2%}",
            "年化報酬率": f"{annual_return:.2%}",
            "總獲利": f"{total_profit:.2f}",
            "交易次數": f"{num_trades}次",
            "勝率": f"{win_rate:.2%}",
            "盈虧比": f"{profit_loss_ratio:.2f}",
            "最大回撤": f"{max_drawdown:.2%}",
            "持倉時間": f"{duration_days}天"
        }
    else:
        backtest_results = {
            "總報酬率": "0.00%",
            "年化報酬率": "0.00%",
            "總獲利": "0.00",
            "交易次數": "0次",
            "勝率": "0.00%",
            "盈虧比": "0.00",
            "最大回撤": "0.00%",
            "持倉時間": "0天"
        }
    
    return trades_df, backtest_results, portfolio_df
