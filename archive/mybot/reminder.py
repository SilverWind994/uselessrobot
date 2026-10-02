import schedule
import time
import psycopg2
import send_message
import random
import os

DATABASE_NAME = "robot"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = ""  # 已脱敏：本地数据库密码
DATABASE_HOST = "127.0.0.1"
DATABASE_PORT = "5432"

def connectDatabase():
    conn = psycopg2.connect(database=DATABASE_NAME, user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST, port=DATABASE_PORT)
    cursor = conn.cursor()
    return conn,cursor

def disconnectDatabase(conn,cursor):
    conn.commit()
    cursor.close()
    conn.close()

def remind():
    timestamp=time.time()
    local_time = time.localtime(timestamp)
    local_time = time.strftime("%Y-%m-%d %H:%M:00", local_time)

    conn,cursor = connectDatabase()

    
    sql = "SELECT user_id,is_group,group_id,content,time_remind FROM REMINDER WHERE time_remind <= '"+local_time+"'"
    cursor.execute(sql)
    data = cursor.fetchall()
    sql = "DELETE FROM REMINDER WHERE time_remind <= '"+local_time+"'"
    cursor.execute(sql)

    disconnectDatabase(conn,cursor)
    for msg in data:
        user_id = msg[0]
        is_group = msg[1]
        group_id = msg[2]
        content = msg[3]
        if(is_group):
            send_message.sendTextToGroupWithAt(group_id,user_id,content)
        else:
            send_message.sendTextToPrivate(user_id,content)
    
    conn,cursor = connectDatabase()
    timestamp=time.time()
    local_time = time.localtime(timestamp)
    # if(local_time.tm_min %10 == 8):
    #     send_message.sendTextToPrivate(0,"在线")
    # if(local_time.tm_hour == 8 or local_time.tm_hour == 9 ):
    #     sql = "SELECT ISMORNING FROM ISMORNING;"
    #     cursor.execute(sql)
    #     data = cursor.fetchall()
    #     data = data[0][0]
    #     if(data == False):
    #         sql = "UPDATE ISMORNING SET ISMORNING = TRUE;"
    #         cursor.execute(sql)
    #         sql = "SELECT COUNT(*) FROM TALE;"
    #         cursor.execute(sql)
    #         data = cursor.fetchall()
    #         data = data[0][0]
    #         if(data == 0):
    #             tale = '已经不知道说什么了，那么最后，很高兴遇到大家，最后一次说早安了，以后也要一直加油喵。'
    #         else:
    #             select = random.randint(0, data-1)
    #             sql = "SELECT TALE FROM TALE ORDER BY TALE LIMIT 1 OFFSET " + str(select) + ";"
    #             cursor.execute(sql)
    #             data = cursor.fetchall()
    #             tale = data[0][0]
    #         content = "今天是"+str(local_time.tm_year)+"年"+str(local_time.tm_mon)+"月"+str(local_time.tm_mday)+"日，今天也要加油喵\n" + tale
    #         sql = "SELECT USERID,ISGROUP,GROUPID FROM MORNING;"
    #         cursor.execute(sql)
    #         data = cursor.fetchall()
    #         folder_path = 'C:\\mybot\\fig'
    #         file_names = os.listdir(folder_path)
    #         file_name = file_names[random.randint(0, len(file_names)-1)]
    #         file_name = 'C:\\mybot\\fig\\'+file_name
    #         for i in data:
    #             send_message.sendText(str(i[0]),str(i[1]),str(i[2]),content)
    #             send_message.sendImg(str(i[0]),str(i[1]),str(i[2]),file_name)
    #         sql = "DELETE FROM TALE WHERE TALE = '"+str(tale)+"';"
    #         cursor.execute(sql)
    #         os.remove(file_name)
    
    # if(local_time.tm_hour ==10):
    #     sql = "UPDATE ISMORNING SET ISMORNING = FALSE;"
    #     cursor.execute(sql)
        
    disconnectDatabase(conn,cursor)


schedule.every().minute.at(":00").do(remind)

while True:
    schedule.run_pending()
    time.sleep(3)