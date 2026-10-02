import psycopg2
import time
import random
import re
DATABASE_NAME = "bless"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = ""  # 已脱敏：本地数据库密码
DATABASE_HOST = "127.0.0.1"
DATABASE_PORT = "5432"

def SecretBless(user_id,is_group,group_id,message):
    if(user_id != 3187638890):
        return ""
    if(len(message) == 1):
        return "请输入指令"
    message = message[1].strip().split()
    if(message[0] == "祝福" or message[0] == "bless"):
        return UEBless(user_id,is_group,group_id,message)
    elif(message[0] == "展示祝福" or message[0] == "show"):
        return ShowBless(user_id,is_group,group_id)
    return

def UEBless(user_id,is_group,group_id,message):
    conn,cursor = ConnectDatabase()
    sql = "SELECT ISSHOWN FROM SECRETBLESS;"
    cursor.execute(sql)
    data = cursor.fetchall()
    data = data[0][0]
    if(data == False):
        return "需要公开上一次的预测才能进行下一次预测哦"
    if(len(message) < 2):
        return "需要输入预测的选手，如果用逗号隔开视为随机选取其中一位选手"
    player_name = message[1].strip()
    player_name = re.split("[,，]",player_name)
    player_name = player_name[random.randint(0,len(player_name)-1)]
    if(player_name == ""):
        return "预测选手名称为空"
    timestamp = int(time.time())
    sql = "UPDATE SECRETBLESS SET PLAYER='"+str(player_name)+"',ISSHOWN = false,TIMESTAMP='"+str(timestamp)+"';"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return "记录预测成功"

def ShowBless(user_id,is_group,group_id):
    if(is_group == False):
        return "需要在群聊中公开祝福"
    if(group_id != 385394206):
        return "需要在指定群聊中公开祝福"
    conn,cursor = ConnectDatabase()
    sql = "SELECT PLAYER,TIMESTAMP FROM SECRETBLESS;"
    cursor.execute(sql)
    data = cursor.fetchall()
    data = data[0]
    player_name = data[0]
    timestamp = int(data[1])
    dt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
    
    sql = "UPDATE SECRETBLESS SET ISSHOWN = true;"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return "仙贝祝福了"+str(player_name)+"\n祝福时间是" + dt

def ConnectDatabase():
    conn = psycopg2.connect(database=DATABASE_NAME, user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST, port=DATABASE_PORT)
    cursor = conn.cursor()
    return conn,cursor

def DisconnectDatabase(conn,cursor):
    conn.commit()
    cursor.close()
    conn.close()