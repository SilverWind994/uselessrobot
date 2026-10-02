import json_opt
import send_message as send
import random
from PIL import Image,ImageDraw,ImageFont
import photo_opt

doraTo = {0:6,1:2,2:3,3:4,4:5,5:6,6:7,7:8,8:9,9:1,10:16,11:12,12:13,13:14,14:15,15:16,16:17,17:18,18:19,19:11,20:26,21:22,22:23,23:24,24:25,25:26,26:27,27:28,28:29,29:21,31:32,32:33,33:34,34:31,35:36,36:37,37:35}


def Mahjong17(user_id,is_group,group_id,message,user_name):
    if(is_group):
        # 群聊中的各种功能
        data = json_opt.GetJson(user_id,is_group,group_id)
        if((data["status"] != "mahjong17") and (data["status"] != "none")):
            return "当前在进行其他任务哦"
        elif(data["status"] == "none"):
            return SetGame(user_id,is_group,group_id,user_name)
        else:
            if(len(message)<=1):
                return "缺少指令喵，虽然好像只有加入的指令但是姑且还是需要输入一下，太可恶了"
            elif(message[1]=="join" or message[1]=="加入"):
                return StartGame(user_id,is_group,group_id,user_name)
            else:
                return "听不懂喵，能听明白的只有加入游戏什么的"
    else:
        # 单人的功能
        data = json_opt.GetJson(user_id,is_group,group_id)
        if((data["status"] != "mahjong17") and (data["status"] != "none")):
            return "当前在进行其他任务哦"
        elif(data["status"] == "none"):
            return "请在群聊中开启游戏"
        elif(data["status"] == "mahjong17"):
            group_id = data["data"]["group_id"]
            data = json_opt.GetJson(user_id,True,group_id)
            mahjong17_data = data["data"]
            
            if(not mahjong17_data["game_start"]):
                return "游戏暂未开始"
            if(len(message)<=1):
                return "缺少需要整理或者打出的牌"
            if(mahjong17_data["turn"] == -1):
                playerGameId = -1
                if(mahjong17_data["player_id"][0] == user_id):
                    playerGameId = 0
                elif(mahjong17_data["player_id"][1] == user_id):
                    playerGameId = 1
                if(playerGameId == -1):
                    return "出问题了呜呜"
                if(mahjong17_data["hand_tiles"][playerGameId][0] != -1):
                    return "已经选好牌了，请等待对手选牌"
                selectTiles = message[1].strip()
                count = 0
                mahjong17_data["hand_tiles"][playerGameId][0] = 0
                select_num = [0,0,0,0,0,0,0,0,0,0]
                select_tile = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
                for c in selectTiles:
                    if(c.isdecimal()):
                        select_num[int(c)]+=1
                    elif(c == 'm' or c == 'p' or c == 's' or c == 'z'):
                        base = 0
                        if(c == 'p'):
                            base = 10
                        if(c == 's'):
                            base = 20
                        if(c == 'z'):
                            base = 30
                            if(select_num[0]+select_num[8]+select_num[9]>0):
                                return "有不认识的字牌"
                        for i in range(10):
                            if(select_num[i] == 0):
                                continue
                            select_tile[i+base] += select_num[i]
                            select_num[i] = 0
                    else:
                        return "选择牌的格式不正确"
                if(selectTiles[-1] != 'm' and selectTiles[-1] != 'p' and selectTiles[-1] != 's' and selectTiles[-1] != 'z'):
                    return "选择牌的格式不正确"
                count = 0
                for i in select_tile:
                    count += i
                if(count != 13):
                    return "选择的牌数需要为13张"
                for i in range(38):
                    if(mahjong17_data["tiles"][playerGameId][i] < select_tile[i]):
                        return "选择了自己未拥有的牌"
                    mahjong17_data["left_tiles"][playerGameId][i] = mahjong17_data["tiles"][playerGameId][i] - select_tile[i]
                    mahjong17_data["hand_tiles"][playerGameId][i] = select_tile[i]
                if(mahjong17_data["hand_tiles"][1-playerGameId][0] != -1):
                    mahjong17_data["turn"] = 0
                    send.sendTextToPrivate(mahjong17_data["player_id"][mahjong17_data["player_turn"]],"请打出第一张牌")
                    json_opt.SetJson(user_id,True,group_id,data)
                    SendTileToPlayer(mahjong17_data["player_id"][0],False,group_id)
                    SendTileToGroup(user_id,True,group_id)
                json_opt.SetJson(user_id,True,group_id,data)
                return "选牌完毕"
            else:
                playerGameId = -1
                if(mahjong17_data["player_id"][0] == user_id):
                    playerGameId = 0
                elif(mahjong17_data["player_id"][1] == user_id):
                    playerGameId = 1
                if(playerGameId != mahjong17_data["player_turn"]):
                    return "当前不是你的回合"
                selectTake = message[1].strip()
                if(selectTake == "rong" or selectTake == "荣" or selectTake == "和" or selectTake == "荣和"):
                    send.sendTextToGroup(group_id,mahjong17_data["player_name"][playerGameId]+"宣布荣和")
                    SendEndToGroup(user_id,True,group_id)
                    send.sendTextToPrivate(mahjong17_data["player_id"][1-playerGameId],"对手宣布荣和")
                    if(mahjong17_data["player_turn"] == 0):
                        if(mahjong17_data["turn"]== 0):
                            EndGame(user_id,True,group_id)
                            send.sendTextToGroup(group_id,"但是根本没人打牌，意思是"+str(mahjong17_data["player_name"][0])+"直接投了说是")
                        else:
                            cut = mahjong17_data["take_tiles"][1][mahjong17_data["turn"]-1]
                    else:
                        cut = mahjong17_data["take_tiles"][0][mahjong17_data["turn"]]
                    GetPoints(mahjong17_data["hand_tiles"][playerGameId],cut,mahjong17_data["dora"],group_id)
                    
                    EndGame(user_id,True,group_id)
                    return ""
                if(mahjong17_data["turn"] == 17):
                    if(selectTake == "pass" or selectTake == "过" or selectTake == "流局"):
                        send.sendTextToGroup(group_id,"流局")
                        send.sendTextToPrivate(mahjong17_data["player_name"][1-playerGameId],"流局")
                        SendEndToGroup(user_id,True,group_id)
                        EndGame(user_id,True,group_id)
                        return ""
                    else:
                        return "当前只能选择荣和或者流局"
                if(len(selectTake)!=2):
                    return "无法识别打出的牌"
                if(not selectTake[0].isdecimal()):
                    return "无法识别打出的牌"
                if(selectTake[1] != 'm' and selectTake[1] != 's' and selectTake[1] != 'p' and selectTake[1] != 'z'):
                    return "无法识别打出的牌"
                tile = int(selectTake[0]) 
                if(selectTake[1] == 'p'):
                    tile += 10
                if(selectTake[1] == 's'):
                    tile += 20
                if(selectTake[1] == 'z'):
                    if(tile == 0 or tile == 8 or tile == 9):
                        return "无法识别打出的牌"
                    tile += 30
                if(mahjong17_data["left_tiles"][playerGameId][tile] == 0):
                    return "剩余手牌中没有这张牌"
                mahjong17_data["left_tiles"][playerGameId][tile] -= 1
                mahjong17_data["take_tiles"][playerGameId][mahjong17_data["turn"]] = tile
                mahjong17_data["player_turn"] += 1 
                if(mahjong17_data["player_turn"] == 2):
                    mahjong17_data["player_turn"] = 0
                    mahjong17_data["turn"] += 1
                send.sendTextToPrivate(mahjong17_data["player_id"][mahjong17_data["player_turn"]],"对手打出"+str(selectTake))
                json_opt.SetJson(user_id,True,group_id,data)
                SendTileToPlayer(mahjong17_data["player_id"][mahjong17_data["player_turn"]],False,group_id)
                SendTileToGroup(user_id,True,group_id)
                
                return "你打出了" + str(selectTake)
    return

def SetGame(user_id,is_group,group_id,user_name):
    data =  {
        "status": "mahjong17",
        "data": {
            "game_start":False,
            "player_id":[user_id,0],
            "player_name":[user_name,""],
            "player_num":2,
            "turn":-1,
            "player_turn":0,
            "furiten":[False,False],
            "dora":[-1,-1],
            "tiles":[[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]],
            "hand_tiles":[[-1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[-1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]],
            "left_tiles":[[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]],
            "take_tiles":[[-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1],[-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1]],
        },
        "group_bind":True
    }
    player_data = {
        "status": "mahjong17",
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
    return "准备十七步麻将，"+user_name+"加入游戏，当前1名玩家。"

def StartGame(user_id,is_group,group_id,user_name):
    data2 = json_opt.GetJson(user_id,False,group_id)
    if(data2["status"] != "none"):
        return "想要加入游戏的玩家当前在进行其他任务。"
    data = json_opt.GetJson(user_id,is_group,group_id)
    mahjong17_data = data["data"]
    if(mahjong17_data["player_id"][1] != 0):
        return "游戏已经开始了"
    if(mahjong17_data["player_id"][0] == user_id):
        return "你已经在准备中"
    mahjong17_data["player_id"][1] = user_id
    mahjong17_data["player_name"][1] = user_name
    
    tileMountain= []
    for i in range(1,10):
        for j in range(4):
            tileMountain.append(i)
    for i in range(11,20):
        for j in range(4):
            tileMountain.append(i)
    for i in range(21,30):
        for j in range(4):
            tileMountain.append(i)
    for i in range(31,38):
        for j in range(4):
            tileMountain.append(i)
    tileMountain[16] = 0
    tileMountain[52] = 10
    tileMountain[88] = 20            
    for i in range(136):
        change = random.randint(i,135)
        temp = tileMountain[i]
        tileMountain[i] = tileMountain[change]
        tileMountain[change] = temp
    
    for i in range(34):
        mahjong17_data["tiles"][0][tileMountain[i]] += 1
        mahjong17_data["tiles"][1][tileMountain[i + 34]] += 1
        
    mahjong17_data["dora"] = [tileMountain[68],tileMountain[69]]
    mahjong17_data["game_start"] = True
    json_opt.SetJson(user_id,is_group,group_id,data)
    player_data = {
        "status": "mahjong17",
        "data":{
            "group_id":group_id
        },
        "group_bind":True
    }
    json_opt.SetJson(user_id,False,group_id,player_data)
    
    doraNum = tileMountain[68]
    dora = str(doraNum%10)
    if(int(doraNum / 10) == 0):
        dora += "m"
    if(int(doraNum / 10) == 1):
        dora += "p"
    if(int(doraNum / 10) == 2):
        dora += "s"
    if(int(doraNum / 10) == 3):
        dora += "z"
    Send34TileToPlayer(user_id,is_group,group_id,dora)
    return "十七步麻将开始，双方请在私聊中组建手牌。本局宝牌指示牌为" + dora



# # 总数
# def GetPoints(handtiles,rong,dora):
#     doraNum = dora[0]
#     dorao = str(doraNum%10)
#     if(int(doraNum / 10) == 0):
#         dorao += "m"
#     if(int(doraNum / 10) == 1):
#         dorao += "p"
#     if(int(doraNum / 10) == 2):
#         dorao += "s"
#     if(int(doraNum / 10) == 3):
#         dorao += "z"
#     doraNum = dora[0]
#     dorai = str(doraNum%10)
#     if(int(doraNum / 10) == 0):
#         dorai += "m"
#     if(int(doraNum / 10) == 1):
#         dorai += "p"
#     if(int(doraNum / 10) == 2):
#         dorai += "s"
#     if(int(doraNum / 10) == 3):
#         dorai += "z"
    
#     return "算分还没做，唉,自己算一下吧，宝牌指示牌是"+str(dorao)+",里宝牌是"+str(dorai)

def GetPoints(handtiles,cut,dora,group_id):
    handtiles_draw = handtiles.copy()
    tiles = handtiles.copy()
    tiles[cut] += 1
    redDoraNum = 0
    if(tiles[0] == 1):
        tiles[0] = 0
        tiles[5] += 1
        redDoraNum += 1
    if(tiles[10] == 1):
        tiles[10] = 0
        tiles[15] += 1
        redDoraNum += 1
    if(tiles[20] == 1):
        tiles[20] = 0
        tiles[25] += 1
        redDoraNum += 1

    if(handtiles[0] == 1):
        handtiles[0] = 0
        handtiles[5] += 1
    if(handtiles[10] == 1):
        handtiles[10] = 0
        handtiles[15] += 1
    if(handtiles[20] == 1):
        handtiles[20] = 0
        handtiles[25] += 1
    oDora = doraTo[dora[0]]
    oDoraNum = tiles[oDora]
    iDora = doraTo[dora[1]]
    iDoraNum = tiles[iDora]
    types = GetType(tiles,[],[],[])
    qidui = GetQidui(tiles)
    
    maxScore = 0
    maxFu = 0
    maxFan = 0
    maxFans = []
    
    if(tiles[1]*tiles[9]*tiles[11]*tiles[19]*tiles[21]*tiles[29]*tiles[31]*tiles[32]*tiles[33]*tiles[34]*tiles[35]*tiles[36]*tiles[37] == 2):
        if(tiles[cut] == 1):
            maxScore = 32000
            maxFu = 25
            maxFan = 100
            maxFans = ["国士无双"]
        else:
            maxScore = 64000
            maxFu = 25
            maxFan = 200
            maxFans = ["国士无双十三面"]
            
    for l in types:
        shunzi = l[0]
        kezi = l[1]
        quetou = l[2]
        
        score = 0
        fu = GetFu(shunzi,kezi,quetou,cut)
        fan = 0
        fans = []
        
        if((35 in kezi) and(36 in kezi) and(37 in kezi)):
            score += 32000
            fan += 100
            fans.append("大三元")
        for i in range(0,21,10):
            leave = abs(handtiles[1 + i]-3) + abs(handtiles[9 + i]-3) + abs(handtiles[2 + i]-1) + abs(handtiles[3 + i]-1) + abs(handtiles[4 + i]-1) + abs(handtiles[5 + i]-1) + abs(handtiles[6 + i]-1) + abs(handtiles[7 + i]==1) + abs(handtiles[8 + i]-1)
            if((leave == 0) and (cut > i) and (cut <= i + 9)):
                score += 64000
                fan += 200
                fans.append("纯正九莲宝灯")
            if((leave == 2) and (handtiles[1 + i]+handtiles[2 + i]+handtiles[3 + i]+handtiles[4 + i]+handtiles[5 + i]+handtiles[6 + i]+handtiles[7 + i]+handtiles[8 + i]+handtiles[9 + i] == 13)):
                if((cut - i == 1) or (cut - i == 9)):
                    if(handtiles[cut] == 2):
                        score += 32000
                        fan += 100
                        fans.append("九莲宝灯")
                else:
                    if(handtiles[cut] == 0):
                        score += 32000
                        fan += 100
                        fans.append("九莲宝灯")
        if(tiles[31]+tiles[32]+tiles[33]+tiles[34]+tiles[35]+tiles[36]+tiles[37] == 14):
            score += 32000
            fan += 100
            fans.append("字一色")
        if(tiles[22]+tiles[23]+tiles[24]+tiles[26]+tiles[28]+tiles[36] == 14):
            score += 32000
            fan += 100
            fans.append("绿一色")
        if(tiles[1]+tiles[9]+tiles[11]+tiles[19]+tiles[21]+tiles[29] == 14):
            score += 32000
            fan += 100
            fans.append("清老头")
        if(tiles[31]+tiles[32]+tiles[33]+tiles[34] == 11):
            score += 32000
            fan += 100
            fans.append("小四喜")
        if(len(kezi) == 4 and tiles[cut] == 2):
            score += 64000
            fan += 200
            fans.append("四暗刻单骑")
        if(tiles[31]+tiles[32]+tiles[33]+tiles[34] == 12):
            score += 64000
            fan += 200
            fans.append("大四喜")
            
        if(fan != 0):
            if(score > maxScore):
                maxScore = score
                maxFu = fu
                maxFan = fan
                maxFans = fans
            continue
        
        fan += 1
        fans.append(["立直","1番"])
        if(tiles[1]+tiles[9]+tiles[11]+tiles[19]+tiles[21]+tiles[29]+tiles[31]+tiles[32]+tiles[33]+tiles[34]+tiles[35]+tiles[36]+tiles[37]==0):
            fan += 1
            fans.append(["断幺九","1番"])
        if(tiles[32] == 3):
            fan += 1
            fans.append(["自风牌：南","1番"])
        if(tiles[31] == 3):
            fan += 1
            fans.append(["场风牌：东","1番"])
        if(tiles[35] == 3):
            fan += 1
            fans.append(["三元牌：白","1番"])
        if(tiles[36] == 3):
            fan += 1
            fans.append(["三元牌：发","1番"])
        if(tiles[37] == 3):
            fan += 1
            fans.append(["三元牌：中","1番"])
        if(len(shunzi) == 4):
            for i in shunzi:
                if(((i == cut) and (i%10 < 7))or((i == cut-2) and (i%10 > 1))):
                    if(quetou[0] != 31 and quetou[0] != 32 and quetou[0] != 35 and quetou[0] != 36 and quetou[0] != 37):
                        fan += 1
                        fans.append(["平和","1番"])
                        fu = 30
                        break
        yibeikouCount = 0
        for i in range(len(shunzi)):
            for j in range(i+1,len(shunzi)):
                if(shunzi[i] == shunzi[j]):
                    yibeikouCount += 1
        if((yibeikouCount == 1) or (yibeikouCount == 3)):
            fan += 1
            fans.append(["一杯口","1番"])
        if(len(kezi)>=3):
            for i in range(1,10):
                if((i in kezi) and ((i+10) in kezi) and ((20+i) in kezi)):
                    fan += 2
                    fans.append(["三色同刻","2番"])
        if(len(kezi) == 4):
            fan += 2
            fans.append(["对对和","2番"])
            fan += 2
            fans.append(["三暗刻","2番"])
        if((len(kezi) == 3) and (not(cut in kezi))):
            fan += 2
            fans.append(["三暗刻","2番"])
        if(tiles[35]+tiles[36]+tiles[37]==8):
            fan += 2
            fans.append(["小三元","2番"])
            
        chunquanJudge = True
        for i in shunzi:
            if((i%10 != 1)and(i%10 !=7)):
                chunquanJudge = False
                break
        for i in kezi:
            if(((i%10 != 1)and(i%10 !=9))or(i>30)):
                chunquanJudge = False
                break
        if(((quetou[0]%10 != 1)and(quetou[0]%10 !=9))or(quetou[0]>30)):
            chunquanJudge = False
        
            
        if(tiles[1]+tiles[9]+tiles[11]+tiles[19]+tiles[21]+tiles[29]+tiles[31]+tiles[32]+tiles[33]+tiles[34]+tiles[35]+tiles[36]+tiles[37]==14):
            fan += 2
            fans.append(["混老头","2番"])
        else:
            judge = True
            if(chunquanJudge):
                judge = False
            for i in shunzi:
                if((i%10 != 1)and(i%10 !=7)):
                    judge = False
                    break
            for i in kezi:
                if((i%10 != 1)and(i%10 !=9)and(i<30)):
                    judge = False
                    break
            if(quetou[0]%10 != 1)and(quetou[0]%10 !=9)and(quetou[0]<30):
                judge = False
            if(judge):
                fan += 2
                fans.append(["混全带幺九","2番"])
        for i in range(0,21,10):
            if(((i+1)in shunzi) and ((i+4)in shunzi) and ((i+7)in shunzi)):
                fan += 2
                fans.append(["一气通贯","2番"])
        for i in range(1,8):
            if((i in shunzi) and ((i+10) in shunzi) and ((20+i) in shunzi)):
                fan += 2
                fans.append(["三色同顺","2番"])
        if((yibeikouCount == 2)or(yibeikouCount == 6)):
            fan += 3
            fans.append(["二杯口","3番"])
        
        if(chunquanJudge):
            fan += 3
            fans.append(["纯全带幺九","3番"])
        for i in range(0,21,10):
            if(tiles[i+1]+tiles[i+2]+tiles[i+3]+tiles[i+4]+tiles[i+5]+tiles[i+6]+tiles[i+7]+tiles[i+8]+tiles[i+9] == 14):
                fan += 6
                fans.append(["清一色","6番"])
            elif(tiles[i+1]+tiles[i+2]+tiles[i+3]+tiles[i+4]+tiles[i+5]+tiles[i+6]+tiles[i+7]+tiles[i+8]+tiles[i+9]+tiles[31]+tiles[32]+tiles[33]+tiles[34]+tiles[35]+tiles[36]+tiles[37] == 14):
                fan += 3
                fans.append(["混一色","3番"])
        if(oDoraNum != 0):
            fan += oDoraNum
            fans.append(["宝牌",str(oDoraNum)+"番"])
        if(redDoraNum != 0):
            fan += redDoraNum
            fans.append(["红宝牌",str(redDoraNum)+"番"])
        if(iDoraNum != 0):
            fan += iDoraNum
            fans.append(["里宝牌",str(iDoraNum)+"番"])
        
        
        if(fan == 1):
            if(fu == 30):
                score = 1000
            if(fu == 40):
                score = 1300
            if(fu == 50):
                score = 1600
            if(fu == 60):
                score = 2000
            if(fu == 70):
                score = 2300
        if(fan == 2):
            if(fu == 30):
                score = 2000
            if(fu == 40):
                score = 2600
            if(fu == 50):
                score = 3200
            if(fu == 60):
                score = 3900
            if(fu == 70):
                score = 4500
        if(fan == 3):
            if(fu == 30):
                score = 3900
            if(fu == 40):
                score = 5200
            if(fu == 50):
                score = 6400
            if(fu == 60):
                score = 8000
            if(fu == 70):
                score = 8000
        if(fan == 4):
            if(fu == 30):
                score = 8000
            else:
                score = 8000
        if(fan == 5):
            score = 8000
        if(fan >= 6):
            score = 12000
        if(fan >= 8):
            score = 16000
        if(fan >= 11):
            score = 24000
        if(fan >= 13):
            score = 32000
        if(score > maxScore):
            maxScore = score
            maxFu = fu
            maxFan = fan
            maxFans = fans
        
    if(len(qidui) != 0):
        if(qidui[0] == 31):
            maxScore = 32000
            maxFu = 25
            maxFan = 100
            maxFans = ["字一色"]
            
        score = 0
        fu = 25
        fan = 0
        fans = []
        
        fan += 1
        fans.append(["立直","1番"])
        if(tiles[1]+tiles[9]+tiles[11]+tiles[19]+tiles[21]+tiles[29]+tiles[31]+tiles[32]+tiles[33]+tiles[34]+tiles[35]+tiles[36]+tiles[37]==0):
            fan += 1
            fans.append(["断幺九","1番"])
        fan += 2
        fans.append(["七对","2番"])
        if(tiles[1]+tiles[9]+tiles[11]+tiles[19]+tiles[21]+tiles[29]+tiles[31]+tiles[32]+tiles[33]+tiles[34]+tiles[35]+tiles[36]+tiles[37]==14):
            fan += 2
            fans.append(["混老头","2番"])
        for i in range(0,21,10):
            if(tiles[i+1]+tiles[i+2]+tiles[i+3]+tiles[i+4]+tiles[i+5]+tiles[i+6]+tiles[i+7]+tiles[i+8]+tiles[i+9] == 14):
                fan += 6
                fans.append(["清一色","6番"])
            elif(tiles[i+1]+tiles[i+2]+tiles[i+3]+tiles[i+4]+tiles[i+5]+tiles[i+6]+tiles[i+7]+tiles[i+8]+tiles[i+9]+tiles[31]+tiles[32]+tiles[33]+tiles[34]+tiles[35]+tiles[36]+tiles[37] == 14):
                fan += 3
                fans.append(["混一色","3番"])
        if(oDoraNum != 0):
            fan += oDoraNum
            fans.append(["宝牌",str(oDoraNum)+"番"])
        if(redDoraNum != 0):
            fan += redDoraNum
            fans.append(["红宝牌",str(redDoraNum)+"番"])
        if(iDoraNum != 0):
            fan += iDoraNum
            fans.append(["里宝牌",str(iDoraNum)+"番"])
        

        if(fan == 3):
            score = 3200
        if(fan == 4):
            score = 6400
        if(fan == 5):
            score = 8000
        if(fan >= 6):
            score = 12000
        if(fan >= 8):
            score = 16000
        if(fan >= 11):
            score = 24000
        if(fan >= 13):
            score = 32000
        if(score > maxScore):
            maxScore = score
            maxFu = fu
            maxFan = fan
            maxFans = fans
            
    minSize = 190        
    if(maxFan<100 and maxFan > 0):
        minSize = 230
    image = Image.new(mode='RGB',size=(660,max(minSize,150 + len(maxFans) * 40)),color="SteelBlue")
    draw = ImageDraw.Draw(image)
    font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
    font = ImageFont.truetype(font_path,25)
    draw.text((20,5),"宝牌指示牌","BLACK",font)
    draw.text((200,5),"里宝指示牌","BLACK",font)
    tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(dora[0])+".png")
    image.paste(tile_photo,(150,5))
    tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(dora[1])+".png")
    image.paste(tile_photo,(330,5))
    
    loc = 0
    for i in range(38):
        if(i % 10 == 0):
            continue
        if(i % 10 == 5):
            if(handtiles_draw[i-5] == 1):
                tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i-5)+".png")
                image.paste(tile_photo,(20+43*loc,70))
                loc += 1
        for j in range(handtiles_draw[i]):
            tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
            image.paste(tile_photo,(20+43*loc,70))
            loc += 1
    tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(cut)+".png")
    image.paste(tile_photo,(600,70))
    
    if(maxFan >= 100):
        loc = 0
        for i in maxFans:
            draw.text((20,140 + loc * 40),i,"BLACK",font)
            loc += 1
    else:
        loc = 0
        for i in maxFans:
            draw.text((20,140 + loc * 40),i[0],"BLACK",font)
            draw.text((180,140 + loc * 40),i[1],"BLACK",font)
            loc += 1
    if(maxFan < 100 and maxFan>0):
        draw.text((350,140),str(maxFu)+"符"+str(maxFan)+"番","BLACK",font)
        draw.text((350,180),str(maxScore)+"点","BLACK",font)
    else:
        if(maxFan == 100):
            draw.text((350,140),"役满","BLACK",font)
        if(maxFan == 200):
            draw.text((350,140),"两倍役满","BLACK",font)
        if(maxFan == 300):
            draw.text((350,140),"三倍役满","BLACK",font)
        if(maxFan == 400):
            draw.text((350,140),"四倍役满","BLACK",font)
        if(maxFan == 500):
            draw.text((350,140),"五倍役满","BLACK",font)
    if(maxFan == 0):
        draw.text((350,140),"诈胡","BLACK",font)
    
    file_path = photo_opt.SavePhoto(0,True,group_id,image)
    send.sendImgToGroup(group_id,file_path)
    
    
    return 

def GetType(tiles, shunzi, kezi, quetou):
    if(len(shunzi)+len(kezi)+len(quetou) == 5):
        return [[shunzi,kezi,quetou]]
    result = []
    for i in range(38):
        if (tiles[i] != 0):
            if ((tiles[i] >= 3)):
                temptiles = tiles.copy()
                temptiles[i] -= 3
                tempkezi = kezi.copy()
                tempkezi.append(i)
                tempresult = GetType(temptiles, shunzi, tempkezi, quetou)
                result += tempresult
            if ((tiles[i] >= 2) and (len(quetou) == 0)):
                temptiles = tiles.copy()
                temptiles[i] -= 2
                tempquetou = quetou.copy()
                tempquetou.append(i)
                tempresult = GetType(temptiles,shunzi, kezi, tempquetou)
                result += tempresult
            if ((i < 28) and (tiles[i] != 0) and (tiles[i + 1] != 0) and (tiles[i + 2] != 0)):
                temptiles = tiles.copy()
                temptiles[i]-=1
                temptiles[i + 1]-=1
                temptiles[i + 2]-=1
                tempshunzi = shunzi.copy()
                tempshunzi.append(i)
                tempresult = GetType(temptiles, tempshunzi, kezi, quetou)
                result += tempresult
            break
    return result

def GetQidui(tiles):
    qidui = []
    for i in tiles:
        if i == 0:
            continue
        elif i == 2:
            qidui.append(i)
        else:
            return []
    return qidui

def GetFu(shunzi,kezi,quetou,cut):
    fu = 30
    for i in kezi:
        if((i%10 == 1) or (i % 10==9) or (i > 30)):
            fu += 8
            if(cut == i):
                fu -= 4
                for j in shunzi:
                    if ((j == cut) or (j == cut - 1) or (j == cut - 2)):
                        fu += 4
        else:
            fu += 4
            if(cut == i):
                fu -= 2
                for j in shunzi:
                    if ((j == cut) or (j == cut - 1) or (j == cut - 2)):
                        fu += 2
    if(quetou[0] == cut):
        fu += 2
    else:
        for i in shunzi:
            if (i== cut -2)or((i%10 == 1) and (i==cut))or((i%10 == 7) and (i==cut)):
                fu +=2
                break
    if(quetou[0] == 31 or quetou[0] == 32 or quetou[0] == 35 or quetou[0] == 36 or quetou[0] == 37):
        fu += 2
    
    return fu + 9 - (fu + 9)% 10

def Send34TileToPlayer(user_id,is_group,group_id,dora):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mahjong17_data = data["data"]
    tiles = mahjong17_data["tiles"]
    
    image = Image.new(mode='RGB',size=(734,135),color="SteelBlue")
    loc = 0
    for i in range(38):
        if(i % 10 == 0):
            continue
        if(i % 10 == 5):
            if(tiles[0][i-5] == 1):
                tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i-5)+".png")
                if(loc <= 16):
                    image.paste(tile_photo,(3+43*loc,5))
                else:
                    image.paste(tile_photo,(3+43*(loc-17),70))
                loc += 1
        if(tiles[0][i] != 0):
            num = tiles[0][i]
            tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
            for j in range(num):
                if(loc <= 16):
                    image.paste(tile_photo,(3+43*loc,5))
                else:
                    image.paste(tile_photo,(3+43*(loc-17),70))
                loc += 1
    file_path = photo_opt.SavePhoto(mahjong17_data["player_id"][0],False,group_id,image)
    send.sendImg(mahjong17_data["player_id"][0],False,group_id,file_path)
    image = Image.new(mode='RGB',size=(734,135),color="SteelBlue")
    loc = 0
    for i in range(38):
        if(i % 10 == 0):
            continue
        if(i % 10 == 5):
            if(tiles[1][i-5] == 1):
                tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i-5)+".png")
                if(loc <= 16):
                    image.paste(tile_photo,(3+43*loc,5))
                else:
                    image.paste(tile_photo,(3+43*(loc-17),70))
                loc += 1
        if(tiles[1][i] != 0):
            num = tiles[1][i]
            tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
            for j in range(num):
                if(loc <= 16):
                    image.paste(tile_photo,(3+43*loc,5))
                else:
                    image.paste(tile_photo,(3+43*(loc-17),70))
                loc += 1
    file_path = photo_opt.SavePhoto(mahjong17_data["player_id"][1],False,group_id,image)
    send.sendImg(mahjong17_data["player_id"][1],False,group_id,file_path)
    send.sendTextToPrivate(mahjong17_data["player_id"][0],"本局宝牌指示牌为"+dora)
    send.sendTextToPrivate(mahjong17_data["player_id"][1],"本局宝牌指示牌为"+dora)
    return 

def SendTileToPlayer(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,True,group_id)
    mahjong17_data = data["data"]
    handTiles = mahjong17_data["hand_tiles"]
    leftTiles = mahjong17_data["left_tiles"]
    takeTiles = mahjong17_data["take_tiles"]
    playerGameId = -1
    if(mahjong17_data["player_id"][0] == user_id):
        playerGameId = 0
    elif(mahjong17_data["player_id"][1] == user_id):
        playerGameId = 1
    
    image = Image.new(mode='RGB',size=(1020,270),color="SteelBlue")
    draw = ImageDraw.Draw(image)
    font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
    font = ImageFont.truetype(font_path,25)
    
    draw.text((5,5),"对手舍牌","BLACK",font)
    draw.text((5,70),"己方舍牌","BLACK",font)
    draw.text((5,135),"舍牌候补","BLACK",font)
    draw.text((5,200),"己方手牌","BLACK",font)

    loc = 0
    for i in takeTiles[1-playerGameId]:
        if(i == -1):
            break
        tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
        image.paste(tile_photo,(110+43*loc,5))
        loc += 1
        
    loc = 0
    for i in takeTiles[playerGameId]:
        if(i == -1):
            break
        tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
        image.paste(tile_photo,(110+43*loc,70))
        loc += 1
    
    loc = 0
    for i in range(38):
        if(i % 10 == 0):
            continue
        if(i % 10 == 5):
            if(leftTiles[playerGameId][i-5] == 1):
                tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i-5)+".png")
                image.paste(tile_photo,(110+43*loc,135))
                loc += 1
        if(leftTiles[playerGameId][i] != 0):
            num = leftTiles[playerGameId][i]
            tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
            for j in range(num):
                image.paste(tile_photo,(110+43*loc,135))
                loc += 1
                
    loc = 0
    for i in range(38):
        if(i % 10 == 0):
            continue
        if(i % 10 == 5):
            if(handTiles[playerGameId][i-5] == 1):
                tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i-5)+".png")
                image.paste(tile_photo,(110+43*loc,200))
                loc += 1
        if(handTiles[playerGameId][i] != 0):
            num = handTiles[playerGameId][i]
            tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
            for j in range(num):
                image.paste(tile_photo,(110+43*loc,200))
                loc += 1
    file_path = photo_opt.SavePhoto(user_id,False,group_id,image)
    send.sendImg(user_id,False,group_id,file_path)
    return 

def SendTileToGroup(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mahjong17_data = data["data"]
    takeTiles = mahjong17_data["take_tiles"]
    l = mahjong17_data["turn"]
    image = Image.new(mode='RGB',size=(260 + 43 * l,135),color="SteelBlue")
    draw = ImageDraw.Draw(image)
    font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
    font = ImageFont.truetype(font_path,25)
    draw.text((5,5),mahjong17_data["player_name"][0],"BLACK",font)
    draw.text((5,70),mahjong17_data["player_name"][1],"BLACK",font)
    
    loc = 0
    for i in takeTiles[0]:
        if(i == -1):
            break
        tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
        image.paste(tile_photo,(210+43*loc,5))
        loc += 1
        
    loc = 0
    for i in takeTiles[1]:
        if(i == -1):
            break
        tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
        image.paste(tile_photo,(210+43*loc,70))
        loc += 1
    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
    send.sendImg(user_id,is_group,group_id,file_path)
    return 

def SendEndToGroup(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mahjong17_data = data["data"]
    handTiles = mahjong17_data["hand_tiles"]
    leftTiles = mahjong17_data["left_tiles"]
    takeTiles = mahjong17_data["take_tiles"]
    
    
    image = Image.new(mode='RGB',size=(1020,460),color="SteelBlue")
    draw = ImageDraw.Draw(image)
    font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
    font = ImageFont.truetype(font_path,25)
    
    draw.text((5,5),mahjong17_data["player_name"][0],"BLACK",font)
    draw.text((5,35),"舍牌","BLACK",font)
    draw.text((5,100),"候补","BLACK",font)
    draw.text((5,165),"手牌","BLACK",font)
    
    draw.text((5,230),mahjong17_data["player_name"][1],"BLACK",font)
    draw.text((5,260),"舍牌","BLACK",font)
    draw.text((5,325),"候补","BLACK",font)
    draw.text((5,390),"手牌","BLACK",font)

    loc = 0
    for i in takeTiles[0]:
        if(i == -1):
            break
        tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
        image.paste(tile_photo,(60+43*loc,35))
        loc += 1
        
    loc = 0
    for i in range(38):
        if(i % 10 == 0):
            continue
        if(i % 10 == 5):
            if(leftTiles[0][i-5] == 1):
                tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i-5)+".png")
                image.paste(tile_photo,(60+43*loc,100))
                loc += 1
        if(leftTiles[0][i] != 0):
            num = leftTiles[0][i]
            tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
            for j in range(num):
                image.paste(tile_photo,(60+43*loc,100))
                loc += 1
                
    loc = 0
    for i in range(38):
        if(i % 10 == 0):
            continue
        if(i % 10 == 5):
            if(handTiles[0][i-5] == 1):
                tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i-5)+".png")
                image.paste(tile_photo,(60+43*loc,165))
                loc += 1
        if(handTiles[0][i] != 0):
            num = handTiles[0][i]
            tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
            for j in range(num):
                image.paste(tile_photo,(60+43*loc,165))
                loc += 1
    
    
    loc = 0
    for i in takeTiles[1]:
        if(i == -1):
            break
        tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
        image.paste(tile_photo,(60+43*loc,260))
        loc += 1
    
    loc = 0
    for i in range(38):
        if(i % 10 == 0):
            continue
        if(i % 10 == 5):
            if(leftTiles[1][i-5] == 1):
                tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i-5)+".png")
                image.paste(tile_photo,(60+43*loc,325))
                loc += 1
        if(leftTiles[1][i] != 0):
            num = leftTiles[1][i]
            tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
            for j in range(num):
                image.paste(tile_photo,(60+43*loc,325))
                loc += 1
                
    loc = 0
    for i in range(38):
        if(i % 10 == 0):
            continue
        if(i % 10 == 5):
            if(handTiles[1][i-5] == 1):
                tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i-5)+".png")
                image.paste(tile_photo,(60+43*loc,390))
                loc += 1
        if(handTiles[1][i] != 0):
            num = handTiles[1][i]
            tile_photo = Image.open("C:\\mybot\\mahjong\\mj"+str(i)+".png")
            for j in range(num):
                image.paste(tile_photo,(60+43*loc,390))
                loc += 1
    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
    send.sendImg(user_id,is_group,group_id,file_path)
    return

def EndGame(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mahjong17_data = data["data"]
    
    for i in range(mahjong17_data["player_num"]):
        json_opt.ResetJson(mahjong17_data["player_id"][i],False,group_id)
    json_opt.ResetJson(0,True,group_id)
    return