import streamlit as st
import pandas as pd
from data import *
import plotly.graph_objects as go
st.set_page_config(layout="wide")

def main():
    with st.form(key='my_form'):
        input_value = st.text_input(label='請輸入股票代號')
        submit_button = st.form_submit_button(label='查詢')

    if submit_button:
        target_url = f"https://norway.twsthr.info/StockHolders.aspx?stock={input_value}"
        st.markdown(f"[ {input_value} 的神秘金字塔]({target_url})")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["每日盤後資訊", "外資投信同買", "外資買賣超", "投信買賣超","台幣匯率"])
    with tab1:
        st.subheader("三大法人")
        df_three , data_date = three_data()
        df_three = df_three.reset_index(drop=True)  
        st.write(f"數據日期：{data_date}")
        st.dataframe(df_three)  
        st.subheader("外資未平倉")
        df = futures()
        st.dataframe(df)
        st.subheader("成交量")
        df_turnover = turnover()
        df_turnover.set_index('日期', inplace=True)
        st.bar_chart(df_turnover['成交量'])

    with tab2:
        df_com_buy, data_date = for_ib_common()
        st.write(f"數據日期：{data_date}")
        st.dataframe(df_com_buy)
        
    with tab3:
        _, df_buy_top50, df_sell_top50, data_date = for_buy_sell()
        df_buy_top50 = df_buy_top50.reset_index(drop=True)
        df_buy_top50.index = df_buy_top50.index + 1

        df_sell_top50 = df_sell_top50.reset_index(drop=True)
        df_sell_top50.index = df_sell_top50.index + 1
        st.write(f"數據日期：{data_date}")

        st.subheader("外資買超前50:")
        st.dataframe(df_buy_top50)

        st.subheader("外資賣超前50:")
        st.dataframe(df_sell_top50)

    with tab4:
        _, df_buy_top50, df_sell_top50, data_date = ib_buy_sell()
        df_buy_top50 = df_buy_top50.reset_index(drop=True)
        df_buy_top50.index = df_buy_top50.index + 1

        df_sell_top50 = df_sell_top50.reset_index(drop=True)
        df_sell_top50.index = df_sell_top50.index + 1
        st.write(f"數據日期：{data_date}")

        st.subheader("投信買超前50:")
        st.dataframe(df_buy_top50)

        st.subheader("投信賣超前50:")
        st.dataframe(df_sell_top50)

    with tab5:
        History_ExchangeRate = exchange_rate()
        fig = go.Figure()

        fig.add_trace(go.Scatter(x=History_ExchangeRate.index, 
                                y=History_ExchangeRate['buy_rate'], 
                                mode='lines+markers',
                                name='買進匯率'))
        fig.add_trace(go.Scatter(x=History_ExchangeRate.index, 
                                y=History_ExchangeRate['sell_rate'], 
                                mode='lines+markers',
                                name='賣出匯率'))
        
        fig.update_layout(yaxis_range=[30,33.5])
        st.plotly_chart(fig)
        st.write(History_ExchangeRate.sort_index(ascending=False))


if __name__ == "__main__":
    main()
