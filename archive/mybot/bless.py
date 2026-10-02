import psycopg2
import send_message as send
from plottable import Table,ColDef
import pandas
import matplotlib.pyplot as plt
import matplotlib
import photo_opt

DATABASE_NAME = "bless"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = ""  # 已脱敏：本地数据库密码
DATABASE_HOST = "127.0.0.1"
DATABASE_PORT = "5432"

def Bless(user_id,is_group,group_id,message):
    if(len(message) == 1):
        detail(user_id,is_group,group_id)
        return total(user_id,is_group,group_id)
    message = message[1].lower().strip()
    if(message == "total" or message == "总览"):
        return total(user_id,is_group,group_id)
    elif(message == "detail" or message == "详情"):
        return detail(user_id,is_group,group_id)
    return

def total(user_id,is_group,group_id):
    conn,cursor = ConnectDatabase()
    sql = "SELECT COUNT(*) FROM BLESS WHERE UERANK <> 0;;"
    cursor.execute(sql)
    data = cursor.fetchall()
    total = data[0][0]
    
    sql = "SELECT SUM(UESCORE) FROM BLESS WHERE UERANK <> 0;"
    cursor.execute(sql)
    data = cursor.fetchall()
    pt = data[0][0]
    
    sql = "SELECT COUNT(*) FROM BLESS WHERE UERANK = 1;"
    cursor.execute(sql)
    data = cursor.fetchall()
    num1 = data[0][0]
    
    sql = "SELECT COUNT(*) FROM BLESS WHERE UERANK = 2;"
    cursor.execute(sql)
    data = cursor.fetchall()
    num2 = data[0][0]
    
    sql = "SELECT COUNT(*) FROM BLESS WHERE UERANK = 3;"
    cursor.execute(sql)
    data = cursor.fetchall()
    num3 = data[0][0]
    
    sql = "SELECT COUNT(*) FROM BLESS WHERE UERANK = 4;"
    cursor.execute(sql)
    data = cursor.fetchall()
    num4 = data[0][0]
    
    sql = "SELECT SUM(UERANK) FROM BLESS"
    cursor.execute(sql)
    data = cursor.fetchall()
    numsum = data[0][0]
    averank = round(numsum/float(total), 2)
    DisconnectDatabase(conn,cursor)
    return "仙贝祝福总分:"+str(pt)+"\n一位次数:"+str(num1)+"\n二位次数:"+str(num2)+"\n三位次数:"+str(num3)+"\n四位次数:"+str(num4)+"\n平均顺位:"+str(averank)


def detail(user_id,is_group,group_id):
    conn,cursor = ConnectDatabase()
    sql = "SELECT MATCHMESSAGE,PLAYER1,SCORE1,PLAYER2,SCORE2,PLAYER3,SCORE3,PLAYER4,SCORE4,UE,UESCORE,UERANK FROM BLESS ORDER BY MATCHMESSAGE ASC;"
    cursor.execute(sql)
    data = cursor.fetchall()
    
    matchDay = []
    blessMessage = []
    for i in data:
        matchDay.append(i[0])
        blessMessage.append([i[1],i[2],i[3],i[4],i[5],i[6],i[7],i[8],i[9],i[10],i[11]])
    tableDf = pandas.DataFrame(data=blessMessage, index=matchDay, columns=["一位","一位pt","二位","二位pt","三位","三位pt","四位","四位pt","仙贝祝福","祝福pt","祝福顺位"], dtype=None, copy=False)
    table_col_defs =  [
        ColDef("比赛场次",width=1.8, title="比赛场次"),
        ColDef("一位",width=1.8, title="一位"),
        ColDef("二位",width=1.8, title="二位"),
        ColDef("三位",width=1.8, title="三位"),
        ColDef("四位",width=1.8, title="四位")]
    fig,ax = plt.subplots(figsize=(24,len(matchDay)*0.6))
    tableDf.index.set_names("比赛场次",inplace=True)
    table = Table(tableDf,column_definitions=table_col_defs,textprops={"fontsize": 16, "ha": "left", "fontname": "SimHei"})
    filename = photo_opt.getPhotoPath(user_id,is_group,group_id)
    fig.savefig(filename)
    send.sendImg(user_id,is_group,group_id,filename)
    DisconnectDatabase(conn,cursor)
    return

def ConnectDatabase():
    conn = psycopg2.connect(database=DATABASE_NAME, user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST, port=DATABASE_PORT)
    cursor = conn.cursor()
    return conn,cursor

def DisconnectDatabase(conn,cursor):
    conn.commit()
    cursor.close()
    conn.close()