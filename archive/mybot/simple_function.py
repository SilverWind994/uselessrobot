import random
import os
import re
import psycopg2
import time
import json
import json_opt
import send_message as send
import qq_info_image as qq_image
from collections import defaultdict

DATABASE_NAME = "robot"
DATABASE_USER = "postgres"
DATABASE_PASSWORD = ""  # 已脱敏：本地数据库密码
DATABASE_HOST = "127.0.0.1"
DATABASE_PORT = "5432"



def Help(message):
    message = message.lower()
    msg = ""
    if message == "":
        msg = """   使用"help 对应指令名称的方式来查看指令的详细的说明
        每个指令使用 中文指令(没有点) .英文指令 /英文指令 英文指令 .指令简写 均可使用 空格分隔参数
        指令简介
        ·帮助/help 查看帮助，但你都看到这句话了肯定也不需要这里告诉你怎么查看帮助
        ·复读/echo 纯纯复读机
        ·答案之书/answer 答案之书
        ·总之差评 会复读总之差评
        ·今日运势/fortune 这玩意没用
        ·抽签/lots 空格后面用逗号分隔需要抽的东西，随机抽取一样
        ·抽群友/lotsgm 随机抽一个群友，但是有什么用呢
        ·随机UE/randomUE 随机发送一张UE表情包
        ·随机hasfin/randomhasfin 随机发送一张hasfin表情包
        ·随机半吨/random# 随机发送一张半吨代码表情包
        ·骰子/dice 空格后面用ndm表示，默认1d100的骰子
        ·记事/note 第一个参数用数字表示年月日时分，年需要四位，月日时分均需要两位，时分可以省略，小时默认八点，分钟默认00分 第二个表示要记录的事项
        ·清一色/fullflush 清一色听牌练习
        ·猜单词/hardle 很诡异的猜单词游戏
        ·飞行棋/flightchess/.fc 飞行棋
        ·麻酱宝藏/mahjonggold/.mg 印加宝藏麻酱版 
        ·快艇骰子/yahtzee/.y 快艇骰子
        ·赛事计分/ucml ml晋级规则的不便捷的分数记录查看功能
        ·结束/stop 在该用到的时候会提示的，唉
        ·早安/morning 用on开启off关闭 每天八点发一些意义不明的话
        ·17步麻将/m17 唉神秘的麻将游戏，会发很多图一直刷屏
        ·祝福/bless 看看仙贝送了多少奶茶出去
        ·麻将比大小/mgw 紧张刺激的赤木和僧我三威的最后一战
        ·mje 完全不像王权的东西
        ·赛博占卜/赛博塔罗/cyberdivination/cybertarot/.cd/.ct 赛博占卜
        ·ai 很朴素的版本的ai，后面有空慢慢调整唉
        ·aiset 后面的话可以对ai进行一些基础设定，比如你是一个什么什么，但是会覆盖之前的设定
        ·dsc 后面跟steam_id可以锐评游戏喜好，steam_id可以在steam右上角管理账户-账户明细里，xxx的账户下面的17位数字（没改用户url的话也是自定义url），顺便需要公开steam游戏和时长，当然有些朋友只对好友公开也行就是了
        ·dsc2 跟上面的一样，但是游玩时间少于1小时就不管了
        ·猜词/wordguess/.wg 后面跟猜的词，ai给出和答案的相关百分比（和下面的那玩意是一组的）
        · .wgss 设置猜词的题目
        ·spm/spma/spmq/spms 反正都是海龟汤的功能，但也没人来看帮助所以瞎写也不会有人知道的"""
    elif(message == "复读" or message == "echo"):
        msg = "复读指令后的内容，当然除了文字以外的东西都没做处理，会复读怪东西"
    elif(message == "帮助" or message == "help"):
        msg = "就像你这么用就可以了，太强了"
    elif(message == "总之差评"):
        msg = "总之差评"
    elif(message == "随机UE" or message == "randomUE"):
        msg = "没有参数，随机发一个ue表情包，但好多我也没存下来说是"
    elif(message == "结束" or message == "stop"):
        msg = "一些任务同一时间只能进行一个，如果前一个没进行完想结束进行下一个就使用这个指令"
    elif(message == "今日运势" or message == "fortune"):
        msg = "给一个1-100的随机数，每个人每天是不变的，唉，纯没用占位置"
    elif(message == "抽签" or message == "lots"):
        msg = "用逗号分隔需要抽的东西，随机抽取一样，最后如果加了逗号什么的会导致后面不存在的内容也被当作抽签项目，如果抽中的话就是空的"
    elif(message == "骰子" or message == "dice"):
        msg = "用ndm表示掷出n个m面骰子，默认使用1d100的骰子"
    elif(message == "记事" or message == "note"):
        msg = "第一个参数用数字表示年月日时分，年需要四位，月日时分均需要两位，时分可以省略，小时默认八点，分钟默认00分 第二个表示要记录的事项，会在指定的时间发送记录的事项，如果在群聊中使用会艾特记录人"
    elif(message == "清一色" or message == "fullflush"):
        msg = """   第一次发送指令获取清一色听牌题目
        出题后使用指令需跟一个参数表示题目的回答，用数字表示待牌，如"清一色 258"，每种牌能且只能回答一次，但顺序不影响
        """
    elif(message == "猜单词" or message == "hardle"):
        msg = """   第一次发送指令，用一个参数表示单词的长度，最低为3最高为10
        出题后使用指令需跟一个参数表示题目的回答，寄器人会告知位置正确的字母个数（绿色背景上的数字）和字母正确但是位置错误的数目（黄色背景上的数字）
        共有十次答题机会
        但坦率地说，这个词库反正也不太好用，好像复数时态什么的都没有
        """
    elif(message == "飞行棋" or message == "flightchess" or message == "fc"):
        msg = """   第一次发送指令开始铺设棋盘
        使用 加入/join 参数加入游戏 使用 开始/start 参数开始游戏 满四个时自动开始（大概吧主要测试也没有到四个人）
        游戏开始后自动投掷骰子，使用数字作为参数表示要移动的棋子，如果不移动或者都不满足条件使用数字0
        简易的规则说明：
        投掷到5或者6可以让飞机进入准备区
        投掷到6并移动后需要继续进行投掷
        同一名玩家连续三次投掷到6会将所有没用到达终点的棋子移动回基地
        棋子在行进过程中走至一格时，若已有敌方棋子停留，可将敌方的棋子逐回基地。如果格子中有多个敌方棋子，那自己也会返回基地。
        """
    elif(message == "麻酱宝藏" or message == "mahjonggold" or message == "mg"):
        msg = """   第一次发送指令开始准备游戏
        使用 加入/join 参数加入游戏 使用 开始/start 参数开始游戏 满五个时自动开始（大概）至少需要两人开始游戏
        游戏规则：就是印加宝藏，如果唐宁老师在我感觉他能解释
        大致就是每回合翻开一张卡牌，然后玩家进行决策
        卡牌有三种，点棒卡，还在场的玩家平分所有分数，多出来的留在原地。役满卡，留在原地。陷阱卡，第二次翻开同一张陷阱卡的时候，还没用撤退的玩家损失当前所有分数。
        玩家每次翻开卡牌的时候可以选择继续或者离开。选择离开可以带走当前身上所有分数，并且之前无法平分的点数和役满也可以一起带走（多人一起离开继续平分，役满留在原地）
        当所有玩家撤退，第二次遇到相同的陷阱，则游戏一轮结束。游戏共进行五轮。每一轮添加一张役满卡。如果役满卡被掀开，即使没有被人带走也会在下一轮移除。如果因为触发陷阱结束一轮，则删除一张对应的陷阱卡。
        
        玩家对机器人私聊使用指令加参数 继续/对日/continue 表示继续，使用 下车/离开/leave 表示结束探险。 如"麻酱宝藏 对日"
        """
    elif(message == "快艇骰子" or message == "yahtzee" or message == "y"):
        msg = """    第一次发送指令开始准备游戏
        使用 加入/join 参数加入游戏 使用 开始/start 参数开始游戏 满四个时自动开始（大概）
        游戏规则：每个人投掷五个骰子，可以选择其中任意个骰子进行重投，最多重投两次，然后选择计分方式
        一点到六点(1s-6s)：投出的相应点数的骰子的点数和，例如投出三个五点，选择五点的计分方式可以获得15分
        全选(chance)：按所有点数的点数和计分
        四同(4k)：至少有四个骰子点数相同时，按所有点数的点数和计分，不满足条件计0分
        葫芦(fullhouse/fh)：三个骰子点数相同，另外两个骰子点数也相同（包括五个骰子都相同的情况），按所有点数的点数和计分，不满足条件计0分
        小顺(shortstraight/ss)：至少有四个骰子点数连续（1和6不连续），计15分，不满足条件计0分
        大顺(longstraight/ls)：五个骰子点数连续（1和6不连续），计30分，不满足条件计0分
        快艇(yahtzee)：五个骰子点数相同，计50分，不满足条件计0分
        每种计分方式最多使用一次
        当一点到六点总分大于等于63分时，将额外获得35分奖励分
        游戏进行12轮
        当重投骰子时候，第一个参数为 重投/reroll ，第二个参数表示要重投的骰子位置，例如想重投第1，2，5个骰子  "快艇骰子 重投 125"
        当计分时候，第一个参数为 计分/score ，第二个参数表示使用的计分方式，例如  "快艇骰子 计分 快艇"
        """
    elif(message == "赛事计分" or message == "ucml"):
        msg = """
        需要将46341524 优衣先辈添加为赛事管理员才能创建对局和获取成绩
        
        需要超级管理权限的指令：
        比赛场信息/matchinformation/mi 两个参数对应为比赛的uniqueid（非赛事id）和seasonid，可以在赛事管理界面的地址栏中找到
        ucml mi 76178771 1
        添加管理/addadministrator/aa 一个参数作为管理的qq号
        ucml aa 510480838 将半吨代码添加为管理员
        移除管理/removeadministrator/ra 一个参数作为管理的qq号
        ucml ra 510480838 移除半吨代码的管理员
        新赛季/startnewseason/sns 从比赛结束阶段切换到比赛准备阶段
        ucml sns
        下一阶段/nextstage/ns 进行到下一个阶段（比赛准备阶段->常规赛阶段->半决赛阶段->决赛阶段->比赛结束阶段）
        ucml ns
        
        需要管理员权限的指令：
        添加队伍/addteam/at 队伍名 队伍颜色(用逗号隔开三个0-255的值)
        ucml at 木木仙贝一个人一队 36,134,185 添加一个背景色为宝石蓝的队伍木木仙贝一个人一队
        颜色最好使用浅一点的颜色，毕竟字都是黑色的
        移除队伍/removeteam/rt 队伍名
        ucml rt 木木仙贝一个人一队
        添加队员/addplayer/ap 队员名 队伍名
        ucml ap Mooner 木木仙贝一个人一队 将Mooner添加到队伍中，比赛中途最好不要更改雀魂昵称
        移除队员/removeplayer/rp 队员名
        ucml rp Mooner 将Mooner移除
        开始比赛/matchstart/ms 东家昵称 南家昵称 西家昵称 北家昵称 （等一下名字里面有空格好像要出问题，不过如果有再说吧）
        ucml ms 赤木茂 宫永咲 狛枝凪斗 铃木优衣
        记录结果/recordmatchresult/rmr
        ucml rmr 用于获取比赛的结果，在比赛后输入一次更新一下就可以
        
        不需要权限的指令：
        查看管理/showadministrator/sa 查看所有管理员的qq号
        队伍成员/teamplayer/tp  查看每个队伍和分别包含哪些队员
        队伍信息/teammessage/tm 查看队伍的得分情况，用参数1，2，3分别代表常规赛，半决赛，决赛的情况
        ucml tm 1 查看常规赛阶段的队伍得分
        个人信息/playermessage/pm 查看个人的得分情况，用参数0，1，2，3分别代表总成绩，常规赛，半决赛，决赛的情况
        ucml pm 1 查看常规赛阶段的个人得分
        比赛结果/matchresult/mr 查看所有比赛的结果，用参数0，1，2，3分别代表总成绩，常规赛，半决赛，决赛的情况
        ucml mr 1 查看常规赛阶段的每一局的成绩
        
        出现提到的最好不要的情况或者其他bug什么的联系管理员（联系方式已脱敏）
        """
    elif(message == "m17" or message == "17步麻将"):
        msg = """    第一次发送指令开始准备游戏
        使用 加入/join 参数加入游戏
        基本参照17步麻将规则，但是双方开局默认已经立直，场风为东，自风均为南（为什么一样，因为有懒狗）
        私聊发送 .m17+选的牌进行组牌 +打出的牌出牌 需要和牌时+rong/荣 双方均打完时，先手方如果不和牌需要 pass/流局
        """
    elif(message == "bless" or message == "祝福"):
        msg = """    无参数或者为总览显示主要信息
        参数为详情显示每场详细预测
        """
    elif(message == "mgw" or message == "麻将大小"):
        msg = """    第一次发送指令开始准备游
        私聊中使用 mgw 数字 选择牌 mgw random 随机出牌
        """
    elif(message == "mje" or message == "麻将王权"):
        msg = """    第一次发送指令开始准备游
        mje a或者mje b做出选择
        mje item使用道具
        """
    elif(message == "赛博占卜" or message == "赛博塔罗" or message == "cybertarot" or  message == "cyberdivination" or message == ".cd" or message == ".ct"):
        msg = """    第一个参数表示使用的牌组，目前有韦特(waite/维特)塔罗牌组和bilibili(2233/哔哩哔哩)塔罗牌组。
    
        第二个参数表示使用的展开法，目前有
        一张牌展开(一张牌/SingleOneCardSpread/SOCS),
        过去现在未来展开(过去现在未来/PastPresentAndFutureSpread/PPAFS),
        目标设定展开(目标设定/SettingAGoalSpread/SAGS),
        二选一展开(二选一/ChoiceSpread/CS)

        例如 cybertarot bilibili SAGS
        """
    
    return msg

def Repeat(message):
    if(len(message)==1):
        msg = "缺少复读内容"
    else:
        msg = message[1]
    return msg

def DrawLots(message):
    if(len(message)==1):
        msg = "缺少抽签内容"
    else:
        lots = re.split("[,，]",message[1])
        for i in lots:
            if(i == "睡觉"):
                msg = "抽到了 睡觉"
                return msg
        msg = "抽到了 "+ lots[random.randint(0, len(lots)-1)]
    return msg

def DrawLotsGM(user_id,is_group,group_id,message):
    if(not is_group):
        return "需要在群聊中进行"
    if(len(message)==1):
        num = 1
    elif(message[1].strip().isdigit()):
        num = int(message[1].strip())
    else:
        num = 1

    num = max(num,1)
    num = min(num,10)
    members = []
    msg = send.getGroupMembers(group_id)
    member = json.loads(msg.text)
    member = member["data"]
    for i in range(num):
        num_a = len(member)
        r = random.randint(0,num_a-1)
        members.append({"qq":member[r]["user_id"],"nickname":member[r]["nickname"]})

    print(members)
    

    
    image_path = qq_image.generate_qq_grid_image(members)
    send.sendImgToGroup(group_id,image_path)
    return ""
    return "抽中了"+member["nickname"]+"-"+member["card"]+"("+str(member["user_id"])+")"


def RandomUe():
    folder_path = 'C:\\mybot\\uefig'
    file_names = os.listdir(folder_path)
    file_name = file_names[random.randint(0, len(file_names)-1)]
    return 'C:\\mybot\\uefig\\'+file_name

def RandomHasfin():
    folder_path = 'C:\\mybot\\hasfinfig'
    file_names = os.listdir(folder_path)
    file_name = file_names[random.randint(0, len(file_names)-1)]
    return 'C:\\mybot\\hasfinfig\\'+file_name

def RandomHT():
    folder_path = 'C:\\mybot\\htfig'
    file_names = os.listdir(folder_path)
    file_name = file_names[random.randint(0, len(file_names)-1)]
    return 'C:\\mybot\\htfig\\'+file_name

def RandomMeme(userId,isGroup,groupId):
    folder_path = 'C:\\mybot\\meme'
    file_names = os.listdir(folder_path)
    if(len(file_names) == 0):
        send.sendText(userId,isGroup,groupId,"没有梗图了")
        return
    file_name = file_names[random.randint(0, len(file_names)-1)]
    file_name = 'C:\\mybot\\meme\\'+file_name
    send.sendImg(userId,isGroup,groupId,file_name)
    os.remove(file_name)
    return ''
    

def RandomTaleFig(message):
    folder_path = 'C:\\mybot\\tale'
    if(len(message)>1):
        message[1] = message[1].lower()
        if message[1] == 's': 
            file_names = os.listdir(folder_path)
            
            name_stats = defaultdict(int)
            pattern = re.compile(r'^([^\d]+)\d+')
            
            for filename in file_names:
                match = pattern.match(filename)
                if match:
                    name = match.group(1).rstrip() 
                    name_stats[name] += 1
            result = "名言统计："+str(len(file_names))+"\n"
            newline = False
            for name, count in sorted(name_stats.items(), key=lambda x: x[1], reverse=True):
                result += f"{name}: {count}"
                if(newline):
                    result += "\n"
                else:
                    result += "     "
                newline = not newline
                
            return result.strip()
        else:
            file_names = os.listdir(folder_path)
            matching_files = [f for f in file_names if f.startswith(message[1])]
            file_name = matching_files[random.randint(0, len(matching_files)-1)]
        
    else:
        file_names = os.listdir(folder_path)
        file_name = file_names[random.randint(0, len(file_names)-1)]
    return 'C:\\mybot\\tale\\'+file_name

def Dice(message):
    num = 1
    face = 100
    if(len(message)>1):
        if(message[1][0]=='d'):
            face = message[1][1:]
            if(not face.isdecimal()):
                return("骰子炸了")
            if(len(face)>8):
                return("面数太多看不清是啥")
            face = int(face)
        else:
            dice =  re.split("d",message[1])
            if((not dice[0].isdecimal())or(not dice[1].isdecimal())):
                return("骰子炸了")
            if(len(dice[0])>3):
                return("寄器人被骰子埋了")
            if(len(dice[1])>8):
                return("面数太多看不清是啥")
            num = int(dice[0])
            face = int(dice[1])
    msg = ""
    for i in range(num):
        msg = msg + str(random.randint(1, face)) + " "
    msg = msg[:-1]
    return msg

def record_reminder(data,message):
    message =  message[1].split(" ")
    if(len(message)<2):
        return "听不懂喵"
    time_str = str(message[0])
    content = message[1]

    if(not time_str.isdecimal()):
        return "看不懂时间喵"
    if(len(time_str)>12):
        return "时间太精确了做不到喵"
    if(len(time_str)<8):
        return "时间太宽泛了不知道啥时候提醒嘞"
    if((len(time_str)==9) or (len(time_str)==11)):
        return "晕了喵"
    if((len(time_str)==8)):
        time_str = time_str + "0800"
    if((len(time_str)==10)):
        time_str = time_str + "00"
    time_str = time_str[0:4]+"-"+time_str[4:6]+"-"+time_str[6:8]+" "+time_str[8:10]+":"+time_str[10:]+":00"
    if(not is_valid_datetime(time_str)):
        return "这个时间是存在的吗，看不明白喵"
    if(len(message) >= 3):
        user_to = message[2]
        if(not user_to.isdecimal()):
            return "QQ号应该全是数字吧"
        if(data["message_type"]!="group"):
            return "只有群里能艾特别人哦"
        user_id = user_to
        is_group = True
        group_id = data["group_id"]
    else:
        user_id = data["user_id"]
        group_id = 0
        if(data["message_type"]=="group"):
            is_group = True
            group_id = data["group_id"]
        elif(data["message_type"]=="private"):
            is_group = False
        else:
            return "呜呜肯定是没记住，而且最好锤一下那谁说一下看看哪里出了差错"
    
    conn,cursor = connectDatabase()
    sql = "INSERT INTO reminder(user_id,is_group, group_id, content,time_remind) VALUES ("+str(user_id)+","+str(is_group)+","+str(group_id)+",'"+str(content)+"','"+str(time_str)+"');"
    cursor.execute(sql)

    disconnectDatabase(conn,cursor)

    return "记住了（希望不会忘记提醒）"

def morning(user_id,is_group,group_id,message):
    if(len(message)==1):
        return "缺少指令"
    if(message[1] == "on"):
        conn,cursor = connectDatabase()
        if(is_group):
            sql = "SELECT COUNT(*) FROM MORNING WHERE GROUPID = " +str(group_id) + ";"
            cursor.execute(sql)
            data = cursor.fetchall()
            data = data[0][0]
            if(data != 0):
                return "已经开启了喵"
            sql = "INSERT INTO MORNING(USERID,ISGROUP,GROUPID) VALUES("+str(user_id)+","+str(is_group)+","+str(group_id)+");"
            cursor.execute(sql)
        else:
            sql = "SELECT COUNT(*) FROM MORNING WHERE USERID = " +str(user_id) + ";"
            cursor.execute(sql)
            data = cursor.fetchall()
            data = data[0][0]
            if(data != 0):
                return "已经开启了喵"
            sql = "INSERT INTO MORNING(USERID,ISGROUP,GROUPID) VALUES("+str(user_id)+","+str(is_group)+","+str(group_id)+");"
            cursor.execute(sql)
        disconnectDatabase(conn,cursor)
        return "开启没有用的早安提醒"
    elif(message[1] == "off"):
        conn,cursor = connectDatabase()
        if(is_group):
            sql = "DELETE FROM MORNING WHERE GROUPID = " +str(group_id) + ";"
            cursor.execute(sql)
        else:
            sql = "DELETE FROM MORNING WHERE USERID = " +str(user_id) + ";"
            cursor.execute(sql)
        disconnectDatabase(conn,cursor)
        return "关闭没有用的早安提醒,如果你开了的话"
    else:
        return "指令不正确喵"


def is_valid_datetime(date_str):
    try:
        time.strptime(date_str,  "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError:
        return False

def Stop(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    if(is_group):
        if(data["group_bind"]):
            for i in range(data["data"]["player_num"]):
                json_opt.ResetJson(data["data"]["player_id"][i],False,group_id)
        json_opt.ResetJson(user_id,is_group,group_id)
    else:
        if(data["group_bind"]):
            return "需要去群里结束目前的活动哇呜"
        else:
            json_opt.ResetJson(user_id,is_group,group_id)
    return "不管之前在没在干啥反正停下了，我去睡觉了喵"

def connectDatabase():
    conn = psycopg2.connect(database=DATABASE_NAME, user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST, port=DATABASE_PORT)
    cursor = conn.cursor()
    return conn,cursor

def disconnectDatabase(conn,cursor):
    conn.commit()
    cursor.close()
    conn.close()