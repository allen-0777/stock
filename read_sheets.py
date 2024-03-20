import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# 身份验证并连接到Google Sheets
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('/mnt/c/Users/M0896/Desktop/stock-main/.key/ivory-streamer-361312-234cfe073038.json', scope)
client = gspread.authorize(creds)

# 获取工作表数据
sheet_for_ib_common_buy = client.open("holding_list").worksheet('外投同買')
records = sheet_for_ib_common_buy.get_all_records()

# 将数据转换为DataFrame
data = pd.DataFrame.from_records(records)

# 确保日期列是日期格式
data['日期'] = pd.to_datetime(data['日期'])

# 根据证券代号和日期排序
data.sort_values(by=['證券代號', '日期'], inplace=True)

# 计算连续日期
data['連買天數'] = data.groupby('證券代號')['日期'].diff().dt.days.eq(1).groupby(data['證券代號']).cumsum()

# 删除每个证券代号的重复项，只保留最后一个条目（最新日期）
data = data.drop_duplicates(subset='證券代號', keep='last')

# 先按日期降序排列，再按连续购买天数降序排列
data.sort_values(by=['日期', '連買天數'], ascending=[False, False], inplace=True)

# 打印数据查看结果
print(data)
