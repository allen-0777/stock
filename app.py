import streamlit as st
import pandas as pd
from data import *
# data = SomeObject()
st.set_page_config(layout="wide")

def main():
    # 創建側邊欄
    # selection = st.sidebar.radio("選擇頁面", ["籌碼", "其他"])

    # 根據選擇的頁面顯示不同內容
    # if selection == "籌碼":
        # st.header("籌碼分析")

    tab1, tab2, tab3, tab4 = st.tabs(["每日盤後資訊", "外資投信同買", "外資買賣超", "投信買賣超"])
    with tab1:
        st.subheader("三大法人")
        df_three , data_date = three_data()
        df_three = df_three.reset_index(drop=True)  
        st.write(f"數據日期：{data_date}")
        st.dataframe(df_three)  
        st.subheader("成交量")
        df_turnover = turnover()
        df_turnover.set_index('日期', inplace=True)
        st.bar_chart(df_turnover['成交量'])

    with tab2:
        df_com_buy, data_date = for_ib_common()
        st.write(f"數據日期：{data_date}")
        st.dataframe(df_com_buy)
        
    with tab3:
        # st.header("自營商")
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


        # selected_date = st.date_input("篩選時間")

    # elif selection == "其他":
    #     st.header("其他分析")

if __name__ == "__main__":
    main()