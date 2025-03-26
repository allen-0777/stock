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
import logging

# 配置日誌系統
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("台股分析")

def log_message(message: str, level: str = "info") -> None:
    """統一的日誌記錄函數
    
    Args:
        message: 要記錄的消息
        level: 日誌級別，可以是 "debug", "info", "warning", "error" 或 "critical"
    """
    level = level.lower()
    if level == "debug":
        logger.debug(message)
    elif level == "info":
        logger.info(message)
        print(message)  # 同時打印到控制台
    elif level == "warning":
        logger.warning(message)
        print(f"警告: {message}")
    elif level == "error":
        logger.error(message)
        print(f"錯誤: {message}")
    elif level == "critical":
        logger.critical(message)
        print(f"嚴重錯誤: {message}")
    else:
        logger.info(message)
        print(message)

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
                log_message(f"獲取數據失敗: {url}, 錯誤: {e}", level="error")
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
            log_message(f"非同步請求失敗: {url}, 錯誤: {e}, 稍後重試...", level="warning")
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
                log_message(f"日期 {datestr} 沒有數據，嘗試前一天。")
                now -= timedelta(days=1)
                continue
            
            df = pd.DataFrame(data["data"], columns=data["fields"])
            return df, now.strftime("%Y-%m-%d")
        except Exception as e:
            log_message(f"獲取數據時出錯: {e}, 嘗試前一天數據。")
            now -= timedelta(days=1)
    
    # 如果所有嘗試都失敗，返回空 DataFrame
    log_message("警告：所有數據獲取嘗試都失敗了")
    return pd.DataFrame(), ""

@st.cache_data(ttl=1800)
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
            log_message("警告：三大法人數據為空")
            # 返回空的 DataFrame 但保持正確的結構
            return pd.DataFrame(columns=['單位名稱', '買賣差']), data.get("date", "")
        
        data_list = data["data"]
        data_date = data["date"]
        df = pd.DataFrame(data_list, columns=data["fields"]).drop(columns=['買進金額', '賣出金額'])
        df['買賣差'] = pd.to_numeric(df['買賣差額'].str.replace(',', ''), errors='coerce') / 1e8
        return df[['單位名稱', '買賣差']], data_date
    except Exception as e:
        log_message(f"獲取三大法人數據時出錯: {e}")
        # 返回空的 DataFrame
        return pd.DataFrame(columns=['單位名稱', '買賣差']), ""

@st.cache_data(ttl=1800)
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
            log_message("警告：成交量數據為空")
            return pd.DataFrame(columns=['日期', '成交量', '漲跌點數'])
        
        data_list = data["data"]
        df = pd.DataFrame(data_list, columns=data["fields"])
        df_new = df.drop(['成交股數', '成交筆數','發行量加權股價指數'], axis=1)
        df['成交金額'] = df['成交金額'].astype(str)
        df['成交量'] = df['成交金額'].apply(format_number)
        new_df = df[['日期', '成交量','漲跌點數']].copy()

        return new_df
    except Exception as e:
        log_message(f"獲取成交量數據時出錯: {e}")
        return pd.DataFrame(columns=['日期', '成交量', '漲跌點數'])

@st.cache_data(ttl=1800)
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
        log_message(f"獲取外資買賣超數據時出錯: {e}")
        # 返回空的 DataFrame
        empty_df = pd.DataFrame(columns=['證券代號', '證券名稱', '外資買賣超股數'])
        return empty_df, empty_df, empty_df, ""

@st.cache_data(ttl=1800)
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
        log_message(f"獲取投信買賣超數據時出錯: {e}")
        # 返回空的 DataFrame
        empty_df = pd.DataFrame(columns=['證券代號', '證券名稱', '投信買賣超股數'])
        return empty_df, empty_df, empty_df, ""

@st.cache_data(ttl=1800)
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
        log_message(f"獲取外資投信同買數據時出錯: {e}")
        # 返回空的 DataFrame
        return pd.DataFrame(columns=['證券代號', '證券名稱', '外資買賣超股數', '投信買賣超股數']), ""

@st.cache_data(ttl=7200)
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
            log_message("警告：匯率表格未找到")
            # 返回空的 DataFrame 但保持正確的結構
            return pd.DataFrame(columns=['buy_rate', 'sell_rate'])
            
        rate_table = rate_table.find(name='tbody').find_all(name='tr')
        
        if not rate_table:
            log_message("警告：匯率表格行未找到")
            return pd.DataFrame(columns=['buy_rate', 'sell_rate'])

        # 直接使用美金匯率歷史資料的 URL
        history_rate_link = "https://rate.bot.com.tw/xrt/quote/l6m/USD"
        
        resp = make_request(history_rate_link)
        resp.encoding = 'utf-8'
        history = BeautifulSoup(resp.text, "lxml")
        history_table = history.find(name='table', attrs={'title':'歷史本行營業時間牌告匯率'})
        
        if not history_table:
            log_message("警告：歷史匯率表格未找到")
            return pd.DataFrame(columns=['buy_rate', 'sell_rate'])
            
        history_table = history_table.find(name='tbody').find_all(name='tr')
        
        if not history_table:
            log_message("警告：歷史匯率表格行未找到")
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
                    log_message(f"解析匯率數據時出錯: {e}")
                    continue

        # 如果沒有獲取到任何數據，返回空的 DataFrame
        if not date_history:
            log_message("警告：未獲取到任何匯率歷史數據")
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
        log_message(f"獲取匯率數據時出錯: {e}")
        # 返回空的 DataFrame
        return pd.DataFrame(columns=['buy_rate', 'sell_rate'])

@st.cache_data(ttl=7200)
def futures() -> pd.DataFrame:
    """獲取期貨數據
    
    Returns:
        DataFrame: 期貨未平倉數據
    """
    url = 'https://www.taifex.com.tw/cht/3/futContractsDate'
    
    # 預設的空 DataFrame
    default_df = pd.DataFrame({
        "多空淨額未平倉口數": [0, 0, 0],
        "多空淨額未平倉契約金額": [0, 0, 0]
    }, index=["自營商", "投信", "外資"])

    try:
        # 使用 requests 先獲取內容
        response = make_request(url)
        
        # 嘗試方法一：使用 pd.read_html 解析
        try:
            tables = pd.read_html(StringIO(response.text))
            log_message(f"找到 {len(tables)} 個表格")
            for i, table in enumerate(tables):
                log_message(f"表格 {i} 形狀: {table.shape}")
            
            # 檢查表格數量
            if len(tables) < 1:
                log_message("未找到任何表格，使用預設數據")
                return default_df
                
            # 嘗試找到包含「臺股期貨」的表格
            target_table = None
            for i, table in enumerate(tables):
                if isinstance(table, pd.DataFrame) and not table.empty:
                    # 將所有列轉換為字符串以進行搜索
                    table_str = table.astype(str)
                    if table_str.apply(lambda x: x.str.contains('臺股期貨').any()).any():
                        log_message(f"表格 {i} 包含臺股期貨資訊")
                        target_table = table
                        break
            
            if target_table is not None:
                # 找出包含自營商、投信和外資的行
                result_df = default_df.copy()  # 先使用預設 DataFrame
                
                # 尋找包含三大法人的行
                for idx, row in target_table.iterrows():
                    row_str = row.astype(str).str.cat(sep=' ')
                    
                    if '自營商' in row_str:
                        # 尋找倒數第二列和倒數第一列的數值
                        try:
                            result_df.loc["自營商", "多空淨額未平倉口數"] = pd.to_numeric(row.iloc[-2], errors='coerce')
                            result_df.loc["自營商", "多空淨額未平倉契約金額"] = pd.to_numeric(row.iloc[-1], errors='coerce')
                        except:
                            pass
                            
                    elif '投信' in row_str:
                        try:
                            result_df.loc["投信", "多空淨額未平倉口數"] = pd.to_numeric(row.iloc[-2], errors='coerce')
                            result_df.loc["投信", "多空淨額未平倉契約金額"] = pd.to_numeric(row.iloc[-1], errors='coerce')
                        except:
                            pass
                            
                    elif '外資' in row_str or '外國人' in row_str:
                        try:
                            result_df.loc["外資", "多空淨額未平倉口數"] = pd.to_numeric(row.iloc[-2], errors='coerce')
                            result_df.loc["外資", "多空淨額未平倉契約金額"] = pd.to_numeric(row.iloc[-1], errors='coerce')
                        except:
                            pass
                
                return result_df
            
            # 嘗試方法二：直接處理第一個足夠大的表格
            for table in tables:
                if table.shape[0] > 5 and table.shape[1] > 5:  # 表格足夠大
                    try:
                        # 取前三行，假設是三大法人
                        df = table.head(3)
                        if df.shape[0] >= 3:
                            # 假設最後兩列是我們需要的數據
                            result_df = pd.DataFrame({
                                "多空淨額未平倉口數": df.iloc[:, -2].values,
                                "多空淨額未平倉契約金額": df.iloc[:, -1].values
                            }, index=["自營商", "投信", "外資"])
                            return result_df
                    except Exception as e:
                        log_message(f"處理表格時出錯: {e}")
        
        except Exception as e:
            log_message(f"使用 pd.read_html 解析時出錯: {e}")
        
        # 嘗試方法三：使用 BeautifulSoup 解析
        try:
            soup = BeautifulSoup(response.text, 'lxml')
            tables = soup.find_all('table')
            
            if tables:
                for table in tables:
                    rows = table.find_all('tr')
                    if len(rows) >= 4:  # 至少需要有足夠的行
                        data = []
                        for row in rows[1:4]:  # 跳過標題行，取三大法人
                            cols = row.find_all('td')
                            if len(cols) >= 2:
                                try:
                                    # 尝试获取最后两列的数据
                                    net_position = pd.to_numeric(cols[-2].get_text().strip().replace(',', ''), errors='coerce')
                                    amount = pd.to_numeric(cols[-1].get_text().strip().replace(',', ''), errors='coerce')
                                    data.append([net_position, amount])
                                except:
                                    data.append([0, 0])
                        
                        if len(data) == 3:
                            result_df = pd.DataFrame(data, columns=["多空淨額未平倉口數", "多空淨額未平倉契約金額"], 
                                                  index=["自營商", "投信", "外資"])
                            return result_df
        
        except Exception as e:
            log_message(f"使用 BeautifulSoup 解析時出錯: {e}")
        
        # 如果所有方法都失敗，返回預設數據
        log_message("所有解析方法均失敗，返回預設數據")
        return default_df
        
    except Exception as e:
        log_message(f"獲取期貨數據時發生錯誤: {e}")
        return default_df

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
        log_message(f"格式化數字時出錯: {e}, 輸入: {num_str}")
        return 0.0

@st.cache_data(ttl=86400)
def get_stock_history(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """獲取股票歷史數據
    
    Args:
        stock_id: 股票代號，例如 "2330"
        start_date: 開始日期，格式為 "YYYY-MM-DD"
        end_date: 結束日期，格式為 "YYYY-MM-DD"
        
    Returns:
        DataFrame: 股票歷史數據，包含日期、開盤價、最高價、最低價、收盤價、成交量等
    """
    # 特殊處理用於測試的數據
    if stock_id == 'TEST':
        try:
            test_df = pd.read_csv('example_stock_data.csv')
            test_df['日期'] = pd.to_datetime(test_df['日期'])
            test_df.set_index('日期', inplace=True)
            
            # 確保測試數據有足夠的交易信號
            # 計算移動平均線以確保有交叉點
            test_df['MA5'] = test_df['收盤價'].rolling(window=5).mean()
            test_df['MA20'] = test_df['收盤價'].rolling(window=20).mean()
            
            # 過濾日期範圍
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)
            mask = (test_df.index >= start_date) & (test_df.index <= end_date)
            filtered_df = test_df[mask].copy()
            
            log_message(f"返回測試數據，共 {len(filtered_df)} 條記錄")
            return filtered_df
        except Exception as e:
            log_message(f"讀取測試數據時出錯: {e}", level="error")
            # 如果測試數據讀取失敗，繼續使用正常的數據獲取方法
    
    # 正常的數據獲取邏輯
    try:
        log_message(f"使用yfinance獲取 {stock_id} 從 {start_date} 到 {end_date} 的歷史數據")
        
        # 轉換台灣股票代碼為Yahoo格式 (添加.TW或.TWO後綴)
        if not stock_id.endswith('.TW') and not stock_id.endswith('.TWO'):
            # 判斷是上市還是上櫃
            if len(stock_id) == 4 and stock_id.startswith('6'):
                yahoo_stock_id = f"{stock_id}.TWO"  # 上櫃股票
            else:
                yahoo_stock_id = f"{stock_id}.TW"   # 上市股票
        else:
            yahoo_stock_id = stock_id
        
        # 使用yfinance下載數據
        stock_data = yf.download(
            tickers=yahoo_stock_id,
            start=start_date,
            end=end_date,
            progress=False,
            timeout=15
        )
        
        # 檢查是否成功獲取數據
        if not stock_data.empty:
            log_message(f"成功從yfinance獲取 {stock_id} 的數據，共 {len(stock_data)} 條記錄")
            
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
        else:
            log_message(f"從yfinance獲取的 {stock_id} 數據為空，嘗試其他方法")
    except Exception as e:
        log_message(f"使用yfinance獲取數據時出錯: {str(e)}，嘗試其他方法")
    
    # 第二种方法：使用台湾证券交易所 API (如果 yfinance 失败)
    try:
        log_message(f"嘗試從TWSE獲取 {stock_id} 的歷史數據")
        
        # 解析日期
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 初始化結果 DataFrame
        result_df = pd.DataFrame()
        
        # 逐月獲取數據
        current_date = start_date_obj
        
        while current_date <= end_date_obj:
            year = current_date.year
            month = current_date.month
            
            # 構建月份的數據請求
            url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={year}{month:02d}01&stockNo={stock_id}&response=json"
            log_message(f"請求月度數據: {url}")
            
            try:
                response = make_request(url)
                data = response.json()
                
                if data["stat"] == "OK" and "data" in data:
                    # 將月度數據添加到結果中
                    month_df = pd.DataFrame(data["data"], columns=data["fields"])
                    result_df = pd.concat([result_df, month_df])
                else:
                    log_message(f"無法獲取 {year}年{month}月 的數據，狀態: {data.get('stat', 'N/A')}")
                
                # 每次請求後等待一下，避免頻繁請求被封
                time.sleep(0.5)
            
            except Exception as e:
                log_message(f"獲取 {year}年{month}月 的數據時出錯: {e}")
            
            # 移動到下一個月
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            current_date = datetime(year, month, 1)
        
        # 處理數據類型
        if not result_df.empty:
            # 轉換日期
            result_df['日期'] = result_df['日期'].apply(convert_tw_date)
            
            # 轉換數字類型
            for col in ['開盤價', '最高價', '最低價', '收盤價']:
                result_df[col] = result_df[col].str.replace(',', '').astype(float)
            
            for col in ['成交股數', '成交金額', '成交筆數']:
                result_df[col] = result_df[col].str.replace(',', '').astype(float)
            
            # 設置日期為索引
            result_df['日期'] = pd.to_datetime(result_df['日期'])
            result_df.set_index('日期', inplace=True)
            
            # 按日期排序
            result_df.sort_index(inplace=True)
            
            log_message(f"成功從TWSE獲取 {stock_id} 的數據，共 {len(result_df)} 條記錄")
            return result_df
    except Exception as e:
        log_message(f"從TWSE獲取 {stock_id} 的歷史數據時出錯: {e}")
    
    # 如果所有方法都失敗，返回空 DataFrame
    log_message(f"無法獲取 {stock_id} 的歷史數據")
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
        log_message(f"日期轉換錯誤: {e}, 輸入: {tw_date}")
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
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date=20240301&stockNo={stock_id}&response=json"
        response = make_request(url)
        data = response.json()
        
        if data["stat"] == "OK" and "data" in data:
            info = data["data"][0]
            stock_info = {
                "股票代號": stock_id,
                "股票名稱": info[0] if len(info) > 0 else "未知",
                "產業別": "未知",  # STOCK_DAY API 不提供產業別信息
                "上市日期": "未知"  # STOCK_DAY API 不提供上市日期信息
            }
            return stock_info
        else:
            log_message(f"無法獲取股票 {stock_id} 的基本信息")
            return {"股票代號": stock_id, "股票名稱": "未知", "產業別": "未知", "上市日期": "未知"}
    
    except Exception as e:
        log_message(f"獲取股票 {stock_id} 的基本信息時發生錯誤: {e}")
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
        log_message(f"計算技術指標時發生錯誤: {e}")
        return df

@st.cache_data(ttl=86400)
def backtest_strategy(df, strategy, params, initial_capital=100000):
    """回測交易策略
    
    Args:
        df: 股票數據 DataFrame
        strategy: 策略名稱，例如 "ma_cross", "rsi", "macd", "bollinger", "foreign"
        params: 策略參數字典
        initial_capital: 初始資金
        
    Returns:
        dict: 回測結果，包含績效指標和交易記錄
    """
    log_message(f"開始回測策略: {strategy}, 參數: {params}, 資料長度: {len(df)}")
    
    # 檢查數據是否足夠
    if len(df) < 30:
        log_message("數據長度不足，無法進行回測", level="warning")
        return {
            "success": False,
            "error": "數據長度不足，無法進行回測",
            "trades": []
        }
    
    # 複製數據框以避免修改原始數據
    df = df.copy()
    
    # 生成信號
    signals = pd.Series(0, index=df.index)
    trades = []
    positions = []
    
    try:
        # 計算技術指標
        if strategy in ["ma_cross", "移動平均線交叉"]:
            # 移動平均線交叉策略
            short_window = params.get("short_window", 5)
            long_window = params.get("long_window", 20)
            
            # 檢查窗口大小是否合理
            if short_window >= long_window:
                log_message(f"短期窗口 {short_window} 必須小於長期窗口 {long_window}", level="warning")
                return {
                    "success": False,
                    "error": f"短期窗口 {short_window} 必須小於長期窗口 {long_window}",
                    "trades": []
                }
            
            df['MA_short'] = df['收盤價'].rolling(window=short_window).mean()
            df['MA_long'] = df['收盤價'].rolling(window=long_window).mean()
            
            log_message(f"計算了短期均線 (MA{short_window}) 和長期均線 (MA{long_window})")
            
            # 生成交叉信號
            for i in range(long_window + 1, len(df)):
                # 金叉: 短期均線從下方穿過長期均線
                if df['MA_short'].iloc[i-1] <= df['MA_long'].iloc[i-1] and df['MA_short'].iloc[i] > df['MA_long'].iloc[i]:
                    signals.iloc[i] = 1
                    date_str = df.index[i].strftime('%Y-%m-%d')
                    price = float(df['收盤價'].iloc[i])  # 確保價格是標量
                    trades.append({
                        "日期": date_str,
                        "類型": "買入",
                        "價格": price,
                        "原因": f"金叉: MA{short_window}({float(df['MA_short'].iloc[i]):.2f}) > MA{long_window}({float(df['MA_long'].iloc[i]):.2f})"
                    })
                    log_message(f"[{date_str}] 產生買入信號，價格: {price:.2f}，原因: 金叉")
                
                # 死叉: 短期均線從上方穿過長期均線
                elif df['MA_short'].iloc[i-1] >= df['MA_long'].iloc[i-1] and df['MA_short'].iloc[i] < df['MA_long'].iloc[i]:
                    signals.iloc[i] = -1
                    date_str = df.index[i].strftime('%Y-%m-%d')
                    price = float(df['收盤價'].iloc[i])  # 確保價格是標量
                    trades.append({
                        "日期": date_str,
                        "類型": "賣出",
                        "價格": price,
                        "原因": f"死叉: MA{short_window}({float(df['MA_short'].iloc[i]):.2f}) < MA{long_window}({float(df['MA_long'].iloc[i]):.2f})"
                    })
                    log_message(f"[{date_str}] 產生賣出信號，價格: {price:.2f}，原因: 死叉")
        
        elif strategy in ["rsi", "RSI超買超賣"]:
            # RSI超買超賣策略
            rsi_period = params.get("rsi_period", 14)
            overbought = params.get("overbought", 70)
            oversold = params.get("oversold", 30)
            
            # 檢查參數是否合理
            if overbought <= oversold:
                log_message(f"超買閾值 {overbought} 必須大於超賣閾值 {oversold}", level="warning")
                return {
                    "success": False,
                    "error": f"超買閾值 {overbought} 必須大於超賣閾值 {oversold}",
                    "trades": []
                }
            
            # 計算RSI
            delta = df['收盤價'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=rsi_period).mean()
            avg_loss = loss.rolling(window=rsi_period).mean()
            
            rs = avg_gain / avg_loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            log_message(f"計算了 RSI({rsi_period}) 指標，超買閾值: {overbought}, 超賣閾值: {oversold}")
            
            # 生成RSI信號
            prev_was_oversold = False
            prev_was_overbought = False
            
            for i in range(rsi_period + 1, len(df)):
                current_rsi = df['RSI'].iloc[i]
                prev_rsi = df['RSI'].iloc[i-1]
                
                # 超賣後反彈
                if prev_rsi < oversold and current_rsi >= oversold and not prev_was_oversold:
                    signals.iloc[i] = 1
                    date_str = df.index[i].strftime('%Y-%m-%d')
                    price = float(df['收盤價'].iloc[i])  # 確保價格是標量
                    trades.append({
                        "日期": date_str,
                        "類型": "買入",
                        "價格": price,
                        "原因": f"RSI從超賣區域反彈: {float(prev_rsi):.2f} -> {float(current_rsi):.2f}"
                    })
                    log_message(f"[{date_str}] 產生買入信號，價格: {price:.2f}，原因: RSI從超賣區域反彈")
                    prev_was_oversold = True
                elif current_rsi >= overbought:
                    prev_was_oversold = False
                
                # 超買後回落
                if prev_rsi > overbought and current_rsi <= overbought and not prev_was_overbought:
                    signals.iloc[i] = -1
                    date_str = df.index[i].strftime('%Y-%m-%d')
                    price = float(df['收盤價'].iloc[i])  # 確保價格是標量
                    trades.append({
                        "日期": date_str,
                        "類型": "賣出",
                        "價格": price,
                        "原因": f"RSI從超買區域回落: {float(prev_rsi):.2f} -> {float(current_rsi):.2f}"
                    })
                    log_message(f"[{date_str}] 產生賣出信號，價格: {price:.2f}，原因: RSI從超買區域回落")
                    prev_was_overbought = True
                elif current_rsi <= oversold:
                    prev_was_overbought = False
        
        elif strategy in ["macd", "MACD交叉"]:
            # MACD交叉策略
            fast_period = params.get("fast_period", 12)
            slow_period = params.get("slow_period", 26)
            signal_period = params.get("signal_period", 9)
            
            # 計算MACD
            exp1 = df['收盤價'].ewm(span=fast_period, adjust=False).mean()
            exp2 = df['收盤價'].ewm(span=slow_period, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=signal_period, adjust=False).mean()
            df['MACD'] = macd
            df['MACD_Signal'] = signal
            df['MACD_Hist'] = macd - signal
            
            log_message(f"計算了MACD指標，快週期: {fast_period}, 慢週期: {slow_period}, 信號週期: {signal_period}")
            
            # 生成MACD交叉信號
            for i in range(slow_period + signal_period, len(df)):
                # 金叉：MACD線上穿信號線
                if df['MACD'].iloc[i-1] <= df['MACD_Signal'].iloc[i-1] and df['MACD'].iloc[i] > df['MACD_Signal'].iloc[i]:
                    signals.iloc[i] = 1
                    date_str = df.index[i].strftime('%Y-%m-%d')
                    price = float(df['收盤價'].iloc[i])  # 確保價格是標量
                    trades.append({
                        "日期": date_str,
                        "類型": "買入",
                        "價格": price,
                        "原因": f"MACD金叉: {float(df['MACD'].iloc[i]):.2f} > {float(df['MACD_Signal'].iloc[i]):.2f}"
                    })
                    log_message(f"[{date_str}] 產生買入信號，價格: {price:.2f}，原因: MACD金叉")
                
                # 死叉：MACD線下穿信號線
                elif df['MACD'].iloc[i-1] >= df['MACD_Signal'].iloc[i-1] and df['MACD'].iloc[i] < df['MACD_Signal'].iloc[i]:
                    signals.iloc[i] = -1
                    date_str = df.index[i].strftime('%Y-%m-%d')
                    price = float(df['收盤價'].iloc[i])  # 確保價格是標量
                    trades.append({
                        "日期": date_str,
                        "類型": "賣出",
                        "價格": price,
                        "原因": f"MACD死叉: {float(df['MACD'].iloc[i]):.2f} < {float(df['MACD_Signal'].iloc[i]):.2f}"
                    })
                    log_message(f"[{date_str}] 產生賣出信號，價格: {price:.2f}，原因: MACD死叉")
        
        elif strategy in ["bollinger", "布林通道突破"]:
            # 布林通道突破策略
            bollinger_period = params.get("bollinger_period", 20)
            num_std = params.get("num_std", 2.0)
            
            # 計算布林通道
            df['BB_Middle'] = df['收盤價'].rolling(window=bollinger_period).mean()
            df['BB_Std'] = df['收盤價'].rolling(window=bollinger_period).std()
            df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * num_std)
            df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * num_std)
            
            log_message(f"計算了布林通道，週期: {bollinger_period}, 標準差倍數: {num_std}")
            
            # 生成布林通道突破信號
            for i in range(bollinger_period + 1, len(df)):
                # 價格突破下軌（超賣）
                if df['收盤價'].iloc[i-1] >= df['BB_Lower'].iloc[i-1] and df['收盤價'].iloc[i] < df['BB_Lower'].iloc[i]:
                    signals.iloc[i] = 1
                    date_str = df.index[i].strftime('%Y-%m-%d')
                    price = float(df['收盤價'].iloc[i])  # 確保價格是標量
                    trades.append({
                        "日期": date_str,
                        "類型": "買入",
                        "價格": price,
                        "原因": f"價格突破布林下軌: {price:.2f} < {float(df['BB_Lower'].iloc[i]):.2f}"
                    })
                    log_message(f"[{date_str}] 產生買入信號，價格: {price:.2f}，原因: 突破布林下軌")
                
                # 價格突破上軌（超買）
                elif df['收盤價'].iloc[i-1] <= df['BB_Upper'].iloc[i-1] and df['收盤價'].iloc[i] > df['BB_Upper'].iloc[i]:
                    signals.iloc[i] = -1
                    date_str = df.index[i].strftime('%Y-%m-%d')
                    price = float(df['收盤價'].iloc[i])  # 確保價格是標量
                    trades.append({
                        "日期": date_str,
                        "類型": "賣出",
                        "價格": price,
                        "原因": f"價格突破布林上軌: {price:.2f} > {float(df['BB_Upper'].iloc[i]):.2f}"
                    })
                    log_message(f"[{date_str}] 產生賣出信號，價格: {price:.2f}，原因: 突破布林上軌")
        
        elif strategy in ["foreign", "外資買超"]:
            # 外資買超策略
            log_message("外資買超策略目前未實現，將來會加入")
        
        log_message(f"信號生成完成，共有買入信號 {len([s for s in signals if s == 1])} 個，賣出信號 {len([s for s in signals if s == -1])} 個")
        
        # 如果沒有產生任何交易信號，返回錯誤
        if len(trades) == 0:
            log_message("沒有產生任何交易信號", level="warning")
            return {
                "success": False,
                "error": "沒有產生任何交易信號，請調整策略參數或選擇更長的回測期間",
                "trades": []
            }
        
        # 執行回測
        # 假設每次交易使用全部資金
        cash = float(initial_capital)
        shares = 0.0
        equity = []
        benchmark = []
        
        for i in range(len(df)):
            price = float(df['收盤價'].iloc[i])  # 確保價格是標量
            
            if signals.iloc[i] == 1:  # 買入信號
                if cash > 0:
                    shares = cash / price
                    cash = 0.0
                    positions.append({
                        "日期": df.index[i].strftime('%Y-%m-%d'),
                        "操作": "買入",
                        "價格": price,
                        "股數": shares,
                        "現金": cash,
                        "總值": shares * price + cash
                    })
            elif signals.iloc[i] == -1:  # 賣出信號
                if shares > 0:
                    cash = shares * price
                    shares = 0.0
                    positions.append({
                        "日期": df.index[i].strftime('%Y-%m-%d'),
                        "操作": "賣出",
                        "價格": price,
                        "股數": 0.0,
                        "現金": cash,
                        "總值": cash
                    })
            
            # 更新每日權益
            current_equity = shares * price + cash
            equity.append(current_equity)
            
            # 計算基準
            first_price = float(df['收盤價'].iloc[0])  # 確保第一天價格是標量
            benchmark_shares = initial_capital / first_price
            benchmark_value = benchmark_shares * price
            benchmark.append(benchmark_value)
        
        # 創建權益曲線
        portfolio_df = pd.DataFrame({
            '淨值': equity,
            '基準淨值': benchmark
        }, index=df.index)
        
        # 計算績效指標
        initial_capital_float = float(initial_capital)
        final_equity = float(portfolio_df['淨值'].iloc[-1])
        total_return = (final_equity / initial_capital_float - 1) * 100
        
        # 計算年化收益率
        days = (df.index[-1] - df.index[0]).days
        annualized_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100 if days > 0 else 0
        
        # 買入並持有收益率
        final_benchmark = float(benchmark[-1])
        buy_hold_return = (final_benchmark / initial_capital_float - 1) * 100
        
        # 夏普比率（假設無風險利率為 0）
        daily_returns = portfolio_df['淨值'].pct_change().dropna()
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if len(daily_returns) > 0 and daily_returns.std() != 0 else 0
        
        # 最大回撤
        cumulative_max = portfolio_df['淨值'].cummax()
        drawdown = (portfolio_df['淨值'] / cumulative_max - 1) * 100
        max_drawdown = float(drawdown.min()) if not drawdown.empty else 0
        
        # 計算勝率和其他指標時確保使用標量比較
        win_trades = [t for t in positions if t['操作'] == '賣出' and float(t['現金']) > initial_capital_float]
        total_sell_trades = [t for t in positions if t['操作'] == '賣出']
        win_rate = len(win_trades) / len(total_sell_trades) * 100 if len(total_sell_trades) > 0 else 0
        
        # 計算賺賠比
        if len(win_trades) > 0 and len(total_sell_trades) - len(win_trades) > 0:
            avg_win = sum([(float(t['現金']) - initial_capital_float) for t in win_trades]) / len(win_trades)
            lose_trades = [t for t in positions if t['操作'] == '賣出' and float(t['現金']) <= initial_capital_float]
            avg_lose = sum([(initial_capital_float - float(t['現金'])) for t in lose_trades]) / len(lose_trades) if len(lose_trades) > 0 else 1
            profit_loss_ratio = abs(avg_win / avg_lose) if avg_lose != 0 else 0
        else:
            profit_loss_ratio = 0
        
        log_message(f"回測完成，總收益率: {total_return:.2f}%，年化收益率: {annualized_return:.2f}%，最大回撤: {max_drawdown:.2f}%")
        
        # 返回回測結果
        return {
            "success": True,
            "總收益率": f"{total_return:.2f}%",
            "年化收益率": f"{annualized_return:.2f}%",
            "買入並持有收益率": f"{buy_hold_return:.2f}%",
            "夏普比率": f"{sharpe_ratio:.2f}",
            "最大回撤": f"{max_drawdown:.2f}%",
            "勝率": f"{win_rate:.2f}%",
            "盈虧比": f"{profit_loss_ratio:.2f}",
            "交易次數": len([t for t in positions if t['操作'] == '買入']),
            "portfolio_df": portfolio_df,
            "trades": trades,
            "positions": positions
        }
    except Exception as e:
        log_message(f"回測過程中出錯: {str(e)}", level="error")
        import traceback
        log_message(traceback.format_exc(), level="error")
        return {
            "success": False,
            "error": f"回測過程中出錯: {str(e)}",
            "trades": []
        }

def exception_handler(default_return=None):
    """異常處理裝飾器
    
    Args:
        default_return: 出現異常時的默認返回值
        
    Returns:
        裝飾後的函數
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 獲取函數名稱
                func_name = func.__name__
                # 記錄錯誤
                log_message(f"執行 {func_name} 時發生錯誤: {str(e)}", level="error")
                # 返回默認值
                return default_return
        return wrapper
    return decorator
