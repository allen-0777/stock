import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import streamlit as st
from data import log_message
import ssl

# 為了解決SSL證書問題，設置無SSL驗證選項
ssl._create_default_https_context = ssl._create_unverified_context

def get_stock_data(stock_code, start_date, end_date):
    """
    使用 yfinance 獲取股票歷史數據
    
    參數:
    - stock_code: 股票代碼（如 '2330.TW'）
    - start_date: 開始日期
    - end_date: 結束日期
    
    返回:
    - 股票歷史數據 DataFrame
    """
    try:
        # 如果沒有添加.TW，自動添加
        if not stock_code.endswith('.TW') and not stock_code.endswith('.TWO'):
            # 判斷是上市還是上櫃
            if len(stock_code) == 4 and stock_code.startswith('6'):
                stock_code = f"{stock_code}.TWO"  # 上櫃股票
            else:
                stock_code = f"{stock_code}.TW"   # 上市股票
            
        log_message(f"獲取 {stock_code} 從 {start_date} 到 {end_date} 的股票數據")
        data = yf.download(stock_code, start=start_date, end=end_date, progress=False)
        
        if data.empty:
            log_message(f"無法獲取 {stock_code} 的股票數據", level="warning")
            return pd.DataFrame()
            
        log_message(f"成功獲取 {stock_code} 的股票數據，共 {len(data)} 條記錄")
        return data
    except Exception as e:
        log_message(f"獲取 {stock_code} 股票數據時發生錯誤: {str(e)}", level="error")
        return pd.DataFrame()

def calculate_ma(data, short_window=5, long_window=20):
    """
    計算移動平均線並添加到數據中
    
    參數:
    - data: 股票數據 DataFrame
    - short_window: 短期移動平均窗口大小
    - long_window: 長期移動平均窗口大小
    
    返回:
    - 添加了移動平均線的 DataFrame
    """
    if data.empty:
        return data
        
    # 複製數據以避免修改原始數據
    df = data.copy()
    
    # 計算短期和長期移動平均線
    df[f'MA{short_window}'] = df['Close'].rolling(window=short_window).mean()
    df[f'MA{long_window}'] = df['Close'].rolling(window=long_window).mean()
    
    return df

def generate_signals(data, short_window=5, long_window=20):
    """
    基於移動平均線交叉生成買賣信號
    
    參數:
    - data: 包含移動平均線的股票數據 DataFrame
    - short_window: 短期移動平均窗口大小
    - long_window: 長期移動平均窗口大小
    
    返回:
    - 添加了信號的 DataFrame
    """
    if not isinstance(data, pd.DataFrame) or data.empty:
        log_message("信號生成數據為空或格式錯誤", level="error")
        return data
        
    # 複製數據以避免修改原始數據
    df = data.copy()
    
    # 確保移動平均線列存在
    short_ma_col = f'MA{short_window}'
    long_ma_col = f'MA{long_window}'
    
    if short_ma_col not in df.columns or long_ma_col not in df.columns:
        log_message(f"無法找到移動平均線列: {short_ma_col} 或 {long_ma_col}", level="error")
        return df
    
    # 初始化所有列
    df['Signal'] = 0  # 信號列
    df['Position'] = 0  # 持倉狀態列
    
    # 安全地處理每一行數據
    signal_values = [0] * len(df)  # 預先創建信號列表，默認為0
    
    for i in range(1, len(df)):  # 從第二行開始，因為我們需要比較前一行
        # 當前和前一個時間點的短期和長期均線
        curr_short = df[short_ma_col].iloc[i]
        prev_short = df[short_ma_col].iloc[i-1]
        curr_long = df[long_ma_col].iloc[i]
        prev_long = df[long_ma_col].iloc[i-1]
        
        # 買入信號: 短期均線從下方穿過長期均線
        if prev_short <= prev_long and curr_short > curr_long:
            signal_values[i] = 1
        
        # 賣出信號: 短期均線從上方穿過長期均線
        elif prev_short >= prev_long and curr_short < curr_long:
            signal_values[i] = -1
    
    # 一次性賦值信號列
    df['Signal'] = signal_values
    
    # 根據信號計算持倉狀態
    position_values = [0] * len(df)  # 預先創建持倉列表，默認為0
    current_position = 0
    
    for i in range(1, len(df)):
        signal = signal_values[i]
        if signal == 1:  # 買入信號
            current_position = 1
        elif signal == -1:  # 賣出信號
            current_position = -1
        position_values[i] = current_position
    
    # 一次性賦值持倉列
    df['Position'] = position_values
    
    return df

def backtest_strategy(data, initial_capital=100000):
    """
    回測交易策略
    
    參數:
    - data: 包含信號的股票數據 DataFrame
    - initial_capital: 初始資金金額
    
    返回:
    - 回測結果 DataFrame
    - 交易記錄 DataFrame
    - 統計數據 Dictionary
    """
    if not isinstance(data, pd.DataFrame) or data.empty:
        log_message("回測數據為空或格式錯誤", level="error")
        return pd.DataFrame(), pd.DataFrame(), {}
        
    # 複製數據以避免修改原始數據
    df = data.copy()
    
    # 初始化結果 DataFrame
    backtest_results = pd.DataFrame(index=df.index)
    backtest_results['Close'] = df['Close']
    backtest_results['Signal'] = df['Signal']
    backtest_results['Position'] = df['Position']
    
    # 初始化資金、持股數量和交易列表
    capital = initial_capital
    shares = 0
    trades = []
    in_position = False  # 是否持有股票
    
    # 逐行處理每個交易日
    for i in range(len(df)):
        # 使用 .iloc 來安全地索引單個值
        signal = df['Signal'].iloc[i]
        price = df['Close'].iloc[i]
        date = df.index[i]
        
        # 確保日期是純量值
        if isinstance(date, pd.Series):
            date = date.iloc[0]
        
        # 買入信號處理 - 使用純量比較
        if signal == 1 and not in_position:  # 買入信號且未持有股票
            # 計算可買入的股數（假設全倉買入）
            shares = int(capital // price)
            if shares > 0:  # 確保有足夠資金買入至少一股
                trade_value = shares * price
                capital -= trade_value  # 扣除資金
                in_position = True  # 設置持倉狀態
                trades.append({
                    'Date': date,
                    'Type': 'Buy',
                    'Price': float(price) if isinstance(price, pd.Series) else price,
                    'Shares': int(shares) if isinstance(shares, pd.Series) else shares,
                    'Value': float(trade_value) if isinstance(trade_value, pd.Series) else trade_value,
                    'Capital': float(capital) if isinstance(capital, pd.Series) else capital
                })
                
        # 賣出信號處理 - 使用純量比較
        elif signal == -1 and in_position:  # 賣出信號且持有股票
            if shares > 0:  # 確保有股票可賣
                trade_value = shares * price
                capital += trade_value  # 增加資金
                in_position = False  # 清除持倉狀態
                trades.append({
                    'Date': date,
                    'Type': 'Sell',
                    'Price': float(price) if isinstance(price, pd.Series) else price,
                    'Shares': int(shares) if isinstance(shares, pd.Series) else shares,
                    'Value': float(trade_value) if isinstance(trade_value, pd.Series) else trade_value,
                    'Capital': float(capital) if isinstance(capital, pd.Series) else capital
                })
                shares = 0  # 重置持股數量
    
    # 計算最終資產價值
    final_value = capital
    if shares > 0 and len(df) > 0:  # 如果還有股票未賣出
        # 用最後一個交易日的收盤價計算剩餘股票價值
        final_value += shares * df['Close'].iloc[-1]
    
    # 計算策略收益率
    total_return = (final_value - initial_capital) / initial_capital * 100
    
    # 計算買入並持有策略收益率
    buy_hold_return = 0
    if len(df) >= 2:  # 至少需要兩個數據點
        try:
            # 使用 .iloc 安全獲取第一個和最後一個價格
            first_price = float(df['Close'].iloc[0])
            last_price = float(df['Close'].iloc[-1])
            
            # 確保安全的除法
            if first_price > 0:  # 防止除零錯誤
                buy_hold_return = (last_price - first_price) / first_price * 100
        except Exception as e:
            log_message(f"計算買入並持有收益時發生錯誤: {str(e)}", level="warning")
    
    # 創建交易記錄 DataFrame
    trades_df = pd.DataFrame()
    if trades:  # 如果有交易記錄
        # 確保所有交易記錄中的值都是標量
        clean_trades = []
        for trade in trades:
            clean_trade = {
                'Date': trade['Date'],
                'Type': trade['Type'],
                'Price': float(trade['Price']) if isinstance(trade['Price'], pd.Series) else trade['Price'],
                'Shares': int(trade['Shares']) if isinstance(trade['Shares'], pd.Series) else trade['Shares'],
                'Value': float(trade['Value']) if isinstance(trade['Value'], pd.Series) else trade['Value'],
                'Capital': float(trade['Capital']) if isinstance(trade['Capital'], pd.Series) else trade['Capital']
            }
            clean_trades.append(clean_trade)
            
        trades_df = pd.DataFrame(clean_trades)
        trades_df.set_index('Date', inplace=True)
    
    # 統計信息
    stats = {
        'Initial Capital': float(initial_capital),  # 確保所有數值都是基本類型而非 Series
        'Final Value': float(final_value),
        'Total Return (%)': float(total_return),
        'Buy & Hold Return (%)': float(buy_hold_return),
        'Number of Trades': len(trades),
        'Win Rate (%)': 0.0
    }
    
    # 計算勝率
    if len(trades) >= 2:  # 至少需要一組買賣交易
        buy_trades = [t for t in trades if t['Type'] == 'Buy']
        sell_trades = [t for t in trades if t['Type'] == 'Sell']
        
        if buy_trades and sell_trades:  # 確保有買入和賣出記錄
            # 計算獲利交易次數
            wins = 0
            pairs = min(len(buy_trades), len(sell_trades))  # 取較小值，確保成對
            
            for i in range(pairs):
                # 確保比較的是純量值而非Series
                buy_price = float(buy_trades[i]['Price']) if isinstance(buy_trades[i]['Price'], pd.Series) else buy_trades[i]['Price']
                sell_price = float(sell_trades[i]['Price']) if isinstance(sell_trades[i]['Price'], pd.Series) else sell_trades[i]['Price']
                
                # 如果賣出價高於買入價，則為盈利交易
                if sell_price > buy_price:
                    wins += 1
            
            # 計算勝率
            stats['Win Rate (%)'] = float((wins / pairs) * 100 if pairs > 0 else 0)
    
    return backtest_results, trades_df, stats

def plot_backtest_results(data, trades_df):
    """
    繪製回測結果圖
    
    參數:
    - data: 回測結果 DataFrame
    - trades_df: 交易記錄 DataFrame
    
    返回:
    - matplotlib 圖表
    """
    # 確保 data 是 DataFrame
    if not isinstance(data, pd.DataFrame) or data.empty:
        log_message("繪圖數據為空或格式錯誤", level="error")
        return None
        
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 繪製股價和移動平均線
    ax.plot(data.index, data['Close'], label='收盤價', color='blue', alpha=0.5)
    
    # 查找並繪製移動平均線
    ma_columns = [col for col in data.columns if isinstance(col, str) and col.startswith('MA')]
    for col in ma_columns:
        window = col[2:]  # 提取數字部分
        ax.plot(data.index, data[col], label=f'{window}日均線', 
                alpha=0.8, linewidth=1.5)
    
    # 標記買賣點
    if isinstance(trades_df, pd.DataFrame) and not trades_df.empty:
        buy_signals = trades_df[trades_df['Type'] == 'Buy']
        sell_signals = trades_df[trades_df['Type'] == 'Sell']
        
        if not buy_signals.empty:
            # 確保繪圖數據是純量
            buy_x = buy_signals.index
            buy_y = [float(p) if isinstance(p, pd.Series) else p for p in buy_signals['Price']]
            ax.scatter(buy_x, buy_y, 
                      marker='^', color='green', s=120, label='買入信號')
        if not sell_signals.empty:
            # 確保繪圖數據是純量
            sell_x = sell_signals.index
            sell_y = [float(p) if isinstance(p, pd.Series) else p for p in sell_signals['Price']]
            ax.scatter(sell_x, sell_y, 
                      marker='v', color='red', s=120, label='賣出信號')
    
    # 添加網格和美化
    ax.set_title('交易策略回測結果', fontsize=15)
    ax.set_xlabel('日期', fontsize=12)
    ax.set_ylabel('價格', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best')
    
    # 格式化x軸日期標籤
    fig.autofmt_xdate()
    
    # 添加註釋 - 使用數據中的第一個和最後一個日期
    if len(data) > 1:
        try:
            # 安全地獲取日期和價格
            first_date = data.index[0]
            last_date = data.index[-1]
            first_price = float(data['Close'].iloc[0])
            last_price = float(data['Close'].iloc[-1])
            
            # 僅當日期是日期類型時才格式化
            first_date_str = first_date.strftime("%Y-%m-%d") if hasattr(first_date, 'strftime') else str(first_date)
            last_date_str = last_date.strftime("%Y-%m-%d") if hasattr(last_date, 'strftime') else str(last_date)
            
            ax.annotate(f'開始: {first_date_str}', 
                       xy=(first_date, first_price),
                       xytext=(10, 30), textcoords='offset points',
                       arrowprops=dict(arrowstyle='->'))
            
            ax.annotate(f'結束: {last_date_str}', 
                       xy=(last_date, last_price),
                       xytext=(-70, -30), textcoords='offset points',
                       arrowprops=dict(arrowstyle='->'))
        except Exception as e:
            log_message(f"添加圖表註釋時發生錯誤: {str(e)}", level="warning")
    
    plt.tight_layout()
    return fig 