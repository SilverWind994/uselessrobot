import send_message as send
import psycopg2
import re
from plottable import Table,ColDef
import pandas
import matplotlib.pyplot as plt
import matplotlib
import photo_opt
import time
import requests
import json
import random
from PIL import Image,ImageDraw,ImageFont

DATABASE_NAME = "ucml"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = ""  # 已脱敏：本地数据库密码
DATABASE_HOST = "127.0.0.1"
DATABASE_PORT = "5432"

def ucmt(userId,isGroup,groupId,message,userName):
    if(len(message) == 1):
        return "缺少指令参数"
    message = message[1].strip()
    if(message == "m"):
        return drawMatch(userId,isGroup,groupId)
    elif(message == "a"):
        return startAll()
    elif(message == "n"):
        return NextStage()
    else:
        return startMatch(message)
    return "不存在这个指令"

def drawGroup(backGround,players,colors,points1,points2,ranks,loc,groupName,groupType):
    draw = ImageDraw.Draw(backGround)
    draw.rectangle([loc, (loc[0]+442, loc[1]+202)], fill="black")
    draw.rectangle([(loc[0]+2, loc[1]+2), (loc[0]+440, loc[1]+40)], fill="white")
    draw.rectangle([(loc[0]+2, loc[1]+40), (loc[0]+440, loc[1]+80)], fill=colors[0])
    draw.rectangle([(loc[0]+2, loc[1]+80), (loc[0]+440, loc[1]+120)], fill=colors[1])
    draw.rectangle([(loc[0]+2, loc[1]+120), (loc[0]+440, loc[1]+160)], fill=colors[2])
    draw.rectangle([(loc[0]+2, loc[1]+160), (loc[0]+440, loc[1]+200)], fill=colors[3])
    draw.rectangle([(loc[0]+2, loc[1]+40), (loc[0]+440, loc[1]+41)], fill="black")
    draw.rectangle([(loc[0]+2, loc[1]+80), (loc[0]+442, loc[1]+81)], fill="black")
    draw.rectangle([(loc[0]+2, loc[1]+120), (loc[0]+442, loc[1]+121)], fill="black")
    draw.rectangle([(loc[0]+2, loc[1]+160), (loc[0]+442, loc[1]+161)], fill="black")
    draw.rectangle([(loc[0]+180, loc[1]+2), (loc[0]+181, loc[1]+202)], fill="black")
    draw.rectangle([(loc[0]+245, loc[1]+2), (loc[0]+246, loc[1]+202)], fill="black")
    draw.rectangle([(loc[0]+310, loc[1]+2), (loc[0]+311, loc[1]+202)], fill="black")
    draw.rectangle([(loc[0]+375, loc[1]+2), (loc[0]+376, loc[1]+202)], fill="black")
    font = ImageFont.truetype("C:\\feiTFM\\Deng.ttf",20)
    draw.text((loc[0]+10, loc[1]+8),groupName,"BLACK",font)
    draw.text((loc[0]+193, loc[1]+8),"一回","BLACK",font)
    draw.text((loc[0]+258, loc[1]+8),"二回","BLACK",font)
    draw.text((loc[0]+323, loc[1]+8),"总分","BLACK",font)
    draw.text((loc[0]+388, loc[1]+8),"名次","BLACK",font)
    draw.text((loc[0]+10, loc[1]+48),players[0],"BLACK",font)
    draw.text((loc[0]+10, loc[1]+88),players[1],"BLACK",font)
    draw.text((loc[0]+10, loc[1]+128),players[2],"BLACK",font)
    draw.text((loc[0]+10, loc[1]+168),players[3],"BLACK",font)

    if(not(points1[0] == points1[1] and points1[0] == points1[2] and points1[0] == points1[3])):
        draw.text((loc[0]+185, loc[1]+48),f"{points1[0]:.1f}","BLACK",font)
        draw.text((loc[0]+185, loc[1]+88),f"{points1[1]:.1f}","BLACK",font)
        draw.text((loc[0]+185, loc[1]+128),f"{points1[2]:.1f}","BLACK",font)
        draw.text((loc[0]+185, loc[1]+168),f"{points1[3]:.1f}","BLACK",font)
        draw.text((loc[0]+315, loc[1]+48),f"{points1[0]+points2[0]:.1f}","BLACK",font)
        draw.text((loc[0]+315, loc[1]+88),f"{points1[1]+points2[1]:.1f}","BLACK",font)
        draw.text((loc[0]+315, loc[1]+128),f"{points1[2]+points2[2]:.1f}","BLACK",font)
        draw.text((loc[0]+315, loc[1]+168),f"{points1[3]+points2[3]:.1f}","BLACK",font)
        
    if(not(points2[0] == points2[1] and points2[0] == points2[2] and points2[0] == points2[3])):
        draw.text((loc[0]+250, loc[1]+48),f"{points2[0]:.1f}","BLACK",font)
        draw.text((loc[0]+250, loc[1]+88),f"{points2[1]:.1f}","BLACK",font)
        draw.text((loc[0]+250, loc[1]+128),f"{points2[2]:.1f}","BLACK",font)
        draw.text((loc[0]+250, loc[1]+168),f"{points2[3]:.1f}","BLACK",font)
    
    
    
    rankName = ["一位","二位","淘汰","淘汰"]
    if(groupType == 1):
        rankName = ["一位","二位","复活","淘汰"]
    if(groupType == 3):
        rankName = ["冠军","亚军","季军","殿军"]
    if(groupType == 4):
        rankName = ["一位","淘汰","淘汰","淘汰"]
        
    if(not(ranks[0] == 0)):
        draw.text((loc[0]+388, loc[1]+48),rankName[ranks[0]-1],"BLACK",font)
        draw.text((loc[0]+388, loc[1]+88),rankName[ranks[1]-1],"BLACK",font)
        draw.text((loc[0]+388, loc[1]+128),rankName[ranks[2]-1],"BLACK",font)
        draw.text((loc[0]+388, loc[1]+168),rankName[ranks[3]-1],"BLACK",font)


def drawMatch(user_id,is_group,group_id):
    image = Image.new(mode='RGB',size=(1850,3200),color="pink")

    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:\\feiTFM\\Deng.ttf",80)
    
    
    players = ["TBD","TBD","TBD","TBD"]
    points1 = [0,0,0,0]
    points2 = [0,0,0,0]
    ranks = [0,0,0,0]
    colors = [(244,121,131),(141,75,187),(68,206,246),(255,33,33)]
    
    draw.rectangle([(50,80), (590,2950)], fill="black")
    draw.rectangle([(52,82), (588,2948)], fill="white")
    draw.text((200, 100),"第一轮","BLACK",font)
    players,colors,points1,points2,ranks = getTable("A桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,200),"A桌",1)
    players,colors,points1,points2,ranks = getTable("B桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,450),"B桌",1)
    players,colors,points1,points2,ranks = getTable("C桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,700),"C桌",1)
    players,colors,points1,points2,ranks = getTable("D桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,950),"D桌",1)
    players,colors,points1,points2,ranks = getTable("E桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,1200),"E桌",1)
    players,colors,points1,points2,ranks = getTable("F桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,1450),"F桌",1)
    players,colors,points1,points2,ranks = getTable("G桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,1700),"G桌",1)
    players,colors,points1,points2,ranks = getTable("H桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,1950),"H桌",1)
    players,colors,points1,points2,ranks = getTable("I桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,2200),"I桌",1)
    players,colors,points1,points2,ranks = getTable("J桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,2450),"J桌",1)
    players,colors,points1,points2,ranks = getTable("K桌")
    drawGroup(image,players,colors,points1,points2,ranks,(100,2700),"K桌",1)
    
    draw.rectangle([(650,80), (1190,2200)], fill="black")
    draw.rectangle([(652,82), (1188,2198)], fill="white")
    draw.text((800, 100),"第二轮","BLACK",font)
    players,colors,points1,points2,ranks = getTable("1桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,200),"1桌",2)
    players,colors,points1,points2,ranks = getTable("2桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,450),"2桌",2)
    players,colors,points1,points2,ranks = getTable("3桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,700),"3桌",2)
    players,colors,points1,points2,ranks = getTable("4桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,950),"4桌",2)
    players,colors,points1,points2,ranks = getTable("5桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,1200),"5桌",2)
    players,colors,points1,points2,ranks = getTable("6桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,1450),"6桌",2)
    players,colors,points1,points2,ranks = getTable("7桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,1700),"7桌",2)
    players,colors,points1,points2,ranks = getTable("8桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,1950),"8桌",2)
    
    draw.rectangle([(650,2230), (1190,3100)], fill="black")
    draw.rectangle([(652,2232), (1188,3098)], fill="white")
    draw.text((800, 2250),"复活赛","BLACK",font)
    players,colors,points1,points2,ranks = getTable("复活1桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,2350),"复活1桌",4)
    players,colors,points1,points2,ranks = getTable("复活2桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,2600),"复活2桌",4)
    players,colors,points1,points2,ranks = getTable("复活3桌")
    drawGroup(image,players,colors,points1,points2,ranks,(700,2850),"复活3桌",4)
    
    draw.rectangle([(1250,80), (1790,1200)], fill="black")
    draw.rectangle([(1252,82), (1788,1198)], fill="white")
    draw.text((1400, 100),"第三轮","BLACK",font)
    players,colors,points1,points2,ranks = getTable("①桌")
    drawGroup(image,players,colors,points1,points2,ranks,(1300,200),"①桌",2)
    players,colors,points1,points2,ranks = getTable("②桌")
    drawGroup(image,players,colors,points1,points2,ranks,(1300,450),"②桌",2)
    players,colors,points1,points2,ranks = getTable("③桌")
    drawGroup(image,players,colors,points1,points2,ranks,(1300,700),"③桌",2)
    players,colors,points1,points2,ranks = getTable("④桌")
    drawGroup(image,players,colors,points1,points2,ranks,(1300,950),"④桌",2)
    
    
    draw.rectangle([(1250,1230), (1790,1850)], fill="black")
    draw.rectangle([(1252,1232), (1788,1848)], fill="white")
    draw.text((1400, 1250),"半决赛","BLACK",font)
    players,colors,points1,points2,ranks = getTable("正直桌")
    drawGroup(image,players,colors,points1,points2,ranks,(1300,1350),"正直桌",2)
    players,colors,points1,points2,ranks = getTable("祝福桌")
    drawGroup(image,players,colors,points1,points2,ranks,(1300,1600),"祝福桌",2)
    
    draw.rectangle([(1250,1880), (1790,2250)], fill="black")
    draw.rectangle([(1252,1882), (1788,2248)], fill="white")
    draw.text((1400, 1900),"总决赛","BLACK",font)
    players,colors,points1,points2,ranks = getTable("决赛桌")
    drawGroup(image,players,colors,points1,points2,ranks,(1300,2000),"决赛桌",3)
    
    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
    send.sendImg(user_id,is_group,group_id,file_path)

def getPlayerColor(playerName):
    if(playerName == 'TBD'):
        return (255,255,255)
    conn,cursor = ConnectDatabase()
    sql = "SELECT COLORR,COLORG,COLORB FROM tplayer WHERE PLAYERNAME = '"+playerName+"';"
    cursor.execute(sql)
    data = cursor.fetchall()
    DisconnectDatabase(conn,cursor)
    return (data[0][0],data[0][1],data[0][2])

def getTable(tableName):
    conn,cursor = ConnectDatabase()
    sql = "SELECT player,round1,round2,rank FROM tgroup WHERE groupname = '" + tableName + "' order by seat asc;"
    cursor.execute(sql)
    data = cursor.fetchall()
    DisconnectDatabase(conn,cursor)
    players = [data[0][0],data[1][0],data[2][0],data[3][0]]
    colors = [getPlayerColor(players[0]),getPlayerColor(players[1]),getPlayerColor(players[2]),getPlayerColor(players[3])]
    points1 = [data[0][1],data[1][1],data[2][1],data[3][1]]
    points2 = [data[0][2],data[1][2],data[2][2],data[3][2]]
    ranks = [data[0][3],data[1][3],data[2][3],data[3][3]]
    return players,colors,points1,points2,ranks

def NextStage():
    conn,cursor = ConnectDatabase()
    sql = "SELECT STAGE FROM TSTAGE;"
    cursor.execute(sql)
    data = cursor.fetchall()
    stage = data[0][0]
    if(stage == 4):
        DisconnectDatabase(conn,cursor)
        return stage
    stage = stage + 1
    sql = "UPDATE TSTAGE SET STAGE="+str(stage)+";"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return stage

def GetStage():
    conn,cursor = ConnectDatabase()
    sql = "SELECT STAGE FROM TSTAGE;"
    cursor.execute(sql)
    data = cursor.fetchall()
    stage = data[0][0]
    DisconnectDatabase(conn,cursor)
    return stage

def startAll():
    stage = GetStage()
    if(stage == 1):
        msg = "第一轮:"
        msg += "\nA桌:"
        msg += startMatch("A桌")
        msg += "\nB桌:"
        msg += startMatch("B桌")
        msg += "\nC桌:"
        msg += startMatch("C桌")
        msg += "\nD桌:"
        msg += startMatch("D桌")
        msg += "\nE桌:"
        msg += startMatch("E桌")
        msg += "\nF桌:"
        msg += startMatch("F桌")
        msg += "\nG桌:"
        msg += startMatch("G桌")
        msg += "\nH桌:"
        msg += startMatch("H桌")
        msg += "\nI桌:"
        msg += startMatch("I桌")
        msg += "\nJ桌:"
        msg += startMatch("J桌")
        msg += "\nK桌:"
        msg += startMatch("K桌")
    elif(stage == 2):
        msg = "复活轮:"
        msg += "\n复活1桌:"
        msg += startMatch("复活1桌")
        msg += "\n复活2桌:"
        msg += startMatch("复活2桌")
        msg += "\n复活3桌:"
        msg += startMatch("复活3桌")
    elif(stage == 3):
        msg = "第二轮:"
        msg += "\n1桌:"
        msg += startMatch("1桌")
        msg += "\n2桌:"
        msg += startMatch("2桌")
        msg += "\n3桌:"
        msg += startMatch("3桌")
        msg += "\n4桌:"
        msg += startMatch("4桌")
        msg += "\n5桌:"
        msg += startMatch("5桌")
        msg += "\n6桌:"
        msg += startMatch("6桌")
        msg += "\n7桌:"
        msg += startMatch("7桌")
        msg += "\n8桌:"
        msg += startMatch("8桌")
    elif(stage == 4):
        msg = "第三轮:"
        msg += "\n①桌:"
        msg += startMatch("①桌")
        msg += "\n②桌:"
        msg += startMatch("②桌")
        msg += "\n③桌:"
        msg += startMatch("③桌")
        msg += "\n④桌:"
        msg += startMatch("④桌")
    elif(stage == 5):
        msg = "半决赛:"
        msg += "\n正直桌:"
        msg += startMatch("正直桌")
        msg += "\n祝福桌:"
        msg += startMatch("祝福桌")
    elif(stage == 6):
        msg = "总决赛:"
        msg += "决赛桌:"
        msg += startMatch("决赛桌")
    return msg

def startMatch(tableName):
    conn,cursor = ConnectDatabase()
    sql = "SELECT player,round2 FROM tgroup WHERE groupname = '" + tableName + "';"
    cursor.execute(sql)
    data = cursor.fetchall()
    if((data[0][1] == data[1][1]) and (data[0][1] == data[2][1]) and (data[0][1] == data[3][1])):
        return MatchStart(data[0][0],data[1][0],data[2][0],data[3][0])
    else:
        return "该组的比赛已经完成了"
    
def MatchStart(player1,player2,player3,player4):
    playerNames = [player1,player2,player3,player4]
    conn,cursor = ConnectDatabase()
    sql = "SELECT UNIQUEID,SEASON FROM MATCHMESSAGE;"
    cursor.execute(sql)
    data = cursor.fetchall()
    uniqueid = data[0][0]
    season = data[0][1]
    
    url = 'https://contest-gate-202411.maj-soul.com/api/contest/ready_player_list?unique_id='+str(uniqueid)+'&season_id='+str(season)
    token = GetToken()
    headers = getHeaders()
    headers["Authorization"] = 'Majsoul '+token
    response = requests.get(url,headers=headers)
    if(response.status_code != 200):
        token = GetNewToken()
        headers["Authorization"] = 'Majsoul '+token
        response = requests.get(url,headers=headers)
    if(response.status_code != 200):
        DisconnectDatabase(conn,cursor)
        return "笨比机器人大概是开不了比赛了喵"
    players = json.loads(response.text)['data']
    players_ready = [False,False,False,False]
    players_id = [0,0,0,0]
    for player in players:
        for i in range(4):
            if(player['nickname'] == playerNames[i]):
                players_ready[i] = True
                players_id[i] = player['account_id']
    if(players_ready[0] and players_ready[1] and players_ready[2] and players_ready[3]):
        pass
    else:
        msg = "未准备选手："
        for i in range(4):
            if(not players_ready[i]):
                msg += playerNames[i]+","
        DisconnectDatabase(conn,cursor)
        return msg
    
    for i in range(3):
        exchange = random.randint(i,3)
        temp = players_id[i]
        players_id[i] = players_id[exchange]
        players_id[exchange] = temp
        temp = playerNames[i]
        playerNames[i] = playerNames[exchange]
        playerNames[exchange] = temp

    url = 'https://contest-gate-202411.maj-soul.com/api/contest/create_game_plan'
    data = {
        "account_list":  players_id,
        "ai_level": 0,
        "game_start_time":round(time.time()),
        "init_points": [25000, 25000, 25000, 25000],
        "remark": "",
        "season_id": season,
        "shuffle_seats": False,
        "unique_id":uniqueid
    }
    data=json.dumps(data)
    response = requests.post(
        url, data=data, headers=headers
    )
    if(response.status_code!=200):
        token = GetNewToken()
        headers["Authorization"] = 'Majsoul '+token
        response = requests.post(
            url, data=data, headers=headers
        )
    if(response.status_code!=200):
        return "笨比机器人大概是开不了比赛了喵"
    DisconnectDatabase(conn,cursor)
    return "比赛开启成功 东 "+playerNames[0]+",南 "+playerNames[1]+",西 "+playerNames[2]+",北 "+playerNames[3]

def GetToken():
    conn,cursor = ConnectDatabase()
    sql = "SELECT TOKEN FROM TOKEN"
    cursor.execute(sql)
    data = cursor.fetchall()
    token = data[0][0]
    DisconnectDatabase(conn,cursor)
    return token

def GetNewToken():
    data = {
        "account": "",  # 已脱敏：登录账号
        "password": "",  # 已脱敏：登录密码哈希
        "type":0
    }
    data=json.dumps(data)
    url = 'https://contest-gate-202411.maj-soul.com/api/login'
    headers = getHeaders()
    response = requests.post(
        url, data=data, headers=headers
    )
    print(response.text)
    token = json.loads(response.text)['data']['token']
    conn,cursor = ConnectDatabase()
    sql = "UPDATE TOKEN SET TOKEN = '"+str(token)+"' "
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return token

def getHeaders():
    cookie = ''  # 已脱敏：旧会话 Cookie
    headers = {
        'Accept': 'application/json, text/plain, */*',
        #'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Authorization': '',  # 已脱敏：旧会话 Token
        # 'Connection': 'keep-alive',
        # 'Content-Length': '62',  # 这个通常不需要手动设置，requests会自动处理
        'Content-Type': 'application/json',
        'Cookie': cookie,
        'Host': 'contest-gate-202411.maj-soul.com',
        'Origin': 'https://www.maj-soul.com',
        'Referer': 'https://www.maj-soul.com/',
        'Sec-CH-UA': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'Sec-CH-UA-Mobile': '?0',
        'Sec-CH-UA-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'X-Web-Client-Version': 'v1.0.0-101-gd8c3e24'
    }
    return headers

def IsManager(userId):
    conn,cursor = ConnectDatabase()
    sql = "SELECT COUNT(*) FROM MANAGER WHERE USERID = "+str(userId)+";"
    cursor.execute(sql)
    data = cursor.fetchall()
    data = data[0][0]
    DisconnectDatabase(conn,cursor)
    if(data == 0):
        return False
    return True

def ConnectDatabase():
    conn = psycopg2.connect(database=DATABASE_NAME, user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST, port=DATABASE_PORT)
    cursor = conn.cursor()
    return conn,cursor

def DisconnectDatabase(conn,cursor):
    conn.commit()
    cursor.close()
    conn.close()