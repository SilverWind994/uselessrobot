import json_opt
import json
import copy
import send_message as send
import random
from PIL import Image,ImageDraw,ImageFont
import photo_opt
import math

regularEvents = [
{
    "story":"你发现了一个无良玩具商偷偷把铳牌偷偷放在泰迪熊里，把泰迪熊送给难民孩子们。",
    "a":"太可恶了，必须找到玩具商给他来一个阳炎射线跟他爆了",
    "b":"太可恶了，总不能让孩子们放铳，只能下车了",
    "resultA":[10,5,0,0,0],
    "resultB":[-10,5,0,0,0],
    "storyA":"原来商人也是被勒索的，有一个四人小队说后续的事情他们会解决的。",
    "storyB":"孩子们纷纷打出铳牌，但你已经下车了所以没有人放铳。"
},
{
    "story":"在森林里迷路了呜呜呜，来了一位商人，她说如果你帮她偷到一颗养鸡蛋就给你食物。",
    "a":"义正言辞地拒绝她的要求，用点棒购买食物，警告她如果再想偷东西就",
    "b":"什么养鸡蛋，这林子里有野鸡吗，给她随便找个蛋糊弄一下吧",
    "resultA":[6,12,0,0,-50],
    "resultB":[0,-12,0,0,0],
    "storyA":"商人也没再说什么卖给你一些食物以后很快跑走了，她穿什么跑这么快的。",
    "storyB":"在背包里找到了蛋黄月饼，那为什么不自己吃呢"
},
{   
    "story":"遇到了一只松鼠，当你靠近他的时候他突然向你咬了过来",
    "a":"来一瓶动物交谈药水看看怎么个事",
    "b":"还是绕路走吧，不知道被松鼠咬到疼不疼",
    "resultA":[0,10,-7,-3,0],
    "resultB":[-7,0,0,0,0],
    "storyA":"不是哪有动物交谈药水那种玩意",
    "storyB":"离松鼠有一段距离后他就不管你了，不知道为什么"
},
{   
    "story":"“我现在急需一把可破盾魔法回旋镖，你能帮帮我吗？”走在路上一个年轻人拦住了你，他向你提出了这个无厘头的请求。",
    "a":"“可破盾魔法回旋镖？”",
    "b":"“我这就去帮你找！”",
    "resultA":[0,0,2,0,200],
    "resultB":[0,0,-8,-8,0],
    "storyA":"“谢谢你的好意！”年轻人从地上的对话信息里把回旋镖拔了出来，给你留下了一袋金子。",
    "storyB":"你立马去各处问关于可破盾魔法回旋镖的信息，但是你找了半天也没有找到什么，但是年轻人已经不见了踪影"
},
{
    "story":"一个少女将木头雕刻的星星放到你的手上，说希望你能参加她姐姐的婚礼。",
    "a":"答应她的请求",
    "b":"是个怪人，不管她",
    "resultA":[0,10,-5,0,0],
    "resultB":[-5,0,0,10,0],
    "storyA":"仔细询问才知道，原来她的姐姐是八木唯的美术老师，你们一起去参加了她姐姐的婚礼。",
    "storyB":"少女有些失望，但是带着星星去找下一个人了。"
},
{   
    "story":"清晨，你路过一家面包店，你走了进去，一位痞里痞气的没好气地大叔接待了你。但是当你选择了一款看起来很花哨的面包后，大叔突然对你十分殷勤，并且希望多送你一些。",
    "a":"不会有诈吧，算了还是不要了",
    "b":"免费的话不要白不要，况且资质齐全的面包能有啥问题",
    "resultA":[-6,0,-6,0,0],
    "resultB":[6,0,6,0,200],
    "storyA":"大叔把你轰出了店铺，真是太没有职业操守了，唉。",
    "storyB":"醒来的时候已经是傍晚了，面包店里一位女孩在找看你，她说他的爸爸去追她的妈妈去了。并给你打包了一些没那么花哨的面包告诉你这些可以放心吃。"
},
{
    "story":"城市里有一帮神秘的人在进行聚会，他们的标志是一条通体发黑的龙。",
    "a":"过去凑个热闹",
    "b":"算了算了",
    "resultA":[-8,-8,-8,0,0],
    "resultB":[8,8,8,0,0],
    "storyA":"黑龙会欢迎你的加入小伙子。",
    "storyB":"指不定要被城管处理的，还是不要掺和好了。"
},
{
    "story":"忙碌了一天准备吃个烧烤喵，你来到了一家烧烤摊，点了一份烤鸡但是老板说她们只有烤八目鳗，你的选择是",
    "a":"烤八目鳗",
    "b":"饱腹+不可思议+适合拍照+文化底蕴+昂贵+猎奇",
    "resultA":[0,0,0,8,-10],
    "resultB":[10,10,10,-10,-100],
    "storyA":"之前没吃过诶，不过还是非常好吃的啊呜。",
    "storyB":"老板端上来了一份什么都加了一点的饭团，不知道为什么你觉得确实符合要求。"
},
{
    "story":"你在网上冲浪的时候看到了一位近期运气非常差的麻将士的切片，你选择",
    "a":"大肆嘲讽该麻将士水平极低",
    "b":"疯狂职责切片的人吃人血馒头",
    "resultA":[5,-5,0,5,-400],
    "resultB":[5,-5,0,-5,-400],
    "storyA":"并没有人赞同你的观点，有人质疑你是否打出了正确的每一打。",
    "storyB":"发现并没有人理你，被人当作饭后谈资后道心破碎。"
},
{
    "story":"一群人围在一栋大楼前吵吵嚷嚷的，发生了什么事情呢？",
    "a":"向愤怒人群中的人打听怎么回事",
    "b":"向旁边路过的老者询问他是否知道什么",
    "resultA":[5,0,0,-10,0],
    "resultB":[-5,0,0,5,0],
    "storyA":"“其他人我不知道的，主要是我养的松鼠被创了”",
    "storyB":"“我还蛮喜欢这家公司的业务的，我也到了要拜托他们的时候了”"
},
{
    "story":"汪次郎将你拉到一边，掏出了一个红色的💊和一的蓝色的💊。",
    "a":"红色药丸",
    "b":"蓝色药丸",
    "resultA":[0,0,0,0,0],
    "resultB":[0,0,0,0,0],
    "storyA":"是草莓硬糖",
    "storyB":"是蓝莓硬糖"
},
]

yearEvents = [
[
{
    "story":"在神社结束了一天的忙碌，大家决定聚在一起打牌，大家都对于你这个神社的新人很感兴趣，都想在你的背后当背后灵。你选择让谁首先观战你呢？",
    "a":"一姬",
    "b":"八木唯",
    "resultA":[5,5,-5,-5,400],
    "resultB":[-10,0,10,5,0],
    "storyA":"一姬观战你并在你的背后指指点点，鼓动你不断副露一番进攻，心情大好给你涨了工资",
    "storyB":"八木唯在你身后安静地看着你打牌，你感到非常平静，可以沉下心来思考。"
},
{
    "story":"神社里来了一位浑身湿漉漉的白发少年，他说他以前从来没打过牌，于是安安静静地看着你们打牌。一姬看他似乎非常认真，邀请他也一起打牌。",
    "a":"在他的身后观摩牌局",
    "b":"亲身和他对弈一番",
    "resultA":[0,0,10,0,0],
    "resultB":[0,0,-10,0,-200],
    "storyA":"观摩少年打牌的过程中，你发现了许多自己并不理解的打法，复盘的时候，你从这个自称没有打过牌的少年的交谈中学到了很多读牌读人的知识。",
    "storyB":"你觉得自己明明打的没什么问题，但是怎么也赢不了，是不是真的自己运气不到家。后面的工作也魂不守舍的被一姬扣了工资。"
},
{
    "story":"神社这一阵子太多人来参拜，留下了很多垃圾，你被安排进行大扫除。",
    "a":"认真进行扫除",
    "b":"扫除太累了，外包两个清洁工好了",
    "resultA":[0,10,0,0,200],
    "resultB":[0,-10,0,0,-200],
    "storyA":"直到天黑都在进行扫除，一姬看到整洁的神社心情大好，请大家大吃一顿。",
    "storyB":"外包的事情很快被发现了，一姬直接把工资结给了清洁工，但你也没要回你付给清洁工的费用。"
},
{
    "story":"神社不远处路边有一只看起来已经没有气息的松鼠。",
    "a":"安葬这只松鼠",
    "b":"等待专业的人来处理",
    "resultA":[0,0,0,-8,0],
    "resultB":[0,0,0,8,0],
    "storyA":"",
    "storyB":""
},
{
    "story":"神社外面的路灯坏了喵，有一个说自己是修路灯的人来了。他说想请你帮个忙，时候会给你报酬。",
    "a":"搭把手",
    "b":"不会是什么坏人吧",
    "resultA":[3,0,0,-6,200],
    "resultB":[0,-5,0,10,0],
    "storyA":"修好路灯，他给了你两百点棒。他说今天他的同伴妻子生了重病所以他要早点回去，于是最后的工作就是他自己解决了。在交谈中你知道他以前还是一名吉他手，他简单唱了两句振奋人心的歌曲。唱的还是不错的，但想必这个能力在歌手中就显得不够看了吧。",
    "storyB":"你觉得这个人肯定有问题，这种工作都是至少两人一组的，他肯定不怀好心，还是赶紧走吧。"
},
{ 
    "story":"城市一个不起眼的角落里有一家酒吧，黑发少女在柜台擦着酒杯。你询问她能不能给你推荐一些温和的酒。",
    "a":"Fluffy Dream",
    "b":"Sunshine Cloud",
    "resultA":[0,0,-20,0,-170],
    "resultB":[0,0,20,0,-150],
    "storyA":"喝了以后趴在酒吧的桌上睡了一觉，好像做了一个成为世界第一麻将高手的梦。",
    "storyB":"感觉有些像没有放糖的巧克力牛奶。"
},
{ 
    "story":"抚子今天来神社打牌的时候带来了一些鸡尾酒，她说自己偶然间发现了一家酒吧，酒也很好，里面也能遇到很多有趣的人。要来一杯吗？",
    "a":"一杯标价160点棒的饮料，是抚子最喜欢的",
    "b":"一杯标价260点棒的饮料，即使抚子也不太会大口喝这玩意",
    "resultA":[-5,-5,-5,0,0],
    "resultB":[10,5,-10,0,200],
    "storyA":"小酌了一口，微微发苦。旁边的抚子却一饮而尽。",
    "storyB":"你选择这杯的时候抚子感到非常诧异，自己都忘了喝。你喝了一大口，感觉嗓子被酒精堵住，喉咙火辣辣地疼。抚子惊讶于你的豪爽，骑上车带着快要不省人事你在城市兜了一圈，似乎给你购买了一份礼物，但你已经记不清了。"
},
{ 
    "story":"神社有一帮新的客人，除了打牌也会玩各种其他的桌游。其中一位拿出了两份桌游问你要不要一起来玩。",
    "a":"怒海求生",
    "b":"铁路环游",
    "resultA":[6,10,0,-6,0],
    "resultB":[-6,-10,0,0,0],
    "storyA":"放弃了胜利救下了被打晕前将东西都给你的信赖你的伙伴，不过这游戏真的有信赖可言吗？总之玩得很开心。",
    "storyB":"虽然没有拿到第一，守护住了自己的铁路，玩得很开心。"
},
{ 
    "story":"一个莽撞的少年骑车在路上狂飙，眼看着要撞上一只猫。",
    "a":"救下那只猫",
    "b":"车这么快肯定来不及的",
    "resultA":[10,1,0,-5,0],
    "resultB":[0,-5,10,0,0],
    "storyA":"然而车的速度比你快多了，不过好在猫的速度比车也快很多，立马跳到路边缩进你的怀里，哇呜可爱的猫猫他不怕生的吗？",
    "storyB":"确实，但是猫猫迅速就跳走了。"
},
{ 
    "story":"\"注意了！巨大的厄运彗星已经撕裂天空！末日即将来临！\"一个神棍男人在路旁演讲。",
    "a":"正直地让听众不要被他的胡说八道骗了",
    "b":"乱说怪话才会被彗星砸，还是赶紧走吧",
    "resultA":[0,6,8,0,0],
    "resultB":[0,0,-6,8,0],
    "storyA":"并没有听众听你的，毕竟根本也没有听众。",
    "storyB":"溜了溜了，一个人在那里叽里咕噜什么呢。"
},
{ 
    "story":"神社年度优秀员工评选了，一姬邀请你参加神社年会，但是你恰好得了感冒，该怎么办呢？",
    "a":"还是参加年会吧，小心一点好了",
    "b":"得好好休息一下，况且传染给其他人就不好了",
    "resultA":[0,5,0,-5,0],
    "resultB":[0,0,0,10,200],
    "storyA":"年度最佳员工给了因为买不到三号电池所以在仓库里呆了一整年的扫地机器人，年会差评如潮。",
    "storyB":"不知道是谁在床头给你放了一块麻将糕，吃完恢复了体力。"
},
],
[]]

mainEvents = [[{
    "story":"你正躺在床上玩雀魂，现在已经是南四局，自己前期落后了很多分数，但是现在终于抓到一把好牌。这副牌如果立直，只要和牌就可以逆转避四，如果选择默听，则必须要直击竞争家才能避四。正当你思考该如何应对的时候，突然隔壁的大卡车创开了墙把你创进异世界。睁开眼睛时你发现，你正在麻将对局中，面前的牌赫然是你刚刚对局中的牌。",
    "a":"立直",
    "b":"默听",
    "resultA":[0,10,0,0,-2000],
    "resultB":[0,-10,0,0,-2000],
    "storyA":"正直地拍出立直棒宣布立直，“荣喵！”对面的一姬宣告和牌，你吃四了。“你已经没有点棒了喵，不如今年就留在神社打工还债喵”",
    "storyB":"你小心地打出牌默听，“荣喵！”对面的一姬宣告和牌，你吃四了。“你已经没有点棒了喵，不如今年就留在神社打工还债喵”",
    "specialStatus":{"statusType":0,"statusNum":[0,0,0,0,0]}
}]]

items = [{
    "name":"《现代麻将的绝对手顺》",
    "description":"在麻将的世界中找到平衡，使所有属性都变为50。"
},{
    "name":"《亚空间杀法》",
    "description":"学习掌控绝对运势的能力，将运势变为95并且本年度不会再改变，替换当前的年度效果。"
},{
    "name":"《雀魂绝艺总纲》",
    "description":"虽然看起来是一本麻将书，但里面记载的都是直播赚钱技巧，立即提升10%的点棒数量。"
}]



def MahjongEmpire(user_id,is_group,group_id,message,user_name):
    status_data = json_opt.GetJson(user_id,is_group,group_id)
    if((status_data["status"]!="mahjongempire")and(status_data["status"]!="none")):
        return "还在进行其他任务，输入结束/stop，结束任务后开始新的任务"
    elif(status_data["status"]=="none"):
        SetGame(user_id,is_group,group_id)
        return 
    else:
        if(len(message)<=1):
            return "缺少指令喵"
        message = message[1].strip()
        if(message == "item" or message == "道具"):
            return UseItem(user_id,is_group,group_id)
        elif(message == "A" or message == "a"):
            Choose(user_id,is_group,group_id,"a")
            return
        elif(message == "B" or message == "b"):
            Choose(user_id,is_group,group_id,"b")
            return
        else:
            return "请做出选择，或者.mje item使用道具喵"
    
def SetGame(user_id,is_group,group_id):
    regularEO = []
    for i in range(len(regularEvents)):
        regularEO.append(False)
    yearEO = []
    for i in range(len(yearEvents[0])):
        yearEO.append(False)
        
    mainEventId = random.randint(0,len(mainEvents)-1)
    itemId = random.randint(0,len(items)-1)
    
    
    data =  {
        "status": "mahjongempire",
        "data": {
            "regularEO":regularEO,
            "yearEO":yearEO,
            "mainEO":mainEventId,
            "year":1,
            "month":1,
            "lastEvent":mainEvents[mainEventId][0],
            "item":{"itemId":itemId,"used":False},
            "atk":50, # 进攻/守备
            "int":50, # 正直/精明
            "sci":50, # 科学/运势
            "whi":50, # 门清/副露
            "score":0,
            "status":{"statusType":0,"statusNum":[0,0,0,0,0]}
        },
        "group_bind":False
    }
    json_opt.SetJson(user_id,is_group,group_id,data)
    send.sendText(user_id,is_group,group_id,"初始道具"+items[itemId]["name"]+","+items[itemId]["description"])
    send.sendText(user_id,is_group,group_id,mainEvents[mainEventId][0]["story"]+"你选择：A."+mainEvents[mainEventId][0]["a"]+",B."+mainEvents[mainEventId][0]["b"]+"。")
    return

def Choose(user_id,is_group,group_id,choice):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mahjongempire_data = data["data"]
    event = mahjongempire_data["lastEvent"]
    if(choice == "a"):
        result = event["resultA"]
        story = event["storyA"]
    else:
        result = event["resultB"]
        story = event["storyB"]
    if("specialStatus" in event):
        mahjongempire_data["status"] = event["specialStatus"]
    if(mahjongempire_data["status"]["statusType"] == 1):
        result[0] += mahjongempire_data["status"]["statusNum"][0]
        result[1] += mahjongempire_data["status"]["statusNum"][1]
        result[2] += mahjongempire_data["status"]["statusNum"][2]
        result[3] += mahjongempire_data["status"]["statusNum"][3]
        result[4] += mahjongempire_data["status"]["statusNum"][4]
    if(mahjongempire_data["status"]["statusType"] == 2):
        result[0] *= mahjongempire_data["status"]["statusNum"][0]
        result[1] *= mahjongempire_data["status"]["statusNum"][1]
        result[2] *= mahjongempire_data["status"]["statusNum"][2]
        result[3] *= mahjongempire_data["status"]["statusNum"][3]
        result[4] *= mahjongempire_data["status"]["statusNum"][4]
        
    if(mahjongempire_data["atk"]>80):
        if(result[0] > 0):
            result[0] *= 0.8
        else:
            result[0] *= 1.2
    if(mahjongempire_data["atk"]<20):
        if(result[0] > 0):
            result[0] *= 1.2
        else:
            result[0] *= 0.8
            
    if(mahjongempire_data["int"]>80):
        if(result[1] > 0):
            result[1] *= 0.8
        else:
            result[1] *= 1.2
    if(mahjongempire_data["int"]<20):
        if(result[1] > 0):
            result[1] *= 1.2
        else:
            result[1] *= 0.8
            
    if(mahjongempire_data["sci"]>80):
        if(result[2] > 0):
            result[2] *= 0.8
        else:
            result[2] *= 1.2
    if(mahjongempire_data["sci"]<20):
        if(result[2] > 0):
            result[2] *= 1.2
        else:
            result[2] *= 0.8
            
    if(mahjongempire_data["whi"]>80):
        if(result[3] > 0):
            result[3] *= 0.8
        else:
            result[3] *= 1.2
    if(mahjongempire_data["whi"]<20):
        if(result[3] > 0):
            result[3] *= 1.2
        else:
            result[3] *= 0.8

    result[0] = math.floor(result[0] + 0.5)
    result[1] = math.floor(result[1] + 0.5)
    result[2] = math.floor(result[2] + 0.5)
    result[3] = math.floor(result[3] + 0.5)
    result[4] = math.floor(result[4] + 0.5)
    mahjongempire_data["atk"] += result[0]
    mahjongempire_data["int"] += result[1]
    mahjongempire_data["sci"] += result[2]
    mahjongempire_data["whi"] += result[3]
    score = result[4]
    score += (10-int(min(mahjongempire_data["atk"],100-mahjongempire_data["atk"])/10))**2
    score += (10-int(min(mahjongempire_data["int"],100-mahjongempire_data["int"])/10))**2
    score += (10-int(min(mahjongempire_data["sci"],100-mahjongempire_data["sci"])/10))**2
    score += (10-int(min(mahjongempire_data["whi"],100-mahjongempire_data["whi"])/10))**2
    mahjongempire_data["score"] += score
    json_opt.SetJson(user_id,is_group,group_id,data)
    send.sendText(user_id,is_group,group_id,story)
    msg = str(mahjongempire_data["year"])+"年"+str(mahjongempire_data["month"])+"月结束\n"
    msg += "进攻/守备：" + str(mahjongempire_data["atk"]) + "/" +str(100-mahjongempire_data["atk"]) + "\n"
    msg += "正直/精明：" + str(mahjongempire_data["int"]) + "/" +str(100-mahjongempire_data["int"]) + "\n"
    msg += "科学/运势：" + str(mahjongempire_data["sci"]) + "/" +str(100-mahjongempire_data["sci"]) + "\n"
    msg += "门清/副露：" + str(mahjongempire_data["whi"]) + "/" +str(100-mahjongempire_data["whi"]) + "\n"
    msg += "点棒：" + str(mahjongempire_data["score"])
    
    send.sendText(user_id,is_group,group_id,msg)
    if(mahjongempire_data["atk"]>100 or mahjongempire_data["atk"]<0 or mahjongempire_data["int"]>100 or mahjongempire_data["int"]<0 or mahjongempire_data["sci"]>100 or mahjongempire_data["sci"]<0 or mahjongempire_data["whi"]>100 or mahjongempire_data["whi"]<0):
        GameOver(user_id,is_group,group_id)
    NextMonth(user_id,is_group,group_id)
    return
    
def NextMonth(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mahjongempire_data = data["data"]
    if(mahjongempire_data["month"] != 12):
        mahjongempire_data["month"] += 1
        r=random.randint(1,3)
        if(r == 1):
            count = 0
            for i in mahjongempire_data["regularEO"]:
                if(not i):
                    count += 1
            eventNum = random.randint(0,count-1)
            loc = 0
            while(True):
                if(mahjongempire_data["regularEO"][loc]):
                    loc+=1
                    continue
                if(eventNum == 0):
                    event = regularEvents[loc]
                    mahjongempire_data["regularEO"][loc] = True
                    break
                else:
                    eventNum -= 1
                    loc += 1
        else:
            count = 0
            for i in mahjongempire_data["yearEO"]:
                if(not i):
                    count += 1
            eventNum = random.randint(0,count-1)
            loc = 0
            while(True):
                if(mahjongempire_data["yearEO"][loc]):
                    loc+=1
                    continue
                if(eventNum == 0):
                    event = yearEvents[mahjongempire_data["year"]-1][loc]
                    mahjongempire_data["yearEO"][loc] = True
                    break
                else:
                    eventNum -= 1
                    loc += 1
    else:
        mahjongempire_data["year"] += 1
        mahjongempire_data["month"] = 1
        if(mahjongempire_data["year"] == 2):
            GameWin(user_id,is_group,group_id)
            return
        yearEO = []
        for i in range(len(yearEvents[mahjongempire_data["year"]-1])):
            yearEO.append(False)
        mahjongempire_data["yearEO"] = yearEO
        event = mainEvents[mahjongempire_data["mainEO"][mahjongempire_data["year"]-1]]
    mahjongempire_data["lastEvent"] = event
    json_opt.SetJson(user_id,is_group,group_id,data)
    msg = str(mahjongempire_data["year"])+"年"+str(mahjongempire_data["month"])+"月\n"
    msg+= event["story"]+"你选择：A."+event["a"]+",B."+event["b"]+"。"
    send.sendText(user_id,is_group,group_id,event["story"]+"你选择：A."+event["a"]+"，B."+event["b"]+"。")
    
    return

def GameOver(user_id,is_group,group_id):
    send.sendText(user_id,is_group,group_id,"似了啦，都你害的啦，反正结局还没做说是")
    json_opt.ResetJson(user_id,is_group,group_id)
    return 

def GameWin(user_id,is_group,group_id):
    send.sendText(user_id,is_group,group_id,"后面的区域以后再来探索吧")
    json_opt.ResetJson(user_id,is_group,group_id)

def UseItem(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    mahjongempire_data = data["data"]
    if(mahjongempire_data["item"]["used"]):
        return "道具已经使用过了"
    itemId = mahjongempire_data["item"]["itemId"]
    mahjongempire_data["item"]["used"] = True
    msg = ""
    if(itemId == 0):
        mahjongempire_data["atk"] = 50
        mahjongempire_data["int"] = 50
        mahjongempire_data["sci"] = 50
        mahjongempire_data["whi"] = 50
        msg = "使用《现代麻将的绝对手顺》使所有属性都变为50。"
    if(itemId == 1):
        mahjongempire_data["status"]["statusType"] = 2
        mahjongempire_data["status"]["statusNum"] = [1,1,0,1,1]
        mahjongempire_data["sci"] = 5
        msg = "使用《亚空间杀法》将运势变为95并且本年度不会再改变，替换当前的年度效果。"
    if(itemId == 2):
        mahjongempire_data["score"] = int(mahjongempire_data["score"] * 1.1)
        msg = "使用《雀魂绝艺总纲》提升10%的点棒数量。"
    json_opt.SetJson(user_id,is_group,group_id,data)
    return msg