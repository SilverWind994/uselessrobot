import json_opt
import random
from PIL import Image,ImageDraw,ImageFont
import photo_opt
import send_message as send

def Hardle(user_id,is_group,group_id,message):
    status_data = json_opt.GetJson(user_id,is_group,group_id)

    if((status_data["status"]!="hardle")and(status_data["status"]!="none")):
        return "还在进行其他任务，输入结束/stop，结束任务后开始新的任务"
    elif(status_data["status"]=="none"):
        if(len(message)==1):
            return "请输入要猜测的单词的长度喵"
        else:
            if(not message[1].isdecimal()):
                return "要输入猜的单词的字母个数喵"
            length = int(message[1])
            if(length>15):
                return "太长了喵"
            if(length<2):
                return "太短了喵"
            with open("C:\\mybot\\hardle\\word"+str(length)+"c.txt", "r") as file:
                content = file.read()
            words = content.split(" ")
            words_num = len(words)
            choose = random.randint(0,words_num-1)
            word = words[choose].lower()
            status_data = {"status":"hardle","data":{"word":word,"guess":[],"yellow":[],"green":[],"len":length,"guess_time":0},"group_bind":False}
            json_opt.SetJson(user_id,is_group,group_id,status_data)
        return "猜单词开始，绿色代表猜中位置，黄色代表猜对字母但位置不对，单词长度为"+str(length)+"，更换了出题词库，现在不会出太生僻的词了，虽然这样长度15只有两个词了"
    else:
        word_guess = message[1]
        hardle_data = status_data["data"]
        length = hardle_data["len"]
        word_guess = word_guess.lower()
        with open("C:\\mybot\\hardle\\word"+str(length)+".txt", "r") as file:
            content = file.read()

        words = content.split(" ")
        guess_time = hardle_data["guess_time"]
        word = hardle_data["word"]
        
        if(len(message)==1):
            return "请猜一个单词"
        if(not word_guess.isalpha()):
            return "不太像个英文单词，咋办"
        if(len(word_guess) != length):
            return "长度不对喵"
        
        if(not word_guess in content):
            return "不认识这个单词喵，可能是我太笨了"
        if(word_guess in hardle_data["guess"]):
            return "这个单词已经猜过了喵"
        if(word_guess==word):
            json_opt.ResetJson(user_id,is_group,group_id)
            return "答对了喵"
        maxGuess = max(10,length)
        if(guess_time==maxGuess-1):
            json_opt.ResetJson(user_id,is_group,group_id)
            return "呜呜，次数达到上限了，正确答案是"+word
        hardle_data["guess"].append(word_guess)
        
        use_answer = []
        use_guess = []
        green = 0
        yellow = 0
        for i in range(length):
            if(word[i] == word_guess[i]):
                use_guess.append(True)
                use_answer.append(True)
                green += 1
            else:
                use_guess.append(False)
                use_answer.append(False)
        for i in range(length):
            if(use_guess[i]):
                continue
            for j in range(length):
                if(use_answer[j]):
                    continue
                if(word_guess[i] == word[j]):
                    use_answer[j] = True
                    yellow += 1
                    break
        hardle_data["green"].append(green)
        hardle_data["yellow"].append(yellow)
        hardle_data["guess_time"] += 1
        json_opt.SetJson(user_id,is_group,group_id,status_data)
        DrawBoardAndSend(user_id,is_group,group_id)
        return ""

def DrawBoardAndSend(user_id,is_group,group_id):
    data = json_opt.GetJson(user_id,is_group,group_id)
    hardle_data = data["data"]
    length = hardle_data["len"]
    long = max(10,length)
    guess_time = hardle_data["guess_time"]
    image = Image.new(mode='RGB',size=(length*60+90,30+60*long),color="white")
    draw = ImageDraw.Draw(image)
    for i in range(long):
        for j in range(length):
            draw.rectangle((20+j*60, 20+i*60, 70+j*60, 70+i*60), outline=(0,0,0), width=5)
        draw.rectangle((20+length*60, 20+i*60, 50+length*60, 50+i*60), outline=(225,225,0), width=20)
        draw.rectangle((40+length*60, 40+i*60, 70+length*60, 70+i*60), outline="green", width=20)
    
    font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
    font1 = ImageFont.truetype(font_path,40)
    font2 = ImageFont.truetype(font_path,20)
    for i in range(guess_time):
        for j in range(length):
            letter = hardle_data["guess"][i][j].upper()
            a,b,text_width,c = font1.getbbox(letter)
            draw.text((45-text_width/2+j*60,20+i*60),letter,"BLACK",font1)
        draw.text((30+60*length,20+60*i),str(hardle_data["yellow"][i]),"BLACK",font2)
        draw.text((50+60*length,40+60*i),str(hardle_data["green"][i]),"BLACK",font2)
    file_path = photo_opt.SavePhoto(user_id,is_group,group_id,image)
    send.sendImg(user_id,is_group,group_id,file_path)
    return 