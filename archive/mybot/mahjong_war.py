import json_opt
import send_message as send
import random
from PIL import Image,ImageDraw,ImageFont
import photo_opt


def MahjongWar(user_id,is_group,group_id,message,user_name):
    if(is_group):
        # 群聊中的各种功能
        data = json_opt.GetJson(user_id,is_group,group_id)
        if((data["status"] != "mahjongwar") and (data["status"] != "none")):
            return "当前在进行其他任务哦"
        elif(data["status"] == "none"):
            return SetGame(user_id,is_group,group_id,user_name)
        else:
            if(len(message)<=1):
                return PlayerJoin(user_id,is_group,group_id,user_name)
            elif(message[1]=="join" or message[1]=="加入"):
                return PlayerJoin(user_id,is_group,group_id,user_name)
            else:
                return "听不懂喵"
    else:
        # 单人的功能
        data = json_opt.GetJson(user_id,is_group,group_id)
        if((data["status"] != "mahjongwar") and (data["status"] != "none")):
            return "当前在进行其他任务哦"
        elif(data["status"] == "none"):
            return "请在群聊中开启游戏"
        elif(data["status"] == "mahjongwar"):
            group_id = data["data"]["group_id"]
            data = json_opt.GetJson(user_id,True,group_id)
            mgw_data = data["data"]
            if(not mgw_data["game_start"]):
                return "游戏暂未开始"
            else:
                player_order = -1
                for i in range(mgw_data["player_num"]):
                    if(mgw_data["player_id"][i]==user_id):
                        player_order = i
                        break
                if(mgw_data["take"][player_order] != 0):
                    return "本轮已经决定要出的牌了"
                else:
                    if(len(message)<=1):
                        return "要打出的牌"
                    else:
                        tileStr = message[1].strip()
                        tile = 0
                        if(tileStr == '1' or tileStr == '1p'):
                            tile = 1
                        elif(tileStr == '2' or tileStr == '2p'):
                            tile = 2
                        elif(tileStr == '3' or tileStr == '3p'):
                            tile = 3
                        elif(tileStr == '4' or tileStr == '4p'):
                            tile = 4
                        elif(tileStr == '5' or tileStr == '5p'):
                            tile = 5
                        elif(tileStr == '6' or tileStr == '6p'):
                            tile = 6
                        elif(tileStr == '7' or tileStr == '7p'):
                            tile = 7
                        elif(tileStr == '8' or tileStr == '8p'):
                            tile = 8
                        elif(tileStr == '9' or tileStr == '9p'):
                            tile = 9
                        elif(tileStr == 'random' or tileStr == '随机'):
                            tile = 0
                            loc = random.randint(0,len(mgw_data["handtile"][player_order])-1)
                            tile = mgw_data["handtile"][player_order][loc]
                        else:
                            return "不认得打出的牌哇呜"
                if(not tile in mgw_data["handtile"][player_order]):
                    return "手里没有要打的牌哦"
                mgw_data["handtile"][player_order].remove(tile)
                mgw_data["taketile"][player_order].append(tile)
                mgw_data["take"][player_order] = tile
                if(len(mgw_data["handtile"][player_order])== 1):
                    mgw_data["taketile"][player_order].append(mgw_data["handtile"][player_order][0])
                    json_opt.SetJson(user_id,True,group_id,data)
                    if(mgw_data["take"][1-player_order] != 0):
                        return GameOver(user_id,True,group_id)
                    else:
                        return "打出"+str(tile)+"，请等待对手选择要出的牌,下一轮将自动选择最后一张牌"
                if(mgw_data["take"][1-player_order] != 0):
                    json_opt.SetJson(user_id,True,group_id,data)
                    return NextTrun(user_id,True,group_id)
                json_opt.SetJson(user_id,True,group_id,data)
                return "打出"+str(tile)+"，请等待对手选择要出的牌"
        else:
            return "不是，你是怎么到这里来的"
        
def SetGame(user_id,is_group,group_id,user_name):
    data = {
        "status": "mahjongwar",
        "data": {
            "game_start":False,
            "player_num":2,
            "player_id":[user_id,0],
            "player_name":[user_name,""],
            "handtile":[[1,2,3,4,5,6,7,8,9],[1,2,3,4,5,6,7,8,9]],
            "taketile":[[],[]],
            "take":[0,0]
        },
        "group_bind":True
    }
    player_data = {
        "status": "mahjongwar",
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
    return "准备麻将比大小游戏，"+user_name+"加入游戏，当前1名玩家。"

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
    
    data["data"]["player_id"][1] = user_id
    data["data"]["player_name"][1] = user_name
    data["data"]["game_start"] = True
    player_data = {
        "status": "mahjongwar",
        "data":{
            "group_id":group_id
        },
        "group_bind":True
    }

    json_opt.SetJson(user_id,is_group,group_id,data)
    json_opt.SetJson(user_id,False,group_id,player_data)

    return "玩家"+user_name +"加入游戏，游戏开始，双方请选择要打出的牌"

def NextTrun(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mgw_data = data["data"]
    
    mgw_data["take"][0] = 0
    mgw_data["take"][1] = 0
    DrawBoardAndSend(user_id,is_group,group_id)
    json_opt.SetJson(user_id,is_group,group_id,data)

    return "双方都已经做出选择，请进行下一轮"

def GameOver(user_id,is_group,group_id):
    DrawBoardAndSend(user_id,is_group,group_id)
    data = json_opt.GetJson(user_id,is_group,group_id)
    mgw_data = data["data"]
    for i in range(mgw_data["player_num"]):
        json_opt.ResetJson(mgw_data["player_id"][i],False,group_id)
    json_opt.ResetJson(0,True,group_id)
    
    send.sendText(user_id,is_group,group_id,"游戏结束")
    
    
    return "选牌完毕，下一轮选牌将自动进行，游戏结束，请在群内查看游戏结果"

def DrawBoardAndSend(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mgw_data = data["data"]
    score = [0,0]
    length = len(mgw_data["taketile"][0])
    image = Image.new(mode='RGB',size=(380+43*length,135),color="SteelBlue")
    
    for i in range(len(mgw_data["taketile"][0])):
        image_temp = Image.open("C:\\mybot\\mahjong\\mj1"+str(mgw_data["taketile"][0][i])+".png")
        image.paste(image_temp,(380+43*i,5))
    for i in range(len(mgw_data["taketile"][1])):
        image_temp = Image.open("C:\\mybot\\mahjong\\mj1"+str(mgw_data["taketile"][1][i])+".png")
        image.paste(image_temp,(380+43*i,70))
    
    font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
    font_size = 40
    font = ImageFont.truetype(font_path,font_size)

    draw = ImageDraw.Draw(image)
    draw.text((10,5),str(mgw_data["player_name"][0]),(0,0,0),font)
    draw.text((10,70),str(mgw_data["player_name"][1]),(0,0,0),font)
    
    score = [0,0]
    for i in range(len(mgw_data["taketile"][0])):
        if(mgw_data["taketile"][0][i]>mgw_data["taketile"][1][i]):
            score[0] += mgw_data["taketile"][0][i] + mgw_data["taketile"][1][i]
        elif(mgw_data["taketile"][0][i]<mgw_data["taketile"][1][i]):
            score[1] += mgw_data["taketile"][0][i] + mgw_data["taketile"][1][i]
    draw.text((290,5),str(score[0])+"分",(0,0,0),font)
    draw.text((290,70),str(score[1])+"分",(0,0,0),font)        

    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
    send.sendImgToGroup(group_id,file_path)
    return