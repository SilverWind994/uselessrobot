import json_opt
import copy
import send_message as send
import random
from PIL import Image,ImageDraw,ImageFont
import photo_opt


def Tarot(user_id,is_group,group_id,message,user_name):
    if(len(message)<=1):
        return "缺少指令喵"
    elif(message[1]=="help"):
        return """    第一个参数表示使用的牌组，目前有韦特(waite/维特)塔罗牌组和bilibili(2233/哔哩哔哩)塔罗牌组。
    
    第二个参数表示使用的展开法，目前有
    一张牌展开(一张牌/SingleOneCardSpread/SOCS),
    过去现在未来展开(过去现在未来/PastPresentAndFutureSpread/PPAFS),
    目标设定展开(目标设定/SettingAGoalSpread/SAGS),
    二选一展开(二选一/ChoiceSpread/CS)
    
    例如 cybertarot bilibili SAGS
    """
    else:
        message = message[1].lower().strip().split()
        prefix = ""
        suffix = ""
        width = 0
        half = 0
        if(len(message) != 2):
            return "指令不对喵"
        if(message[0] == "waite" or message[0] == "维特" or message[0] == "韦特"):
            perfix = "C:\\mybot\\tarot\\waite\\"
            suffix = ".jpg"
            width = 360
            half = 180
        elif(message[0] == "bilibili" or message[0] == "2233" or message[0] == "哔哩哔哩"):
            perfix = "C:\\mybot\\tarot\\bilibili\\"
            suffix = ".png"
            width = 300
            half = 150
        else:
            return "暂时没有对应类型的塔罗牌喵"
        
        cards = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,101,102,103,104,105,106,107,108,109,110,111,112,113,114,201,202,203,204,205,206,207,208,209,210,211,212,213,214,301,302,303,304,305,306,307,308,309,310,311,312,313,314,401,402,403,404,405,406,407,408,409,410,411,412,413,414]
        for i in range(0,77):
            select = random.randint(i,77)
            temp = cards[i]
            cards[i] = cards[select]
            cards[select] = temp
            
        backgroundPath = perfix+"background.png"
        background = Image.open(backgroundPath)
        msg = ""
        if(message[1]=="一张牌展开" or message[1] == "singleonecardspread"or message[1] == "socs"):
            card = Image.open(perfix+str(cards[0])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1280-half,980))
            msg = "代表问题的答案喵。"
        elif(message[1]=="过去现在未来展开" or message[1]=="过去现在未来" or message[1] == "pastpresentandfuturespread"or message[1] == "ppafs"):
            card = Image.open(perfix+str(cards[0])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(880-half,980))
            
            card = Image.open(perfix+str(cards[1])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1280-half,980))
            
            card = Image.open(perfix+str(cards[2])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1680-half,980))
            msg = "最左侧代表过去发生的事情，中间代表现在的状况，右侧是未来可能发生的事情喵。"
        
        elif(message[1]=="目标设定展开" or message[1]=="目标设定" or message[1] == "settingagoalspread"or message[1] == "sags"):
            card = Image.open(perfix+str(cards[0])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1280-half,260))
            
            card = Image.open(perfix+str(cards[1])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(960-half,1700))
            
            card = Image.open(perfix+str(cards[2])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1600-half,1700))
            
            card = Image.open(perfix+str(cards[3])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1280-half,980))
            msg = "最上方的牌代表目标，右下方的牌表示帮助达成目标的助力，左下方的牌代表达成目标的阻碍，中央的牌代表达成目标的方法"
        elif(message[1]=="二选一展开" or message[1]=="二选一" or message[1] == "choicespread"or message[1] == "cs"):
            card = Image.open(perfix+str(cards[0])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1280-half,1700))
            
            card = Image.open(perfix+str(cards[1])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1000-half,980))
            
            card = Image.open(perfix+str(cards[2])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1560-half,980))
            
            card = Image.open(perfix+str(cards[3])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(720-half,260))
            
            card = Image.open(perfix+str(cards[4])+suffix)
            card = card.resize((width,600))
            if(random.randint(0,1)== 1):
                card = card.rotate(180, expand=True)
            background.paste(card,(1840-half,260))
            msg = "最下方的牌代表现在的处境，中间的两张牌代表两个选项的状况，上方的两张牌代表所指向的未来。"
        else:
            return "暂时没有对应类型的展开法喵"
        
        file_path = photo_opt.SavePhoto(user_id,is_group,group_id,background)
        send.sendImg(user_id,is_group,group_id,file_path)
        return msg+"但无论结果如何，要相信自己的才是通向未来的钥匙喵。"