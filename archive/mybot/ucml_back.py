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
DATABASE_NAME = "ucml"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = ""  # 已脱敏：本地数据库密码
DATABASE_HOST = "127.0.0.1"
DATABASE_PORT = "5432"

def ucml(userId,isGroup,groupId,message,userName):
    if(len(message) == 1):
        return "缺少指令参数"
    message = message[1].split(" ",1)
    temp = "0"
    if(len(message)>=2):
        message[1] = message[1].strip()
        temp = message[1]
    message[0] = message[0].lower()
    if((message[0] == "查看管理")or(message[0] == "showadministrator")or(message[0] == "sa")):
        return ShowManager("",userId)
    elif((message[0] == "新赛季")or(message[0] == "startnewseason")or(message[0] == "sns")):
        return StartNewSeason("",userId,isGroup,groupId)
    elif((message[0] == "下一阶段")or(message[0] == "nextstage")or(message[0] == "ns")):
        return NextStage("",userId,isGroup,groupId)
    elif((message[0] == "队伍成员")or(message[0] == "teamplayer")or(message[0] == "tp")):
        return GetTeamAndPlayer("",userId,isGroup,groupId)
    elif((message[0] == "队伍信息")or(message[0] == "teammessage")or(message[0] == "tm")):
        return GetTeamMessage(temp,userId,isGroup,groupId)
    elif((message[0] == "个人信息")or(message[0] == "playermessage")or(message[0] == "pm")):
        return GetPlayerMessage(temp,userId,isGroup,groupId)
    
    elif((message[0] == "比赛结果")or(message[0] == "matchresult")or(message[0] == "mr")):
        return GetMatchResult(temp,userId,isGroup,groupId)
    elif((message[0] == "记录结果")or(message[0] == "recordmatchresult")or(message[0] == "rmr")):
        return RecordMatchResult("",userId,isGroup,groupId)
    elif(message[0] == "手动结果"):
        return MatchResult(temp,userId,isGroup,groupId)
    
    elif((message[0] == "赛程")or(message[0] == "schedule")or(message[0] == "sch")):
        send.sendImg(userId,isGroup,groupId,"C:\\mybot\\ucml\\赛程.png")
        return 
    
    elif(len(message) == 1):
        return "需要参数或者指令有误"
    elif((message[0] == "比赛场信息")or(message[0] == "matchinformation")or(message[0] == "mi")):
        return SetMatchMessage(message[1],userId)
    elif((message[0] == "添加管理")or(message[0] == "addadministrator")or(message[0] == "aa")):
        return AddManager(message[1],userId)
    elif((message[0] == "移除管理")or(message[0] == "removeadministrator")or(message[0] == "ra")):
        return RemoveManager(message[1],userId)
    elif((message[0] == "添加队伍")or(message[0] == "addteam")or(message[0] == "at")):
        return AddTeam(message[1],userId)
    elif((message[0] == "移除队伍")or(message[0] == "removeteam")or(message[0] == "rt")):
        return DeleteTeam(message[1],userId)
    elif((message[0] == "添加队员")or(message[0] == "addplayer")or(message[0] == "ap")):
        return AddPlayer(message[1],userId)
    elif((message[0] == "移除队员")or(message[0] == "removeplayer")or(message[0] == "rp")):
        return DeletePlayer(message[1],userId)
    elif((message[0] == "开始比赛")or(message[0] == "matchstart")or(message[0] == "ms")):
        return MatchStart(message[1],userId)
    
    return "不存在这个指令"

def SetMatchMessage(message,userId):
    if(not IsSuperManager(userId)):
        return "没有添加管理员的权限"
    message=message.split()
    if(len(message)<=1):
        return "需要分别输入uniqueid和season"
    if((not message[0].isdecimal())or(not message[1].isdecimal())):
        return "uniqueid或者season不正确"
    conn,cursor = ConnectDatabase()
    sql = "UPDATE MATCHMESSAGE SET uniqueid="+str(message[0])+";"
    cursor.execute(sql)
    sql = "UPDATE MATCHMESSAGE SET season="+str(message[1])+";"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return "比赛信息设置完成,uniqueid为"+str(message[0])+",season为"+str(message[1])

# 添加管理员
def AddManager(message,userId):
    if(not IsSuperManager(userId)):
        return "没有添加管理员的权限"
    conn,cursor = ConnectDatabase()
    if((not message.isdecimal())or(len(message)>12)):
        DisconnectDatabase(conn,cursor)
        return "不是正确的QQ号格式"
    sql = "SELECT COUNT(*) FROM MANAGER WHERE USERID = "+str(message)+";"
    cursor.execute(sql)
    data = cursor.fetchall()
    data = data[0][0]
    if(data != 0):
        DisconnectDatabase(conn,cursor)
        return str(message)+"已经是管理员力"
    sql = "INSERT INTO MANAGER(USERID) VALUES ("+str(message)+");"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return "将"+str(message)+"添加为管理员"

# 删除管理员
def RemoveManager(message,userId):
    if(not IsSuperManager(userId)):
        return "没有删除管理员的权限"
    conn,cursor = ConnectDatabase()
    if((not message.isdecimal())or(len(message)>12)):
        sql = "DELETE FROM MANAGER WHERE USERID = "+str(message)+";"
        cursor.execute(sql)
        DisconnectDatabase(conn,cursor)
        return "虽然不是正确的QQ号格式所以应该不会出现才对，但万一真有我也努力删了"
    sql = "DELETE FROM MANAGER WHERE USERID = "+str(message)+";"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return  "删除管理员"+str(message)

# 查看管理员名单
def ShowManager(message,userId):
    conn,cursor = ConnectDatabase()
    sql = "SELECT USERID FROM MANAGER;"
    cursor.execute(sql)
    data = cursor.fetchall()
    DisconnectDatabase(conn,cursor)
    res = "当前所有管理员:"
    for i in range(len(data)-1):
        res += (str(data[i][0])+",")
    res += str(data[len(data)-1][0])
    return  res

# 添加队伍
def AddTeam(message,userId):
    if(not IsManager(userId)):
        return "没有添加队伍的权限"
    
    stage = GetStageDatabase()
    if(stage != 0):
        return "比赛已经开始，不能额外添加队伍"
    
    message = message.split()
    if(len(message)!=2):
        return "添加队伍需要一个代表队伍名字的参数和一个代表队伍颜色的参数，很抱歉但是队伍名字不能包含空格。"
    teamName = message[0]
    teamColor = re.split("[,，]",message[1])
    if(len(teamColor) != 3):
        return "队伍颜色应当用逗号隔开三个值分别代表RGB。"
    for i in range(3):
        if(not teamColor[i].isdecimal()):
            return "队伍颜色应当用逗号隔开三个整数值分别代表RGB。"
        if(int(teamColor[i])>255 or int(teamColor[i])<0):
            return "队伍颜色应当用逗号隔开三个0-255之间的整数值分别代表RGB。"
        teamColor[i] = int(teamColor[i])
        
    conn,cursor = ConnectDatabase()
    sql = "SELECT COUNT(*) FROM TEAM WHERE TEAMNAME = '"+str(teamName)+"';"
    cursor.execute(sql)
    data = cursor.fetchall()
    data = data[0][0]
    if(data != 0):
        DisconnectDatabase(conn,cursor)
        return "已经有同名的队伍了"
    sql = "INSERT INTO TEAM(TEAMNAME,COLORR,COLORG,COLORB) VALUES('"+str(teamName)+"',"+str(teamColor[0])+","+str(teamColor[1])+","+str(teamColor[2])+");"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return "添加队伍"+teamName

# 删除队伍
def DeleteTeam(message,userId):
    if(not IsManager(userId)):
        return "没有删除队伍的权限"
    stage = GetStageDatabase()
    if(stage != 0):
        return "比赛已经开始，不能删除队伍"
    conn,cursor = ConnectDatabase()
    sql = "SELECT COUNT(*) FROM TEAM WHERE TEAMNAME = '" + str(message) + "';"
    cursor.execute(sql)
    data = cursor.fetchall()
    data = data[0][0]
    if(data == 0):
        DisconnectDatabase(conn,cursor)
        return "队伍不存在"
    teamName = message
    sql = "DELETE FROM TEAM WHERE TEAMNAME = '"+str(teamName)+"';"
    cursor.execute(sql)
    sql = "DELETE FROM PLAYER WHERE TEAMNAME = '"+str(teamName)+"';"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return "删除队伍" + str(message)

# 添加队员
def AddPlayer(message,userId):
    if(not IsManager(userId)):
        return "没有添加队员的权限"
    stage = GetStageDatabase()
    message = message.split()
    if(len(message)!=2):
        return "添加队员需要一个代表队员名称的参数和一个代表队伍名称的参数，很抱歉但是名称不能包含空格。"
    playerName = message[0]
    playerTeam = message[1]
    conn,cursor = ConnectDatabase()
    sql = "SELECT COLORR,COLORG,COLORB FROM TEAM WHERE TEAMNAME = '" + str(playerTeam) +  "';"
    cursor.execute(sql)
    data = cursor.fetchall()
    if(len(data) == 0):
        DisconnectDatabase(conn,cursor)
        return "队伍不存在"
    colorR = data[0][0]
    colorG = data[0][1]
    colorB = data[0][2]
    sql = "SELECT COUNT(*) FROM PLAYER WHERE PLAYERNAME = '"+str(playerName) + "';"
    cursor.execute(sql)
    data = cursor.fetchall()
    data = data[0][0]
    if(data != 0):
        DisconnectDatabase(conn,cursor)
        return "队员已存在"
    sql = "INSERT INTO PLAYER(PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB) VALUES('"+str(playerName)+"','"+str(playerTeam)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+");"
    cursor.execute(sql)
    if(stage >= 1):
        sql = "INSERT INTO PLAYERTOTAL(PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB,PLAYERMATCH,PLAYERFIRST,PLAYERSECOND,PLAYERTHIRD,PLAYERFORTH,PLAYERSCORE) VALUES('"+str(playerName)+"','"+str(playerTeam)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,0);"
        cursor.execute(sql)
        sql = "INSERT INTO PLAYERREGULAR(PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB,PLAYERMATCH,PLAYERFIRST,PLAYERSECOND,PLAYERTHIRD,PLAYERFORTH,PLAYERSCORE) VALUES('"+str(playerName)+"','"+str(playerTeam)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,0);"
        cursor.execute(sql)
    if(stage >= 2):
        sql = "INSERT INTO PLAYERSEMIFINAL(PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB,PLAYERMATCH,PLAYERFIRST,PLAYERSECOND,PLAYERTHIRD,PLAYERFORTH,PLAYERSCORE) VALUES('"+str(playerName)+"','"+str(playerTeam)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,0);"
        cursor.execute(sql)
    if(stage >= 3):
        sql = "INSERT INTO PLAYERFINAL(PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB,PLAYERMATCH,PLAYERFIRST,PLAYERSECOND,PLAYERTHIRD,PLAYERFORTH,PLAYERSCORE) VALUES('"+str(playerName)+"','"+str(playerTeam)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,0);"
        cursor.execute(sql)
    
    DisconnectDatabase(conn,cursor)
    return "队员"+str(playerName)+"加入队伍"+str(playerTeam)

# 删除队员
def DeletePlayer(message,userId):
    if(not IsManager(userId)):
        return "没有删除队员的权限"
    stage = GetStageDatabase()
    if(stage != 0):
        return "比赛已经开始，不能删除队员"
    conn,cursor = ConnectDatabase()
    sql = "DELETE FROM PLAYER WHERE PLAYERNAME = '"+str(message)+"';"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return "删除队员"+str(message)

# 开始赛季
def StartNewSeason(message,userId,isGroup,groupId):
    if(not IsSuperManager(userId)):
        return "没有开始新赛季的权限"
    stage = GetStageDatabase()
    if(stage != 4):
        return "赛季未结束，无法开始下一赛季"
    conn,cursor = ConnectDatabase()
    sql = "UPDATE STAGE SET STAGE=0;"
    cursor.execute(sql)
    
    sql = "UPDATE MATCHMESSAGE SET STAGE=0;"
    cursor.execute(sql)
    sql = "UPDATE LASTRECORD SET LASTRECORD=0;"
    cursor.execute(sql)
    sql = "DELETE FROM TEAM;"
    cursor.execute(sql)
    sql = "DELETE FROM PLAYER;"
    cursor.execute(sql)
    sql = "DELETE FROM TEAMREGULAR;"
    cursor.execute(sql)
    sql = "DELETE FROM TEAMSEMIFINAL;"
    cursor.execute(sql)
    sql = "DELETE FROM TEAMFINAL;"
    cursor.execute(sql)
    sql = "DELETE FROM PLAYERTOTAL;"
    cursor.execute(sql)
    sql = "DELETE FROM PLAYERREGULAR;"
    cursor.execute(sql)
    sql = "DELETE FROM PLAYERSEMIFINAL;"
    cursor.execute(sql)
    sql = "DELETE FROM PLAYERFINAL;"
    cursor.execute(sql)
    sql = "DELETE FROM MATCHRESULT;"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return "赛季准备阶段"

# 下一阶段
def NextStage(message,userId,isGroup,groupId):
    if(not IsSuperManager(userId)):
        return "没有进入下一阶段的权限"
    stage = GetStageDatabase()
    if(stage == 0):
        conn,cursor = ConnectDatabase()
        sql = "SELECT COUNT(*) FROM TEAM;"
        cursor.execute(sql)
        data = cursor.fetchall()
        data = data[0][0]
        if(data<6):
            DisconnectDatabase(conn,cursor)
            return "队伍过少（唉设定至少6个队伍，感觉再少就太怪了）"
        sql = "SELECT TEAMNAME FROM TEAM;"
        cursor.execute(sql)
        data = cursor.fetchall()
        for i in data:
            teamName = i[0]
            sql = "SELECT COUNT(*) FROM PLAYER WHERE TEAMNAME = '"+str(teamName)+"';"
            cursor.execute(sql)
            teamPlayerNum = cursor.fetchall()
            teamPlayerNum = teamPlayerNum[0][0]
            if(teamPlayerNum==0):
                DisconnectDatabase(conn,cursor)
                return "存在没有队员的队伍"
            
        timestamp=float(time.time())
        sql = "UPDATE STAGETIME SET REGULAR ='"+str(timestamp)+"';"
        cursor.execute(sql)
        
        sql = "SELECT TEAMNAME,COLORR,COLORG,COLORB FROM TEAM;"
        cursor.execute(sql)
        data = cursor.fetchall()
        for i in data:
            teamName = i[0]
            colorR = i[1]
            colorG = i[2]
            colorB = i[3]
            sql = "INSERT INTO TEAMREGULAR(TEAMNAME,COLORR,COLORG,COLORB,TEAMMATCH,TEAMFIRST,TEAMSECOND,TEAMTHIRD,TEAMFORTH,LASTSTAGE,TEAMSCORE) VALUES('"+str(teamName)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,0,0)"
            cursor.execute(sql)
        sql = "SELECT PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB FROM PLAYER"
        cursor.execute(sql)
        data = cursor.fetchall()
        for i in data:
            playerName = i[0]
            playerTeam = i[1]
            colorR = i[2]
            colorG = i[3]
            colorB = i[4]
            sql = "INSERT INTO PLAYERTOTAL(PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB,PLAYERMATCH,PLAYERFIRST,PLAYERSECOND,PLAYERTHIRD,PLAYERFORTH,PLAYERSCORE) VALUES('"+str(playerName)+"','"+str(playerTeam)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,0);"
            cursor.execute(sql)
            sql = "INSERT INTO PLAYERREGULAR(PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB,PLAYERMATCH,PLAYERFIRST,PLAYERSECOND,PLAYERTHIRD,PLAYERFORTH,PLAYERSCORE) VALUES('"+str(playerName)+"','"+str(playerTeam)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,0);"
            cursor.execute(sql)
        DisconnectDatabase(conn,cursor)
        NextStageDatabase()
        GetTeamAndPlayer(message,userId,isGroup,groupId)
        return "常规赛阶段开始"
    elif(stage == 1):
        conn,cursor = ConnectDatabase()
        timestamp=float(time.time())
        sql = "UPDATE STAGETIME SET SEMIFINAL ='"+str(timestamp)+"';"
        cursor.execute(sql)
        sql = "SELECT TEAMNAME,COLORR,COLORG,COLORB,TEAMSCORE FROM TEAMREGULAR ORDER BY TEAMSCORE DESC;"
        cursor.execute(sql)
        data = cursor.fetchall()
        teamSemiFinal = []
        for i in range(6):
            teamName = data[i][0]
            colorR = data[i][1]
            colorG = data[i][2]
            colorB = data[i][3]
            teamScore = data[i][4]
            teamSemiFinal.append(teamName)
            teamScore = round(teamScore / 2.0 +0.01,1)
            print(teamName)
            print(teamScore)
            sql = "INSERT INTO TEAMSEMIFINAL(TEAMNAME,COLORR,COLORG,COLORB,TEAMMATCH,TEAMFIRST,TEAMSECOND,TEAMTHIRD,TEAMFORTH,LASTSTAGE,TEAMSCORE) VALUES('"+str(teamName)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,"+str(teamScore)+","+str(teamScore)+")"
            cursor.execute(sql)
        for teamName in teamSemiFinal:
            sql = "SELECT PLAYERNAME,COLORR,COLORG,COLORB FROM PLAYERREGULAR WHERE TEAMNAME = '"+str(teamName)+"';"
            cursor.execute(sql)
            players = cursor.fetchall()
            for player in players:
                playerName = player[0]
                colorR = player[1]
                colorG = player[2]
                colorB = player[3]
                sql = "INSERT INTO PLAYERSEMIFINAL(PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB,PLAYERMATCH,PLAYERFIRST,PLAYERSECOND,PLAYERTHIRD,PLAYERFORTH,PLAYERSCORE) VALUES('"+str(playerName)+"','"+str(teamName)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,0);"
                cursor.execute(sql)
        DisconnectDatabase(conn,cursor)
        NextStageDatabase()
        GetTeamMessage("1",userId,isGroup,groupId)
        GetPlayerMessage("1",userId,isGroup,groupId)
        return "进入半决赛阶段"
    elif(stage == 2):
        conn,cursor = ConnectDatabase()
        timestamp=float(time.time())
        sql = "UPDATE STAGETIME SET FINAL ='"+str(timestamp)+"';"
        cursor.execute(sql)
        sql = "SELECT TEAMNAME,COLORR,COLORG,COLORB,TEAMSCORE FROM TEAMSEMIFINAL ORDER BY TEAMSCORE DESC;"
        cursor.execute(sql)
        data = cursor.fetchall()
        teamSemiFinal = []
        for i in range(4):
            teamName = data[i][0]
            colorR = data[i][1]
            colorG = data[i][2]
            colorB = data[i][3]
            teamScore = data[i][4]
            teamSemiFinal.append(teamName)
            teamScore = round(teamScore / 2.0 +0.01,1)
            sql = "INSERT INTO TEAMFINAL(TEAMNAME,COLORR,COLORG,COLORB,TEAMMATCH,TEAMFIRST,TEAMSECOND,TEAMTHIRD,TEAMFORTH,LASTSTAGE,TEAMSCORE) VALUES('"+str(teamName)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,"+str(teamScore)+","+str(teamScore)+")"
            cursor.execute(sql)
        for teamName in teamSemiFinal:
            sql = "SELECT PLAYERNAME,COLORR,COLORG,COLORB FROM PLAYERSEMIFINAL WHERE TEAMNAME = '"+str(teamName)+"';"
            cursor.execute(sql)
            players = cursor.fetchall()
            for player in players:
                playerName = player[0]
                colorR = player[1]
                colorG = player[2]
                colorB = player[3]
                sql = "INSERT INTO PLAYERFINAL(PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB,PLAYERMATCH,PLAYERFIRST,PLAYERSECOND,PLAYERTHIRD,PLAYERFORTH,PLAYERSCORE) VALUES('"+str(playerName)+"','"+str(teamName)+"',"+str(colorR)+","+str(colorG)+","+str(colorB)+",0,0,0,0,0,0);"
                cursor.execute(sql)
        DisconnectDatabase(conn,cursor)
        NextStageDatabase()
        GetTeamMessage("2",userId,isGroup,groupId)
        GetPlayerMessage("2",userId,isGroup,groupId)
        return "进入决赛阶段"
    elif(stage == 3):
        NextStageDatabase()
        return EndSeason(userId,isGroup,groupId)
    elif(stage == 4):
        return "赛季已经结束，请开始下一赛季"
    return

# 记录比赛信息
def MatchResult(message,userId,isGroup,GroupId):
    if(not IsManager(userId)):
        return "没有记录分数的权限"
    stage = GetStageDatabase()
    stageName = ""
    if(stage == 0):
        return "赛季未正式开始"
    elif(stage == 1):
        stageName = "REGULAR"
    elif(stage == 2):
        stageName = "SEMIFINAL"
    elif(stage == 3):
        stageName = "FINAL"
    elif(stage == 4):
        return "赛季已经结束"
    else:
        return "有笨比 @si1verwind"
    message = message.split()
    if(len(message) != 8):
        return "比赛结果格式不正确"
    playerNames = [message[0],message[2],message[4],message[6]]
    playerScores = [message[1],message[3],message[5],message[7]]
    for i in range(4):
        temp = playerScores[i]
        if temp[0] == '-':
            temp = temp[1:]
        if(not temp.isdecimal()):
            return "分数格式不正确"
        playerScores[i] = int(playerScores[i])
    count = 0
    for score in playerScores:
        count += score
    if(count != 100000):
        return "总点数和不为100000"
    conn,cursor = ConnectDatabase()
    for name in playerNames:
        sql = "SELECT COUNT(*) FROM PLAYER" + stageName +" WHERE PLAYERNAME = '" + str(name) +"';"
        cursor.execute(sql)
        data = cursor.fetchall()
        data = data[0][0]
        if(data == 0):
            return name+"不在当前的参赛选手中"
    for i in range(4):
        for j in range(3,i,-1):
            if(playerScores[j]>playerScores[j-1]):
                temp = playerScores[j-1]
                playerScores[j-1] = playerScores[j]
                playerScores[j] = temp
                temp = playerNames[j-1]
                playerNames[j-1] = playerNames[j]
                playerNames[j] = temp
    scores = [45,5,-15,-35]
    ranks = ["FIRST","SECOND","THIRD","FORTH"]
    if(playerScores[0] == playerScores[3]):
        scores = [0,0,0,0]
        ranks = ["FIRST","FIRST","FIRST","FIRST"]
    elif(playerScores[0] == playerScores[2]):
        scores = [11.7,11.7,11.7,-35]
        ranks = ["FIRST","FIRST","FIRST","FORTH"]
    elif(playerScores[1] == playerScores[3]):
        scores = [45,-15,-15,-15]
        ranks = ["FIRST","SECOND","SECOND","SECOND"]
    elif(playerScores[1] == playerScores[2]):
        scores = [45,-5,-5,-35]
        ranks = ["FIRST","SECOND","SECOND","FORTH"]
    elif((playerScores[0] == playerScores[1]) and (playerScores[2] == playerScores[3])):
        scores = [25,25,-25,-25]
        ranks = ["FIRST","FIRST","THIRD","THIRD"]
    elif(playerScores[0] == playerScores[1]):
        scores = [25,25,-15,-35]
        ranks = ["FIRST","FIRST","THIRD","FORTH"]
    elif(playerScores[2] == playerScores[3]):
        scores = [45,5,-25,-25]
        ranks = ["FIRST","SECOND","THIRD","THIRD"]
    playerScores[0] = round((playerScores[0]-25000) / 1000.0 + scores[0],1)
    playerScores[1] = round((playerScores[1]-25000) / 1000.0 + scores[1],1)
    playerScores[2] = round((playerScores[2]-25000) / 1000.0 + scores[2],1)
    playerScores[3] = round((playerScores[3]-25000) / 1000.0 + scores[3],1)
    
    playerTeams = ["","","",""]
    colorR = [0,0,0,0]
    colorG = [0,0,0,0]
    colorB = [0,0,0,0]
    for i in range(4):
        sql = "SELECT TEAMNAME FROM PLAYERTOTAL WHERE PLAYERNAME = '" +playerNames[i]+ "';" 
        cursor.execute(sql)
        data = cursor.fetchall()
        playerTeams[i] = data[0][0]
    
    if((playerTeams[0]==playerTeams[1])or(playerTeams[0]==playerTeams[2])or(playerTeams[0]==playerTeams[3])or(playerTeams[1]==playerTeams[2])or(playerTeams[1]==playerTeams[3])or(playerTeams[2]==playerTeams[3])):
        return "有队员来自重复的队伍"
    for i in range(4):
        
        sql = "SELECT TEAMNAME,PLAYERMATCH,PLAYER" + ranks[i] + ",PLAYERSCORE FROM PLAYERTOTAL WHERE PLAYERNAME = '" +playerNames[i]+ "';" 
        cursor.execute(sql)
        data = cursor.fetchall()
        playerTeams[i] = data[0][0]
        playerMatch = data[0][1] + 1
        playerRank = data[0][2] + 1
        playerScore = round(data[0][3] + playerScores[i],1)
        sql = "UPDATE PLAYERTOTAL SET PLAYERMATCH = "+str(playerMatch)+",PLAYER" + ranks[i] + "="+str(playerRank)+",PLAYERSCORE ="+str(playerScore)+" WHERE PLAYERNAME = '" +playerNames[i]+ "';"
        cursor.execute(sql)
        
        sql = "SELECT TEAMNAME,PLAYERMATCH,PLAYER" + ranks[i] + ",PLAYERSCORE FROM PLAYER"+stageName+" WHERE PLAYERNAME = '" +playerNames[i]+ "';" 
        cursor.execute(sql)
        data = cursor.fetchall()
        playerMatch = data[0][1] + 1
        playerRank = data[0][2] + 1
        playerScore = round(data[0][3] + playerScores[i],1)
        sql = "UPDATE PLAYER"+stageName+" SET PLAYERMATCH = "+str(playerMatch)+",PLAYER" + ranks[i] + "="+str(playerRank)+",PLAYERSCORE ="+str(playerScore)+" WHERE PLAYERNAME = '" +playerNames[i]+ "';"
        cursor.execute(sql)
        
        sql = "SELECT COLORR,COLORG,COLORB,TEAMMATCH,TEAM" + ranks[i] + ",TEAMSCORE FROM TEAM"+stageName+" WHERE TEAMNAME = '" +playerTeams[i]+ "';"
        cursor.execute(sql)
        data = cursor.fetchall()
        colorR[i] = data[0][0]
        colorG[i] = data[0][1]
        colorB[i] = data[0][2]
        teamMatch = data[0][3] + 1
        teamRank = data[0][4] + 1
        teamScore = round(data[0][5] + playerScores[i],1)
        sql = "UPDATE TEAM"+stageName+" SET TEAMMATCH = "+str(teamMatch)+",TEAM" + ranks[i] + "="+str(teamRank)+",TEAMSCORE ="+str(teamScore)+" WHERE TEAMNAME = '" +playerTeams[i]+ "';"
        cursor.execute(sql)
    
    sql = "SELECT MAX(ID) FROM MATCHRESULT;"
    cursor.execute(sql)
    maxId = cursor.fetchall()
    if( maxId[0][0] == None):
        maxId = 1
    else:
        maxId = maxId[0][0] + 1
    sql = "INSERT INTO MATCHRESULT(ID,TYPE,PLAYERNAMEFIRST,SCOREFIRST,TEAMNAMEFIRST,COLORRFIRST,COLORGFIRST,COLORBFIRST,PLAYERNAMESECOND,SCORESECOND,TEAMNAMESECOND,COLORRSECOND,COLORGSECOND,COLORBSECOND,PLAYERNAMETHIRD,SCORETHIRD,TEAMNAMETHIRD,COLORRTHIRD,COLORGTHIRD,COLORBTHIRD,PLAYERNAMEFORTH,SCOREFORTH,TEAMNAMEFORTH,COLORRFORTH,COLORGFORTH,COLORBFORTH) VALUES("
    sql = sql + str(maxId)+",'" +str(stage)+"',"
    sql = sql +"'"+ playerNames[0] + "',"+str(playerScores[0])+",'"+playerTeams[0]+"',"+str(colorR[0])+","+str(colorG[0])+","+str(colorB[0])+","
    sql = sql +"'"+ playerNames[1] + "',"+str(playerScores[1])+",'"+playerTeams[1]+"',"+str(colorR[1])+","+str(colorG[1])+","+str(colorB[1])+","
    sql = sql +"'"+ playerNames[2] + "',"+str(playerScores[2])+",'"+playerTeams[2]+"',"+str(colorR[2])+","+str(colorG[2])+","+str(colorB[2])+","
    sql = sql +"'"+ playerNames[3] + "',"+str(playerScores[3])+",'"+playerTeams[3]+"',"+str(colorR[3])+","+str(colorG[3])+","+str(colorB[3])+");"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    msg = "一位:" +playerTeams[0]+"  "+ playerNames[0] +"  "+str(playerScores[0])+ "pt\n二位:" +playerTeams[1]+"  "+ playerNames[1] +"  "+str(playerScores[1])+ "pt\n三位:" +playerTeams[2]+"  "+ playerNames[2] +"  "+str(playerScores[2])+ "pt\n四位:" +playerTeams[3]+"  "+ playerNames[3] +"  "+str(playerScores[3])+ "pt"
    send.sendText(userId,isGroup,GroupId,msg)
    return "分数记录成功"

# 开始比赛
def MatchStart(message,userId):
    if(not IsManager(userId)):
        return "没有开始比赛的权限"
    stage = GetStageDatabase()
    stageName = ""
    if(stage == 0):
        return "赛季未正式开始"
    elif(stage == 1):
        stageName = "REGULAR"
    elif(stage == 2):
        stageName = "SEMIFINAL"
    elif(stage == 3):
        stageName = "FINAL"
    elif(stage == 4):
        return "赛季已经结束"
    else:
        return "有笨比 @si1verwind"
    message = message.split()
    if(len(message) != 4):
        return "请依依次输入四位选手"
    playerNickNames = [message[0],message[1],message[2],message[3]]
    conn,cursor = ConnectDatabase()
    sql = "SELECT UNIQUEID,SEASON FROM MATCHMESSAGE;"
    cursor.execute(sql)
    data = cursor.fetchall()
    uniqueid = data[0][0]
    season = data[0][1]
    
    playerNames = GetMajsoulNames(playerNickNames)
    
    # for i in range(4):
    #     sql = "SELECT COUNT(*) FROM PLAYER" + stageName +" WHERE PLAYERNAME = '" + str(playerNames[i]) +"';"
    #     cursor.execute(sql)
    #     data = cursor.fetchall()
    #     data = data[0][0]
    #     if(data == 0):
    #         DisconnectDatabase(conn,cursor)
    #         return playerNickNames[i]+"("+playerNames[i]+")不在当前的参赛选手中"
    # playerTeams = ["","","",""]
    # for i in range(4):
    #     sql = "SELECT TEAMNAME FROM PLAYERTOTAL WHERE PLAYERNAME = '" +playerNames[i]+ "';" 
    #     cursor.execute(sql)
    #     data = cursor.fetchall()
    #     playerTeams[i] = data[0][0]
    # if((playerTeams[0]==playerTeams[1])or(playerTeams[0]==playerTeams[2])or(playerTeams[0]==playerTeams[3])or(playerTeams[1]==playerTeams[2])or(playerTeams[1]==playerTeams[3])or(playerTeams[2]==playerTeams[3])):
    #     DisconnectDatabase(conn,cursor)
    #     return "有队员来自重复的队伍"
    
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
                msg += playerNickNames[i]+"("+playerNames[i]+")  "
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
        temp = playerNickNames[i]
        playerNickNames[i] = playerNickNames[exchange]
        playerNickNames[exchange] = temp

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
    return "比赛开启成功 东 "+playerNickNames[0]+"("+playerNames[0]+") 南 "+playerNickNames[1]+"("+playerNames[1]+") 西 "+playerNickNames[2]+"("+playerNames[2]+") 北 "+playerNickNames[3]+"("+playerNames[3]+")"

# 记录比赛信息
def RecordMatchResult(message,userId,isGroup,GroupId):
    if(not IsManager(userId)):
        return "没有权限"
    conn,cursor = ConnectDatabase()
    sql = "SELECT UNIQUEID,SEASON FROM MATCHMESSAGE;"
    cursor.execute(sql)
    data = cursor.fetchall()
    uniqueid = data[0][0]
    season = data[0][1]
    url = "https://contest-gate-202411.maj-soul.com/api/contest/fetch_contest_game_records?unique_id="+str(uniqueid)+"&season_id="+str(season)+"&offset=0&limit=10000"
    headers = getHeaders()
    token = GetToken()
    headers["Authorization"] = 'Majsoul '+token
    response = requests.get(url,headers=headers)
    if(response.status_code != 200):
        token = GetNewToken()
        headers["Authorization"] = 'Majsoul '+token
        response = requests.get(url,headers=headers)
    if(response.status_code != 200):
        DisconnectDatabase(conn,cursor)
        return "获取数据失败了"
    matchResults = json.loads(response.text)["data"]["record_list"]
    sql = "SELECT LASTRECORD FROM LASTRECORD;"
    cursor.execute(sql)
    data = cursor.fetchall()
    lastRecord = data[0][0]
    DisconnectDatabase(conn,cursor)
    
    for result in matchResults:
        if(result["removed"]==1):
            continue
        if(result["end_time"]>lastRecord):
            msg = ""
            for i in range(4):
                for j in result["accounts"]:
                    if(j["seat"] == i):
                        msg += (j["nickname"]+" ")
                        break
                for j in result["result"]["players"]:
                    if(j["seat"] == i):
                        msg += (str(j["part_point_1"])+" ")
                        break
            MatchResult(msg.strip(),userId,isGroup,GroupId)
    conn,cursor = ConnectDatabase()
    nowRecord = float(time.time())
    sql = "UPDATE LASTRECORD SET LASTRECORD ="+str(nowRecord)+";"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return "比赛信息记录成功"

def RefreshResult(message,userId):
    return

def EndSeason(userId,isGroup,groupId):
    send.sendText(userId,isGroup,groupId,"常规赛阶段结果:")
    GetTeamMessage("1",userId,isGroup,groupId)
    GetPlayerMessage("1",userId,isGroup,groupId)
    send.sendText(userId,isGroup,groupId,"半决赛阶段结果:")
    GetTeamMessage("2",userId,isGroup,groupId)
    GetPlayerMessage("2",userId,isGroup,groupId)
    send.sendText(userId,isGroup,groupId,"选手个人成绩总结:")
    GetPlayerMessage("0",userId,isGroup,groupId)
    send.sendText(userId,isGroup,groupId,"决赛阶段结果:")
    GetTeamMessage("3",userId,isGroup,groupId)
    GetPlayerMessage("3",userId,isGroup,groupId)
    return "赛季结束"

def GetTeamMessage(message,userId,isGroup,groupId):
    askStage = 1
    stage = GetStageDatabase()
    message = message.lower()
    if ((message == "1") or (message == "regular")):
        askStage = 1
    elif ((message == "2") or (message == "semifinal")):
        askStage = 2
    elif ((message == "3") or (message == "final")):
        askStage = 3
    else:
        askStage = stage
    if(askStage > stage or stage == 0):
        return "比赛尚未进行到相应阶段"
    if(stage == 4):
        askStage = 3
    stageName = "REGULAR"
    if(askStage == 2):
        stageName = "SEMIFINAL"
    if(askStage == 3):
        stageName = "FINAL"
        
    conn,cursor = ConnectDatabase()
    sql = "SELECT TEAMNAME,TEAMMATCH,TEAMFIRST,TEAMSECOND,TEAMTHIRD,TEAMFORTH,LASTSTAGE,TEAMSCORE,COLORR,COLORG,COLORB FROM TEAM"+str(stageName)+" ORDER BY TEAMSCORE DESC;"
    cursor.execute(sql)
    data = cursor.fetchall()
    teamName = []
    teamData = []
    colorData = []
    DisconnectDatabase(conn,cursor)
    for i in data:
        teamName.append(i[0])
        teamData.append([i[1],i[2],i[3],i[4],i[5],i[6],i[7]])
        colorData.append([i[8],i[9],i[10]])
    tableDf = pandas.DataFrame(data=teamData, index=teamName, columns=["比赛场次","一位","二位","三位","四位","继承pt","总pt"], dtype=None, copy=False)
    table_col_defs =  [
        ColDef("队伍",width=2, title="队伍"),
        ColDef("比赛场次", title="比赛场次"),
        ColDef("一位", title="一位"),
        ColDef("二位", title="二位"),
        ColDef("三位", title="三位"),
        ColDef("四位", title="四位"),
        ColDef("继承pt", title="继承pt"),
        ColDef("总pt", title="总pt")]
    fig,ax = plt.subplots(figsize=(24,len(teamName)*0.5))
    tableDf.index.set_names("队伍",inplace=True)
    table = Table(tableDf,column_definitions=table_col_defs,textprops={"fontsize": 16, "ha": "left", "fontfamily": ["SimHei", "Segoe UI Emoji"]})
    for i in range(len(colorData)):
        table.rows[i].set_facecolor((colorData[i][0]/255.0,colorData[i][1]/255.0,colorData[i][2]/255.0))
    filename = photo_opt.getPhotoPath(userId,isGroup,groupId)
    fig.savefig(filename)
    send.sendImg(userId,isGroup,groupId,filename)
    return

def GetPlayerMessage(message,userId,isGroup,groupId):
    askStage = 0
    stage = GetStageDatabase()
    message = message.lower()
    if ((message == "0") or (message == "total")):
        askStage = 0
    elif ((message == "1") or (message == "regular")):
        askStage = 1
    elif ((message == "2") or (message == "semifinal")):
        askStage = 2
    elif ((message == "3") or (message == "final")):
        askStage = 3
    else:
        askStage = stage
    if(askStage > stage or stage == 0):
        return "比赛尚未进行到相应阶段"
    if(askStage == 4):
        askStage = 0
    stageName = "TOTAL"
    if(askStage == 1):
        stageName = "REGULAR"
    if(askStage == 2):
        stageName = "SEMIFINAL"
    if(askStage == 3):
        stageName = "FINAL"
        
    conn,cursor = ConnectDatabase()
    sql = "SELECT PLAYERNAME,TEAMNAME,PLAYERMATCH,PLAYERFIRST,PLAYERSECOND,PLAYERTHIRD,PLAYERFORTH,PLAYERSCORE,COLORR,COLORG,COLORB FROM PLAYER"+str(stageName)+" ORDER BY PLAYERSCORE DESC;"
    cursor.execute(sql)
    data = cursor.fetchall()
    teamName = []
    teamData = []
    colorData = []
    DisconnectDatabase(conn,cursor)
    for i in data:
        teamName.append(i[0])
        teamData.append([i[1],i[2],i[3],i[4],i[5],i[6],i[7]])
        colorData.append([i[8],i[9],i[10]])
    tableDf = pandas.DataFrame(data=teamData, index=teamName, columns=["队伍","比赛场次","一位","二位","三位","四位","总pt"], dtype=None, copy=False)
    table_col_defs =  [
        ColDef("选手", title="选手"),
        ColDef("队伍",width=2, title="队伍"),
        ColDef("比赛场次", title="比赛场次"),
        ColDef("一位", title="一位"),
        ColDef("二位", title="二位"),
        ColDef("三位", title="三位"),
        ColDef("四位", title="四位"),
        ColDef("总pt", title="总pt")]
    fig,ax = plt.subplots(figsize=(24,len(teamName)*0.5))
    tableDf.index.set_names("选手",inplace=True)
    table = Table(tableDf,column_definitions=table_col_defs,textprops={"fontsize": 16, "ha": "left", "fontfamily": ["SimHei", "Segoe UI Emoji"]})
    for i in range(len(colorData)):
        table.rows[i].set_facecolor((colorData[i][0]/255.0,colorData[i][1]/255.0,colorData[i][2]/255.0))
    filename = photo_opt.getPhotoPath(userId,isGroup,groupId)
    fig.savefig(filename)
    send.sendImg(userId,isGroup,groupId,filename)
    return

def GetTeamAndPlayer(message,userId,isGroup,groupId):
    conn,cursor = ConnectDatabase()
    sql = "SELECT PLAYERNAME,TEAMNAME,COLORR,COLORG,COLORB FROM PLAYER ORDER BY TEAMNAME;"
    cursor.execute(sql)
    data = cursor.fetchall()
    playerName = []
    teamData = []
    colorData = []
    DisconnectDatabase(conn,cursor)
    for i in data:
        playerName.append(i[0])
        teamData.append([i[1]])
        colorData.append([i[2],i[3],i[4]])
    tableDf = pandas.DataFrame(data=teamData, index=playerName, columns=["队伍"], dtype=None, copy=False)

    
    
    table_col_defs =  [
        ColDef("选手",width=1.2, title="选手"),
        ColDef("队伍",width=1.8, title="队伍")]
    if(len(playerName) == 0):
        return "当前没有队员"
    fig,ax = plt.subplots(figsize=(10,len(playerName)*0.5))
    tableDf.index.set_names("选手",inplace=True)
    table = Table(tableDf,column_definitions=table_col_defs,textprops={"fontsize": 16, "ha": "left", "fontfamily": ["SimHei", "Segoe UI Emoji"]})
    
    #table = Table(tableDf,column_definitions=table_col_defs,textprops={"fontsize": 16, "ha": "left", "fontname": "SimHei"})
    for i in range(len(colorData)):
        table.rows[i].set_facecolor((colorData[i][0]/255.0,colorData[i][1]/255.0,colorData[i][2]/255.0))
    filename = photo_opt.getPhotoPath(userId,isGroup,groupId)
    fig.savefig(filename)
    send.sendImg(userId,isGroup,groupId,filename)
    return

def GetMatchResult(message,userId,isGroup,groupId):
    askStage = 0
    stage = GetStageDatabase()
    message = message.lower()
    if ((message == "0") or (message == "total")):
        askStage = 0
    elif ((message == "1") or (message == "regular")):
        askStage = 1
    elif ((message == "2") or (message == "semifinal")):
        askStage = 2
    elif ((message == "3") or (message == "final")):
        askStage = 3
    else:
        askStage = stage
    if(askStage > stage or stage == 0):
        return "比赛尚未进行到相应阶段"
    if(askStage == 4):
        askStage = 0
    stageName = "TOTAL"
    if(askStage == 1):
        stageName = "REGULAR"
    if(askStage == 2):
        stageName = "SEMIFINAL"
    if(askStage == 3):
        stageName = "FINAL"
        
    conn,cursor = ConnectDatabase()
    if(askStage == 0):
        sql = "SELECT ID,TEAMNAMEFIRST,PLAYERNAMEFIRST,SCOREFIRST,TEAMNAMESECOND,PLAYERNAMESECOND,SCORESECOND,TEAMNAMETHIRD,PLAYERNAMETHIRD,SCORETHIRD,TEAMNAMEFORTH,PLAYERNAMEFORTH,SCOREFORTH,COLORRFIRST,COLORGFIRST,COLORBFIRST FROM MATCHRESULT ORDER BY ID ASC;"
    else:
        sql = "SELECT ID,TEAMNAMEFIRST,PLAYERNAMEFIRST,SCOREFIRST,TEAMNAMESECOND,PLAYERNAMESECOND,SCORESECOND,TEAMNAMETHIRD,PLAYERNAMETHIRD,SCORETHIRD,TEAMNAMEFORTH,PLAYERNAMEFORTH,SCOREFORTH,COLORRFIRST,COLORGFIRST,COLORBFIRST FROM MATCHRESULT WHERE TYPE = '"+str(askStage)+"' ORDER BY ID ASC;"
    cursor.execute(sql)
    data = cursor.fetchall()
    matchId = []
    matchData = []
    colorData = []
    DisconnectDatabase(conn,cursor)
    for i in data:
        matchId.append(i[0])
        matchData.append([i[1],i[2],i[3],i[4],i[5],i[6],i[7],i[8],i[9],i[10],i[11],i[12]])
        colorData.append([i[13],i[14],i[15]])
        
    
    tableDf = pandas.DataFrame(data=matchData, index=matchId, columns=["一位队伍","一位选手","一位分数","二位队伍","二位选手","二位分数","三位队伍","三位选手","三位分数","四位队伍","四位选手","四位分数"], dtype=None, copy=False)
    table_col_defs =  [
        ColDef("比赛编号",width = 0.4, title="比赛编号"),
        ColDef("一位队伍", width = 2, title="一位队伍"),
        ColDef("一位选手", title="一位选手"),
        ColDef("一位分数", title="一位分数"),
        ColDef("二位队伍", width = 2, title="二位队伍"),
        ColDef("二位选手", title="二位选手"),
        ColDef("二位分数", title="二位分数"),
        ColDef("三位队伍", width = 2,title="三位队伍"),
        ColDef("三位选手", title="三位选手"),
        ColDef("三位分数", title="三位分数"),
        ColDef("四位队伍", width = 2, title="四位队伍"),
        ColDef("四位选手", title="四位选手"),
        ColDef("四位分数", title="四位分数")]
    fig,ax = plt.subplots(figsize=(40,len(matchId)*0.6))
    tableDf.index.set_names("比赛编号",inplace=True)
    table = Table(tableDf,column_definitions=table_col_defs,textprops={"fontsize": 16, "ha": "left", "fontfamily": ["SimHei", "Segoe UI Emoji"]})
    for i in range(len(colorData)):
        table.rows[i].set_facecolor((colorData[i][0]/255.0,colorData[i][1]/255.0,colorData[i][2]/255.0))
    filename = photo_opt.getPhotoPath(userId,isGroup,groupId)
    fig.savefig(filename)
    send.sendImg(userId,isGroup,groupId,filename)
    return

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

# 查询用户是否是超级管理员
def IsSuperManager(userId):
    conn,cursor = ConnectDatabase()
    sql = "SELECT COUNT(*) FROM SUPERMANAGER WHERE USERID = "+str(userId)+";"
    cursor.execute(sql)
    data = cursor.fetchall()
    data = data[0][0]
    DisconnectDatabase(conn,cursor)
    if(data == 0):
        return False
    return True

# 查询用户是否是管理员
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

# 获取当前比赛阶段
def GetStageDatabase():
    conn,cursor = ConnectDatabase()
    sql = "SELECT STAGE FROM MATCHMESSAGE;"
    cursor.execute(sql)
    data = cursor.fetchall()
    stage = data[0][0]
    DisconnectDatabase(conn,cursor)
    return stage

# 将比赛进行到下一个阶段
def NextStageDatabase():
    conn,cursor = ConnectDatabase()
    sql = "SELECT STAGE FROM MATCHMESSAGE;"
    cursor.execute(sql)
    data = cursor.fetchall()
    stage = data[0][0]
    if(stage == 4):
        DisconnectDatabase(conn,cursor)
        return stage
    stage = stage + 1
    sql = "UPDATE MATCHMESSAGE SET STAGE="+str(stage)+";"
    cursor.execute(sql)
    DisconnectDatabase(conn,cursor)
    return stage

def ConnectDatabase():
    conn = psycopg2.connect(database=DATABASE_NAME, user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST, port=DATABASE_PORT)
    cursor = conn.cursor()
    return conn,cursor

def DisconnectDatabase(conn,cursor):
    conn.commit()
    cursor.close()
    conn.close()
    
    
def GetMajsoulNames(nickNames):
    trueNames = []
    for name in nickNames:
        name = name.lower()
        if "优衣" in name:
            trueNames.append("鈴木優衣")
        elif "ue" in name:
            trueNames.append("鈴木優衣")
        elif "西" in name:
            trueNames.append("古贺荠")
        elif "613" in name:
            trueNames.append("曾鸟栖夜夏")
        elif "qd" in name:
            trueNames.append("SunQ栋")
        elif "北辰" in name:
            trueNames.append("一世梦琉璃")
        elif "木瓜" in name:
            trueNames.append("有风北往1")
        elif "手冲" in name:
            trueNames.append("いかずち")
        elif "哈分" in name:
            trueNames.append("HasFin")
        elif "hasfin" in name:
            trueNames.append("HasFin")
        elif "北笙" in name:
            trueNames.append("Ra1n_北笙")
            
        elif "茶" in name:
            trueNames.append("茶笙我梦")
        elif "yif" in name:
            trueNames.append("Y1f")
        elif "y1f" in name:
            trueNames.append("Y1f")
        elif "兔子" in name:
            trueNames.append("ウサギ連邦酋長")
        elif "纠结" in name:
            trueNames.append("HhhCurry")
        elif "雪" in name:
            trueNames.append("『Reyna』")
        elif "rogister" in name:
            trueNames.append("キガルシュ")
        elif "南木北生" in name:
            trueNames.append("Yoyiちゃん")
        elif "兔兔" in name:
            trueNames.append("兔兔伯爵单推人")
        elif "mooner" in name:
            trueNames.append("Mooner")
        elif "木木" in name:
            trueNames.append("Mooner")
        elif "月月" in name:
            trueNames.append("Mooner")
        elif "银风" in name:
            trueNames.append("silverwind")
        elif "笨比" in name:
            trueNames.append("silverwind")
        elif "影歌" in name:
            trueNames.append("喵喵小面包")
            
        elif "影子" in name:
            trueNames.append("影子灬圣光")
        elif "猫猫" in name:
            trueNames.append("喵喵小面包")
        elif "水神" in name:
            trueNames.append("喵喵小面包")
        elif "德子" in name:
            trueNames.append("鈴木小介")
        elif "唐宁" in name:
            trueNames.append("鈴木小介")
        elif "有马" in name:
            trueNames.append("有馬かな丶")
        elif "小池" in name:
            trueNames.append("有馬かな丶")
        elif "一果" in name:
            trueNames.append("有馬かな丶")
        elif "xcjj" in name:
            trueNames.append("有馬かな丶")
        elif "妈妈" in name:
            trueNames.append("必殺登龍劍")
        elif "小渡" in name:
            trueNames.append("必殺登龍劍")
        elif "登龙" in name:
            trueNames.append("必殺登龍劍")
        elif "cal" in name:
            trueNames.append("CalMasKomm")
        elif "mask" in name:
            trueNames.append("CalMasKomm")
        elif "q仔糖" in name:
            trueNames.append("Q仔糖")
        elif "狗狗" in name:
            trueNames.append("狗狗不喜欢骨头")
        elif "骨头" in name:
            trueNames.append("狗狗不喜欢骨头")
        elif "矢岛" in name:
            trueNames.append("矢島哼")
        elif "星雨" in name:
            trueNames.append("Kira星")
        elif "狼王" in name:
            trueNames.append("LK狼王")
        elif "棒棒" in name:
            trueNames.append("棒棒浮屠")
        elif "白菜" in name:
            trueNames.append("二润")
        elif "飞牛" in name:
            trueNames.append("能飞飞的飞牛")
        elif "山风" in name:
            trueNames.append("优衣献北")
        elif "大天" in name:
            trueNames.append("优衣仙贝")
        elif "lucccf" in name:
            trueNames.append("优衣仙贝")
        elif "天酱" in name:
            trueNames.append("优衣仙贝")
        elif "tonylu" in name:
            trueNames.append("Tonylu")
        elif "透你路" in name:
            trueNames.append("Tonylu")
        elif "魔王" in name:
            trueNames.append("K0ngjumow4ng")
        elif "小白" in name:
            trueNames.append("小白快躺下")
        elif "吉米" in name:
            trueNames.append("Jimmy_page")
        elif "雷" in name:
            trueNames.append("雷神的呼唤")
        elif "fh" in name:
            trueNames.append("Fheicat")
        elif "gengar" in name:
            trueNames.append("Gengar、")
        elif "五子洋" in name:
            trueNames.append("琳琅丶五子洋")
        elif "可可" in name:
            trueNames.append("kekeke呢")
        elif "keke" in name:
            trueNames.append("kekeke呢")
        elif "椰奶" in name:
            trueNames.append("背拉格朗日")
        elif "公式" in name:
            trueNames.append("公式普查")
        elif "龙虎" in name:
            trueNames.append("龙灬虎")
        elif "泰坦" in name:
            trueNames.append("独行者泰坦")
        elif "叶子猹" in name:
            trueNames.append("叶子猹单杀闰土")
        elif "润土" in name:
            trueNames.append("叶子猹单杀闰土")
        elif "闰土" in name:
            trueNames.append("叶子猹单杀闰土")
        elif "晴安" in name:
            trueNames.append("晴安い")
            # trueNames.append("あいちゃんい")
        elif "db" in name:
            trueNames.append("不少人")
        elif "的老公" in name:
            trueNames.append("瑞原明奈的老公")
        elif "yami" in name:
            trueNames.append("瑞原明奈的老公")
        elif "james" in name:
            trueNames.append("JamesJacoby")
        elif "夜空" in name:
            trueNames.append("千里山天和空")
        elif "淡定" in name:
            trueNames.append("淡定是王道")
        elif "前原" in name:
            trueNames.append("前原K7")
        elif "抽象代数" in name:
            trueNames.append("前原K7")
        elif "顾沐" in name:
            trueNames.append("是顾沐鸭")
        elif "morty" in name:
            trueNames.append("Morty桑")
            
        else:
            trueNames.append(name)
        
    return trueNames
