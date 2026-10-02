import uvicorn
from fastapi import FastAPI, Request
import send_message as send
import simple_function as simple
import random
import os
from volcenginesdkarkruntime import Ark
import requests
import datetime

import full_flush
import flight_chess
import mahjong_gold
import mahjong_17
import mahjong_war
import hardle
import yahtzee
import ucml
import ucmt
import bless
import secret_bless
import tarot
import mahjong_empire
import answer
import threading
import aifig
import leaguetwo
import re
import json
from markdown import markdown
from bs4 import BeautifulSoup

from tts import design_voice

app = FastAPI()

message_id = {"id":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
              "loc":0,
              "message":{},
              "message2":{}}

aimessages=[ ]

groupChat = {}

groupChat2 = {689886013:[],385394206:[],913954208:[],949736354:[],480507946:[],1080341951:[],688132922:[],343761411:[]}
# groupChat2p = {689886013:100,385394206:100,913954208:[]}

aifig2pr = {}
aifig3pr = {}
aifig4pr = {}
aivid2pr = {}

aiResponse = {689886013:{"f":100,"s":"你是一个群聊回复机器人。"},
              385394206:{"f":100,"s":"你是一个群聊回复机器人。"},
              913954208:{"f":100,"s":"你是一个群聊回复机器人。"},
              949736354:{"f":100,"s":"你是一个群聊回复机器人。"},
              480507946:{"f":100,"s":"你是一个群聊回复机器人。"},
              1080341951:{"f":100,"s":"你是一个群聊回复机器人。"},
              688132922:{"f":100,"s":"你是一个群聊回复机器人。"},
              343761411:{"f":100,"s":"你是一个群聊回复机器人。"},}

aisetvoice = ["你是一个年轻活力的女高中生"]

class QQNumberFileManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = []  # 存储长整数数组
        self.read()     # 初始化时自动加载文件数据
    
    def read(self):
        try:
            with open(self.file_path, 'r') as f:
                content = f.read().strip()
                if content:
                    # 安全处理大整数（防止精度丢失）
                    self.data = [int(num.strip()) for num in content.split(',') if num.strip()]
                else:
                    self.data = []
            print(f"成功加载 {len(self.data)} 个长整数")
            return True
        except FileNotFoundError:
            print(f"文件 {self.file_path} 不存在，已自动创建")
            open(self.file_path, 'w').close()
            self.data = []
            return True
        except ValueError as e:
            print(f"文件包含非整数数据: {e}")
            # 只保留有效的整数
            self.data = []
            with open(self.file_path, 'r') as f:
                content = f.read().strip()
                for num_str in content.split(','):
                    num_str = num_str.strip()
                    if num_str:
                        try:
                            self.data.append(int(num_str))
                        except ValueError:
                            print(f"忽略非整数数据: '{num_str}'")
            return len(self.data) > 0
        except Exception as e:
            print(f"读取文件错误: {e}")
            return False
    
    def find(self, number):
        try:
            target = int(number)  # 转换为整数
            return any(num == target for num in self.data)
        except ValueError:
            print(f"错误：'{number}' 不是有效的整数")
            return False
        except TypeError:
            print(f"错误：不支持的类型 {type(number).__name__}")
            return False
    
    def add(self, number):
        try:
            target = int(number)
            if target not in self.data:
                self.data.append(target)
                return True
            print(f"{target} 已存在，未重复添加")
            return False
        except ValueError:
            print(f"错误：无法添加 '{number}'，非整数格式")
            return False
        except TypeError:
            print(f"错误：不支持的类型 {type(number).__name__}")
            return False
    
    def remove(self, number):
        try:
            target = int(number)
            if target in self.data:
                self.data.remove(target)
                return True
            return False
        except ValueError:
            print(f"错误：无法移除 '{number}'，非整数格式")
            return False
        except TypeError:
            print(f"错误：不支持的类型 {type(number).__name__}")
            return False
    
    def save(self):
        try:
            # 对大整数使用字符串直接保存（避免科学计数法）
            content = ','.join(str(num) for num in self.data)
            with open(self.file_path, 'w') as f:
                f.write(content)
            print(f"成功保存 {len(self.data)} 个长整数到文件")
            return True
        except OverflowError:
            print("错误：遇到过大无法处理的整数")
            # 尝试分段保存防止大整数问题
            try:
                with open(self.file_path, 'w') as f:
                    for i, num in enumerate(self.data):
                        if i > 0:
                            f.write(',')
                        f.write(str(num))
                return True
            except Exception as e:
                print(f"分段保存失败: {e}")
                return False
        except Exception as e:
            print(f"保存文件错误: {e}")
            return False
users_ids_re = QQNumberFileManager("users_ids_re.txt")
groups_ids_re = QQNumberFileManager("groups_ids_re.txt")

@app.post("/")
async def root(request: Request):
    data = await request.json()  # 获取事件数据
    if(data["post_type"]=="notice" and data["notice_type"]=="notify" and data["sub_type"]=="poke" and data["target_id"] == 1707925198 and data["user_id"] != 1707925198):
        send.sendPokeToGroup(data["user_id"],data["group_id"])
    if(data["post_type"]!="message" and data["post_type"]!="message_sent"):
        return {}
    
    judge = False
    for i in message_id["id"]:
        if(i == data["message_id"]):
            judge = True
            break
    # 会收到多次报文，只响应第一次
    if(judge):
        return
    else:
        message_id["id"][message_id["loc"]] = data["message_id"]
        message_id["message"][message_id["loc"]] = data["raw_message"]
        message_id["loc"] = (message_id["loc"] + 1)%60
    

    
    instruction = data["raw_message"]
    instruction = instruction.lower()

    user_id = data["user_id"]
    if(user_id == 739954740):
        return
    if(data["message_type"]=="group"):
        is_group = True
        group_id = data["group_id"]
    if(data["message_type"]=="private"):
        is_group = False
        group_id = 0

    if(instruction == "__connecttouselessrobot__"):
        if(is_group):
            groups_ids_re.add(group_id)
            groups_ids_re.save()
        else:
            users_ids_re.add(user_id)
            users_ids_re.save()
        send.sendImgBack(data,"机器人链接")
    if(instruction == "__disconnecttouselessrobot__"):
        if(is_group):
            groups_ids_re.remove(group_id)
            groups_ids_re.save()
        else:
            users_ids_re.remove(user_id)
            users_ids_re.save()
        send.sendImgBack(data,"断开机器人链接")
            
    if(is_group):
        if(not groups_ids_re.find(group_id)):
            return {}
    else:
        if(not users_ids_re.find(user_id)):
            return {}

    # print(data["raw_message"])
    
    user_name = data["sender"]["nickname"]
    if(instruction == "112344567789"):
        send.sendVoiceBack(data,"C:\\mybot\\vt\\design_demo.wav")
    if(instruction=="群聊总结" or instruction == ".gc" or instruction == "/gc" or instruction == "gc"):
        if(is_group):
            if(group_id in groupChat):
                chatMessage = groupChat[group_id]
                del groupChat[group_id]
                
                send.sendTextBack(data,"准备进行群聊记录分析")
                deepseekSummarise(data,chatMessage)
            else:
                groupChat[group_id] = "请不考虑之前的所有内容，帮我风趣幽默地总结下面这段群聊对话，其中可能出现一些不是人类对话的信息，是由于发送了文件，图片等，不用管就行。对话如下：\n"
                send.sendTextBack(data,"开始记录群聊信息")
        return {}
    if(group_id in groupChat and (not "[CQ:" in data["raw_message"])):
        groupChat[group_id] += user_name + ":" + data["raw_message"] + "\n"
        if(len(groupChat[group_id])>10800):
            chatMessage = groupChat[group_id]
            del groupChat[group_id]
            send.sendTextBack(data,"准备进行群聊记录分析")
            deepseekSummarise(data,chatMessage)
    if((group_id == 385394206 or group_id == 689886013 or group_id == 343761411 or group_id == 913954208 or group_id == 949736354 or group_id == 480507946 or group_id == 1080341951 or group_id == 688132922) and (not "[CQ:" in data["raw_message"])):
        groupChat2[group_id].append(user_name + ":" + data["raw_message"])
        while(len(groupChat2[group_id])>5):
            del groupChat2[group_id][0]
        rantmp = random.randint(0, 10000)
        if(rantmp < aiResponse[group_id]["f"]):
            result = "\n".join(groupChat2[group_id])
            result += aiResponse[group_id]["s"] + "请以前面提到的身份对更前面的对话中最后一句进行简单回复，通常大约20字以内，遇到需要详细解释的问题也不要超过100字，请直接进行回复，因为这段话会被当做回复发送，不需要提出例如，我是谁，所以我要回复这样的原因。"
            answer2 = deepseekAnswer(data,result)

            random22 = random.randint(0,3)
            if(random22==100 and group_id == 385394206 and len(answer2)<50):
                saved_path = design_voice(
                    voice_description=aisetvoice[0],
                    preview_text=answer2,
                    output_path="C:\\mybot\\output\\design_demo.wav",
                    output_format="wav",
                    api_key="",  # 已脱敏：MiMo API Key
                )
                send.sendVoiceBack(data,"C:\\mybot\\output\\design_demo.wav")
        if(rantmp >= 9900 and group_id != 913954208 and group_id != 1080341951 and group_id != 688132922 and group_id != 343761411):
            folder_path = 'C:\\mybot\\taleanswer'
            file_names = os.listdir(folder_path)
            stra = ""
            
            for i in range(len(file_names)):
                stra = stra + str(i) + ":" + file_names[i] + "\n"
            result = "\n".join(groupChat2[group_id])
            result += """下面我会给出带编号的文件名，文件名就是文件图片的内容，帮我选择一张适合回复的图片，告诉我编号数字，记住，只需要返回数字即可。\n"""
            result += stra
            choose = deepseekChoose(result)
            match = re.search(r'\d+', choose)  # 查找第一个连续的数字
            choose = match.group() if match else None
            print(choose)
            send.sendImgBack(data,'C:\\mybot\\taleanswer\\'+file_names[int(choose)])
        
    if(user_id in aifig2pr and (not "记录了生成图提示词" == data["raw_message"])):
        
        if "[CQ:image" in data["raw_message"]:
            pattern = r'url=([^,]+)'
            match = re.search(pattern, data["raw_message"])
            if match:
                url = match.group(1)
                url = url.replace('&amp;', '&')
            send.sendTextBack(data,aifig.aifig2(user_id,is_group,group_id,aifig2pr[user_id],user_name,url))
        del aifig2pr[user_id]
        return {}
    if(user_id in aifig3pr and (not "记录了生成图提示词" == data["raw_message"])):
        # print(instruction)
        if "[CQ:image" in data["raw_message"]:
            pattern = r'url=([^,]+)'
            match = re.search(pattern, data["raw_message"])
            if match:
                url = match.group(1)
                url = url.replace('&amp;', '&')
            send.sendTextBack(data,aifig.aifig3(user_id,is_group,group_id,aifig3pr[user_id],user_name,url))
        del aifig3pr[user_id]
        return {}    
    if(user_id in aifig4pr and (not "记录了生成图提示词" == data["raw_message"])):
        # print(instruction)
        if "[CQ:image" in data["raw_message"]:
            pattern = r'url=([^,]+)'
            match = re.search(pattern, data["raw_message"])
            if match:
                url = match.group(1)
                url = url.replace('&amp;', '&')
            send.sendTextBack(data,aifig.aifig4(user_id,is_group,group_id,aifig4pr[user_id],user_name,url))
        del aifig4pr[user_id]
        return {}
    if(user_id in aivid2pr and (not "记录了生成视频提示词" == data["raw_message"])):
        # print(instruction)
        if "[CQ:image" in data["raw_message"]:
            pattern = r'url=([^,]+)'
            match = re.search(pattern, data["raw_message"])
            if match:
                url = match.group(1)
                url = url.replace('&amp;', '&')
            send.sendTextBack(data,aifig.aivid2(user_id,is_group,group_id,aivid2pr[user_id],user_name,url))
        del aivid2pr[user_id]
        return {}
    

    
    if(instruction=="帮助" or instruction == ".help" or instruction == "/help" or instruction == "help"):
        send.sendTextBack(data,simple.Help(""))
        return {}
    if(instruction==".l2t" or instruction == "l2t"):
        leaguetwo.LeagueTwoTeam(user_id,is_group,group_id)
        return {}
    if(instruction==".l1t" or instruction == "l1t"):
        leaguetwo.LeagueOneTeam(user_id,is_group,group_id)
        return {}
    if(instruction==".slt" or instruction == "slt"):
        leaguetwo.SuperLeagueTeam(user_id,is_group,group_id)
        return {}
    if(instruction==".l2p" or instruction == "l2p"):
        leaguetwo.LeaguePlayer(user_id,is_group,group_id,'12586')
        return {}
    elif(instruction=="答案之书" or instruction == ".answer" or instruction == "/answer" or instruction == "answer"):
        send.sendTextBack(data,answer.answer())
        return {}
    elif(instruction=="随机ue" or instruction==".randomue" or instruction=="/randomue" or instruction=="randomue"):
        send.sendImgBack(data,simple.RandomUe())
        return {}
    elif(instruction=="随机hasfin" or instruction==".randomhasfin" or instruction=="/randomhasfin" or instruction=="randomhasfin"):
        send.sendImgBack(data,simple.RandomHasfin())
        return {}
    elif(instruction=="随机半吨" or instruction==".random#" or instruction=="/random#" or instruction=="random#"):
        send.sendImgBack(data,simple.RandomHT())
        return {}
    elif(instruction=="meme" or instruction==".meme" or instruction=="/meme" or instruction=="随机梗图"):
        simple.RandomMeme(user_id,is_group,group_id)
        return {}
    elif(instruction=="结束" or instruction==".stop" or instruction=="/stop" or instruction=="stop"):
        send.sendTextBack(data,simple.Stop(user_id,is_group,group_id))
        return {}
    elif(instruction=="gethat" or instruction==".gethat" or instruction=="/gethat" or instruction=="圣诞帽"):
        send.sendTextBack(data,"https://tools.taurusxin.com/hat/")
        return {}
    elif(instruction=="今日运势" or instruction==".fortune" or instruction=="/fortune" or instruction=="fortune"):
        current_date = datetime.date.today()
        f_1 = hash(str(current_date)+str(user_id)+"123") % 100 + 1
        f_2 = hash(str(current_date)+str(user_id)+"456") % 100 + 1
        fortune = max(f_1,f_2)
        if(user_id == 904994820):
            send.sendTextBack(data,"太坏的小熊猫老师 今日运势："+str(fortune))
        elif(fortune == 1):
            send.sendTextBack(data,user_name+" 今日运势不足2，不予显示")
        else:
            send.sendTextBack(data,user_name+" 今日运势："+str(fortune))
        return {}
    elif(instruction=="今日麻将运势" or instruction==".mjfortune" or instruction=="/mjfortune" or instruction=="mjfortune"):
        current_date = datetime.date.today()
        a = [0,0,0,0]
        for i in range(100):
            f = hash(str(current_date)+str(user_id)+str(i)) % 4
            a[f]+=1
        send.sendTextBack(data,user_name+" 今日顺位概率"+str(a[0])+"-"+str(a[1])+"-"+str(a[2])+"-"+str(a[3]))

        return {}

    elif(instruction=="今日运势-" or instruction==".fortune-" or instruction=="/fortune-" or instruction=="fortune-"):
        current_date = datetime.date.today()
        f_1 = hash(str(current_date)+str(user_id)+"123") % 100 + 1
        f_2 = hash(str(current_date)+str(user_id)+"456") % 100 + 1
        fortune = min(f_1,f_2)
        send.sendTextBack(data,user_name+" 另一个骰子是"+str(fortune))
        return {}
    elif(instruction=="今日运势+" or instruction==".fortune+" or instruction=="/fortune+" or instruction=="fortune+"):
        current_date = datetime.date.today()
        fortune = 0
        for i in range(10):
            f = hash(str(current_date)+str(user_id)+str(i)) % 100000 + 1
            fortune = fortune + hash(str(current_date)+str(user_id)+str(i)) % 100000 + 1
            if(i > 5 and f <= 1000):
                break
        send.sendTextBack(data,user_name+" 今日运势plus:"+str(fortune))
        return {}
    
    message = data["raw_message"].split(" ",1)
    instruction = message[0]
    instruction = instruction.lower()
    if(len(message)>1):
        message[1] = message[1].strip()
    if(len(message) == 0):
        return
    else:
        if(instruction=="帮助" or instruction == ".help" or instruction == "/help" or instruction == "help"):
            send.sendTextBack(data,simple.Help(message[1]))
            return {}
        if(instruction==".l2p" or instruction == "l2p" or instruction == ".lp" or instruction == "lp"):
            leaguetwo.LeaguePlayer(user_id,is_group,group_id,message[1])
            return {}
        if((instruction=="aiset2" or instruction == ".aiset2" or instruction == "/aiset2")and(group_id == 385394206 or group_id == 343761411 or group_id == 689886013 or group_id == 913954208 or group_id == 949736354 or group_id == 480507946 or group_id == 1080341951 or group_id == 688132922)):
            message2 = message[1].split(" ")
            if(len(message2)==2):
                if(not message2[0].isdigit()):
                    send.sendTextBack(data,"回复概率需要设为数字喵。")
                else:
                    num = int(message2[0])
                    num = max(0,num)
                    num = min(2000,num)
                    aiResponse[group_id]["f"]= num
                    aiResponse[group_id]["s"]= message2[1]
                    send.sendTextBack(data,"ai自动回复概率为万分之"+str(num)+",性格设置词为"+message2[1])

            else:
                send.sendTextBack(data,"设置参数有问题喵。")
            return {}
        if(instruction=="ai" or instruction == ".ai" or instruction == "/ai"):
            new_thread = threading.Thread(target=deepseek, args=(data, message))
            new_thread.start()
            send.sendTextBack(data,"唉这个得等一会才有反应，或者没有反应")
            return {}
        if(instruction=="dsc" or instruction == ".dsc" or instruction == "/dsc"):
            if(len(message)<=1):
                send.sendTextBack(data,"请输入steam_id")
                return {}
            steam_id = message[1]
            API_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key=YOUR_STEAM_API_KEY&steamid="+steam_id+"&include_appinfo=true"
            # API_URL = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=YOUR_STEAM_API_KEY&steamid=76561198852284325&format=json"
            print(API_URL)
            response = requests.get(API_URL)
            data2 = response.json()
            print(data2)
            # 提取游戏数据（时长保留两位小数）
            games = data2["response"]["games"]
            msg = "以下是我的steam游戏和游戏时长，请根据游戏的名称与时长信息，专业、深刻且幽默风趣地评价下我的游戏品味，并解析下我的性格特点与内心世界。尽可能多说一些。"
            for game in games:
                name = game.get("name", "Unknown")
                playtime = game.get("playtime_forever", 0) # 单位为分钟
                msg = msg + "游戏名称："+name+",游戏时长:"+str(round(playtime / 60, 2))+"小时."

            new_thread = threading.Thread(target=deepseekcommentgame, args=(data, msg))
            new_thread.start()
            send.sendTextBack(data,"唉这个也得等一会才有反应，或者没有反应")
            return {}
        
        if(instruction=="dsc2" or instruction == ".dsc2" or instruction == "/ds2c"):
            if(len(message)<=1):
                send.sendTextBack(data,"请输入steam_id")
                return {}
            steam_id = message[1]
            API_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key=YOUR_STEAM_API_KEY&steamid="+steam_id+"&include_appinfo=true"
            # API_URL = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key=YOUR_STEAM_API_KEY&steamid=76561198852284325&format=json"
            print(API_URL)
            response = requests.get(API_URL)
            data2 = response.json()
            # 提取游戏数据（时长保留两位小数）
            games = data2["response"]["games"]
            msg = "以下是我的steam游戏和游戏时长，请根据游戏的名称与时长信息，专业、深刻且幽默风趣地评价下我的游戏品味，并解析下我的性格特点与内心世界。尽可能多说一些。"
            for game in games:
                name = game.get("name", "Unknown")
                playtime = game.get("playtime_forever", 0) # 单位为分钟
                if(playtime<1):
                    continue
                msg = msg + "游戏名称："+name+",游戏时长:"+str(round(playtime / 60, 2))+"小时."

            new_thread = threading.Thread(target=deepseekcommentgame, args=(data, msg))
            new_thread.start()
            send.sendTextBack(data,"唉这个也得等一会才有反应，或者没有反应")
            return {}
        # if(instruction=="猜词" or instruction=="wordguess" or instruction==".wordguess" or instruction=="/wordguess" or instruction==".wg"):
        #     if(wordGuess['over']):
        #         send.sendTextBack(data,"今天的已经猜出来了喵")
        #         return {}
        #     if(len(message)<=1):
        #         send.sendTextBack(data,"请输入猜测的词")
        #         return {}
        #     word = message[1]
        #     if(len(word)>12):
        #         send.sendTextBack(data,"太长了喵")
        #     if(wordGuess['answer'] == word):
        #         send.sendTextBack(data,"猜对了喵")
        #         wordGuess['over'] = True
        #         return {}
        #     wordGuess["time"]+=1
        #     sentence = '我们正在玩猜词游戏，朋友猜了"'+word+'"，答案是"'+wordGuess['answer']+'"，能告诉我"'+wordGuess['answer']+'"和"'+word+'"两个词的相关度吗，不要出现任何有关词的信息，只需要给出唯一一个百分数即可，精确到小数点后两位。'
            
        #     new_thread = threading.Thread(target=deepseekguessword, args=(data, sentence,word))
        #     new_thread.start()
        #     send.sendTextBack(data,"唉因为没有自己弄，所以还是得等ai反应")
        #     return {}
        # if(instruction==".wgss"):
            
        #     if(wordGuess["time"] <= 10 and wordGuess["over"] == False):
        #         send.sendTextBack(data,"至少要猜测十次或者猜出答案才能重新命题")
        #         return {}
            
        #     if(len(message)<=1):
        #         send.sendTextBack(data,"请输入要猜测的词")
        #         return {}
        #     word = message[1]
            
        #     if(len(word)>12):
        #         send.sendTextBack(data,"太长了喵")
        #     wgmessage=[
        #         {"role": "system", "content": "我们正在玩一个猜词游戏，你需要帮忙给出两个词之间关联度的百分数，第一个是答案，第二个是我猜的东西，只需要给百分数不需要任何额外的信息。"}
        #     ]
        #     wordGuess['answer'] = word
        #     wordGuess['over'] = False
        #     send.sendTextBack(data,"好了")
        #     return {}
        # if(instruction==".spm"):
        #     if(len(message)<=1):
        #         send.sendTextBack(data,"请输入猜测的信息喵")
        #         return {}
        #     new_thread = threading.Thread(target=deepseeksituationPuzzleMessage, args=(data, message[1]))
        #     new_thread.start()
        #     send.sendTextBack(data,"唉总之反正还是所以应该大抵得等ai反应")
        #     return {}
        # if(instruction==".spmq"):
        #     send.sendTextBack(data,situationPuzzleMessage[0]["question"])
        #     return {}
        # if(instruction==".spma"):
        #     print(situationPuzzleMessage[0])
        #     send.sendTextBack(data,situationPuzzleMessage[0]["answer"])
        #     return {}
        # if(instruction==".spms"):
        #     if(len(message)<=1):
        #         send.sendTextBack(data,"请以\".spmss 谜面 谜底\"的形式输入海龟汤信息，不要出现其他空格")
        #         return {}
        #     spm = message[1].split(" ")
        #     if(len(spm)!=2):
        #         send.sendTextBack(data,"请以\".spmss 谜面 谜底\"的形式输入海龟汤信息，不要出现其他空格")
        #         return {}
        #     situationPuzzleMessage[0] = {
        #         "question":spm[0],
        #         "answer":spm[1],
        #         "guesses":[]
        #     }
        #     send.sendTextBack(data,"设置好海龟汤了")
        #     return {}
        if(instruction=="aiset" or instruction==".aiset" or instruction=="/aiset"):
            aimessages.clear()
            aimessages.append({"role": "user", "content": message[1]})
            send.sendTextBack(data,"进行了神秘的重新设定")
            return {}
        # if(instruction=="aiclear" or instruction==".aiclear" or instruction=="/aiclear"):
        #     aimessages = [{"role": "user", "content": "你的名字叫正直超人。平时喜欢打麻将，最喜欢的vtuber是\"优衣先辈\"和\"HasFin\"。"}]
        #     send.sendTextBack(data,"清除了之前的对话记录")
        #     return {}
        #if(instruction == "复读" or instruction==".echo" or instruction=="/echo" or instruction=="echo"):
            #send.sendTextBack(data,simple.Repeat(message))
            #return {}
        if(instruction == "抽签" or instruction==".lots" or instruction=="/lots" or instruction=="lots"):
            send.sendTextBack(data,simple.DrawLots(message))
            return {}
        if(instruction == "抽群友" or instruction == ".lotsgm" or instruction == "/lotsgm" or instruction == "lotsgm" ):
            send.sendTextBack(data,simple.DrawLotsGM(user_id,is_group,group_id,message))
            return {}
        if(instruction == "骰子" or instruction==".dice" or instruction=="/dice" or instruction=="dice"):
            send.sendTextBack(data,simple.Dice(message))
            return {}
        if(instruction=="名人名言" or instruction==".wks#" or instruction=="/wks#" or instruction=="wks"):
            rstr = simple.RandomTaleFig(message)
            if rstr[0] == 'C':
                send.sendImgBack(data,rstr)
            else:
                send.sendTextBack(data,rstr)
            return {}
        if(instruction == "早安" or instruction==".morning" or instruction=="/morning" or instruction=="morning"):
            send.sendTextBack(data,simple.morning(user_id,is_group,group_id,message))
            return {}
        if(instruction == "记事" or instruction==".note" or instruction=="/note" or instruction=="note"):
            send.sendTextBack(data,simple.record_reminder(data,message))
            return {}
        # if(instruction == "祝福" or instruction==".bless" or instruction=="/bless" or instruction=="bless"):
        #     send.sendTextBack(data,bless.Bless(user_id,is_group,group_id,message))
        #     return {}
        if(instruction == "秘密祝福" or instruction==".secretbless" or instruction=="/secretbless" or instruction=="secretbless"):
            send.sendTextBack(data,secret_bless.SecretBless(user_id,is_group,group_id,message))
            return {}
        if(instruction == "赛博占卜" or instruction == "赛博塔罗" or instruction == "/cybertarot" or instruction == ".cybertarot" or instruction == "cybertarot" or instruction == "/cyberdivination" or instruction == "cyberdivination" or instruction == ".cyberdivination" or instruction == ".cd"or instruction == ".ct"):
            send.sendTextBack(data,tarot.Tarot(user_id,is_group,group_id,message,user_name))
            return {}
        
        if(instruction == "ai图像" or instruction == "aifig" or instruction == "/aifig" or instruction == ".aifig" or instruction == "aifig"):
            send.sendTextBack(data,aifig.aifig(user_id,is_group,group_id,message,user_name))
            return {}
        if(instruction == "ai图像2" or instruction == "aifig2" or instruction == "/aifig2" or instruction == ".aifig2" or instruction == "aifig2"):
            aifig2pr[user_id]=message[1]
            send.sendTextBack(data,"记录了生成图提示词")
            return {}
        if(instruction == "ai图像3" or instruction == "aifig3" or instruction == "/aifig3" or instruction == ".aifig3" or instruction == "aifig3"):
            aifig3pr[user_id]=message[1]
            send.sendTextBack(data,"记录了生成图提示词")
            return {}
        if(instruction == "ai图像4" or instruction == "aifig4" or instruction == "/aifig4" or instruction == ".aifig4" or instruction == "aifig4"):
            aifig4pr[user_id]=message[1]
            send.sendTextBack(data,"记录了生成图提示词")
            return {}
        
        # 一些连续进行的事件
        if(instruction == "清一色" or instruction==".fullflush" or instruction=="/fullflush" or instruction=="fullflush"):
            send.sendTextBack(data,full_flush.FullFlush(user_id,is_group,group_id,message))
            return{}
        if(instruction == "猜单词" or instruction==".hardle" or instruction=="/hardle" or instruction=="hardle"):
            send.sendTextBack(data,hardle.Hardle(user_id,is_group,group_id,message))
            return{}
        if(instruction == "飞行棋" or instruction==".flightchess" or instruction=="/flightchess" or instruction=="flightchess" or instruction==".fc"):
            send.sendTextBack(data,flight_chess.FlightChess(user_id,is_group,group_id,message,user_name))
            return{}
        if(instruction == "麻酱宝藏" or instruction==".mahjonggold" or instruction=="/mahjonggold" or instruction=="mahjonggold" or instruction==".mg"):
            send.sendTextBack(data,mahjong_gold.MahjongGold(user_id,is_group,group_id,message,user_name))
            return{}
        if(instruction == "17步麻将" or instruction=="十七步麻将" or instruction==".m17" or instruction=="m17" or instruction=="/m17"):
            send.sendTextBack(data,mahjong_17.Mahjong17(user_id,is_group,group_id,message,user_name))
            return{}
        if(instruction == "麻将比大小" or instruction=="mahjongwar" or instruction==".mgw" or instruction=="mgw" or instruction=="/mgw"):
            send.sendTextBack(data,mahjong_war.MahjongWar(user_id,is_group,group_id,message,user_name))
            return{}
        if(instruction == "麻将帝国" or instruction=="mahjongempire" or instruction==".mje" or instruction=="mje" or instruction=="/mje"):
            send.sendTextBack(data,mahjong_empire.MahjongEmpire(user_id,is_group,group_id,message,user_name))
            return{}
        if(instruction == "快艇骰子" or instruction==".yahtzee" or instruction=="/yahtzee" or instruction=="yahtzee" or instruction==".y"):
            send.sendTextBack(data,yahtzee.Yahtzee(user_id,is_group,group_id,message,user_name))
            return{}
        if(instruction == "赛事计分" or instruction == "ueml" or instruction == "/ueml" or instruction == ".ueml"):
            send.sendTextBack(data,ucml.ucml(user_id,is_group,group_id,message,user_name))
            return{}
        if(instruction == "aisetvoice" and (user_id == 0 or user_id ==0)):
            aisetvoice[0]=message[1]
            send.sendTextBack(data,"音色设置为"+aisetvoice[0])
            return{}
        if(instruction == "aivoice" and (user_id == 0 or user_id ==0)):
            saved_path = design_voice(
                voice_description=aisetvoice[0],
                preview_text=message[1],
                output_path="C:\\mybot\\output\\design_demo.wav",
                output_format="wav",
                api_key="",  # 已脱敏：MiMo API Key
            )
            send.sendVoiceBack(data,"C:\\mybot\\output\\design_demo.wav")
            return{}
        # if(instruction == "ucmt" or instruction == "/ucmt" or instruction == ".ucmt"):
        #     send.sendTextBack(data,ucmt.ucmt(user_id,is_group,group_id,message,user_name))
        #     return{}
    return {}

def deepseek(data,message):
    # print(aimessages)
    aimessages.append({"role": "user", "content":message[1]})
    # aimessages = [{"role": "user", "content":message[1]}]
    while(len(aimessages)>100):
        del aimessages[1]
    completion = client.bot_chat.completions.create(
        model= "bot-20250303191538-p5fql",
        messages=aimessages
    )
    markdown_text = completion.choices[0].message.content.strip()
    html = markdown(markdown_text)  # 先将Markdown转为HTML
    soup = BeautifulSoup(html, "html.parser")
    plain_text = soup.get_text()  # 从HTML提取纯文本
    aimessages.append({"role": "assistant", "content":plain_text.strip()})
    # aimessages.append({"role": "assistant", "content":completion.choices[0].message.content.strip()})
    # print("--------------------------------------------------")
    # print(completion.choices[0])
    # print(completion.choices[0].message.content)
    send.sendTextBack(data,plain_text.strip())
    # send.sendTextBack(data,completion.choices[0].message.content.strip())

def deepseekcommentgame(data,msg):
    completion = client.bot_chat.completions.create(
        model= "bot-20250303191538-p5fql",
        messages=[{"role": "user", "content":msg}]
    )
    #print(message[1]+"解决")
    #print(completion.choices[0].message.content)
    send.sendTextBack(data,completion.choices[0].message.content)
    
# def deepseekguessword(data,message,word):
#     #print(message[1]+"开始")
#     wgmessage.append({"role": "user", "content":message})
#     while(len(wgmessage)>100):
#         del wgmessage[1]
#     completion = client.bot_chat.completions.create(
#         model= "bot-20250303191538-p5fql",
#         messages=wgmessage
#     )
#     wgmessage.append({"role": "assistant", "content":completion.choices[0].message.content})
#     #print(message[1]+"解决")
#     #print(completion.choices[0].message.content)
#     send.sendTextBack(data,word+":"+completion.choices[0].message.content)
    
# def deepseeksituationPuzzleMessage(data,message):
#     #print(message[1]+"开始")
#     msg = "我们正在进行一次海龟汤游戏，海龟汤题目是:"+situationPuzzleMessage[0]["question"]+"。\n海龟汤答案是:"+situationPuzzleMessage[0]["answer"]+"。\n"
#     msg += "我的猜测是:"+message+"。请只告诉我的猜测是否正确，用是或者否或者不重要来回答。如果猜测覆盖了海龟汤答案全部的信息可以回复\"猜对了喵\"，其他猜测用是或者否或者不重要来回答。"
    
#     situationPuzzleMessage[0]["guesses"].append({"role": "user", "content":msg})
#     while(len(situationPuzzleMessage[0]["guesses"])>100):
#         del situationPuzzleMessage[0]["guesses"][0]
#     completion = client.bot_chat.completions.create(
#         model= "bot-20250303191538-p5fql",
#         messages=situationPuzzleMessage[0]["guesses"]
#     )
#     situationPuzzleMessage[0]["guesses"].append({"role": "assistant", "content":completion.choices[0].message.content})
#     #print(message[1]+"解决")
#     #print(completion.choices[0].message.content)
#     send.sendTextBack(data,completion.choices[0].message.content)

def deepseekSummarise(data,chatMessage):
    #print(message[1]+"开始")
    tempmessage = [{"role": "user", "content":chatMessage}]
    completion = client.bot_chat.completions.create(
        model= "bot-20251014140300-8dxqc",
        messages=tempmessage
    )
    send.sendTextBack(data,completion.choices[0].message.content)

def deepseekAnswer(data,chatMessage):
    tempmessage = [{"role": "user", "content":chatMessage}]
    completion = client.bot_chat.completions.create(
        model= "bot-20250303191538-p5fql",
        messages=tempmessage
    )
    if('silverwind' in completion.choices[0].message.content or '银风' in completion.choices[0].message.content):
        return
    send.sendTextBack(data,completion.choices[0].message.content.strip())
    return completion.choices[0].message.content.strip()

def deepseekChoose(chatMessage):
    tempmessage = [{"role": "user", "content":chatMessage}]
    completion = client.bot_chat.completions.create(
        model= "bot-20250303191538-p5fql",
        messages=tempmessage
    )
    return completion.choices[0].message.content.strip()

if __name__ == "__main__":
    client = Ark(api_key=os.environ.get("ARK_API_KEY"))
    uvicorn.run(app, port=8080)