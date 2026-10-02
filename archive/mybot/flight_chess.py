import json_opt
import random
from PIL import Image
import photo_opt
import send_message as send

position = {
    "player_home":[[(811,69),(908,69),(811,162),(908,162)],
                   [(811,814),(908,814),(811,908),(908,908)],
                   [(68,809),(168,809),(68,902),(168,902)],
                   [(68,63),(165,63),(68,156),(165,157)]],
    "player_start":[[(700,25),(700,20),(700,15),(700,10)],
                     [(948,695),(953,695),(958,695),(963,695)],
                     [(279,946),(279,951),(279,956),(279,961)],
                     [(30,271),(25,271),(20,271),(15,271)]],
    "player_final":[[[(489,153),(494,153),(499,153),(504,153)],
                     [(489,209),(494,209),(499,209),(504,209)],
                     [(489,265),(494,265),(499,265),(504,265)],
                     [(489,321),(494,321),(499,321),(504,321)],
                     [(489,377),(494,377),(499,377),(504,377)]],
                    [[(825,487),(825,492),(825,497),(825,502)],
                     [(769,487),(769,492),(769,497),(769,502)],
                     [(713,487),(713,492),(713,497),(713,502)],
                     [(657,487),(657,492),(657,497),(657,502)],
                     [(601,487),(601,492),(601,497),(601,502)]],
                    [[(489,831),(494,831),(499,831),(504,831)],
                     [(489,775),(494,775),(499,775),(504,775)],
                     [(489,719),(494,719),(499,719),(504,719)],
                     [(489,663),(494,663),(499,663),(504,663)],
                     [(489,607),(494,607),(499,607),(504,607)]],
                    [[(151,487),(151,492),(151,497),(151,502)],
                     [(221,487),(221,492),(221,497),(221,502)],
                     [(267,487),(267,492),(267,497),(267,502)],
                     [(323,487),(323,492),(323,497),(323,502)],
                     [(379,487),(379,492),(379,497),(379,502)]]],
    "roads":[[(662,83),(667,78),(672,73),(677,68)],
             [(686,145),(691,145),(696,145),(701,145)],
             [(686,202),(691,202),(696,202),(701,202)],
             [(661,270),(656,270),(651,270),(646,270)],
             [(709,314),(617,319),(612,324),(607,329)],
             [(773,286),(773,291),(773,296),(773,301)],
             [(831,286),(831,291),(831,296),(831,301)],
             [(894,312),(899,307),(904,302),(909,297)],
             [(916,373),(921,373),(926,373),(931,373)],
             [(916,431),(921,431),(926,431),(931,431)],
             [(911,487),(916,487),(921,487),(926,487)],
             [(916,545),(921,545),(926,545),(931,545)],
             [(916,598),(921,598),(926,598),(931,598)],
             [(892,664),(897,669),(902,674),(907,679)],
             [(829,686),(829,691),(829,696),(829,701)],
             [(772,686),(772,691),(772,696),(772,701)],
             [(710,661),(710,656),(710,651),(710,646)],
             [(663,706),(658,706),(653,706),(648,706)],
             [(687,771),(682,771),(677,771),(672,771)],
             [(687,825),(682,825),(677,825),(672,825)],
             [(667,892),(672,897),(677,902),(682,907)],
             [(599,913),(599,918),(599,923),(599,928)],
             [(546,913),(546,918),(546,923),(546,928)],
             [(491,913),(491,918),(491,923),(491,928)],
             [(432,913),(432,918),(432,923),(432,928)],
             [(376,913),(376,918),(376,923),(376,928)],
             [(314,894),(309,899),(304,904),(299,909)],
             [(290,826),(285,826),(280,826),(275,826)],
             [(290,770),(285,770),(280,770),(275,770)],
             [(311,707),(316,707),(321,707),(326,707)],
             [(265,663),(265,658),(265,653),(265,648)],
             [(205,685),(205,680),(205,675),(205,670)],
             [(145,685),(145,680),(145,675),(145,670)],
             [(86,664),(81,669),(76,674),(71,679)],
             [(59,600),(54,600),(49,600),(44,600)],
             [(59,543),(54,543),(49,543),(44,543)],
             [(59,487),(54,487),(49,487),(44,487)],
             [(59,428),(54,428),(49,428),(44,428)],
             [(59,373),(54,373),(49,373),(44,373)],
             [(80,308),(75,303),(70,298),(65,293)],
             [(147,284),(147,289),(147,294),(147,299)],
             [(203,284),(203,289),(203,294),(203,299)],
             [(264,309),(264,314),(264,319),(264,324)],
             [(312,266),(317,266),(322,266),(327,266)],
             [(290,201),(295,201),(300,201),(305,201)],
             [(290,144),(295,144),(300,144),(305,144)],
             [(312,81),(307,76),(302,71),(297,66)],
             [(374,57),(374,52),(374,47),(374,42)],
             [(433,57),(433,52),(433,47),(433,42)],
             [(490,57),(490,52),(490,47),(490,42)],
             [(545,57),(545,52),(545,47),(545,42)],
             [(602,57),(602,52),(602,47),(602,42)]],
}

color = ["红色","黄色","蓝色","绿色"]


def FlightChess(user_id,is_group,group_id,message,user_name):
    # 只有群里能用
    if(not is_group):
        return "请在群聊中开启此功能"
    
    # 当前如果有其他活动则需要结束
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    if((status_data["status"]!="none") and (status_data["status"]!="flightchess")):
        return "请先结束当前的活动"
    
    # 开始一局的准备
    elif(status_data["status"]=="none"):
        status_data = {
            "status": "flightchess",
            "data": {
                "game_start":False,
                "player_num":1,
                "player_id":[user_id,0,0,0],
                "player_name":[user_name,"","",""],
                "player_turn":0,
                "player_flights":[[-1,-1,-1,-1],[-1,-1,-1,-1],[-1,-1,-1,-1],[-1,-1,-1,-1]],
                "continuous_throwing":0,
                "dice_points":0
            },
            "group_bind":False
        }
        json_opt.SetJson(user_id,is_group,group_id,status_data)
        
        return "铺设飞行棋棋盘，当前1名玩家"
    
    # 已经在某个阶段当中
    elif(status_data["status"]=="flightchess"):
        flight_data = status_data["data"]
        
        # 游戏已经开始的部分
        if(flight_data["game_start"]):
            if(user_id != flight_data["player_id"][flight_data["player_turn"]]):
                return ""
            if(len(message)<=1):
                return "请选择你要移动的棋子"
            if((message[1]!="0") and (message[1]!="1") and (message[1]!="2") and (message[1]!="3") and (message[1]!="4")):
                return "不存在这个编号喵"
            return NextTurn(user_id,is_group,group_id,message)
        # 游戏还没开始的部分
        else:
            if(len(message)<=1):
                return "请输入对应的指令"
            if((message[1] == "开始") or (message[1] == "start")):
                return StartGame(user_id,is_group,group_id)
            elif((message[1] == "加入") or (message[1] == "join")):
                for i in range(flight_data["player_num"]):
                    if(flight_data["player_id"][i] == user_id):
                        return "你已经加入游戏了"
                flight_data["player_id"][flight_data["player_num"]] = user_id
                flight_data["player_name"][flight_data["player_num"]] = user_name
                flight_data["player_num"] = flight_data["player_num"] + 1
                json_opt.SetJson(user_id,is_group,group_id,status_data)
                if(flight_data["player_num"]==4):
                    return StartGame(user_id,is_group,group_id)
                return "玩家 "+str(user_name)+" 加入游戏"
            else:
                return "当前还没有开始游戏"
            
    else:
        return "不是为什么还有其他情况的"
    
def StartGame(user_id,is_group,group_id):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    flight_data = status_data["data"]
    flight_data["game_start"] = True
    flight_data["continuous_throwing"] = 1
    dice = random.randint(1,6)
    flight_data["dice_points"] = dice
    
    msg_rt = "红色玩家：" + flight_data["player_name"][0]
    if(flight_data["player_num"]>1):
        msg_rt = msg_rt + "\r\n黄色玩家：" + flight_data["player_name"][1]
    if(flight_data["player_num"]>2):
        msg_rt = msg_rt + "\r\n蓝色玩家：" + flight_data["player_name"][2]
    if(flight_data["player_num"]>3):
        msg_rt = msg_rt + "\r\n绿色玩家：" + flight_data["player_name"][3]
    msg_rt = msg_rt + "\r\n红色玩家掷出" + str(dice) + "点，请选择要移动的棋子"
    json_opt.SetJson(user_id,is_group,group_id,status_data)
    DrawBoardAndSend(user_id,is_group,group_id)
    return msg_rt

def NextTurn(user_id,is_group,group_id,message):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    flight_data = status_data["data"]
    player_turn = flight_data["player_turn"]
    player_name = flight_data["player_name"][int(player_turn)]
    dice = flight_data["dice_points"]
    move = False
    msg = ""
    if(message[1] == "0"):
        msg = msg + color[player_turn] + player_name + "选择不移动棋子\r\n"
    else:
        move = True
        flight_num = int(message[1])-1
        
        loc = flight_data["player_flights"][player_turn][flight_num]
        if(loc == -1):
            if(dice<5):
                return "骰子不到五点，不满足起飞要求"
            flight_data["player_flights"][player_turn][flight_num] = 0
        elif(loc == 56):
            return "已经到达终点了，不许乱动"
        else:
            msg = msg + color[player_turn] + player_name + "选择移动"+str(flight_num+1)+"号棋子\r\n"
            loc2 = loc + dice
            if((loc2==14) or (loc2 == 18)):
                loc2 = loc2 + 16
            elif((loc2%4==2) and (loc2<50)):
                loc2 = loc2 + 4
                
            if(loc2>56):
                loc2 = 112-loc2
                
            # TODO 检查有没有创机
            if(loc2>0 and loc2 <= 50):
                loc_check = loc2 + player_turn * 13
                if(loc_check > 52):
                    loc_check -= 52
                for i in range(4):
                    if(i == player_turn):
                        continue
                    count = 0
                    for j in range(4):
                        loc_check2 = 60
                        if(flight_data["player_flights"][i][j] <= 50 and flight_data["player_flights"][i][j] > 0):
                            loc_check2 = flight_data["player_flights"][i][j] + i * 13
                            if(loc_check2 > 52 ):
                                loc_check2 -= 52
                        if(loc_check2 == loc_check):
                            count += 1
                            flight_data["player_flights"][i][j] = -1
                    if(count >= 2):
                        loc2 = -1
            flight_data["player_flights"][player_turn][flight_num] = loc2
        if(flight_data["player_flights"][player_turn][0]+flight_data["player_flights"][player_turn][1]+flight_data["player_flights"][player_turn][2]+flight_data["player_flights"][player_turn][3]==224):
            GameOver(user_id,is_group,group_id)
            return color[player_turn] + player_name + "赢得了比赛"
    
    new_dice = random.randint(1,6)
    if(dice==6):
        if((flight_data["continuous_throwing"]==2) and (new_dice == 6)):
            msg = msg + "然后" + color[player_turn] + player_name + "第三次掷出六点，所有没到达终点的飞机全被打回起点了呜呜呜\r\n"
            for i in range(4):
                if(flight_data["player_flights"][player_turn][i] != 56):
                    flight_data["player_flights"][player_turn][i] = -1
            flight_data["continuous_throwing"] = 1
            flight_data["player_turn"] = (flight_data["player_turn"] + 1) % flight_data["player_num"]
            new_dice = random.randint(1,6)
            flight_data["dice_points"] = new_dice
            msg = msg + color[flight_data["player_turn"]] + flight_data["player_name"][flight_data["player_turn"]] + "掷骰子，掷出了"+str(new_dice)+"点，请选择要移动的棋子"
        else:
            flight_data["continuous_throwing"] += 1
            flight_data["dice_points"] = new_dice
            msg = msg + color[player_turn] + player_name + "再掷一次骰子，掷出了"+str(new_dice)+"点，请选择要移动的棋子"
    else:
        flight_data["continuous_throwing"] = 1
        flight_data["player_turn"] = (flight_data["player_turn"] + 1) % flight_data["player_num"]
        new_dice = random.randint(1,6)
        flight_data["dice_points"] = new_dice
        msg = msg + color[flight_data["player_turn"]] + flight_data["player_name"][flight_data["player_turn"]] + "掷骰子，掷出了"+str(new_dice)+"点，请选择要移动的棋子"
    
    json_opt.SetJson(user_id,is_group,group_id,status_data)
    if(move):
        DrawBoardAndSend(user_id,is_group,group_id)
    return msg

def DrawBoardAndSend(user_id,is_group,group_id):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    flight_data = status_data["data"]
    background = Image.open("C:\\mybot\\flight_chess\\chess_board.png").convert("RGBA")
    flights = []
    for i in range(4):
        temp = []
        for j in range(5):
            file_path = "C:\\mybot\\flight_chess\\flight_"+str(i+1)+str(j+1)+".png"
            temp.append(Image.open(file_path).convert("RGBA"))
        flights.append(temp)
    flights_loc = flight_data["player_flights"]
    for i in range(flight_data["player_num"]):
        for j in range(4):
            image = flights[i][j]
            image_loc = (0,0)
            if(flights_loc[i][j]==-1):
                image_loc = position["player_home"][i][j]
            elif(flights_loc[i][j]==56):
                image_loc = position["player_home"][i][j]
                image = flights[i][4]
            else:
                count = 0
                for k in range(j):
                    if(flights_loc[i][j]==flights_loc[i][k]):
                        count += 1
                if(flights_loc[i][j]==0):
                    image_loc = position["player_start"][i][count]
                elif(flights_loc[i][j]>50):
                    image_loc = position["player_final"][i][flights_loc[i][j]-51][count]
                else:
                    loc = flights_loc[i][j] + 13 * i
                    if(loc>52):
                        loc -= 52
                    image_loc = position["roads"][loc-1][count]
                
            background.paste(image,image_loc,image)
    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,background)
    send.sendImg(user_id,is_group,group_id,file_path)
    return

def GameOver(user_id,is_group,group_id):
    json_opt.ResetJson(user_id,is_group,group_id)
    return