import json_opt
import random
import psycopg2
from PIL import Image,ImageDraw,ImageFont
import photo_opt
import send_message as send

DATABASE_NAME = "robot"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = ""  # 已脱敏：本地数据库密码
DATABASE_HOST = "127.0.0.1"
DATABASE_PORT = "5432"

def ConnectDatabase():
    conn = psycopg2.connect(database=DATABASE_NAME, user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST, port=DATABASE_PORT)
    cursor = conn.cursor()
    return conn,cursor

def DisconnectDatabase(conn,cursor):
    conn.commit()
    cursor.close()
    conn.close()


def Yahtzee(user_id,is_group,group_id,message,user_name):
    
    if(len(message)>1 and (message[1]=="排行榜" or message[1]=="rankinglist") ):
        return SendRankingList(user_id,is_group,group_id)
    # 只有群里能用
    if(not is_group):
        return "请在群聊中开启此功能"
    
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    if((status_data["status"]!="none") and (status_data["status"]!="yahtzee")):
        return "请先结束当前的活动"
    
    elif(status_data["status"]=="none"):
        status_data = {
            "status": "yahtzee",
            "data": {
                "game_start": False,
                "player_num":1,
                "player_id": [
                    user_id,
                    0,
                    0,
                    0
                ],
                "player_name": [
                    user_name,
                    "",
                    "",
                    ""
                ],
                "trun": 1,
                "player_turn":0,
                "player_score": [
                    [-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1],[-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1],[-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1],[-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1]
                ],
                "dice":[1,2,3,4,5],
                "roll":1
            },
            "group_bind": False
        }
        json_opt.SetJson(user_id,is_group,group_id,status_data)
        
        return "准备快艇骰子，当前1名玩家"
    
    elif(status_data["status"]=="yahtzee"):
        yahtzee_data = status_data["data"]
        if(yahtzee_data["game_start"]):
            if(user_id != yahtzee_data["player_id"][yahtzee_data["player_turn"]]):
                return "当前玩家是"+yahtzee_data["player_name"][yahtzee_data["player_turn"]]
            message = message[1].split(" ",1)
            if((message[0]=="重投")or(message[0]=="reroll")):
                if(len(message)<=1):
                    return "指令不全喵"
                return Reroll(user_id,is_group,group_id,message[1])
            elif((message[0]=="计分")or(message[0]=="score")):
                if(len(message)<=1):
                    return "指令不全喵"
                return Score(user_id,is_group,group_id,message[1])
            elif((message[0]=="投降")or(message[0]=="surrender")):
                return "投降也没有用喵"
            else:
                return "指令有误喵"
        else:
            if(len(message)<=1):
                return "请输入加入/join加入游戏,或者开始/start开始游戏"
            elif((message[1] == "加入") or (message[1] == "join")):
                player_num = yahtzee_data["player_num"]
                for i in range(player_num):
                    if(yahtzee_data["player_id"][i] == user_id):
                        return "你已经加入游戏了"
                if(yahtzee_data["game_start"]):
                    return "游戏已经开始了"
                yahtzee_data["player_id"][player_num] = user_id
                yahtzee_data["player_name"][player_num] = user_name
                yahtzee_data["player_num"] = player_num + 1
                json_opt.SetJson(user_id,is_group,group_id,status_data)
                if(player_num == 3):
                    yahtzee_data["game_start"] = True
                    json_opt.SetJson(user_id,is_group,group_id,status_data)
                    send.sendTextToGroup(group_id,user_name+"加入游戏，游戏开始")
                    StartGame(user_id,is_group,group_id)
                
                send.sendTextToGroup(group_id,user_name+"加入游戏")
                return ""
            elif((message[1] == "开始") or (message[1] == "start")):
                yahtzee_data["game_start"] = True
                json_opt.SetJson(user_id,is_group,group_id,status_data)
                StartGame(user_id,is_group,group_id)
            else:
                return "听不懂喵听不懂喵"
    else:
        return "不是你怎么来这里的我请问了"
    
def StartGame(user_id,is_group,group_id):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    yahtzee_data = status_data["data"]
    for i in range(5):
        yahtzee_data["dice"][i] = random.randint(1,6)
    yahtzee_data["dice"].sort()
    json_opt.SetJson(user_id,is_group,group_id,status_data)
    DrawDiceAndSend(user_id,is_group,group_id)
    send.sendTextToGroupWithAt(group_id,yahtzee_data["player_id"][yahtzee_data["player_turn"]],"开始游戏")
    return

def NextPlayer(user_id,is_group,group_id):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    yahtzee_data = status_data["data"]
    yahtzee_data["roll"] = 1
    yahtzee_data["player_turn"] = yahtzee_data["player_turn"] + 1
    if(yahtzee_data["player_turn"]==yahtzee_data["player_num"]):
        yahtzee_data["trun"] += 1
        yahtzee_data["player_turn"] = 0
        
    
    if(yahtzee_data["trun"] == 13):
        json_opt.SetJson(user_id,is_group,group_id,status_data)
        for i in range(yahtzee_data["player_num"]):
            playerName = yahtzee_data["player_name"]
            playerScore = yahtzee_data["player_score"]
            score = 0
            for j in range(6):
                score += playerScore[i][j]
            if(score >= 63):
                score += 35
            for j in range(6,12,1):
                score += playerScore[i][j]
            conn,cursor = ConnectDatabase()
            sql = "SELECT COUNT(*) FROM YAHTZEERANKING WHERE USERNAME = '"+str(playerName[i])+"';"
            cursor.execute(sql)
            data = cursor.fetchall()
            data = data[0][0]
            if(data == 0):
                sql = "INSERT INTO YAHTZEERANKING(USERNAME,SCORE) VALUES('"+str(playerName[i])+"',"+str(score)+");"
            else:
                sql = "SELECT SCORE FROM YAHTZEERANKING WHERE USERNAME = '"+str(playerName[i])+"';"
                cursor.execute(sql)
                data = cursor.fetchall()
                data = data[0][0]
                if(data < score):
                    sql = "UPDATE YAHTZEERANKING SET SCORE = " + str(score) + " WHERE USERNAME = '" + str(playerName[i]) + "';"
            cursor.execute(sql)
            DisconnectDatabase(conn,cursor)
        
        DrawBoardAndSend(user_id,is_group,group_id)
        SendRankingList(user_id,is_group,group_id)
        json_opt.ResetJson(user_id,is_group,group_id)
        
        return "游戏结束喵"
    for i in range(5):
        yahtzee_data["dice"][i] = random.randint(1,6)
    yahtzee_data["dice"].sort()
    json_opt.SetJson(user_id,is_group,group_id,status_data)
    DrawBoardAndSend(user_id,is_group,group_id)
    DrawDiceAndSend(user_id,is_group,group_id)
    send.sendTextToGroupWithAt(group_id,yahtzee_data["player_id"][yahtzee_data["player_turn"]],"切换玩家")
    return ""

def Reroll(user_id,is_group,group_id,message):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    yahtzee_data = status_data["data"]
    if(yahtzee_data["roll"]==3):
        return "已经没有重投次数了饿"
    for c in message:
        if(c == "1"):
            yahtzee_data["dice"][0] = random.randint(1,6)
        elif(c == "2"):
            yahtzee_data["dice"][1] = random.randint(1,6)
        elif(c == "3"):
            yahtzee_data["dice"][2] = random.randint(1,6)
        elif(c == "4"):
            yahtzee_data["dice"][3] = random.randint(1,6)
        elif(c == "5"):
            yahtzee_data["dice"][4] = random.randint(1,6)
        elif(c == " "):
            continue
        elif(c == ","):
            continue
        elif(c == "，"):
            continue
        else:
            return "要重投的东西好像不太对喵"
    yahtzee_data["dice"].sort()
    yahtzee_data["roll"] = yahtzee_data["roll"] + 1
    json_opt.SetJson(user_id,is_group,group_id,status_data)
    DrawDiceAndSend(user_id,is_group,group_id)
    return "重投了一些骰子，大概"

def Score(user_id,is_group,group_id,message):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    yahtzee_data = status_data["data"]
    player_turn = yahtzee_data["player_turn"]
    
    if((message == "1点")or(message == "一点")or(message == "1s")):
        if(yahtzee_data["player_score"][player_turn][0] != -1):
            return "这个格子的分已经算了"
        score = 0
        for i in yahtzee_data["dice"]:
            if i == 1:
                score += 1
        yahtzee_data["player_score"][player_turn][0] = score
    elif((message == "2点")or(message == "二点")or(message == "两点")or(message == "2s")):
        if(yahtzee_data["player_score"][player_turn][1] != -1):
            return "这个格子的分已经算了"
        score = 0
        for i in yahtzee_data["dice"]:
            if i == 2:
                score += 2
        yahtzee_data["player_score"][player_turn][1] = score
    elif((message == "3点")or(message == "三点")or(message == "3s")):
        if(yahtzee_data["player_score"][player_turn][2] != -1):
            return "这个格子的分已经算了"
        score = 0
        for i in yahtzee_data["dice"]:
            if i == 3:
                score += 3
        yahtzee_data["player_score"][player_turn][2] = score
    elif((message == "4点")or(message == "四点")or(message == "4s")):
        if(yahtzee_data["player_score"][player_turn][3] != -1):
            return "这个格子的分已经算了"
        score = 0
        for i in yahtzee_data["dice"]:
            if i == 4:
                score += 4
        yahtzee_data["player_score"][player_turn][3] = score
    elif((message == "5点")or(message == "五点")or(message == "5s")):
        if(yahtzee_data["player_score"][player_turn][4] != -1):
            return "这个格子的分已经算了"
        score = 0
        for i in yahtzee_data["dice"]:
            if i == 5:
                score += 5
        yahtzee_data["player_score"][player_turn][4] = score
    elif((message == "6点")or(message == "六点")or(message == "6s")):
        if(yahtzee_data["player_score"][player_turn][5] != -1):
            return "这个格子的分已经算了"
        score = 0
        for i in yahtzee_data["dice"]:
            if i == 6:
                score += 6
        yahtzee_data["player_score"][player_turn][5] = score
    elif((message == "全选")or(message == "chance")):
        if(yahtzee_data["player_score"][player_turn][6] != -1):
            return "这个格子的分已经算了"
        score = 0
        for i in yahtzee_data["dice"]:
            score += i
        yahtzee_data["player_score"][player_turn][6] = score
    elif((message == "四条")or(message == "四同")or(message == "4king")or(message == "4k")):
        if(yahtzee_data["player_score"][player_turn][7] != -1):
            return "这个格子的分已经算了"
        if((yahtzee_data["dice"][0]==yahtzee_data["dice"][3]) or (yahtzee_data["dice"][1]==yahtzee_data["dice"][4])):
            score = 0
            for i in yahtzee_data["dice"]:
                score += i
            yahtzee_data["player_score"][player_turn][7] = score
        else:
            yahtzee_data["player_score"][player_turn][7] = 0
    elif((message == "葫芦")or(message == "fullhouse")or(message == "fh")):
        if(yahtzee_data["player_score"][player_turn][8] != -1):
            return "这个格子的分已经算了"
        if(((yahtzee_data["dice"][0]==yahtzee_data["dice"][1]))
           and((yahtzee_data["dice"][3]==yahtzee_data["dice"][4]))
           and(((yahtzee_data["dice"][1]==yahtzee_data["dice"][2]))
               or((yahtzee_data["dice"][2]==yahtzee_data["dice"][3])))):
            score = 0
            for i in yahtzee_data["dice"]:
                score += i
            yahtzee_data["player_score"][player_turn][8] = score
        else:
            yahtzee_data["player_score"][player_turn][8] = 0
    elif((message == "小顺")or(message == "smallstraight")or(message == "ss")):
        if(yahtzee_data["player_score"][player_turn][9] != -1):
            return "这个格子的分已经算了"
        if((3 in yahtzee_data["dice"]) and (4 in yahtzee_data["dice"])):
            if((1 in yahtzee_data["dice"]) and (2 in yahtzee_data["dice"])):
                yahtzee_data["player_score"][player_turn][9] = 15
            elif((2 in yahtzee_data["dice"]) and (5 in yahtzee_data["dice"])):
                yahtzee_data["player_score"][player_turn][9] = 15
            elif((5 in yahtzee_data["dice"]) and (6 in yahtzee_data["dice"])):
                yahtzee_data["player_score"][player_turn][9] = 15
            else:
                yahtzee_data["player_score"][player_turn][9] = 0
        else:
            yahtzee_data["player_score"][player_turn][9] = 0
    elif((message == "大顺")or(message == "largestraight")or(message == "ls")):
        if(yahtzee_data["player_score"][player_turn][10] != -1):
            return "这个格子的分已经算了"
        if((1 in yahtzee_data["dice"]) and (2 in yahtzee_data["dice"]) and (3 in yahtzee_data["dice"]) and (4 in yahtzee_data["dice"]) and (5 in yahtzee_data["dice"])):
            yahtzee_data["player_score"][player_turn][10] = 30
        elif((6 in yahtzee_data["dice"]) and (2 in yahtzee_data["dice"]) and (3 in yahtzee_data["dice"]) and (4 in yahtzee_data["dice"]) and (5 in yahtzee_data["dice"])):
            yahtzee_data["player_score"][player_turn][10] = 30
        else:
            yahtzee_data["player_score"][player_turn][10] = 0
    elif((message == "快艇")or(message == "yahtzee")):
        if(yahtzee_data["player_score"][player_turn][11] != -1):
            return "这个格子的分已经算了"
        if(yahtzee_data["dice"][0]==yahtzee_data["dice"][4]):
            yahtzee_data["player_score"][player_turn][11] = 50
        else:
            yahtzee_data["player_score"][player_turn][11] = 0
    else:
        return "这是什么？"
    json_opt.SetJson(user_id,is_group,group_id,status_data)
    return NextPlayer(user_id,is_group,group_id)
    

def DrawBoardAndSend(user_id,is_group,group_id):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    yahtzee_data = status_data["data"]
    length = yahtzee_data["player_num"] * 200 + 100
    image = Image.new(mode='RGB',size=(length,620),color=(245,255,195))
    draw = ImageDraw.Draw(image)
    draw.rectangle([(100, 60), (300, 620)], fill="pink")
    draw.rectangle([(300, 60), (500, 620)], fill="skyblue")
    draw.rectangle([(500, 60), (700, 620)], fill="PaleGreen")
    draw.rectangle([(700, 60), (900, 620)], fill="MediumPurple")
    font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
    font = ImageFont.truetype(font_path,25)
    draw.text((20,60),"一点","BLACK",font)
    draw.text((20,100),"二点","BLACK",font)
    draw.text((20,140),"三点","BLACK",font)
    draw.text((20,180),"四点","BLACK",font)
    draw.text((20,220),"五点","BLACK",font)
    draw.text((20,260),"六点","BLACK",font)
    draw.text((20,300),"奖励分","BLACK",font)
    draw.text((20,340),"全选","BLACK",font)
    draw.text((20,380),"四同","BLACK",font)
    draw.text((20,420),"葫芦","BLACK",font)
    draw.text((20,460),"小顺","BLACK",font)
    draw.text((20,500),"大顺","BLACK",font)
    draw.text((20,540),"快艇","BLACK",font)
    draw.text((20,580),"总分","BLACK",font)
    draw.text((100,20),yahtzee_data["player_name"][0],"BLACK",font)
    draw.text((300,20),yahtzee_data["player_name"][1],"BLACK",font)
    draw.text((500,20),yahtzee_data["player_name"][2],"BLACK",font)
    draw.text((700,20),yahtzee_data["player_name"][3],"BLACK",font)
    score1 = 0
    score2 = 0
    score3 = 0
    score4 = 0
    for i in range(6):
        if yahtzee_data["player_score"][0][i] != -1:
            draw.text((150,60 + 40 * i),str(yahtzee_data["player_score"][0][i]),"BLACK",font)
            score1 += yahtzee_data["player_score"][0][i]
        if yahtzee_data["player_score"][1][i] != -1:
            draw.text((350,60 + 40 * i),str(yahtzee_data["player_score"][1][i]),"BLACK",font)
            score2 += yahtzee_data["player_score"][1][i]
        if yahtzee_data["player_score"][2][i] != -1:
            draw.text((550,60 + 40 * i),str(yahtzee_data["player_score"][2][i]),"BLACK",font)
            score3 += yahtzee_data["player_score"][2][i]
        if yahtzee_data["player_score"][3][i] != -1:
            draw.text((750,60 + 40 * i),str(yahtzee_data["player_score"][3][i]),"BLACK",font)
            score4 += yahtzee_data["player_score"][3][i]
    if(score1 >= 63):
        score1 += 35
        draw.text((150,300),"35","BLACK",font)
    if(score2 >= 63):
        score2 += 35
        draw.text((350,300),"35","BLACK",font)
    if(score3 >= 63):
        score3 += 35
        draw.text((550,300),"35","BLACK",font)
    if(score4 >= 63):
        score4 += 35
        draw.text((750,300),"35","BLACK",font)
    for i in range(6,12):
        if yahtzee_data["player_score"][0][i] != -1:
            draw.text((150,100 + 40 * i),str(yahtzee_data["player_score"][0][i]),"BLACK",font)
            score1 += yahtzee_data["player_score"][0][i]
        if yahtzee_data["player_score"][1][i] != -1:
            draw.text((350,100 + 40 * i),str(yahtzee_data["player_score"][1][i]),"BLACK",font)
            score2 += yahtzee_data["player_score"][1][i]
        if yahtzee_data["player_score"][2][i] != -1:
            draw.text((550,100 + 40 * i),str(yahtzee_data["player_score"][2][i]),"BLACK",font)
            score3 += yahtzee_data["player_score"][2][i]
        if yahtzee_data["player_score"][3][i] != -1:
            draw.text((750,100 + 40 * i),str(yahtzee_data["player_score"][3][i]),"BLACK",font)
            score4 += yahtzee_data["player_score"][3][i]
    draw.text((150,580),str(score1),"BLACK",font)
    draw.text((350,580),str(score2),"BLACK",font)
    draw.text((550,580),str(score3),"BLACK",font)
    draw.text((750,580),str(score4),"BLACK",font)
    
    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
    send.sendImgToGroup(group_id,file_path)
    return

def DrawDiceAndSend(user_id,is_group,group_id):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    yahtzee_data = status_data["data"]
    
    image = Image.new(mode='RGB',size=(700,100),color=(235,235,205))
    draw = ImageDraw.Draw(image)
    font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
    font = ImageFont.truetype(font_path,25)
    draw.text((15,10),str(yahtzee_data["player_name"][yahtzee_data["player_turn"]]),"BLACK",font)
    draw.text((15,50),"第"+str(yahtzee_data["roll"])+"骰","BLACK",font)
    filename = "C:\\mybot\\yahtzee\\"
    if(yahtzee_data["player_turn"] == 0):
        filename += "r"
    elif(yahtzee_data["player_turn"] == 1):
        filename += "b"
    elif(yahtzee_data["player_turn"] == 2):
        filename += "g"
    else:
        filename += "y"
    for i in range(5):
        image_temp = Image.open(filename+str(yahtzee_data["dice"][i])+".png").convert("RGBA")
        image.paste(image_temp,(200+100*i,5),image_temp)
    
    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
    send.sendImgToGroup(group_id,file_path)
    return

def SendRankingList(user_id,is_group,group_id):
    conn,cursor = ConnectDatabase()
    sql = "SELECT USERNAME,SCORE FROM YAHTZEERANKING ORDER BY SCORE DESC;"
    cursor.execute(sql)
    data = cursor.fetchall()
    DisconnectDatabase(conn,cursor)
    msg = "快艇骰子总排行榜：\r\n"
    for i in range(len(data)):
        msg += str(i+1)+"\t"
        msg += data[i][0] + "\t" + str(data[i][1])
        if(i != len(data)-1):
            msg +="\r\n"
    send.sendText(user_id,is_group,group_id,msg)
    return ""