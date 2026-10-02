import random
import copy
from PIL import Image
import send_message as send
import json_opt
import photo_opt

def FullFlush(user_id,is_group,group_id,message):
    status_data = json_opt.GetJson(user_id,is_group,group_id)

    if((status_data["status"]!="fullflush")and(status_data["status"]!="none")):
        return "还在进行其他任务，输入结束/stop，结束任务后开始新的任务"
    if(status_data["status"]=="none"):
        for i in range(5):
            tiles = Generate()
            count = [0,0,0,0,0,0,0,0,0]
            for j in tiles:
                count[j-1] = count[j-1] + 1
            rong = [False,False,False,False,False,False,False,False,False]
            judge = False
            for j in range(9):
                if(count[j]==4):
                    continue
                temp = copy.deepcopy(count)
                temp[j] = temp[j] + 1
                if(JudgeRong(False,temp) or JudgeQidui(temp)):
                    rong[j] = True
                    judge = True
            if(judge):
                break
        status_data = {"status":"fullflush","data":{"tiles":tiles,"answer":rong},"group_bind":False}
        json_opt.SetJson(user_id,is_group,group_id,status_data)
        sendQuestion(tiles,is_group,user_id,group_id)
        return "请判断所有的听牌型，并用清一色/fullflush 所有听的牌数字进行回复（同一答案回复两次算错），没听则回复清一色/fullflush 没听。"

    if(status_data["status"]=="fullflush"):
        answer = status_data["data"]["answer"]
        if(len(message)==1):
            return "没看到答案喵"
        if(message[1]=="没听"):
            if(not(answer[0] or answer[1] or answer[2] or answer[3] or answer[4] or answer[5] or answer[6] or answer[7] or answer[8])):
                json_opt.ResetJson(user_id,is_group,group_id)
                return "答对了，太强力。"
            return "答错了喵。"
        for i in message[1]:
            if(i == " "):
                continue
            elif(i == "1"):
                if(answer[0]):
                    answer[0] = False
                    continue
                else:
                    return "答错了喵"
            elif(i == "2"):
                if(answer[1]):
                    answer[1] = False
                    continue
                else:
                    return "答错了喵"
            elif(i == "3"):
                if(answer[2]):
                    answer[2] = False
                    continue
                else:
                    return "答错了喵"
            elif(i == "4"):
                if(answer[3]):
                    answer[3] = False
                    continue
                else:
                    return "答错了喵"
            elif(i == "5"):
                if(answer[4]):
                    answer[4] = False
                    continue
                else:
                    return "答错了喵"
            elif(i == "6"):
                if(answer[5]):
                    answer[5] = False
                    continue
                else:
                    return "答错了喵"
            elif(i == "7"):
                if(answer[6]):
                    answer[6] = False
                    continue
                else:
                    return "答错了喵"
            elif(i == "8"):
                if(answer[7]):
                    answer[7] = False
                    continue
                else:
                    return "答错了喵"
            elif(i == "9"):
                if(answer[8]):
                    answer[8] = False
                    continue
                else:
                    return "答错了喵"
            else:
                return "出现了意料之外的东西嘞"
        if(not(answer[0] or answer[1] or answer[2] or answer[3] or answer[4] or answer[5] or answer[6] or answer[7] or answer[8])):
            json_opt.ResetJson(user_id,is_group,group_id)
            return "答对了，太强力。"
        return "答错了喵。"

def Generate():
    tiles = []
    for i in range(1,10):
        for j in range(1,5):
            tiles.append(i)
    for i in range(0,13):
        s = random.randint(i,35)
        temp = tiles[s]
        tiles[s] = tiles[i]
        tiles[i] = temp
    tiles2 = tiles[:13]
    tiles2.sort()
    
    return tiles2

def JudgeRong(quetou,tiles):
    if(tiles == [0,0,0,0,0,0,0,0,0]):
        return True
    for i in range(9):
        if(tiles[i]>=3):
            temp = copy.deepcopy(tiles)
            temp[i] = temp[i] - 3
            if(JudgeRong(quetou,temp)):
                return True
        if((tiles[i]>=2) and (not quetou)):
            temp = copy.deepcopy(tiles)
            temp[i] = temp[i] - 2
            if(JudgeRong(not quetou,temp)):
                return True
        if((i<=6) and (tiles[i]*tiles[i+1]*tiles[i+2] != 0)):
            temp = copy.deepcopy(tiles)
            temp[i] = temp[i] - 1
            temp[i+1] = temp[i+1] - 1
            temp[i+2] = temp[i+2] - 1
            if(JudgeRong(quetou,temp)):
                return True
    return False

def JudgeQidui(tiles):
    for i in range(9):
        if(not (tiles[i]==2 or tiles[i]==0)):
            return False
    return True

def sendQuestion(tiles,is_group,user_id,group_id):
    tile_cat = random.randint(0,2)
    images = []
    if(tile_cat == 0):
        images.append(Image.open("C:\\mybot\\mahjong\\mj1.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj2.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj3.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj4.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj5.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj6.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj7.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj8.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj9.png"))
    if(tile_cat == 1):
        images.append(Image.open("C:\\mybot\\mahjong\\mj11.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj12.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj13.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj14.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj15.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj16.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj17.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj18.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj19.png"))
    if(tile_cat == 2):
        images.append(Image.open("C:\\mybot\\mahjong\\mj21.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj22.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj23.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj24.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj25.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj26.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj27.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj28.png"))
        images.append(Image.open("C:\\mybot\\mahjong\\mj29.png"))
    image = Image.new(mode='RGB',size=(562,70),color="green")
    for i in range(13):
        image.paste(images[tiles[i]-1],(3+43*i,5))

    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
    send.sendImg(user_id,is_group,group_id,file_path)
    return
