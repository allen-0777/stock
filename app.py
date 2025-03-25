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
        
        # 數據過濾選項
        st.markdown("<div class='sidebar-subheader'>數據設置</div>", unsafe_allow_html=True)
        
        # 買賣超金額過濾
        min_amount = st.slider("買賣超金額下限 (萬元)", min_value=0, max_value=10000, value=0, step=100)
        
        # 日期範圍選擇
        today = datetime.now()
        date_range = st.date_input(
            "選擇日期範圍",
            value=(today - timedelta(days=7), today),
            max_value=today
        )
        
        # 三大法人選擇
        st.markdown("<div class='sidebar-subheader'>三大法人篩選</div>", unsafe_allow_html=True)
        show_foreign = st.checkbox("顯示外資", value=True)
        show_investment = st.checkbox("顯示投信", value=True)
        show_dealer = st.checkbox("顯示自營商", value=True)
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # 使用說明
        with st.expander("📖 使用說明"):
            st.markdown("""
            1. **每日盤後資訊**：查看三大法人買賣超、外資未平倉、成交量等數據
            2. **外資投信同買**：顯示外資和投信同時買超的股票
            3. **外資買賣超**：顯示外資買超、賣超前50名股票
            4. **投信買賣超**：顯示投信買超、賣超前50名股票
            5. **台幣匯率**：查看台幣兌美元匯率走勢
            6. **股票查詢**：輸入股票代號查詢相關資訊
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
    
    # 添加股票代號查詢功能
    with st.form(key='my_form'):
        input_value = st.text_input(label='請輸入股票代號', placeholder='例如: 2330')
        submit_button = st.form_submit_button(label='查詢')

    if submit_button and input_value:
        try:
            # 顯示神秘金字塔連結
            target_url = f"https://norway.twsthr.info/StockHolders.aspx?stock={input_value}"
            st.markdown(f"[<b>{input_value} 的大戶持股資訊</b>]({target_url})", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"查詢股票資訊時發生錯誤: {e}")
    
    # 使用頁籤來組織內容
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["每日盤後資訊", "外資投信同買", "外資買賣超", "投信買賣超", "台幣匯率", "交易回測"])
    
    with tab1:
        st.markdown("<div class='sub-header'>三大法人買賣超</div>", unsafe_allow_html=True)
        
        # 添加進度條
        with st.spinner("正在加載三大法人數據..."):
            df_three, data_date = three_data()
        
        if not df_three.empty:
            df_three = df_three.reset_index(drop=True)  
            st.markdown(f"<p>數據日期：<span class='data-date'>{data_date}</span></p>", unsafe_allow_html=True)
            
            # 依據側邊欄選擇篩選三大法人數據
            filtered_df = df_three.copy()
            if not show_foreign:
                filtered_df = filtered_df[filtered_df['單位名稱'] != '外資及陸資']
            if not show_investment:
                filtered_df = filtered_df[filtered_df['單位名稱'] != '投信']
            if not show_dealer:
                filtered_df = filtered_df[filtered_df['單位名稱'] != '自營商']
            
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

    with tab2:
        st.markdown("<div class='sub-header'>外資與投信同步買超</div>", unsafe_allow_html=True)
        
        with st.spinner("正在加載外資投信同買資訊..."):
            df_com_buy, data_date = for_ib_common()
        
        if not df_com_buy.empty:
            st.markdown(f"<p>數據日期：<span class='data-date'>{data_date}</span></p>", unsafe_allow_html=True)
            
            # 根據側邊欄的買賣超金額過濾
            if min_amount > 0:
                # 轉換單位從萬元到元
                min_amount_in_share = min_amount * 10000
                df_com_buy = df_com_buy[
                    (df_com_buy['外資買賣超股數'] >= min_amount_in_share) & 
                    (df_com_buy['投信買賣超股數'] >= min_amount_in_share)
                ]
                
            st.dataframe(df_com_buy, use_container_width=True)
            
            # 添加資訊提示
            st.info("外資和投信同時買超的股票，通常代表強力買盤，值得關注")
        else:
            st.warning("無法獲取外資投信同買資訊或當日無同買個股")
        
    with tab3:
        st.markdown("<div class='sub-header'>外資買賣超排行</div>", unsafe_allow_html=True)
        
        with st.spinner("正在加載外資買賣超資訊..."):
            _, df_buy_top50, df_sell_top50, data_date = for_buy_sell()
        
        if not df_buy_top50.empty and not df_sell_top50.empty:
            # 格式化索引
            df_buy_top50 = df_buy_top50.reset_index(drop=True)
            df_buy_top50.index = df_buy_top50.index + 1

            df_sell_top50 = df_sell_top50.reset_index(drop=True)
            df_sell_top50.index = df_sell_top50.index + 1
            
            st.markdown(f"<p>數據日期：<span class='data-date'>{data_date}</span></p>", unsafe_allow_html=True)

            # 創建兩列布局
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("<div class='sub-header'>外資買超前50:</div>", unsafe_allow_html=True)
                
                # 根據側邊欄的買賣超金額過濾
                if min_amount > 0:
                    # 轉換單位從萬元到股數（粗略估計）
                    min_amount_in_share = min_amount * 1000  # 假設每股約10元
                    df_buy_top50 = df_buy_top50[df_buy_top50['外資買賣超股數'] >= min_amount_in_share]
                
                st.dataframe(df_buy_top50, use_container_width=True)

            with col2:
                st.markdown("<div class='sub-header'>外資賣超前50:</div>", unsafe_allow_html=True)
                
                # 根據側邊欄的買賣超金額過濾
                if min_amount > 0:
                    # 對於賣超，我們關心絕對值
                    min_amount_in_share = min_amount * 1000  # 假設每股約10元
                    df_sell_top50 = df_sell_top50[abs(df_sell_top50['外資買賣超股數']) >= min_amount_in_share]
                
                st.dataframe(df_sell_top50, use_container_width=True)
        else:
            st.warning("無法獲取外資買賣超資訊")

    with tab4:
        st.markdown("<div class='sub-header'>投信買賣超排行</div>", unsafe_allow_html=True)
        
        with st.spinner("正在加載投信買賣超資訊..."):
            _, df_buy_top50, df_sell_top50, data_date = ib_buy_sell()
        
        if not df_buy_top50.empty and not df_sell_top50.empty:
            # 格式化索引
            df_buy_top50 = df_buy_top50.reset_index(drop=True)
            df_buy_top50.index = df_buy_top50.index + 1

            df_sell_top50 = df_sell_top50.reset_index(drop=True)
            df_sell_top50.index = df_sell_top50.index + 1
            
            st.markdown(f"<p>數據日期：<span class='data-date'>{data_date}</span></p>", unsafe_allow_html=True)
            
            # 創建兩列布局
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("<div class='sub-header'>投信買超前50:</div>", unsafe_allow_html=True)
                
                # 根據側邊欄的買賣超金額過濾
                if min_amount > 0:
                    # 轉換單位從萬元到股數（粗略估計）
                    min_amount_in_share = min_amount * 1000  # 假設每股約10元
                    df_buy_top50 = df_buy_top50[df_buy_top50['投信買賣超股數'] >= min_amount_in_share]
                
                st.dataframe(df_buy_top50, use_container_width=True)

            with col2:
                st.markdown("<div class='sub-header'>投信賣超前50:</div>", unsafe_allow_html=True)
                
                # 根據側邊欄的買賣超金額過濾
                if min_amount > 0:
                    # 對於賣超，我們關心絕對值
                    min_amount_in_share = min_amount * 1000  # 假設每股約10元
                    df_sell_top50 = df_sell_top50[abs(df_sell_top50['投信買賣超股數']) >= min_amount_in_share]
                
                st.dataframe(df_sell_top50, use_container_width=True)
        else:
            st.warning("無法獲取投信買賣超資訊")

    with tab5:
        st.markdown("<div class='sub-header'>台幣匯率走勢</div>", unsafe_allow_html=True)
        
        with st.spinner("正在加載匯率資訊..."):
            History_ExchangeRate = exchange_rate()
        
        if not History_ExchangeRate.empty:
            # 根據側邊欄的日期範圍過濾
            if len(date_range) == 2:
                start_date, end_date = date_range
                start_date_str = start_date.strftime('%Y/%m/%d')
                end_date_str = end_date.strftime('%Y/%m/%d')
                
                # 過濾日期範圍內的數據
                mask = (pd.to_datetime(History_ExchangeRate.index) >= pd.to_datetime(start_date_str)) & \
                       (pd.to_datetime(History_ExchangeRate.index) <= pd.to_datetime(end_date_str))
                
                filtered_exchange_rate = History_ExchangeRate[mask]
                
                # 如果過濾後沒有數據，使用原始數據
                if filtered_exchange_rate.empty:
                    filtered_exchange_rate = History_ExchangeRate
                    st.warning(f"選擇的日期範圍內沒有匯率數據，顯示所有可用數據")
            else:
                filtered_exchange_rate = History_ExchangeRate
            
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
            
    with tab6:
        st.markdown("<div class='sub-header'>交易回測系統</div>", unsafe_allow_html=True)
        st.markdown("<p class='info-text'>透過歷史數據模擬不同交易策略的表現，評估策略的獲利能力和風險。</p>", unsafe_allow_html=True)
        
        # 回測設置
        with st.expander("回測設置", expanded=True):
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
                
                # 策略參數
                if selected_strategy == "ma_cross":
                    short_ma = st.slider("短期均線 (天數)", min_value=5, max_value=30, value=5, step=1)
                    long_ma = st.slider("長期均線 (天數)", min_value=10, max_value=120, value=20, step=5)
                
                elif selected_strategy == "rsi":
                    rsi_period = st.slider("RSI 周期", min_value=5, max_value=30, value=14, step=1)
                    rsi_overbought = st.slider("超買閾值", min_value=60, max_value=90, value=70, step=1)
                    rsi_oversold = st.slider("超賣閾值", min_value=10, max_value=40, value=30, step=1)
                
                elif selected_strategy == "macd":
                    macd_fast = st.slider("快線周期", min_value=5, max_value=20, value=12, step=1)
                    macd_slow = st.slider("慢線周期", min_value=20, max_value=50, value=26, step=1)
                    macd_signal = st.slider("信號線周期", min_value=5, max_value=15, value=9, step=1)
                
                elif selected_strategy == "bollinger":
                    bollinger_period = st.slider("布林通道周期", min_value=10, max_value=30, value=20, step=1)
                    bollinger_std = st.slider("標準差倍數", min_value=1.0, max_value=3.0, value=2.0, step=0.1)
                
                elif selected_strategy == "foreign_buy":
                    foreign_buy_threshold = st.slider("外資買超閾值 (張)", min_value=100, max_value=5000, value=1000, step=100)
        
        # 執行回測按鈕
        if st.button("執行回測", use_container_width=True):
            with st.spinner("正在執行回測計算..."):
                # 獲取真實歷史數據
                try:
                    # 獲取策略參數
                    strategy_params = {}
                    
                    if selected_strategy == "ma_cross":
                        strategy_params = {
                            'short_ma': short_ma,
                            'long_ma': long_ma
                        }
                    elif selected_strategy == "rsi":
                        strategy_params = {
                            'rsi_period': rsi_period,
                            'rsi_overbought': rsi_overbought,
                            'rsi_oversold': rsi_oversold
                        }
                    elif selected_strategy == "macd":
                        strategy_params = {
                            'macd_fast': macd_fast,
                            'macd_slow': macd_slow,
                            'macd_signal': macd_signal
                        }
                    elif selected_strategy == "bollinger":
                        strategy_params = {
                            'bollinger_period': bollinger_period,
                            'bollinger_std': bollinger_std
                        }
                    elif selected_strategy == "foreign_buy":
                        strategy_params = {
                            'foreign_buy_threshold': foreign_buy_threshold
                        }
                    
                    # 設定回測時間範圍
                    start_date_str = backtest_start_date.strftime("%Y-%m-%d")
                    end_date_str = backtest_end_date.strftime("%Y-%m-%d")
                    
                    # 獲取股票歷史數據
                    df_stock = get_stock_history(selected_stock, start_date_str, end_date_str)
                    
                    if df_stock.empty:
                        st.error(f"無法獲取 {selected_stock} 的歷史數據，請檢查股票代碼或選擇其他日期範圍")
                        return
                    
                    # 計算技術指標
                    df_with_indicators = calculate_technical_indicators(df_stock)
                    
                    # 執行回測
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
                    
                    # 回測結果
                    st.markdown("<div class='sub-header'>回測結果</div>", unsafe_allow_html=True)
                    
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
                            for key, value in backtest_results.items():
                                st.markdown(f"**{key}:** {value}")
                        
                        with col2:
                            st.markdown("##### 股票基本資訊")
                            stock_info = get_stock_info(selected_stock)
                            for key, value in stock_info.items():
                                st.markdown(f"**{key}:** {value}")
                        
                        # 顯示技術指標
                        st.markdown("##### 技術指標圖表")
                        
                        # 選擇要顯示的指標
                        indicator_options = ["移動平均線", "RSI指標", "MACD指標", "布林通道", "KD指標"]
                        selected_indicator = st.selectbox("選擇技術指標", indicator_options)
                        
                        # 繪製所選指標
                        if selected_indicator == "移動平均線":
                            fig = go.Figure()
                            
                            # 添加K線圖
                            fig.add_trace(go.Candlestick(
                                x=df_with_indicators.index,
                                open=df_with_indicators['開盤價'],
                                high=df_with_indicators['最高價'],
                                low=df_with_indicators['最低價'],
                                close=df_with_indicators['收盤價'],
                                name='股價'
                            ))
                            
                            # 添加移動平均線
                            ma_columns = [col for col in df_with_indicators.columns if isinstance(col, str) and col.startswith('MA')]
                            for col in ma_columns:
                                fig.add_trace(go.Scatter(
                                    x=df_with_indicators.index,
                                    y=df_with_indicators[col],
                                    name=col,
                                    line=dict(width=1.5)
                                ))
                            
                            fig.update_layout(
                                title=f'{stock_options.get(selected_stock, selected_stock)} 移動平均線',
                                xaxis_title='日期',
                                yaxis_title='價格',
                                height=500
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                        elif selected_indicator == "RSI指標":
                            # 創建兩個子圖
                            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                               vertical_spacing=0.1, 
                                               row_heights=[0.7, 0.3])
                            
                            # 添加K線圖
                            fig.add_trace(go.Candlestick(
                                x=df_with_indicators.index,
                                open=df_with_indicators['開盤價'],
                                high=df_with_indicators['最高價'],
                                low=df_with_indicators['最低價'],
                                close=df_with_indicators['收盤價'],
                                name='股價'
                            ), row=1, col=1)
                            
                            # 添加RSI指標
                            fig.add_trace(go.Scatter(
                                x=df_with_indicators.index,
                                y=df_with_indicators['RSI14'],
                                name='RSI(14)',
                                line=dict(color='purple', width=1.5)
                            ), row=2, col=1)
                            
                            # 添加超買超賣線
                            fig.add_shape(
                                type="line",
                                x0=df_with_indicators.index[0],
                                y0=70,
                                x1=df_with_indicators.index[-1],
                                y1=70,
                                line=dict(color="red", width=1, dash="dash"),
                                row=2, col=1
                            )
                            
                            fig.add_shape(
                                type="line",
                                x0=df_with_indicators.index[0],
                                y0=30,
                                x1=df_with_indicators.index[-1],
                                y1=30,
                                line=dict(color="green", width=1, dash="dash"),
                                row=2, col=1
                            )
                            
                            fig.update_layout(
                                title=f'{stock_options.get(selected_stock, selected_stock)} RSI指標',
                                xaxis_title='日期',
                                yaxis_title='價格',
                                height=600
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                        elif selected_indicator == "MACD指標":
                            # 創建兩個子圖
                            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                               vertical_spacing=0.1, 
                                               row_heights=[0.7, 0.3])
                            
                            # 添加K線圖
                            fig.add_trace(go.Candlestick(
                                x=df_with_indicators.index,
                                open=df_with_indicators['開盤價'],
                                high=df_with_indicators['最高價'],
                                low=df_with_indicators['最低價'],
                                close=df_with_indicators['收盤價'],
                                name='股價'
                            ), row=1, col=1)
                            
                            # 添加MACD和信號線
                            fig.add_trace(go.Scatter(
                                x=df_with_indicators.index,
                                y=df_with_indicators['MACD'],
                                name='MACD',
                                line=dict(color='blue', width=1.5)
                            ), row=2, col=1)
                            
                            fig.add_trace(go.Scatter(
                                x=df_with_indicators.index,
                                y=df_with_indicators['MACD_Signal'],
                                name='Signal',
                                line=dict(color='red', width=1.5)
                            ), row=2, col=1)
                            
                            # 添加MACD柱狀圖
                            colors = ['green' if val >= 0 else 'red' for val in df_with_indicators['MACD_Hist']]
                            fig.add_trace(go.Bar(
                                x=df_with_indicators.index,
                                y=df_with_indicators['MACD_Hist'],
                                name='Histogram',
                                marker_color=colors
                            ), row=2, col=1)
                            
                            fig.update_layout(
                                title=f'{stock_options.get(selected_stock, selected_stock)} MACD指標',
                                xaxis_title='日期',
                                yaxis_title='價格',
                                height=600
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                        elif selected_indicator == "布林通道":
                            fig = go.Figure()
                            
                            # 添加K線圖
                            fig.add_trace(go.Candlestick(
                                x=df_with_indicators.index,
                                open=df_with_indicators['開盤價'],
                                high=df_with_indicators['最高價'],
                                low=df_with_indicators['最低價'],
                                close=df_with_indicators['收盤價'],
                                name='股價'
                            ))
                            
                            # 添加布林帶
                            fig.add_trace(go.Scatter(
                                x=df_with_indicators.index,
                                y=df_with_indicators['BB_Upper'],
                                name='上軌',
                                line=dict(color='rgba(173, 216, 230, 0.7)', width=1)
                            ))
                            
                            fig.add_trace(go.Scatter(
                                x=df_with_indicators.index,
                                y=df_with_indicators['BB_Middle'],
                                name='中軌',
                                line=dict(color='rgba(0, 0, 255, 0.7)', width=1)
                            ))
                            
                            fig.add_trace(go.Scatter(
                                x=df_with_indicators.index,
                                y=df_with_indicators['BB_Lower'],
                                name='下軌',
                                line=dict(color='rgba(173, 216, 230, 0.7)', width=1),
                                fill='tonexty',
                                fillcolor='rgba(173, 216, 230, 0.2)'
                            ))
                            
                            fig.update_layout(
                                title=f'{stock_options.get(selected_stock, selected_stock)} 布林通道',
                                xaxis_title='日期',
                                yaxis_title='價格',
                                height=500
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                        elif selected_indicator == "KD指標":
                            # 創建兩個子圖
                            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                               vertical_spacing=0.1, 
                                               row_heights=[0.7, 0.3])
                            
                            # 添加K線圖
                            fig.add_trace(go.Candlestick(
                                x=df_with_indicators.index,
                                open=df_with_indicators['開盤價'],
                                high=df_with_indicators['最高價'],
                                low=df_with_indicators['最低價'],
                                close=df_with_indicators['收盤價'],
                                name='股價'
                            ), row=1, col=1)
                            
                            # 添加KD指標
                            fig.add_trace(go.Scatter(
                                x=df_with_indicators.index,
                                y=df_with_indicators['K'],
                                name='K值',
                                line=dict(color='blue', width=1.5)
                            ), row=2, col=1)
                            
                            fig.add_trace(go.Scatter(
                                x=df_with_indicators.index,
                                y=df_with_indicators['D'],
                                name='D值',
                                line=dict(color='red', width=1.5)
                            ), row=2, col=1)
                            
                            # 添加超買超賣線
                            fig.add_shape(
                                type="line",
                                x0=df_with_indicators.index[0],
                                y0=80,
                                x1=df_with_indicators.index[-1],
                                y1=80,
                                line=dict(color="red", width=1, dash="dash"),
                                row=2, col=1
                            )
                            
                            fig.add_shape(
                                type="line",
                                x0=df_with_indicators.index[0],
                                y0=20,
                                x1=df_with_indicators.index[-1],
                                y1=20,
                                line=dict(color="green", width=1, dash="dash"),
                                row=2, col=1
                            )
                            
                            fig.update_layout(
                                title=f'{stock_options.get(selected_stock, selected_stock)} KD指標',
                                xaxis_title='日期',
                                yaxis_title='價格',
                                height=600
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # 添加交易策略說明
                    st.markdown("##### 策略說明")
                    strategy_desc = {
                        "ma_cross": "均線交叉策略是一種技術分析策略，當短期均線（如5日均線）從下方穿過長期均線（如20日均線）時產生買入訊號，反之則產生賣出訊號。",
                        "rsi": "RSI指標策略使用相對強弱指標來判斷股票的超買或超賣狀態。當RSI低於30時視為超賣，產生買入訊號；當RSI高於70時視為超買，產生賣出訊號。",
                        "macd": "MACD策略結合了趨勢跟蹤和動量指標。當MACD線從下方穿過信號線時產生買入訊號，從上方穿過時產生賣出訊號。",
                        "bollinger": "布林通道策略使用價格波動的標準差建立價格範圍。當價格接近下軌時買入，接近上軌時賣出，適合震盪行情。",
                        "foreign_buy": "外資買超策略追蹤外資的買賣動向，當外資持續買超特定股票超過設定門檻時買入，外資轉為賣超時賣出。"
                    }
                    
                    st.info(strategy_desc.get(selected_strategy, ""))
                    
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
    
    # 添加頁腳
    st.markdown("---")
    st.markdown("<p class='info-text' style='text-align: center;'>© 2025 台股資訊分析儀表板 | 資料僅供參考，不構成投資建議</p>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
