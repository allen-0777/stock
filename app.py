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
            df_three, data_date = three_data()
        
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
            df_futures = futures()
        
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
            df_turnover = turnover()
        
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
            df_com_buy, data_date = for_ib_common()
        
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
            df_buy_top50, df_sell_top50, data_date = foreign_investors_trading()
        
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
            df_buy_top50, df_sell_top50, data_date = investment_trust_trading()
        
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
            History_ExchangeRate = exchange_rate()
        
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
                    options=list(stock_options.keys()),
                    format_func=lambda x: f"{x} - {stock_options[x]}"
                )
                
                # 初始資金
                initial_capital = st.number_input("初始資金 (新台幣)", min_value=10000, max_value=10000000, value=100000, step=10000)
                
                # 交易手續費
                fee_rate = st.slider("交易手續費率 (%)", min_value=0.0, max_value=0.5, value=0.1425, step=0.01, format="%.4f")
                
                # 股價變動停損/停利
                stop_loss = st.slider("停損比例 (%)", min_value=0, max_value=20, value=5, step=1)
                take_profit = st.slider("停利比例 (%)", min_value=0, max_value=50, value=20, step=1)
            
            with col2:
                # 回測時間範圍
                backtest_start_date = st.date_input("回測開始日期", value=date.today() - timedelta(days=365))
                backtest_end_date = st.date_input("回測結束日期", value=date.today())
                
                # 交易策略選擇
                strategy_options = {
                    "ma_cross": "均線交叉策略",
                    "rsi": "RSI指標策略",
                    "macd": "MACD策略",
                    "bollinger": "布林通道策略",
                    "foreign_buy": "外資買超策略"
                }
                selected_strategy = st.selectbox(
                    "選擇交易策略",
                    options=list(strategy_options.keys()),
                    format_func=lambda x: strategy_options[x]
                )
                
                # 策略參數容器
                strategy_params_container = st.container()
                
                # 根據所選策略顯示相應參數
                with strategy_params_container:
                    st.markdown("##### 策略參數")
                    
                    if selected_strategy == "ma_cross":
                        short_ma = st.slider("短期均線 (天數)", min_value=5, max_value=30, value=5, step=1, key="short_ma")
                        long_ma = st.slider("長期均線 (天數)", min_value=10, max_value=120, value=20, step=5, key="long_ma")
                    
                    elif selected_strategy == "rsi":
                        rsi_period = st.slider("RSI 周期", min_value=5, max_value=30, value=14, step=1, key="rsi_period")
                        rsi_overbought = st.slider("超買閾值", min_value=60, max_value=90, value=70, step=1, key="rsi_overbought")
                        rsi_oversold = st.slider("超賣閾值", min_value=10, max_value=40, value=30, step=1, key="rsi_oversold")
                    
                    elif selected_strategy == "macd":
                        macd_fast = st.slider("快線周期", min_value=5, max_value=20, value=12, step=1, key="macd_fast")
                        macd_slow = st.slider("慢線周期", min_value=20, max_value=50, value=26, step=1, key="macd_slow")
                        macd_signal = st.slider("信號線周期", min_value=5, max_value=15, value=9, step=1, key="macd_signal")
                    
                    elif selected_strategy == "bollinger":
                        bollinger_period = st.slider("布林通道周期", min_value=10, max_value=30, value=20, step=1, key="bollinger_period")
                        bollinger_std = st.slider("標準差倍數", min_value=1.0, max_value=3.0, value=2.0, step=0.1, key="bollinger_std")
                    
                    elif selected_strategy == "foreign_buy":
                        foreign_buy_threshold = st.slider("外資買超閾值 (張)", min_value=100, max_value=5000, value=1000, step=100, key="foreign_buy_threshold")
            
            # 提交按鈕 - 確保點擊後保持在交易回測頁面
            submit_button = st.form_submit_button(label="執行回測", use_container_width=True)
            
            # 確保表單提交後保持在交易回測頁面
            if submit_button:
                st.session_state.active_tab = "交易回測"
                # 設置查詢參數以在重新加載頁面後維持在交易回測頁面
                st.query_params["tab"] = "交易回測"
        
        # 如果表單被提交
        if submit_button:
            with st.spinner("正在執行回測計算..."):
                # 獲取真實歷史數據
                try:
                    # 獲取策略參數，根據所選策略建立相應的參數字典
                    if selected_strategy == "ma_cross":
                        strategy_params = {
                            'short_ma': short_ma,
                            'long_ma': long_ma
                        }
                        log_message(f"執行均線交叉策略，參數：短期均線={short_ma}天，長期均線={long_ma}天")
                    
                    elif selected_strategy == "rsi":
                        strategy_params = {
                            'rsi_period': rsi_period,
                            'rsi_overbought': rsi_overbought,
                            'rsi_oversold': rsi_oversold
                        }
                        log_message(f"執行RSI策略，參數：周期={rsi_period}，超買閾值={rsi_overbought}，超賣閾值={rsi_oversold}")
                    
                    elif selected_strategy == "macd":
                        strategy_params = {
                            'macd_fast': macd_fast,
                            'macd_slow': macd_slow,
                            'macd_signal': macd_signal
                        }
                        log_message(f"執行MACD策略，參數：快線={macd_fast}，慢線={macd_slow}，信號線={macd_signal}")
                    
                    elif selected_strategy == "bollinger":
                        strategy_params = {
                            'bollinger_period': bollinger_period,
                            'bollinger_std': bollinger_std
                        }
                        log_message(f"執行布林通道策略，參數：周期={bollinger_period}，標準差={bollinger_std}")
                    
                    elif selected_strategy == "foreign_buy":
                        strategy_params = {
                            'foreign_buy_threshold': foreign_buy_threshold
                        }
                        log_message(f"執行外資買超策略，參數：閾值={foreign_buy_threshold}張")
                    
                    # 記錄回測參數信息
                    log_message(f"開始回測 {selected_stock}，初始資金：{initial_capital}，停損比例：{stop_loss}%，停利比例：{take_profit}%")
                    log_message(f"回測時間範圍：{backtest_start_date} 至 {backtest_end_date}")
                    
                    # 設定回測時間範圍
                    start_date_str = backtest_start_date.strftime("%Y-%m-%d")
                    end_date_str = backtest_end_date.strftime("%Y-%m-%d")
                    
                    # 顯示進度條
                    progress_bar = st.progress(0)
                    
                    # 第一步：獲取股票歷史數據
                    progress_bar.progress(10, text="正在獲取歷史數據...")
                    df_stock = get_stock_history(selected_stock, start_date_str, end_date_str)
                    
                    if df_stock.empty:
                        st.error(f"無法獲取 {selected_stock} 的歷史數據，請檢查股票代碼或選擇其他日期範圍")
                        return
                    
                    # 第二步：計算技術指標
                    progress_bar.progress(30, text="正在計算技術指標...")
                    df_with_indicators = calculate_technical_indicators(df_stock)
                    
                    # 第三步：執行回測
                    progress_bar.progress(50, text="正在執行策略回測...")
                    trades_df, backtest_results, portfolio_df = backtest_strategy(
                        df_with_indicators, 
                        selected_strategy, 
                        strategy_params,
                        initial_capital=initial_capital,
                        fee_rate=fee_rate/100,  # 轉換百分比為小數
                        tax_rate=0.003,  # 台灣股票交易稅率
                        stop_loss=stop_loss/100,  # 轉換百分比為小數
                        take_profit=take_profit/100  # 轉換百分比為小數
                    )
                    
                    # 第四步：生成報告
                    progress_bar.progress(80, text="正在生成回測報告...")
                    
                    # 回測結果
                    st.markdown("<div class='sub-header'>回測結果</div>", unsafe_allow_html=True)
                    
                    # 回測基本信息
                    st.markdown(f"""
                    **回測信息:**
                    - 股票: {selected_stock} ({stock_options.get(selected_stock, '')})
                    - 策略: {strategy_options.get(selected_strategy, selected_strategy)}
                    - 回測時間: {start_date_str} 至 {end_date_str}
                    - 初始資金: {initial_capital:,} 元
                    """)
                    
                    # 回測績效指標
                    metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
                    
                    with metrics_col1:
                        st.metric(label="總報酬率", value=backtest_results["總報酬率"])
                    
                    with metrics_col2:
                        st.metric(label="年化報酬率", value=backtest_results["年化報酬率"])
                    
                    with metrics_col3:
                        st.metric(label="勝率", value=backtest_results["勝率"])
                    
                    with metrics_col4:
                        st.metric(label="最大回撤", value=backtest_results["最大回撤"])
                    
                    # 完成進度條
                    progress_bar.progress(100, text="回測完成！")
                    
                    # 回測結果可視化
                    tab_results, tab_trades, tab_metrics = st.tabs(["績效曲線", "交易記錄", "詳細指標"])
                    
                    with tab_results:
                        # 檢查是否有回測資產淨值數據
                        if not portfolio_df.empty:
                            # 繪製策略淨值曲線
                            fig = go.Figure()
                            
                            fig.add_trace(go.Scatter(
                                x=portfolio_df.index, 
                                y=portfolio_df['淨值'], 
                                mode='lines',
                                name=f'策略淨值 ({strategy_options[selected_strategy]})',
                                line=dict(color='#1E88E5', width=2)
                            ))
                            
                            # 使用股票收盤價模擬大盤基準
                            initial_stock_price = df_stock['收盤價'].iloc[0]
                            benchmark_value = (df_stock['收盤價'] / initial_stock_price) * initial_capital
                            
                            fig.add_trace(go.Scatter(
                                x=df_stock.index, 
                                y=benchmark_value, 
                                mode='lines',
                                name='買入並持有策略',
                                line=dict(color='#FF9800', width=2, dash='dash')
                            ))
                            
                            fig.update_layout(
                                title=f'{stock_options.get(selected_stock, selected_stock)} 回測績效對比',
                                xaxis_title='日期',
                                yaxis_title='淨值 (元)',
                                height=500,
                                hovermode='x unified'
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("無法生成策略淨值曲線，可能是因為交易次數不足或數據問題")
                            
                            # 顯示原始股價走勢
                            fig = go.Figure()
                            fig.add_trace(go.Candlestick(
                                x=df_stock.index,
                                open=df_stock['開盤價'],
                                high=df_stock['最高價'],
                                low=df_stock['最低價'],
                                close=df_stock['收盤價'],
                                name='股價走勢'
                            ))
                            
                            fig.update_layout(
                                title=f'{stock_options.get(selected_stock, selected_stock)} 股價走勢',
                                xaxis_title='日期',
                                yaxis_title='價格 (元)',
                                height=500
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                    
                    with tab_trades:
                        # 顯示交易記錄
                        if not trades_df.empty:
                            st.dataframe(trades_df, use_container_width=True)
                            
                            # 交易記錄統計
                            profit_trades = trades_df[trades_df['淨利'] > 0]
                            loss_trades = trades_df[trades_df['淨利'] < 0]
                            
                            st.markdown(f"""
                            ##### 交易統計:
                            - 總交易次數: {len(trades_df[trades_df['類型'].isin(['買入', '賣出', '停損賣出', '停利賣出', '平倉賣出'])])}
                            - 盈利交易: {len(profit_trades)} 次
                            - 虧損交易: {len(loss_trades)} 次
                            - 平均獲利: {profit_trades['淨利'].mean() if len(profit_trades) > 0 else 0:.2f}
                            - 平均虧損: {loss_trades['淨利'].mean() if len(loss_trades) > 0 else 0:.2f}
                            """)
                        else:
                            st.warning("在回測期間內沒有產生任何交易記錄")
                    
                    with tab_metrics:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("##### 回測結果指標")
                            result_df = pd.DataFrame(list(backtest_results.items()), columns=['指標', '數值'])
                            st.dataframe(result_df, use_container_width=True, hide_index=True)
                        
                        with col2:
                            st.markdown("##### 股票基本資訊")
                            stock_info = get_stock_info(selected_stock)
                            info_df = pd.DataFrame(list(stock_info.items()), columns=['項目', '資訊'])
                            st.dataframe(info_df, use_container_width=True, hide_index=True)
                        
                        # 顯示技術指標
                        st.markdown("##### 技術指標圖表")
                        
                        # 添加時間範圍選擇器，方便用戶觀察不同時間段的技術指標
                        date_range_options = ["全部時間", "最近一個月", "最近三個月", "最近六個月"]
                        selected_date_range = st.radio("選擇時間範圍", date_range_options, horizontal=True)
                        
                        # 根據選擇範圍過濾數據
                        try:
                            if selected_date_range == "最近一個月":
                                end_date = df_with_indicators.index[-1]
                                start_date = end_date - pd.Timedelta(days=30)
                                filtered_df = df_with_indicators[df_with_indicators.index >= start_date]
                                log_message(f"過濾最近一個月數據: 從 {start_date} 到 {end_date}, 數據點數量: {len(filtered_df)}")
                            elif selected_date_range == "最近三個月":
                                end_date = df_with_indicators.index[-1]
                                start_date = end_date - pd.Timedelta(days=90)
                                filtered_df = df_with_indicators[df_with_indicators.index >= start_date]
                                log_message(f"過濾最近三個月數據: 從 {start_date} 到 {end_date}, 數據點數量: {len(filtered_df)}")
                            elif selected_date_range == "最近六個月":
                                end_date = df_with_indicators.index[-1]
                                start_date = end_date - pd.Timedelta(days=180)
                                filtered_df = df_with_indicators[df_with_indicators.index >= start_date]
                                log_message(f"過濾最近六個月數據: 從 {start_date} 到 {end_date}, 數據點數量: {len(filtered_df)}")
                            else:
                                filtered_df = df_with_indicators.copy()
                                log_message(f"使用全部數據, 數據點數量: {len(filtered_df)}")
                            
                            # 打印數據框的日期範圍和索引類型
                            log_message(f"過濾後數據的索引類型: {type(filtered_df.index)}")
                            log_message(f"過濾後數據的列: {filtered_df.columns.tolist()}")
                            
                            # 如果過濾後的數據為空，使用原始數據
                            if filtered_df.empty:
                                filtered_df = df_with_indicators.copy()
                                st.warning(f"選擇的時間範圍內沒有數據，顯示全部時間範圍")
                                log_message("過濾結果為空，使用全部數據")
                        except Exception as e:
                            filtered_df = df_with_indicators.copy()
                            st.warning(f"過濾數據時發生錯誤：{e}，顯示全部時間範圍")
                            log_message(f"過濾數據時發生錯誤: {e}", level="error")
                        
                        # 選擇要顯示的指標
                        indicator_options = ["移動平均線", "RSI指標", "MACD指標", "布林通道", "KD指標"]
                        selected_indicator = st.selectbox("選擇技術指標", indicator_options)
                        
                        # 添加顯示買賣訊號選項
                        show_signals = st.checkbox("顯示買賣訊號", value=True)
                        
                        # 繪製所選指標
                        try:
                            # 確保過濾後的數據框非空且包含必要的列
                            if filtered_df.empty:
                                st.warning("無法繪製圖表：沒有可用的數據")
                                log_message("繪製圖表時發現數據為空", level="warning")
                            # 檢查數據中是否包含必要的列
                            elif not filtered_df.empty:
                                required_columns = ['開盤價', '最高價', '最低價', '收盤價']
                                missing_columns = [col for col in required_columns if col not in filtered_df.columns]
                                if missing_columns:
                                    st.warning(f"無法繪製圖表：缺少必要的列 {missing_columns}")
                                    log_message(f"繪製圖表時缺少必要的列: {missing_columns}", level="warning")
                                else:
                                    if selected_indicator == "移動平均線":
                                        log_message(f"繪製移動平均線圖表，數據點數量: {len(filtered_df)}")
                                        fig = go.Figure()
                                        
                                        # 添加K線圖
                                        fig.add_trace(go.Candlestick(
                                            x=filtered_df.index,
                                            open=filtered_df['開盤價'],
                                            high=filtered_df['最高價'],
                                            low=filtered_df['最低價'],
                                            close=filtered_df['收盤價'],
                                            name='股價',
                                            increasing_line_color='red',  # 漲為紅色（符合台灣市場）
                                            decreasing_line_color='green'  # 跌為綠色
                                        ))
                                        
                                        # 添加移動平均線
                                        ma_columns = [col for col in filtered_df.columns if isinstance(col, str) and col.startswith('MA')]
                                        ma_colors = ['#1E88E5', '#FFC107', '#FF5722', '#9C27B0', '#4CAF50']
                                        
                                        for i, col in enumerate(ma_columns):
                                            color_idx = i % len(ma_colors)
                                            fig.add_trace(go.Scatter(
                                                x=filtered_df.index,
                                                y=filtered_df[col],
                                                name=col,
                                                line=dict(color=ma_colors[color_idx], width=1.5)
                                            ))
                                        
                                        # 如果選擇顯示買賣訊號且策略為均線交叉
                                        if show_signals and selected_strategy == "ma_cross":
                                            # 獲取買入信號
                                            buy_signals = filtered_df[filtered_df['signal'] == 1]
                                            # 獲取賣出信號
                                            sell_signals = filtered_df[filtered_df['signal'] == -1]
                                            
                                            # 添加買入標記
                                            fig.add_trace(go.Scatter(
                                                x=buy_signals.index,
                                                y=buy_signals['收盤價'],
                                                mode='markers',
                                                name='買入信號',
                                                marker=dict(symbol='triangle-up', size=10, color='red')
                                            ))
                                            
                                            # 添加賣出標記
                                            fig.add_trace(go.Scatter(
                                                x=sell_signals.index,
                                                y=sell_signals['收盤價'],
                                                mode='markers',
                                                name='賣出信號',
                                                marker=dict(symbol='triangle-down', size=10, color='green')
                                            ))
                                        
                                        fig.update_layout(
                                            title=f'{stock_options.get(selected_stock, selected_stock)} 移動平均線',
                                            xaxis_title='日期',
                                            yaxis_title='價格',
                                            legend_title_text='指標',
                                            height=600,
                                            template='plotly_white',
                                            hovermode='x unified'
                                        )
                                        
                                        st.plotly_chart(fig, use_container_width=True)
                                        
                                        # 添加均線交叉策略說明
                                        if selected_strategy == "ma_cross":
                                            st.info(f"""
                                            **均線交叉策略說明**：
                                            - 當短期均線(MA{short_ma})上穿長期均線(MA{long_ma})時產生買入訊號
                                            - 當短期均線(MA{short_ma})下穿長期均線(MA{long_ma})時產生賣出訊號
                                            - 這是一個趨勢跟踪策略，適合在明確趨勢的市場中使用
                                            """)
                                        
                                    elif selected_indicator == "RSI指標":
                                        # 創建兩個子圖
                                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                                   vertical_spacing=0.1, 
                                                   row_heights=[0.7, 0.3])
                                        
                                        # 添加K線圖
                                        fig.add_trace(go.Candlestick(
                                            x=filtered_df.index,
                                            open=filtered_df['開盤價'],
                                            high=filtered_df['最高價'],
                                            low=filtered_df['最低價'],
                                            close=filtered_df['收盤價'],
                                            name='股價',
                                            increasing_line_color='red',  # 漲為紅色
                                            decreasing_line_color='green'  # 跌為綠色
                                        ), row=1, col=1)
                                        
                                        # 添加RSI指標
                                        fig.add_trace(go.Scatter(
                                            x=filtered_df.index,
                                            y=filtered_df['RSI14'],
                                            name='RSI(14)',
                                            line=dict(color='purple', width=1.5)
                                        ), row=2, col=1)
                                        
                                        # 添加超買超賣線
                                        # 超買線（70）
                                        fig.add_shape(
                                            type="line",
                                            x0=filtered_df.index[0],
                                            y0=70,
                                            x1=filtered_df.index[-1],
                                            y1=70,
                                            line=dict(color="red", width=1, dash="dash"),
                                            row=2, col=1
                                        )
                                        
                                        # 超賣線（30）
                                        fig.add_shape(
                                            type="line",
                                            x0=filtered_df.index[0],
                                            y0=30,
                                            x1=filtered_df.index[-1],
                                            y1=30,
                                            line=dict(color="green", width=1, dash="dash"),
                                            row=2, col=1
                                        )
                                        
                                        # 中間線（50）
                                        fig.add_shape(
                                            type="line",
                                            x0=filtered_df.index[0],
                                            y0=50,
                                            x1=filtered_df.index[-1],
                                            y1=50,
                                            line=dict(color="gray", width=1, dash="dot"),
                                            row=2, col=1
                                        )
                                        
                                        # 如果選擇顯示買賣訊號且策略為RSI
                                        if show_signals and selected_strategy == "rsi":
                                            # 獲取買入信號
                                            buy_signals = filtered_df[filtered_df['signal'] == 1]
                                            # 獲取賣出信號
                                            sell_signals = filtered_df[filtered_df['signal'] == -1]
                                            
                                            # 添加買入標記
                                            fig.add_trace(go.Scatter(
                                                x=buy_signals.index,
                                                y=buy_signals['收盤價'],
                                                mode='markers',
                                                name='買入信號',
                                                marker=dict(symbol='triangle-up', size=10, color='red')
                                            ), row=1, col=1)
                                            
                                            # 添加賣出標記
                                            fig.add_trace(go.Scatter(
                                                x=sell_signals.index,
                                                y=sell_signals['收盤價'],
                                                mode='markers',
                                                name='賣出信號',
                                                marker=dict(symbol='triangle-down', size=10, color='green')
                                            ), row=1, col=1)
                                        
                                        fig.update_layout(
                                            title=f'{stock_options.get(selected_stock, selected_stock)} RSI指標',
                                            xaxis_title='日期',
                                            yaxis_title='價格',
                                            height=600,
                                            template='plotly_white',
                                            hovermode='x unified'
                                        )
                                        
                                        # 更新RSI圖表的Y軸範圍，確保顯示0-100
                                        fig.update_yaxes(range=[0, 100], row=2, col=1)
                                        
                                        st.plotly_chart(fig, use_container_width=True)
                                        
                                        # 添加RSI策略說明
                                        if selected_strategy == "rsi":
                                            st.info(f"""
                                            **RSI策略說明**：
                                            - 當RSI從超賣區域（{rsi_oversold}以下）上穿超賣閾值時產生買入訊號
                                            - 當RSI從超買區域（{rsi_overbought}以上）下穿超買閾值時產生賣出訊號
                                            - RSI指標適合用於判斷市場的超買超賣狀態，特別適合震盪市場
                                            """)
                                        
                                    elif selected_indicator == "MACD指標":
                                        # 創建兩個子圖
                                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                                   vertical_spacing=0.1, 
                                                   row_heights=[0.7, 0.3])
                                        
                                        # 添加K線圖
                                        fig.add_trace(go.Candlestick(
                                            x=filtered_df.index,
                                            open=filtered_df['開盤價'],
                                            high=filtered_df['最高價'],
                                            low=filtered_df['最低價'],
                                            close=filtered_df['收盤價'],
                                            name='股價',
                                            increasing_line_color='red',  # 漲為紅色
                                            decreasing_line_color='green'  # 跌為綠色
                                        ), row=1, col=1)
                                        
                                        # 添加MACD和信號線
                                        fig.add_trace(go.Scatter(
                                            x=filtered_df.index,
                                            y=filtered_df['MACD'],
                                            name='MACD線',
                                            line=dict(color='blue', width=1.5)
                                        ), row=2, col=1)
                                        
                                        fig.add_trace(go.Scatter(
                                            x=filtered_df.index,
                                            y=filtered_df['MACD_Signal'],
                                            name='信號線',
                                            line=dict(color='red', width=1.5)
                                        ), row=2, col=1)
                                        
                                        # 添加MACD柱狀圖，正值為紅色，負值為綠色（符合台灣市場風格）
                                        colors = ['red' if val >= 0 else 'green' for val in filtered_df['MACD_Hist']]
                                        fig.add_trace(go.Bar(
                                            x=filtered_df.index,
                                            y=filtered_df['MACD_Hist'],
                                            name='柱狀圖',
                                            marker_color=colors
                                        ), row=2, col=1)
                                        
                                        # 如果選擇顯示買賣訊號且策略為MACD
                                        if show_signals and selected_strategy == "macd":
                                            # 獲取買入信號
                                            buy_signals = filtered_df[filtered_df['signal'] == 1]
                                            # 獲取賣出信號
                                            sell_signals = filtered_df[filtered_df['signal'] == -1]
                                            
                                            # 添加買入標記
                                            fig.add_trace(go.Scatter(
                                                x=buy_signals.index,
                                                y=buy_signals['收盤價'],
                                                mode='markers',
                                                name='買入信號',
                                                marker=dict(symbol='triangle-up', size=10, color='red')
                                            ), row=1, col=1)
                                            
                                            # 添加賣出標記
                                            fig.add_trace(go.Scatter(
                                                x=sell_signals.index,
                                                y=sell_signals['收盤價'],
                                                mode='markers',
                                                name='賣出信號',
                                                marker=dict(symbol='triangle-down', size=10, color='green')
                                            ), row=1, col=1)
                                        
                                        fig.update_layout(
                                            title=f'{stock_options.get(selected_stock, selected_stock)} MACD指標',
                                            xaxis_title='日期',
                                            yaxis_title='價格',
                                            height=600,
                                            template='plotly_white',
                                            hovermode='x unified'
                                        )
                                        
                                        # 確保MACD視圖的零線可見
                                        fig.add_shape(
                                            type='line',
                                            x0=filtered_df.index[0],
                                            y0=0,
                                            x1=filtered_df.index[-1],
                                            y1=0,
                                            line=dict(color='gray', width=1, dash='dot'),
                                            row=2, col=1
                                        )
                                        
                                        st.plotly_chart(fig, use_container_width=True)
                                        
                                        # 添加MACD策略說明
                                        if selected_strategy == "macd":
                                            st.info(f"""
                                            **MACD策略說明**：
                                            - 當MACD線（藍線）從下方穿過信號線（紅線）時產生買入訊號
                                            - 當MACD線從上方穿過信號線時產生賣出訊號
                                            - MACD參數設置：快線周期={macd_fast}，慢線周期={macd_slow}，信號線周期={macd_signal}
                                            - MACD是一個綜合趨勢和動量的指標，適合識別中長期趨勢
                                            """)
                                        
                                    elif selected_indicator == "布林通道":
                                        fig = go.Figure()
                                        
                                        # 添加K線圖
                                        fig.add_trace(go.Candlestick(
                                            x=filtered_df.index,
                                            open=filtered_df['開盤價'],
                                            high=filtered_df['最高價'],
                                            low=filtered_df['最低價'],
                                            close=filtered_df['收盤價'],
                                            name='股價',
                                            increasing_line_color='red',  # 漲為紅色
                                            decreasing_line_color='green'  # 跌為綠色
                                        ))
                                        
                                        # 添加布林帶
                                        fig.add_trace(go.Scatter(
                                            x=filtered_df.index,
                                            y=filtered_df['BB_Upper'],
                                            name='上軌',
                                            line=dict(color='rgba(255, 99, 71, 0.7)', width=1)  # 紅色調
                                        ))
                                        
                                        fig.add_trace(go.Scatter(
                                            x=filtered_df.index,
                                            y=filtered_df['BB_Middle'],
                                            name='中軌',
                                            line=dict(color='rgba(30, 136, 229, 0.9)', width=1.5)  # 藍色
                                        ))
                                        
                                        fig.add_trace(go.Scatter(
                                            x=filtered_df.index,
                                            y=filtered_df['BB_Lower'],
                                            name='下軌',
                                            line=dict(color='rgba(46, 125, 50, 0.7)', width=1),  # 綠色調
                                            fill='tonexty',
                                            fillcolor='rgba(173, 216, 230, 0.2)'
                                        ))
                                        
                                        # 如果選擇顯示買賣訊號且策略為布林通道
                                        if show_signals and selected_strategy == "bollinger":
                                            # 獲取買入信號
                                            buy_signals = filtered_df[filtered_df['signal'] == 1]
                                            # 獲取賣出信號
                                            sell_signals = filtered_df[filtered_df['signal'] == -1]
                                            
                                            # 添加買入標記
                                            fig.add_trace(go.Scatter(
                                                x=buy_signals.index,
                                                y=buy_signals['收盤價'],
                                                mode='markers',
                                                name='買入信號',
                                                marker=dict(symbol='triangle-up', size=10, color='red')
                                            ))
                                            
                                            # 添加賣出標記
                                            fig.add_trace(go.Scatter(
                                                x=sell_signals.index,
                                                y=sell_signals['收盤價'],
                                                mode='markers',
                                                name='賣出信號',
                                                marker=dict(symbol='triangle-down', size=10, color='green')
                                            ))
                                        
                                        fig.update_layout(
                                            title=f'{stock_options.get(selected_stock, selected_stock)} 布林通道',
                                            xaxis_title='日期',
                                            yaxis_title='價格',
                                            height=600,
                                            template='plotly_white',
                                            hovermode='x unified'
                                        )
                                        
                                        st.plotly_chart(fig, use_container_width=True)
                                        
                                        # 添加布林通道策略說明
                                        if selected_strategy == "bollinger":
                                            st.info(f"""
                                            **布林通道策略說明**：
                                            - 當價格觸及或接近下軌時產生買入訊號
                                            - 當價格觸及或接近上軌時產生賣出訊號
                                            - 布林通道參數：周期={bollinger_period}，標準差={bollinger_std}
                                            - 布林通道特別適合震盪行情的市場，在趨勢明顯時可能出現假信號
                                            """)
                                        
                                    elif selected_indicator == "KD指標":
                                        # 創建兩個子圖
                                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                                   vertical_spacing=0.1, 
                                                   row_heights=[0.7, 0.3])
                                        
                                        # 添加K線圖
                                        fig.add_trace(go.Candlestick(
                                            x=filtered_df.index,
                                            open=filtered_df['開盤價'],
                                            high=filtered_df['最高價'],
                                            low=filtered_df['最低價'],
                                            close=filtered_df['收盤價'],
                                            name='股價',
                                            increasing_line_color='red',  # 漲為紅色
                                            decreasing_line_color='green'  # 跌為綠色
                                        ), row=1, col=1)
                                        
                                        # 添加KD指標
                                        fig.add_trace(go.Scatter(
                                            x=filtered_df.index,
                                            y=filtered_df['K'],
                                            name='K值',
                                            line=dict(color='blue', width=1.5)
                                        ), row=2, col=1)
                                        
                                        fig.add_trace(go.Scatter(
                                            x=filtered_df.index,
                                            y=filtered_df['D'],
                                            name='D值',
                                            line=dict(color='red', width=1.5)
                                        ), row=2, col=1)
                                        
                                        # 添加超買超賣線
                                        # 超買線（80）
                                        fig.add_shape(
                                            type="line",
                                            x0=filtered_df.index[0],
                                            y0=80,
                                            x1=filtered_df.index[-1],
                                            y1=80,
                                            line=dict(color="red", width=1, dash="dash"),
                                            row=2, col=1
                                        )
                                        
                                        # 超賣線（20）
                                        fig.add_shape(
                                            type="line",
                                            x0=filtered_df.index[0],
                                            y0=20,
                                            x1=filtered_df.index[-1],
                                            y1=20,
                                            line=dict(color="green", width=1, dash="dash"),
                                            row=2, col=1
                                        )
                                        
                                        # 中間線（50）
                                        fig.add_shape(
                                            type="line",
                                            x0=filtered_df.index[0],
                                            y0=50,
                                            x1=filtered_df.index[-1],
                                            y1=50,
                                            line=dict(color="gray", width=1, dash="dot"),
                                            row=2, col=1
                                        )
                                        
                                        # KD黃金交叉/死亡交叉信號 - 可視化交叉點
                                        if show_signals:
                                            # 建立個簡單的KD交叉指標
                                            for i in range(1, len(filtered_df)):
                                                # 檢查黃金交叉 - K線從下方穿過D線
                                                if filtered_df['K'].iloc[i-1] < filtered_df['D'].iloc[i-1] and filtered_df['K'].iloc[i] > filtered_df['D'].iloc[i]:
                                                    fig.add_trace(go.Scatter(
                                                        x=[filtered_df.index[i]],
                                                        y=[filtered_df['收盤價'].iloc[i]],
                                                        mode='markers',
                                                        name='KD黃金交叉',
                                                        marker=dict(symbol='star', size=12, color='red'),
                                                        showlegend=(i==1)  # 只在圖例中顯示一次
                                                    ), row=1, col=1)
                                                # 檢查死亡交叉 - K線從上方穿過D線
                                                elif filtered_df['K'].iloc[i-1] > filtered_df['D'].iloc[i-1] and filtered_df['K'].iloc[i] < filtered_df['D'].iloc[i]:
                                                    fig.add_trace(go.Scatter(
                                                        x=[filtered_df.index[i]],
                                                        y=[filtered_df['收盤價'].iloc[i]],
                                                        mode='markers',
                                                        name='KD死亡交叉',
                                                        marker=dict(symbol='x', size=12, color='green'),
                                                        showlegend=(i==1)  # 只在圖例中顯示一次
                                                    ), row=1, col=1)
                                        
                                        fig.update_layout(
                                            title=f'{stock_options.get(selected_stock, selected_stock)} KD指標',
                                            xaxis_title='日期',
                                            yaxis_title='價格',
                                            height=600,
                                            template='plotly_white',
                                            hovermode='x unified'
                                        )
                                        
                                        # 更新KD圖表的Y軸範圍，確保顯示0-100
                                        fig.update_yaxes(range=[0, 100], row=2, col=1)
                                        
                                        st.plotly_chart(fig, use_container_width=True)
                                        
                                        # 添加KD策略說明
                                        st.info("""
                                        **KD指標策略說明**：
                                        - KD指標是一種衡量超買超賣的動量指標
                                        - 常見交易訊號：
                                          - 黃金交叉：K線從下方穿過D線，買入訊號
                                          - 死亡交叉：K線從上方穿過D線，賣出訊號
                                        - 當K值和D值同時低於20時為超賣區域，當兩者同時高於80時為超買區域
                                        - KD指標適合震盪行情，在強勢趨勢市場中可能產生較多假信號
                                        """)
                                        
                        except Exception as e:
                            st.error(f"繪製技術指標圖表時發生錯誤: {e}")
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
        
        1. **均線交叉策略**：利用短期與長期移動平均線的交叉點作為買入與賣出訊號
        2. **RSI指標策略**：根據相對強弱指標判斷股票超買或超賣狀態
        3. **MACD策略**：結合趨勢跟蹤與動量指標的綜合策略
        4. **布林通道策略**：利用價格波動的標準差建立價格通道，判斷買賣時機
        5. **外資買超策略**：追蹤外資的買賣動向，跟隨外資大戶的交易決策
        
        選擇適合的策略，設置相應參數，即可測試該策略在歷史市場中的表現。
        回測結果僅供參考，不構成投資建議。實際交易可能受到市場流動性、交易成本等因素影響。
        """)
        
        # 顯示策略概念圖
        strategy_concepts = {
            "ma_cross": "https://i.imgur.com/JLtQOLd.png",
            "rsi": "https://i.imgur.com/8NHSVeA.png",
            "macd": "https://i.imgur.com/oRxa15Z.png",
            "bollinger": "https://i.imgur.com/xF3NBJp.png",
            "foreign_buy": "https://i.imgur.com/dRJnAEE.png"
        }
        
        if selected_strategy in strategy_concepts:
            st.image(strategy_concepts[selected_strategy], caption=f"{strategy_options[selected_strategy]} 概念圖示")

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

if __name__ == "__main__":
    main()
