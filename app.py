import streamlit as st
import pandas as pd
from data import *
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime, timedelta, date
import numpy as np

# 設置頁面配置
st.set_page_config(
    page_title="台股資訊分析儀表板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 設置緩存過期時間（秒）
CACHE_TTL = {
    'high_freq': 1800,  # 頻繁更新的數據（30分鐘）
    'medium_freq': 3600,  # 中等頻率更新的數據（1小時）
    'low_freq': 86400,  # 較少更新的數據（24小時）
}

# 首次運行標誌
@st.cache_data(ttl=None)
def get_run_flag():
    return {"first_run": True}

first_run_flag = get_run_flag()

# 初始化會話狀態
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = 0

# 添加錯誤和信息提示容器
def create_message_container():
    if "message_container" not in st.session_state:
        st.session_state.message_container = {
            "error": None,
            "info": None,
            "warning": None
        }
    return st.session_state.message_container

def show_error(message):
    """显示错误信息"""
    container = create_message_container()
    container["error"] = message

def show_info(message):
    """显示信息提示"""
    container = create_message_container()
    container["info"] = message

def show_warning(message):
    """显示警告信息"""
    container = create_message_container()
    container["warning"] = message

def display_messages():
    """显示所有存储的消息"""
    container = create_message_container()
    
    if container["error"]:
        st.error(container["error"])
        container["error"] = None
        
    if container["warning"]:
        st.warning(container["warning"])
        container["warning"] = None
        
    if container["info"]:
        st.info(container["info"])
        container["info"] = None

# 添加自定義 CSS 樣式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #333;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .info-text {
        color: #555;
        font-size: 0.9rem;
    }
    .data-date {
        color: #2196F3;
        font-weight: bold;
    }
    .stDataFrame {
        border: 1px solid #ddd;
        border-radius: 5px;
    }
    .sidebar-header {
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .sidebar-subheader {
        font-size: 1rem;
        font-weight: bold;
        margin-top: 1rem;
        margin-bottom: 0.3rem;
    }
    .sidebar-text {
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # 側邊欄設計
    with st.sidebar:
        st.markdown("<div class='sidebar-header'>台股資訊分析平台</div>", unsafe_allow_html=True)
        st.markdown("<div class='sidebar-text'>提供台灣股市各類數據分析，包括三大法人買賣超、外資未平倉、成交量等資訊。</div>", unsafe_allow_html=True)
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # 添加股票代號查詢功能 - 移動到側邊欄
        st.markdown("<div class='sidebar-subheader'>股票查詢</div>", unsafe_allow_html=True)
        with st.form(key='stock_search_form'):
            input_value = st.text_input(label='請輸入股票代號', placeholder='例如: 2330')
            submit_button = st.form_submit_button(label='查詢')

        if submit_button and input_value:
            try:
                # 顯示神秘金字塔連結，但不顯示股票名稱和其他信息
                target_url = f"https://norway.twsthr.info/StockHolders.aspx?stock={input_value}"
                st.markdown(f"[<b>{input_value} 的大戶持股資訊</b>]({target_url})", unsafe_allow_html=True)
                
                # 嘗試獲取股票基本信息，但不顯示結果
                stock_info = get_stock_info(input_value)
            except Exception as e:
                # 保留錯誤處理但不顯示錯誤信息
                log_message(f"查詢股票資訊時發生錯誤: {e}", level="error")
        
        # 使用說明
        with st.expander("📖 使用說明"):
            st.markdown("""
            1. **每日盤後資訊**：查看三大法人買賣超、外資未平倉、成交量等數據
            2. **外資投信同買**：顯示外資和投信同時買超的股票
            3. **外資買賣超**：顯示外資買超、賣超前50名股票
            4. **投信買賣超**：顯示投信買超、賣超前50名股票
            5. **台幣匯率**：查看台幣兌美元匯率走勢
            6. **交易回測**：輸入股票代號進行交易策略回測
            """)
        
        # 數據更新時間
        st.markdown("<div class='sidebar-subheader'>數據更新</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='sidebar-text'>最後更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>", unsafe_allow_html=True)
        if st.button("重新整理數據"):
            st.rerun()
    
    # 主內容區域
    # 添加標題和描述
    st.markdown("<div class='main-header'>台股資訊分析儀表板</div>", unsafe_allow_html=True)
    st.markdown("<p class='info-text'>此儀表板提供台股市場的即時資訊，包括三大法人買賣超、外資與投信動向、成交量資訊及台幣匯率等數據。</p>", unsafe_allow_html=True)
    
    # 显示消息提示
    display_messages()
    
    # 使用會話狀態跟蹤當前標籤頁
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "每日盤後資訊"
        
    # 定義標籤頁
    tabs = ["每日盤後資訊", "外資投信同買", "外資買賣超", "投信買賣超", "台幣匯率", "交易回測"]
    
    # 使用水平容器作為自定義標籤欄
    cols = st.columns(len(tabs))
    for i, tab in enumerate(tabs):
        if cols[i].button(tab, key=f"tab_{i}", use_container_width=True):
            st.session_state.active_tab = tab
    
    # 顯示標籤內容
    st.write("---")  # 分隔線
    
    # 根據當前標籤顯示相應內容
    if st.session_state.active_tab == "每日盤後資訊":
        st.markdown("<div class='sub-header'>三大法人買賣超</div>", unsafe_allow_html=True)
        
        # 添加進度條
        with st.spinner("正在加載三大法人數據..."):
            df_three, data_date = cached_three_data()
        
        if not df_three.empty:
            df_three = df_three.reset_index(drop=True)  
            st.markdown(f"<p>數據日期：<span class='data-date'>{data_date}</span></p>", unsafe_allow_html=True)
            
            # 設置默認全部顯示三大法人數據（移除過濾選項後）
            filtered_df = df_three.copy()
            # 刪除基於 show_foreign、show_investment 和 show_dealer 的過濾
            
            # 將 DataFrame 顯示為表格
            st.dataframe(filtered_df, use_container_width=True)
            
            # 添加可視化圖表
            fig = go.Figure(go.Bar(
                x=filtered_df['單位名稱'],
                y=filtered_df['買賣差'],
                marker_color=['#FF9800' if x < 0 else '#4CAF50' for x in filtered_df['買賣差']],
                text=filtered_df['買賣差'],
                textposition='auto'
            ))
            fig.update_layout(
                title='三大法人買賣超金額 (億元)',
                xaxis_title='法人類別',
                yaxis_title='買賣超金額 (億元)',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("無法獲取三大法人數據")
        
        st.markdown("<div class='sub-header'>外資未平倉</div>", unsafe_allow_html=True)
        with st.spinner("正在加載期貨數據..."):
            df_futures = cached_futures()
        
        if not df_futures.empty:
            st.dataframe(df_futures, use_container_width=True)
            
            # 添加外資未平倉視覺化
            fig = go.Figure()
            for col in df_futures.columns:
                fig.add_trace(go.Bar(
                    x=df_futures.index,
                    y=df_futures[col],
                    name=col
                ))
            
            fig.update_layout(
                title='三大法人期貨未平倉情況',
                xaxis_title='法人類別',
                height=400,
                barmode='group'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("無法獲取期貨數據")
        
        st.markdown("<div class='sub-header'>成交量趨勢</div>", unsafe_allow_html=True)
        with st.spinner("正在加載成交量數據..."):
            df_turnover = cached_turnover()
        
        if not df_turnover.empty:
            df_turnover.set_index('日期', inplace=True)
            
            # 添加成交量圖表
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_turnover.index,
                y=df_turnover['成交量'],
                name='成交量',
                marker_color='rgba(58, 71, 80, 0.6)'
            ))
            
            fig.update_layout(
                title='每日成交量趨勢',
                xaxis_title='日期',
                yaxis_title='成交量 (億元)',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("無法獲取成交量數據")
    
    elif st.session_state.active_tab == "外資投信同買":
        st.markdown("<div class='sub-header'>外資與投信同步買超</div>", unsafe_allow_html=True)
        
        with st.spinner("正在加載外資投信同買資訊..."):
            df_com_buy, data_date = cached_for_ib_common()
        
        if not df_com_buy.empty:
            st.markdown(f"<p>數據日期：<span class='data-date'>{data_date}</span></p>", unsafe_allow_html=True)
            
            st.dataframe(df_com_buy, use_container_width=True)
            
            # 添加資訊提示
            st.info("外資和投信同時買超的股票，通常代表強力買盤，值得關注")
        else:
            st.warning("無法獲取外資投信同買資訊或當日無同買個股")
    
    elif st.session_state.active_tab == "外資買賣超":
        st.markdown("<div class='sub-header'>外資買超 TOP 50</div>", unsafe_allow_html=True)
        
        with st.spinner("正在加載外資買超資訊..."):
            df_buy_top50, df_sell_top50, data_date = cached_foreign_investors_trading()
        
        if not df_buy_top50.empty:
            st.markdown(f"<p>數據日期：<span class='data-date'>{data_date}</span></p>", unsafe_allow_html=True)
            
            st.dataframe(df_buy_top50, use_container_width=True)
        else:
            st.warning("無法獲取外資買超資訊")
        
        st.markdown("<div class='sub-header'>外資賣超 TOP 50</div>", unsafe_allow_html=True)
        
        if not df_sell_top50.empty:
            st.dataframe(df_sell_top50, use_container_width=True)
        else:
            st.warning("無法獲取外資賣超資訊")
    
    elif st.session_state.active_tab == "投信買賣超":
        st.markdown("<div class='sub-header'>投信買超 TOP 50</div>", unsafe_allow_html=True)
        
        with st.spinner("正在加載投信買超資訊..."):
            df_buy_top50, df_sell_top50, data_date = cached_investment_trust_trading()
        
        if not df_buy_top50.empty:
            st.markdown(f"<p>數據日期：<span class='data-date'>{data_date}</span></p>", unsafe_allow_html=True)
            
            st.dataframe(df_buy_top50, use_container_width=True)
        else:
            st.warning("無法獲取投信買超資訊")
        
        st.markdown("<div class='sub-header'>投信賣超 TOP 50</div>", unsafe_allow_html=True)
        
        if not df_sell_top50.empty:
            st.dataframe(df_sell_top50, use_container_width=True)
        else:
            st.warning("無法獲取投信賣超資訊")
    
    elif st.session_state.active_tab == "台幣匯率":
        st.markdown("<div class='sub-header'>台幣匯率走勢</div>", unsafe_allow_html=True)
        
        with st.spinner("正在加載匯率資訊..."):
            History_ExchangeRate = cached_exchange_rate()
        
        if not History_ExchangeRate.empty:
            # 使用預設日期範圍（最近一個月）
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            start_date_str = start_date.strftime('%Y/%m/%d')
            end_date_str = end_date.strftime('%Y/%m/%d')
            
            # 過濾日期範圍內的數據
            mask = (pd.to_datetime(History_ExchangeRate.index) >= pd.to_datetime(start_date_str)) & \
                   (pd.to_datetime(History_ExchangeRate.index) <= pd.to_datetime(end_date_str))
            
            filtered_exchange_rate = History_ExchangeRate[mask]
            
            # 如果過濾後沒有數據，使用原始數據
            if filtered_exchange_rate.empty:
                filtered_exchange_rate = History_ExchangeRate
                st.warning(f"最近一個月內沒有匯率數據，顯示所有可用數據")
            
            # 創建匯率走勢圖
            fig = go.Figure()
    
            fig.add_trace(go.Scatter(
                x=filtered_exchange_rate.index, 
                y=filtered_exchange_rate['buy_rate'], 
                mode='lines+markers',
                name='買進匯率',
                line=dict(color='#4CAF50', width=2)
            ))
            
            fig.add_trace(go.Scatter(
                x=filtered_exchange_rate.index, 
                y=filtered_exchange_rate['sell_rate'], 
                mode='lines+markers',
                name='賣出匯率',
                line=dict(color='#FF5722', width=2)
            ))
            
            fig.update_layout(
                title='台幣兌美元匯率走勢',
                xaxis_title='日期',
                yaxis_title='匯率',
                height=500,
                yaxis_range=[30, 33.5],
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 顯示匯率資料表
            st.markdown("<div class='sub-header'>匯率歷史數據</div>", unsafe_allow_html=True)
            st.dataframe(filtered_exchange_rate.sort_index(ascending=False), use_container_width=True)
        else:
            st.warning("無法獲取匯率資訊")
    
    elif st.session_state.active_tab == "交易回測":
        st.markdown("<div class='sub-header'>交易回測系統</div>", unsafe_allow_html=True)
        st.markdown("<p class='info-text'>透過歷史數據模擬不同交易策略的表現，評估策略的獲利能力和風險。</p>", unsafe_allow_html=True)
        
        # 將回測參數設置放入表單中，確保所有輸入一次性提交
        with st.form(key="backtest_form"):
            st.markdown("##### 回測設置")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 股票選擇
                stock_options = {
                    "2330": "台積電",
                    "2317": "鴻海",
                    "2454": "聯發科",
                    "2308": "台達電",
                    "2412": "中華電",
                    "2881": "富邦金",
                    "1301": "台塑",
                    "1303": "南亞",
                    "2882": "國泰金",
                    "2303": "聯電"
                }
                selected_stock = st.selectbox(
                    "選擇股票", 
                    list(stock_options.keys()),
                    format_func=lambda x: f"{x} ({stock_options[x]})",
                    help="從列表中選擇一支股票，或在搜索框中輸入代碼搜索"
                )
                
                use_test_data = st.checkbox(
                    "使用測試數據", 
                    value=False,
                    help="使用內置的測試數據進行回測，這些數據專為測試交易策略而設計，包含足夠的交易信號"
                )
                
                # 初始資金
                initial_capital = st.number_input(
                    "初始資金 (新台幣)", 
                    min_value=10000, 
                    max_value=10000000, 
                    value=100000, 
                    step=10000,
                    help="設置回測初始資金金額，資金越多可交易的股數越多"
                )
                
                # 交易手續費
                fee_rate = st.slider(
                    "交易手續費率 (%)", 
                    min_value=0.0, 
                    max_value=0.5, 
                    value=0.1425, 
                    step=0.01, 
                    format="%.4f",
                    help="台股標準手續費率為0.1425%，可根據券商優惠調整"
                )
                
                # 股價變動停損/停利
                stop_loss = st.slider(
                    "停損比例 (%)", 
                    min_value=0, 
                    max_value=20, 
                    value=5, 
                    step=1,
                    help="設置0表示不啟用停損，建議設置5-10%的停損以控制風險"
                )
                take_profit = st.slider(
                    "停利比例 (%)", 
                    min_value=0, 
                    max_value=50, 
                    value=20, 
                    step=1,
                    help="設置0表示不啟用停利，可根據策略和個人風險偏好調整"
                )
            
            with col2:
                # 回測時間範圍
                st.info("💡 提示: 建議回測時間至少包含3個月以上，以獲得更可靠的結果", icon="💡")
                # 使用 datetime.date.today() 而非 date.today() 來避免可能的命名空間問題
                current_date = datetime.now().date()
                default_start_date = current_date - timedelta(days=365)
                backtest_start_date = st.date_input(
                    "回測開始日期", 
                    value=default_start_date,
                    help="回測起始日期，建議選擇至少1年前的日期以獲得足夠數據量"
                )
                backtest_end_date = st.date_input(
                    "回測結束日期", 
                    value=current_date,
                    help="回測結束日期，默認為今天"
                )
                
                # 交易策略選擇
                strategy = st.selectbox(
                    "選擇交易策略", 
                    ["移動平均線交叉", "RSI超買超賣", "MACD交叉", "布林通道突破", "外資買超"],
                    help="選擇要回測的交易策略"
                )
                
                # 根據選擇的策略顯示相應的參數設置
                if strategy == "移動平均線交叉":
                    st.info("📊 移動平均線交叉策略是利用短期與長期移動平均線的交叉點作為買賣信號。當短期線向上穿過長期線時買入，向下穿過時賣出。", icon="📊")
                    short_window = st.slider(
                        "短期窗口", 
                        min_value=5, 
                        max_value=30, 
                        value=5, 
                        step=1,
                        help="短期移動平均線的時間窗口，通常為5-10天"
                    )
                    long_window = st.slider(
                        "長期窗口", 
                        min_value=20, 
                        max_value=120, 
                        value=20, 
                        step=5,
                        help="長期移動平均線的時間窗口，常用20-60天"
                    )
                    
                    # 防止用戶設置錯誤的參數
                    if short_window >= long_window:
                        st.warning("⚠️ 短期窗口應小於長期窗口！請調整參數", icon="⚠️")
                
                elif strategy == "RSI超買超賣":
                    st.info("📉 RSI(相對強弱指標)策略利用市場超買超賣狀態判斷。當RSI低於超賣閾值時買入，高於超買閾值時賣出。", icon="📉")
                    rsi_period = st.slider(
                        "RSI週期", 
                        min_value=7, 
                        max_value=21, 
                        value=14, 
                        step=1,
                        help="計算RSI的時間窗口，標準為14天"
                    )
                    rsi_lower = st.slider(
                        "RSI超賣閾值", 
                        min_value=20, 
                        max_value=40, 
                        value=30, 
                        step=1,
                        help="RSI低於此值視為超賣信號，通常設為30"
                    )
                    rsi_upper = st.slider(
                        "RSI超買閾值", 
                        min_value=60, 
                        max_value=80, 
                        value=70, 
                        step=1,
                        help="RSI高於此值視為超買信號，通常設為70"
                    )
                
                elif strategy == "MACD交叉":
                    st.info("📈 MACD策略利用MACD線與信號線的交叉以及MACD柱狀圖的變化判斷買賣時機。當MACD線上穿信號線時買入，下穿時賣出。", icon="📈")
                    macd_fast = st.slider(
                        "MACD快線", 
                        min_value=8, 
                        max_value=20, 
                        value=12, 
                        step=1,
                        help="MACD快速移動平均線參數，標準為12"
                    )
                    macd_slow = st.slider(
                        "MACD慢線", 
                        min_value=20, 
                        max_value=40, 
                        value=26, 
                        step=1,
                        help="MACD慢速移動平均線參數，標準為26"
                    )
                    macd_signal = st.slider(
                        "信號線", 
                        min_value=5, 
                        max_value=12, 
                        value=9, 
                        step=1,
                        help="MACD信號線參數，標準為9"
                    )
                
                elif strategy == "布林通道突破":
                    st.info("🔔 布林通道策略利用價格突破上軌或下軌作為交易信號。當價格跌破下軌后回升時買入，突破上軌后回落時賣出。", icon="🔔")
                    bollinger_window = st.slider(
                        "布林通道窗口", 
                        min_value=10, 
                        max_value=30, 
                        value=20, 
                        step=1,
                        help="計算移動平均線的時間窗口，標準為20天"
                    )
                    bollinger_std = st.slider(
                        "標準差倍數", 
                        min_value=1.0, 
                        max_value=3.0, 
                        value=2.0, 
                        step=0.1,
                        help="決定通道寬度的標準差倍數，標準為2倍"
                    )
            
            # 提交按鈕 - 確保點擊後保持在交易回測頁面
            submit_button = st.form_submit_button(label="執行回測", use_container_width=True)
            
            # 確保表單提交後保持在交易回測頁面
            if submit_button:
                st.session_state.active_tab = "交易回測"
                # 使用兼容性函數設置查詢參數
                set_query_params({"tab": "交易回測"})
        
        # 如果表單被提交
        if submit_button:
            with st.spinner("正在執行回測計算..."):
                # 獲取真實歷史數據
                try:
                    # 如果用戶選擇了使用測試數據，則將股票代碼設置為"TEST"
                    if use_test_data:
                        actual_stock_id = "TEST"
                        st.info("使用測試數據進行回測，這些數據專為測試交易策略而設計，包含足夠的交易信號。")
                    else:
                        actual_stock_id = selected_stock
                    
                    # 獲取策略參數，根據所選策略建立相應的參數字典
                    if strategy == "移動平均線交叉":
                        strategy_params = {
                            "short_window": short_window,
                            "long_window": long_window
                        }
                    elif strategy == "RSI超買超賣":
                        strategy_params = {
                            "rsi_period": rsi_period,
                            "oversold": rsi_lower,
                            "overbought": rsi_upper
                        }
                    elif strategy == "MACD交叉":
                        strategy_params = {
                            "fast_period": macd_fast,
                            "slow_period": macd_slow,
                            "signal_period": macd_signal
                        }
                    elif strategy == "布林通道突破":
                        strategy_params = {
                            "bollinger_period": bollinger_window,
                            "num_std": bollinger_std
                        }
                    else:
                        strategy_params = {}
                    
                    # 記錄回測參數信息
                    log_message(f"開始回測 {actual_stock_id}，初始資金：{initial_capital}")
                    log_message(f"回測時間範圍：{backtest_start_date} 至 {backtest_end_date}")
                    
                    # 設定回測時間範圍
                    start_date_str = backtest_start_date.strftime("%Y-%m-%d")
                    end_date_str = backtest_end_date.strftime("%Y-%m-%d")
                    
                    # 顯示進度條
                    progress_bar = st.progress(0)
                    
                    # 第一步：獲取股票歷史數據
                    progress_bar.progress(10, text="正在獲取歷史數據...")
                    df_stock = cached_get_stock_history(actual_stock_id, start_date_str, end_date_str)
                    
                    if df_stock.empty:
                        st.error(f"無法獲取 {actual_stock_id} 的歷史數據，請檢查股票代碼或選擇其他日期範圍")
                        return
                    
                    # 第二步：計算技術指標
                    progress_bar.progress(30, text="正在計算技術指標...")
                    df_with_indicators = cached_calculate_technical_indicators(df_stock)
                    
                    # 第三步：執行回測
                    progress_bar.progress(50, text="正在執行策略回測...")
                    backtest_results = backtest_strategy(
                        df_with_indicators, 
                        strategy, 
                        strategy_params,
                        initial_capital=initial_capital
                    )
                    
                    # 检查回测是否成功
                    if not backtest_results.get("success", False):
                        st.error(f"回測失敗：{backtest_results.get('error', '未知錯誤')}")
                        progress_bar.progress(100, text="回測完成，但出現錯誤")
                        
                        # 為主要變數提供預設值，防止後續代碼出錯
                        portfolio_df = pd.DataFrame(columns=['淨值', '基準淨值'])
                        portfolio_df['淨值'] = [initial_capital]
                        trades = []
                        trades_df = pd.DataFrame()
                        positions = []
                        trading_count = 0
                        # 跳過回測結果顯示
                        return
                    
                    # 获取回测结果中的portfolio_df、trades和positions
                    portfolio_df = backtest_results.get("portfolio_df", pd.DataFrame())
                    trades = backtest_results.get("trades", [])
                    positions = backtest_results.get("positions", [])
                    
                    # 转换交易记录为DataFrame以便显示
                    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
                    
                    # 第四步：生成報告
                    progress_bar.progress(80, text="正在生成回測報告...")
                    
                    # 回測結果
                    st.markdown("<div class='sub-header'>回測結果</div>", unsafe_allow_html=True)
                    
                    # 回測基本信息
                    st.markdown(f"""
                    **回測信息:**
                    - 股票: {actual_stock_id} ({stock_options.get(actual_stock_id, '')})
                    - 策略: {strategy}
                    - 回測時間: {start_date_str} 至 {end_date_str}
                    - 初始資金: {initial_capital:,.0f} 元
                    """)
                    
                    # 顯示回測結果摘要
                    st.markdown("### 回測結果摘要")
                    
                    # 使用指標卡片展示關鍵績效指標
                    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
                    with kpi_col1:
                        st.metric(
                            label="最終資產", 
                            value=f"{portfolio_df['淨值'].iloc[-1]:,.0f} 元", 
                            delta=f"{backtest_results.get('總收益率', '0.00%')}",
                            delta_color="normal"
                        )
                        st.metric(
                            label="最大回撤", 
                            value=backtest_results.get("最大回撤", "0.00%"), 
                            delta=None
                        )
                    
                    with kpi_col2:
                        st.metric(
                            label="總收益率", 
                            value=backtest_results.get("總收益率", "0.00%"), 
                            delta=None,
                            delta_color="normal"
                        )
                        st.metric(
                            label="夏普比率", 
                            value=backtest_results.get("夏普比率", "N/A"), 
                            delta=None,
                            delta_color="off"
                        )
                    
                    # 確保交易次數可以正確處理，不論是整數還是字符串
                    trading_count_raw = backtest_results.get("交易次數", 0)
                    if isinstance(trading_count_raw, str):
                        trading_count = int(trading_count_raw.replace("次", ""))
                    else:
                        trading_count = int(trading_count_raw)
                    
                    with kpi_col3:
                        st.metric(
                            label="交易次數", 
                            value=f"{trading_count} 次",
                            delta=f"勝率: {backtest_results.get('勝率', '0.00%')}",
                            delta_color="normal"
                        )
                        st.metric(
                            label="年化報酬率", 
                            value=backtest_results.get("年化收益率", "0.00%"), 
                            delta=None
                        )
                    
                    # 添加回測績效解釋
                    if trading_count > 0:
                        performance_explanation = ""
                        total_return = backtest_results.get("總收益率", "0.00%").replace("%", "")
                        if float(total_return) > 0:
                            performance_explanation += f"策略在測試期間獲得了 **{backtest_results.get('總收益率', '0.00%')}** 的總收益，"
                            performance_explanation += f"盈虧比為 **{backtest_results.get('盈虧比', '0.00')}**，表明策略的風險收益特性。"
                        else:
                            performance_explanation += f"策略在測試期間虧損了 **{backtest_results.get('總收益率', '0.00%')}**，"
                            performance_explanation += f"盈虧比為 **{backtest_results.get('盈虧比', '0.00')}**，表明相對於所承擔的風險，策略表現不佳。"
                        
                        win_rate = backtest_results.get("勝率", "0.00%").replace("%", "")
                        if float(win_rate) > 50:
                            performance_explanation += f" 策略的勝率為 **{backtest_results.get('勝率', '0.00%')}**，"
                            performance_explanation += "大多數交易都是獲利的。"
                        else:
                            performance_explanation += f" 策略的勝率為 **{backtest_results.get('勝率', '0.00%')}**，"
                            performance_explanation += "大多數交易都是虧損的，但獲利交易的平均收益可能高於虧損交易的平均虧損。"
                        
                        max_drawdown = backtest_results.get("最大回撤", "0.00%").replace("%", "")
                        if float(max_drawdown) > 20:
                            performance_explanation += f" 最大回撤為 **{backtest_results.get('最大回撤', '0.00%')}**，"
                            performance_explanation += "表明策略在某些時期面臨較大的風險和波動，需要較好的風險承受能力。"
                        else:
                            performance_explanation += f" 最大回撤為 **{backtest_results.get('最大回撤', '0.00%')}**，"
                            performance_explanation += "顯示策略的下行風險相對可控。"
                        
                        st.info(performance_explanation, icon="💡")
                    
                    # 顯示詳細指標
                    show_detailed_metrics = st.checkbox("顯示詳細績效指標", value=False)
                    if show_detailed_metrics:
                        st.markdown("#### 詳細績效指標")
                        metrics_df = pd.DataFrame({
                            '指標': [
                                '初始資金', '最終資產', '總收益率', '年化報酬率', 
                                '交易次數', '勝率', '盈虧比', '最大回撤',
                                '夏普比率', '買入並持有收益率'
                            ],
                            '數值': [
                                f"{initial_capital:,.0f} 元",
                                f"{portfolio_df['淨值'].iloc[-1]:,.0f} 元",
                                f"{backtest_results.get('總收益率', '0.00%')}",
                                f"{backtest_results.get('年化收益率', '0.00%')}",
                                f"{trading_count} 次",
                                f"{backtest_results.get('勝率', '0.00%')}",
                                f"{backtest_results.get('盈虧比', '0.00')}",
                                f"{backtest_results.get('最大回撤', '0.00%')}",
                                f"{backtest_results.get('夏普比率', 'N/A')}",
                                f"{backtest_results.get('買入並持有收益率', 'N/A')}"
                            ]
                        })
                        st.dataframe(metrics_df, use_container_width=True)
                    
                    # 顯示淨值曲線圖
                    st.markdown("#### 淨值曲線")
                    
                    # 建立每日淨值圖表
                    fig = go.Figure()
                    
                    # 添加策略淨值曲線
                    fig.add_trace(go.Scatter(
                        x=portfolio_df.index, 
                        y=portfolio_df['淨值'], 
                        mode='lines',
                        name=f'策略淨值 ({strategy})',
                        line=dict(color='#1E88E5', width=2)
                    ))
                    
                    # 如果'基準淨值'不存在，則計算基本的買入持有基準
                    if '基準淨值' not in portfolio_df.columns:
                        try:
                            # 計算基準淨值 (買入持有)
                            log_message("開始計算基準淨值")
                            
                            # 確保 df_stock 的索引是日期型態
                            if not isinstance(df_stock.index, pd.DatetimeIndex):
                                df_stock.index = pd.to_datetime(df_stock.index)
                                log_message("轉換 df_stock 索引為日期型態")
                            
                            # 確保 portfolio_df 的索引是日期型態
                            if not isinstance(portfolio_df.index, pd.DatetimeIndex):
                                portfolio_df.index = pd.to_datetime(portfolio_df.index)
                                log_message("轉換 portfolio_df 索引為日期型態")
                            
                            # 獲取第一天和最後一天的價格
                            start_price = df_stock['收盤價'].iloc[0]
                            log_message(f"起始價格: {start_price}")
                            
                            # 為每一個 portfolio_df 中的日期找到對應的股票價格
                            benchmark_values = []
                            valid_dates = []
                            
                            for current_date in portfolio_df.index:
                                # 找到最接近的交易日
                                closest_date = df_stock.index[df_stock.index <= current_date][-1] if any(df_stock.index <= current_date) else df_stock.index[0]
                                price = df_stock.loc[closest_date, '收盤價']
                                benchmark_values.append(price / start_price)
                                valid_dates.append(current_date)
                                
                            # 創建基準淨值 DataFrame
                            benchmark_df = pd.DataFrame({'基準淨值': benchmark_values}, index=valid_dates)
                            log_message(f"成功創建基準淨值，數據點數量: {len(benchmark_df)}")
                            
                            # 添加基準線(買入持有)
                            fig.add_trace(go.Scatter(
                                x=benchmark_df.index, 
                                y=benchmark_df['基準淨值'], 
                                mode='lines',
                                name='基準淨值 (買入持有)',
                                line=dict(color='#FF5252', width=1.5, dash='dash')
                            ))
                        except Exception as e:
                            log_message(f"計算基準淨值時發生錯誤: {e}", level="error")
                            # 如果無法計算基準淨值，則使用最簡單的方式生成平行線作為基準
                            try:
                                # 如果上述計算方法失敗，創建一個簡單的平行基準線
                                log_message("使用簡單方法創建基準線")
                                # 生成與 portfolio_df 相同長度的平直線基準 (起始值為1)
                                simple_benchmark = [1.0] * len(portfolio_df)
                                fig.add_trace(go.Scatter(
                                    x=portfolio_df.index, 
                                    y=simple_benchmark, 
                                    mode='lines',
                                    name='買入持有基準',
                                    line=dict(color='#FF5252', width=1.5, dash='dash')
                                ))
                                log_message("成功創建簡單基準線")
                            except Exception as inner_e:
                                log_message(f"創建簡單基準線時也發生錯誤: {inner_e}", level="error")
                                st.warning("無法顯示基準線，僅顯示策略淨值")
                    else:
                        # 如果已有基準淨值列，直接使用
                        fig.add_trace(go.Scatter(
                            x=portfolio_df.index, 
                            y=portfolio_df['基準淨值'], 
                            mode='lines',
                            name='基準淨值 (買入持有)',
                            line=dict(color='#FF5252', width=1.5, dash='dash')
                        ))
                    
                    # 根據獲利情況標註背景顏色
                    total_return = backtest_results.get("總收益率", "0.00%").replace("%", "")
                    if float(total_return) > 0:
                        # 獲利背景設為綠色
                        background_color = 'rgba(232, 245, 233, 0.8)'
                    else:
                        # 虧損背景設為淺紅色
                        background_color = 'rgba(255, 235, 238, 0.8)'
                    
                    # 標註最大回撤區間
                    if 'drawdown_start' in backtest_results and 'drawdown_end' in backtest_results:
                        fig.add_vrect(
                            x0=backtest_results['drawdown_start'],
                            x1=backtest_results['drawdown_end'],
                            fillcolor="rgba(255, 0, 0, 0.1)",
                            opacity=0.5,
                            layer="below",
                            line_width=0,
                            annotation_text="最大回撤區間",
                            annotation_position="top left"
                        )
                    
                    # 美化圖表
                    fig.update_layout(
                        title='交易策略淨值變化',
                        xaxis_title='日期',
                        yaxis_title='淨值 (起始=1)',
                        legend=dict(
                            yanchor="top",
                            y=0.99,
                            xanchor="left",
                            x=0.01,
                            bgcolor='rgba(255, 255, 255, 0.8)'
                        ),
                        hovermode="x unified",
                        plot_bgcolor=background_color,
                        height=450,
                        margin=dict(l=0, r=0, t=40, b=0),
                    )
                    
                    # 添加網格線
                    fig.update_xaxes(
                        showgrid=True, 
                        gridwidth=1, 
                        gridcolor='rgba(0,0,0,0.1)'
                    )
                    fig.update_yaxes(
                        showgrid=True, 
                        gridwidth=1, 
                        gridcolor='rgba(0,0,0,0.1)'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 顯示交易清單
                    st.markdown("#### 交易明細")
                    show_trades = st.checkbox("顯示所有交易", value=False)
                    
                    if show_trades and not trades_df.empty:
                        # 美化交易DataFrame
                        trades_display = trades_df.copy()
                        
                        # 設置正負收益的顏色
                        def color_profit(val):
                            color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                            return f'color: {color}'
                        
                        # 應用樣式到DataFrame
                        styled_trades = trades_display.style.applymap(
                            color_profit, 
                            subset=['收益', '收益率']
                        )
                        
                        st.dataframe(styled_trades, use_container_width=True)
                    else:
                        st.info("選擇「顯示所有交易」以查看詳細交易清單", icon="ℹ️")
                    
                    # 顯示技術指標圖表
                    try:
                        # 在這裡放置技術指標圖表相關的代碼
                        st.markdown("### 技術指標圖表")
                        
                        # 將時間範圍選擇器放入表單中
                        with st.form(key="indicator_date_range_form"):
                            # 添加時間範圍選擇器，方便用戶觀察不同時間段的技術指標
                            date_range_options = ["全部時間", "最近一個月", "最近三個月", "最近六個月"]
                            selected_date_range = st.radio("選擇時間範圍", date_range_options, horizontal=True)
                            
                            # 添加表單提交按鈕
                            filter_submitted = st.form_submit_button("應用過濾", use_container_width=True)
                        
                        # 根據選擇範圍過濾數據
                        # 獲取日期範圍
                        end_date = df_with_indicators.index[-1]
                        
                        if selected_date_range == "最近一個月":
                            start_date = end_date - pd.Timedelta(days=30)
                        elif selected_date_range == "最近三個月":
                            start_date = end_date - pd.Timedelta(days=90)
                        elif selected_date_range == "最近六個月":
                            start_date = end_date - pd.Timedelta(days=180)
                        else:  # 全部時間
                            filtered_df = df_with_indicators.copy()
                            log_message(f"使用全部數據, 數據點數量: {len(filtered_df)}")
                        
                        # 根據選擇的日期範圍過濾數據
                        if selected_date_range != "全部時間":
                            filtered_df = df_with_indicators[df_with_indicators.index >= start_date]
                            log_message(f"過濾{selected_date_range}數據: 從 {start_date} 到 {end_date}, 數據點數量: {len(filtered_df)}")
                        
                        # 如果過濾後的數據為空，使用原始數據
                        if filtered_df.empty:
                            filtered_df = df_with_indicators.copy()
                            st.warning(f"選擇的時間範圍內沒有數據，顯示全部時間範圍")
                            log_message("過濾結果為空，使用全部數據")
                        
                        # 優化數據以提高繪圖性能
                        if len(filtered_df) > 500:
                            original_len = len(filtered_df)
                            filtered_df = optimize_for_plotting(filtered_df)
                            log_message(f"數據點優化: 從 {original_len} 減少到 {len(filtered_df)} 以提高繪圖性能")
                    except Exception as e:
                        st.error(f"顯示技術指標圖表時發生錯誤: {e}")
                        st.exception(e)
                except Exception as e:
                    st.error(f"執行回測時發生錯誤: {e}")
                    st.exception(e)
    else:
        # 當用戶尚未點擊執行回測按鈕時顯示的內容
        st.info("請設置回測參數，然後點擊「執行回測」按鈕開始模擬交易策略的表現。")
        
        st.markdown("##### 策略說明")
        st.markdown("""
        本回測系統支持以下交易策略：
        
        1. **移動平均線交叉策略**：利用短期與長期移動平均線的交叉點作為買入與賣出訊號
        2. **RSI超買超賣策略**：根據相對強弱指標判斷股票超買或超賣狀態
        3. **MACD策略**：結合趨勢跟蹤與動量指標的綜合策略
        4. **布林通道突破策略**：利用價格突破上軌或下軌作為交易信號
        5. **外資買超策略**：追蹤外資的買賣動向，跟隨外資大戶的交易決策
        
        選擇適合的策略，設置相應參數，即可測試該策略在歷史市場中的表現。
        回測結果僅供參考，不構成投資建議。實際交易可能受到市場流動性、交易成本等因素影響。
        """)
        
        # 顯示策略概念圖
        strategy_concepts = {
            "移動平均線交叉": "https://i.imgur.com/JLtQOLd.png",
            "RSI超買超賣": "https://i.imgur.com/8NHSVeA.png",
            "MACD交叉": "https://i.imgur.com/oRxa15Z.png",
            "布林通道突破": "https://i.imgur.com/xF3NBJp.png",
            "外資買超策略": "https://i.imgur.com/dRJnAEE.png"
        }
        
        if strategy in strategy_concepts:
            st.image(strategy_concepts[strategy], caption=f"{strategy} 概念圖示")

def foreign_investors_trading():
    """獲取外資買賣超資料
    
    Returns:
        DataFrame: 外資買超前 50
        DataFrame: 外資賣超前 50
        str: 數據日期
    """
    _, df_buy_top50, df_sell_top50, data_date = for_buy_sell()
    
    # 格式化索引
    if not df_buy_top50.empty:
        df_buy_top50 = df_buy_top50.reset_index(drop=True)
        df_buy_top50.index = df_buy_top50.index + 1
        
    if not df_sell_top50.empty:
        df_sell_top50 = df_sell_top50.reset_index(drop=True)
        df_sell_top50.index = df_sell_top50.index + 1
    
    return df_buy_top50, df_sell_top50, data_date

def investment_trust_trading():
    """獲取投信買賣超資料
    
    Returns:
        DataFrame: 投信買超前 50
        DataFrame: 投信賣超前 50
        str: 數據日期
    """
    _, df_buy_top50, df_sell_top50, data_date = ib_buy_sell()
    
    # 格式化索引
    if not df_buy_top50.empty:
        df_buy_top50 = df_buy_top50.reset_index(drop=True)
        df_buy_top50.index = df_buy_top50.index + 1
        
    if not df_sell_top50.empty:
        df_sell_top50 = df_sell_top50.reset_index(drop=True)
        df_sell_top50.index = df_sell_top50.index + 1
    
    return df_buy_top50, df_sell_top50, data_date

# 添加緩存裝飾器到數據獲取函數
@st.cache_data(ttl=CACHE_TTL['high_freq'])
def cached_three_data():
    """緩存包裝的三大法人數據函數"""
    return three_data()

@st.cache_data(ttl=CACHE_TTL['high_freq'])
def cached_futures():
    """緩存包裝的期貨數據函數"""
    return futures()

@st.cache_data(ttl=CACHE_TTL['medium_freq'])
def cached_turnover():
    """緩存包裝的成交量數據函數"""
    return turnover()

@st.cache_data(ttl=CACHE_TTL['high_freq'])
def cached_for_ib_common():
    """緩存包裝的外資投信同買函數"""
    return for_ib_common()

@st.cache_data(ttl=CACHE_TTL['high_freq'])
def cached_foreign_investors_trading():
    """緩存包裝的外資買賣超函數"""
    return foreign_investors_trading()

@st.cache_data(ttl=CACHE_TTL['high_freq'])
def cached_investment_trust_trading():
    """緩存包裝的投信買賣超函數"""
    return investment_trust_trading()

@st.cache_data(ttl=CACHE_TTL['medium_freq'])
def cached_exchange_rate():
    """緩存包裝的匯率函數"""
    return exchange_rate()

@st.cache_data(ttl=CACHE_TTL['medium_freq'])
def cached_get_stock_history(stock_code, start_date, end_date):
    """緩存包裝的股票歷史數據函數"""
    return get_stock_history(stock_code, start_date, end_date)

@st.cache_data(ttl=CACHE_TTL['medium_freq'])
def cached_calculate_technical_indicators(df_stock):
    """緩存包裝的技術指標計算函數"""
    return calculate_technical_indicators(df_stock)

# 添加通用API調用安全包裝函數
def safe_api_call(func, *args, fallback_value=None, display_error=True, **kwargs):
    """安全調用API函數，統一處理異常
    
    Args:
        func: 要調用的函數
        *args: 傳遞給函數的位置參數
        fallback_value: 失敗時返回的值
        display_error: 是否在界面顯示錯誤
        **kwargs: 傳遞給函數的關鍵字參數
        
    Returns:
        函數調用結果或失敗時的 fallback_value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_msg = f"API調用錯誤: {func.__name__}, {str(e)}"
        log_message(error_msg, level="error")
        if display_error:
            show_error(error_msg)
        return fallback_value

# 添加 Streamlit 版本檢測函數
def detect_streamlit_version():
    """檢測 Streamlit 版本並決定使用哪個 API"""
    import streamlit as st
    version = st.__version__
    
    try:
        major, minor, patch = map(int, version.split('.'))
        
        # 假設 1.10.0 版本後支持 query_params
        if (major > 1) or (major == 1 and minor >= 10):
            return "new_api"
        else:
            return "old_api"
    except:
        # 如果無法正確解析版本，預設使用舊 API
        return "old_api"

# 查詢參數設置函數
def set_query_params(params):
    """設置查詢參數，兼容不同版本的 Streamlit"""
    try:
        if detect_streamlit_version() == "new_api":
            for key, value in params.items():
                st.query_params[key] = value
        else:
            st.experimental_set_query_params(**params)
    except Exception as e:
        log_message(f"設置查詢參數時出錯: {e}", level="error")

def downsample_dataframe(df, max_points=500):
    """降低大數據集的採樣率以提高繪圖性能
    
    Args:
        df: 要降採樣的DataFrame
        max_points: 最大點數
        
    Returns:
        降採樣後的DataFrame
    """
    if len(df) <= max_points:
        return df
    
    # 計算採樣間隔
    sample_rate = max(len(df) // max_points, 1)
    return df.iloc[::sample_rate].copy()

def optimize_for_plotting(df, target_columns=None, max_points=500):
    """優化DataFrame以提高繪圖性能
    
    Args:
        df: 輸入的DataFrame
        target_columns: 需要保留的列，如果為None則保留所有列
        max_points: 最大數據點數
        
    Returns:
        優化後的DataFrame
    """
    # 創建一個副本避免修改原始數據
    result_df = df.copy()
    
    # 如果指定了列，只保留這些列
    if target_columns:
        keep_cols = [col for col in target_columns if col in result_df.columns]
        result_df = result_df[keep_cols]
    
    # 降採樣
    result_df = downsample_dataframe(result_df, max_points)
    
    return result_df

if __name__ == "__main__":
    main()
