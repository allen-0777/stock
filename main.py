from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from clickhouse_driver import Client
from fastapi.responses import StreamingResponse
import time
import asyncio
from datetime import datetime
from typing import List, Optional

app = FastAPI()

# 初始化ClickHouse客戶端
client = Client(host='localhost', user='default', password='12345678', database='default')

@app.on_event("startup")
def startup_event():
    # 在應用啟動時創建資料表
    create_table_query = """
    CREATE TABLE IF NOT EXISTS SlotGamePlays
    (
        UserID Int32,
        GameSessionID String,
        TimeStamp DateTime,
        BetAmount Float32,
        WinAmount Float32,
        GameType String
    ) ENGINE = MergeTree()
    ORDER BY (TimeStamp, UserID);
    """
    client.execute(create_table_query)

@app.post("/insert/")
def insert_data():
    data = [
        (1, 'session_1', datetime.now(), 100.0, 150.0, 'TypeA'),
        (2, 'session_2', datetime.now(), 200.0, 0.0, 'TypeB')
    ]
    insert_query = "INSERT INTO SlotGamePlays (UserID, GameSessionID, TimeStamp, BetAmount, WinAmount, GameType) VALUES"
    client.execute(insert_query, data)
    return {"message": "Data inserted successfully"}

@app.get("/analysis/")
def analyze_data(start_date: datetime, end_date: datetime, user_id: Optional[int] = None):
    where_clauses = [f"TimeStamp BETWEEN '{start_date}' AND '{end_date}'"]
    if user_id:
        where_clauses.append(f"UserID = {user_id}")

    where_statement = " AND ".join(where_clauses)
    
    query_avg = f"""
    SELECT 
        AVG(BetAmount) AS AvgBet, 
        AVG(WinAmount) AS AvgWin
    FROM SlotGamePlays
    WHERE {where_statement}
    """
    
    avg_results = client.execute(query_avg)
    if not avg_results:
        raise HTTPException(status_code=404, detail="No data found")

    return {
        "用戶": user_id,
        "開始時間": start_date,
        "結束時間": end_date,
        "平均下注金額": avg_results[0][0],
        "平均獲勝金額": avg_results[0][1]
    }

@app.get("/analysis/mapreduce/")
def analyze_data_with_mapreduce(
    start_date: str = Query(..., min_length=8, max_length=8, regex="^[0-9]{8}$"), 
    end_date: str = Query(..., min_length=8, max_length=8, regex="^[0-9]{8}$")
):
    # 將YYYYMMDD格式的字符串轉換為datetime對象
    start_datetime = datetime.strptime(start_date, '%Y%m%d')
    end_datetime = datetime.strptime(end_date, '%Y%m%d')

    query = f"""
    SELECT 
        GameType,
        SUM(BetAmount) AS TotalBetAmount, 
        SUM(WinAmount) AS TotalWinAmount
    FROM SlotGamePlays
    WHERE TimeStamp BETWEEN '{start_datetime}' AND '{end_datetime}'
    GROUP BY GameType
    """
    
    results = client.execute(query)
    if not results:
        raise HTTPException(status_code=404, detail="No data found")

    analysis_results = [
        {"遊戲類型": result[0], "總下注金額": result[1], "總獲勝金額": result[2]} for result in results
    ]

    return {
        "開始時間": start_date,
        "結束時間": end_date,
        "結果": analysis_results
    }

@app.get("/dashboard/recent_activity/")
def recent_activity(last_minutes: int = 30):
    query = f"""
    SELECT 
        COUNT(DISTINCT UserID) AS ActiveUsers,
        SUM(BetAmount) AS TotalBetAmount,
        SUM(WinAmount) AS TotalWinAmount
    FROM SlotGamePlays
    WHERE TimeStamp >= now() - INTERVAL {last_minutes} MINUTE
    """
    results = client.execute(query)
    return {
        "活躍用戶數": results[0][0],
        "總下注金額": results[0][1],
        "總獲勝金額": results[0][2],
        "時間範圍（分鐘）": last_minutes
    }

@app.get("/analysis/monthly_active_users/")
def monthly_active_users(year: int):
    query = f"""
    SELECT 
        toMonth(TimeStamp) AS Month, 
        COUNT(DISTINCT UserID) AS ActiveUsers
    FROM SlotGamePlays
    WHERE toYear(TimeStamp) = {year}
    GROUP BY Month
    ORDER BY Month
    """
    results = client.execute(query)
    monthly_activity = [{"月份": result[0], "活躍用戶數": result[1]} for result in results]
    return {"年份": year, "每月活躍用戶趨勢": monthly_activity}

def fetch_recent_activity():
    last_minutes = 30
    query = f"""
    SELECT 
        COUNT(DISTINCT UserID) AS ActiveUsers,
        SUM(BetAmount) AS TotalBetAmount,
        SUM(WinAmount) AS TotalWinAmount
    FROM SlotGamePlays
    WHERE TimeStamp >= now() - INTERVAL {last_minutes} MINUTE
    """
    results = client.execute(query)
    return {
        "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "活躍玩家": results[0][0],
        "總下注金額": results[0][1],
        "總獲勝金額": results[0][2]
    }

def sse_generator():
    try:
        while True:
            data = fetch_recent_activity()
            yield f"data: {data}\n\n"
            time.sleep(3)  
    except asyncio.CancelledError:
        print("Client disconnected; stopping SSE stream.")
        return
    except Exception as e:
        print(f"Unexpected error: {e}")
        return

@app.get("/sse/recent-activity/")
def sse_recent_activity(background_tasks: BackgroundTasks):
    return StreamingResponse(sse_generator(), media_type="text/event-stream")