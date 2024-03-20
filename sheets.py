import gspread
from oauth2client.service_account import ServiceAccountCredentials
from data import *

scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('/mnt/c/Users/M0896/Desktop/stock-main/.key/ivory-streamer-361312-234cfe073038.json', scope)
client = gspread.authorize(creds)

sheet_three = client.open("holding_list").worksheet('三大法人') 
sheet_for_ib_common_buy = client.open("holding_list").worksheet('外投同買')
sheet_for_buy = client.open("holding_list").worksheet('外資連買')
sheet_for_sell = client.open("holding_list").worksheet('外資連賣')
sheet_for_ib_common_sell = client.open("holding_list").worksheet('外投同賣')
sheet_ib_buy = client.open("holding_list").worksheet('投信連買')
sheet_ib_sell = client.open("holding_list").worksheet('投信連賣')

def write_data_to_sheet(dataframe, worksheet,start_row):
    list_of_rows = dataframe.values.tolist()
    
    worksheet.insert_rows(list_of_rows, start_row)

def etl_three_data():
    df, data_date = three_data()
    df_T = df.T
    df_T = df_T.reset_index()
    df_T.columns = df_T.iloc[0]
    df_T = df_T.drop(df_T.index[0])
    df_T.reset_index(drop=True, inplace=True)
    df_T.insert(0, '日期', data_date)
    df_T.drop(df_T.columns[1], axis=1, inplace=True)
    return df_T

def etl_futures_data():
    df_futures = futures()
    df_futures_T = df_futures.T
    df_futures_T = df_futures_T.reset_index()
    df_futures_T.drop(df_futures_T.columns[0], axis=1, inplace=True)
    df_futures_T.drop(1, axis=0, inplace=True)
    return df_futures_T

def etl_concat_data():
    df_T = etl_three_data()
    df_futures_T = etl_futures_data()
    final_df = pd.concat([df_T, df_futures_T], axis=1)
    return final_df
def etl_for_buy_sell_data():
    df_for_all, df_for_buy, df_for_sell, data_date = for_buy_sell()
    df_for_buy.insert(0, '日期', data_date)
    df_for_sell.insert(0, '日期', data_date)
    return df_for_buy, df_for_sell

def etl_ib_buy_sell_data():
    df_ib_all, df_ib_buy, df_ib_sell, data_date = ib_buy_sell()
    df_ib_buy.insert(0, '日期', data_date)
    df_ib_sell.insert(0, '日期', data_date)
    return df_ib_buy,  df_ib_sell

def etl_for_ib_com_data():
    df_com_buy, df_com_sell, data_date = for_ib_common_buy_sell()
    df_com_buy.insert(0, '日期', data_date)
    df_com_sell.insert(0, '日期', data_date)

    return df_com_buy, df_com_sell

def process_and_write_data():
    final_df = etl_concat_data()
    # print(final_df)
    df_for_buy, df_for_sell = etl_for_buy_sell_data()
    # print(df_for_buy)
    # print(df_for_sell)
    df_ib_buy,df_ib_sell = etl_ib_buy_sell_data()
    # print(df_ib_buy)
    # print(df_ib_sell)
    df_com_buy, df_com_sell = etl_for_ib_com_data()
    # print(df_com_buy)
    # print(df_com_sell)
    write_data_to_sheet(final_df, sheet_three, 4)
    write_data_to_sheet(df_for_buy, sheet_for_buy, 3) 
    write_data_to_sheet(df_for_sell, sheet_for_sell, 3) 
    write_data_to_sheet(df_ib_buy, sheet_ib_buy, 3)  
    write_data_to_sheet(df_ib_sell, sheet_ib_sell, 3)  
    write_data_to_sheet(df_com_buy, sheet_for_ib_common_buy, 3)  
    write_data_to_sheet(df_com_sell, sheet_for_ib_common_sell, 3)  

process_and_write_data()