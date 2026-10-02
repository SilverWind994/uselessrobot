import json_opt
import copy
import send_message as send
import random
from PIL import Image,ImageDraw,ImageFont
import photo_opt


basic_card = [1,2,3,4,5,5,7,7,9,11,11,13,14,15,17]
mistake_card = [100,101,102,103,104]
yakuman_cards = [200,201,202,203,204] #5,7,8,10,12

MAX_PLAYER = 5
MIN_PLAYER = 2

def MahjongGold(user_id,is_group,group_id,message,user_name):
    if(is_group):
        # 群聊中的各种功能
        data = json_opt.GetJson(user_id,is_group,group_id)
        if((data["status"] != "mahjonggold") and (data["status"] != "none")):
            return "当前在进行其他任务哦"
        elif(data["status"] == "none"):
            return SetGame(user_id,is_group,group_id,user_name)
        else:
            if(len(message)<=1):
                return "缺少指令喵"
            elif(message[1]=="join" or message[1]=="加入"):
                return PlayerJoin(user_id,is_group,group_id,user_name)
            elif(message[1]=="start" or message[1]=="开始"):
                return StartGame(user_id,is_group,group_id)
            else:
                return "听不懂喵"
    else:
        # 单人的功能
        data = json_opt.GetJson(user_id,is_group,group_id)
        if((data["status"] != "mahjonggold") and (data["status"] != "none")):
            return "当前在进行其他任务哦"
        elif(data["status"] == "none"):
            return "请在群聊中开启游戏"
        elif(data["status"] == "mahjonggold"):
            group_id = data["data"]["group_id"]
            data = json_opt.GetJson(user_id,True,group_id)
            mg_data = data["data"]
            if(not mg_data["game_start"]):
                return "游戏暂未开始"
            else:
                player_order = -1
                for i in range(mg_data["player_num"]):
                    if(mg_data["player_id"][i]==user_id):
                        player_order = i
                        break
                if(mg_data["leave_player"][player_order]):
                    return "你已经下车了喵"
                elif(mg_data["operate_player"][player_order]):
                    return "本轮已经做好决定了"
                else:
                    if(len(message)<=1):
                        return "缺少指令喵"
                    elif(message[1]=="continue" or message[1]=="继续" or message[1]=="对日"):
                        mg_data["operate_player"][player_order] = True
                        json_opt.SetJson(user_id,True,group_id,data)
                        NextRound(user_id,True,group_id)
                        return "对日！"
                    elif(message[1]=="leave" or message[1]=="下车" or message[1]=="离开"):
                        mg_data["operate_player"][player_order] = True
                        mg_data["is_leaving"][player_order] = True
                        json_opt.SetJson(user_id,True,group_id,data)
                        NextRound(user_id,True,group_id)
                        return "打不过跑了喵"
                    else:
                        return "听不懂喵"
        else:
            return "不是，你是怎么到这里来的"
        
def SetGame(user_id,is_group,group_id,user_name):
    data = {
        "status": "mahjonggold",
        "data": {
            "game_start":False,
            "player_num":1,
            "player_id":[user_id,0,0,0,0],
            "player_name":[user_name,"","","",""],
            "trun":0,
            "score":[0,0,0,0,0],
            "yakuman_in":[False,False,False,False,False],
            "mistake_out":[0,0,0,0,0],

            "cards":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
            "next_card":0,
            "gold_score":0,
            "yakuman_score":0,
            "turn_score":0,
            "leave_player":[False,False,False,False,False],
            "is_leaving":[False,False,False,False,False],
            "operate_player":[True,True,True,True,True]
        },
        "group_bind":True
    }
    player_data = {
        "status": "mahjonggold",
        "data":{
            "group_id":group_id
        },
        "group_bind":True
    }
    data2 = json_opt.GetJson(user_id,False,group_id)
    if(data2["status"] != "none"):
        return "开始游戏的玩家当前在进行其他任务。"
    json_opt.SetJson(user_id,is_group,group_id,data)
    json_opt.SetJson(user_id,False,group_id,player_data)
    return "准备麻将宝藏游戏，"+user_name+"加入游戏，当前1名玩家。"

def PlayerJoin(user_id,is_group,group_id,user_name):
    data2 = json_opt.GetJson(user_id,False,group_id)
    if(data2["status"] != "none"):
        return "想要加入游戏的玩家当前在进行其他任务。"
    data = json_opt.GetJson(user_id,is_group,group_id)
    for i in range(data["data"]["player_num"]):
        if(data["data"]["player_id"][i] == user_id):
            return "你已经加入游戏了"
    if(data["data"]["game_start"]):
        return "游戏已经开始了"
    num = data["data"]["player_num"] 
    data["data"]["player_id"][num] = user_id
    data["data"]["player_name"][num] = user_name
    num += 1
    data["data"]["player_num"]  = num

    player_data = {
        "status": "mahjonggold",
        "data":{
            "group_id":group_id
        },
        "group_bind":True
    }

    json_opt.SetJson(user_id,is_group,group_id,data)
    json_opt.SetJson(user_id,False,group_id,player_data)
    if(num == MAX_PLAYER):
        return "玩家"+user_name +"加入游戏，当前人数"+str(num)+"，将自动开始游戏\r\n" + StartGame(user_id,is_group,group_id)
    return "玩家"+user_name +"加入游戏，当前人数"+str(num)

def StartGame(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mg_data = data["data"]
    if(mg_data["game_start"]):
        return "已经开始嘞"
    if(mg_data["player_num"]<MIN_PLAYER):
        return "人数不足无法开始游戏"
    mg_data["game_start"] = True
    json_opt.SetJson(user_id,is_group,group_id,data)
    msg = NextTrun(user_id,is_group,group_id)
    return

def NextRound(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mg_data = data["data"]
    
    # 信息
    msg = ""
    
    # 确认是否所有玩家完成了决策
    count = 0
    player_num = mg_data["player_num"]
    for i in range(player_num):
        if(mg_data["operate_player"][i]):
            count += 1
    if(count != player_num):
        return
    
    # 所有玩家完成决策，进行下一轮
    
    # 计算本轮离开的人的收益
    msg = "玩家 "
    leave_num = 0
    for i in range(player_num):
        if(mg_data["is_leaving"][i]):
            leave_num += 1
            msg += mg_data["player_name"][i] + "  "
    msg += "选择下车，"
    gold_get = 0
    if(leave_num == 0):
        msg = "没有人临阵脱逃\r\n"
    if(leave_num==1):
        gold_get = mg_data["gold_score"] + mg_data["yakuman_score"]
        mg_data["gold_score"] = 0
        mg_data["yakuman_score"] = 0
        msg += "获得了"+str(gold_get)+"根点棒\r\n"
    elif(leave_num>1):
        gold_get = mg_data["gold_score"] // leave_num
        mg_data["gold_score"] = mg_data["gold_score"] - gold_get * leave_num
        msg += "获得了"+str(gold_get)+"根点棒\r\n"
        
    
    temp_msg = "当前还在场 "
    stay_count = 0
    for i in range(player_num):
        if(mg_data["is_leaving"][i]):
            mg_data["is_leaving"][i] = False
            mg_data["leave_player"][i] = True
            mg_data["score"][i] = mg_data["score"][i] + mg_data["turn_score"] + gold_get
            
        if(not mg_data["leave_player"][i]):
            stay_count += 1
            mg_data["operate_player"][i] = False
            temp_msg += mg_data["player_name"][i] + "  "
    if(stay_count==0):
        msg += "所有人都离开了，准备开始下一轮"
        send.sendTextToGroup(group_id,msg)
        json_opt.SetJson(user_id,is_group,group_id,data)
        EndTurn(user_id,is_group,group_id)
        return
    msg += temp_msg + "\r\n"
    
    next_card = mg_data["next_card"]
    if(mg_data["cards"][next_card]<100):
        gold_get = mg_data["cards"][next_card] // stay_count
        gold_save = mg_data["cards"][next_card] % stay_count
        mg_data["gold_score"] += gold_save

        mg_data["turn_score"] += gold_get
        msg += "发现了大量点棒，在场的玩家每人分到"+str(gold_get)+"根点棒，剩余"+str(gold_save)+"根点棒\r\n"
        msg += "目前在场的人累积了" + str(mg_data["turn_score"]) +"根点棒"
    elif(mg_data["cards"][next_card]<200):
        
        diaster = mg_data["cards"][next_card]
        show = ""
        if(diaster==100):
            show = "舞蹈"
        elif(diaster==101):
            show = "诈立"
        elif(diaster==102):
            show = "错吃"
        elif(diaster==103):
            show = "炸和"
        elif(diaster==104):
            show = "夏哒！"
        
        end = False
        for i in range(next_card):
            if(mg_data["cards"][i]==diaster):
                end = True
                break
        if(end):
            msg += "第二次出现"+show+"冥场面乐，还在场的人输麻了"
            mg_data["mistake_out"][diaster-100] += 1
            # json_opt.SetJson(user_id,is_group,group_id,data)
            mg_data["next_card"] = next_card + 1

            json_opt.SetJson(user_id,is_group,group_id,data)
            send.sendTextToGroup(group_id,msg)
            DrawBoardAndSend(user_id,is_group,group_id)
            EndTurn(user_id,is_group,group_id)
            return
        else:
            msg += "第一次出现"+show+"冥场面，嘻嘻哈哈糊弄过去了"
    else:
        yakuman = ""
        if(mg_data["cards"][next_card]==200):
            mg_data["yakuman_score"] += 5
            yakuman = "国士无双"
        elif(mg_data["cards"][next_card]==201):
            mg_data["yakuman_score"] += 7
            yakuman = "九莲宝灯"
        elif(mg_data["cards"][next_card]==202):
            mg_data["yakuman_score"] += 8
            yakuman = "清老头"
        elif(mg_data["cards"][next_card]==203):
            mg_data["yakuman_score"] += 10
            yakuman = "地和"
        elif(mg_data["cards"][next_card]==204):
            mg_data["yakuman_score"] += 12
            yakuman = "天和"
        msg += "发现了"+yakuman+"役满机会！\r\n"
    
    mg_data["next_card"] = next_card + 1
    json_opt.SetJson(user_id,is_group,group_id,data)
    send.sendTextToGroup(group_id,msg)
    DrawBoardAndSend(user_id,is_group,group_id)
    return

def EndTurn(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mg_data = data["data"]
    for i in range(mg_data["next_card"]):
        if(mg_data["cards"][i]>=200):
            mg_data["yakuman_in"][mg_data["cards"][i]-200] = False

    msg = "本轮结束后玩家点棒如下：\r\n"
    
    for i in range(mg_data["player_num"]):
        msg = msg + mg_data["player_name"][i] + ":" + str(mg_data["score"][i]) + "根点棒\r\n"
    send.sendTextToGroup(group_id,msg)
    json_opt.SetJson(user_id,is_group,group_id,data)
    NextTrun(user_id,is_group,group_id)
    return

def NextTrun(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mg_data = data["data"]
    
    mg_data["next_card"] = 0
    mg_data["gold_score"] = 0
    mg_data["yakuman_score"] = 0
    mg_data["turn_score"] = 0
    mg_data["leave_player"] = [False,False,False,False,False]
    mg_data["is_leaving"] = [False,False,False,False,False]
    mg_data["operate_player"] = [True,True,True,True,True]
    
    if(mg_data["trun"] == 5):
        GameOver(user_id,is_group,group_id)
        return
    mg_data["yakuman_in"][mg_data["trun"]] = True
    mg_data["trun"]+=1
    
    msg="第"+str(mg_data["trun"])+"轮卡池:15张点棒牌(1,2,3,4,5,5,7,7,9,11,11,13,14,15,17) "
    
    cards = copy.deepcopy(basic_card)
    for i in range(5):
        msg += str(3-mg_data["mistake_out"][i]) 
        if(i == 0):
            msg += "张舞蹈 "
        elif(i == 1):
            msg += "张诈立 "
        elif(i == 2):
            msg += "张错吃 "
        elif(i == 3):
            msg += "张诈和 "
        elif(i == 4):
            msg += "张夏哒！ "
        for j in range(3):
            if(j >= mg_data["mistake_out"][i]):
                cards.append(mistake_card[i])
    for i in range(5):
        if(mg_data["yakuman_in"][i]):
            cards.append(yakuman_cards[i])
            if(i == 0):
                msg += "1张国士无双 "
            elif(i == 1):
                msg += "1张九莲宝灯 "
            elif(i == 2):
                msg += "1张清老头 "
            elif(i == 3):
                msg += "1张地和 "
            elif(i == 4):
                msg += "1张天和 "
                
    for i in range(len(cards)):
        j = random.randint(i,len(cards)-1)
        temp = cards[i]
        cards[i] = cards[j]
        cards[j] = temp
    mg_data["cards"] = cards
    json_opt.SetJson(user_id,is_group,group_id,data)
    send.sendTextToGroup(group_id,msg)
    NextRound(user_id,is_group,group_id)
    return

def GameOver(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mg_data = data["data"]
    msg = "游戏结束\r\n"
    for i in range(mg_data["player_num"]):
        msg = msg + mg_data["player_name"][i] + " " + str(mg_data["score"][i]) + "分\r\n"
    
    send.sendTextToGroup(group_id,msg)
    for i in range(mg_data["player_num"]):
        json_opt.ResetJson(mg_data["player_id"][i],False,group_id)
    json_opt.ResetJson(0,True,group_id)
    return

def DrawBoardAndSend(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mg_data = data["data"]
    image = Image.new(mode='RGB',size=(210*mg_data["next_card"]+320,320),color="green")
    for i in range(mg_data["next_card"]):
        image_temp = Image.open("C:\\mybot\\mahjong_gold\\"+str(mg_data["cards"][i])+".png").convert("RGBA")
        image.paste(image_temp,(10+210*i,10),image_temp)
    font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
    font_size = 40
    font = ImageFont.truetype(font_path,font_size)

    draw = ImageDraw.Draw(image)
    draw.text((210*mg_data["next_card"]+10,20),"点棒分数："+str(mg_data["gold_score"]),(0,0,0),font)
    draw.text((210*mg_data["next_card"]+10,120),"役满分数："+str(mg_data["yakuman_score"]),(0,0,0),font)
    draw.text((210*mg_data["next_card"]+10,220),"玩家携带："+str(mg_data["turn_score"]),(0,0,0),font)

    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
    send.sendImgToGroup(group_id,file_path)
    return