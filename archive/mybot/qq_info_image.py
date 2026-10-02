
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import math
def generate_qq_image(qq_number, nickname):
    try:
        # 获取QQ头像
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={qq_number}&s=640"
        avatar_response = requests.get(avatar_url, timeout=5)
        
        if avatar_response.status_code != 200:
            print(f"获取头像失败，状态码: {avatar_response.status_code}")
            return None
        
        # 创建图片
        avatar_img = Image.open(BytesIO(avatar_response.content))
        width, height = avatar_img.size
        
        # 创建新图片，底部留出空间写文字
        new_image = Image.new("RGB", (width, height + 80), (255, 255, 255))
        new_image.paste(avatar_img, (0, 0))
        
        # 绘制文字
        draw = ImageDraw.Draw(new_image)
        # font = ImageFont.truetype("simhei.ttf", 24)  # 使用黑体
        # font = ImageFont.load_default()
        
        font_path = "C:\\mybot\\font\\阿里妈妈数黑体.ttf"
        font = ImageFont.truetype(font_path,25)

        # 绘制QQ号
        qq_text = f"QQ: {qq_number}"
        draw.text((10, height + 10), qq_text, font=font, fill=(0, 0, 0))
        
        # 绘制昵称
        nickname_text = f"昵称: {nickname}"
        draw.text((10, height + 45), nickname_text, font=font, fill=(0, 0, 0))
        
        # 保存图片
        # output_path = f"QQ_{qq_number}.jpg"
        output_path = f"C:\mybot\profile_picture\QQ_{qq_number}.jpg"
        new_image.save(output_path)
        
        return output_path
        
    except Exception as e:
        print(f"生成图片过程中出错: {e}")
        return None


def generate_qq_grid_image(qq_info_list):
    try:
        # 每行显示的头像数量
        items_per_row = 5
        
        # 单个头像区域的尺寸
        single_width = 150
        single_height = 200  # 头像加文字的高度
        
        # 计算行数
        total_items = len(qq_info_list)
        rows = math.ceil(total_items / items_per_row)
        
        grid_width = min(len(qq_info_list),items_per_row) * single_width
        grid_height = rows * single_height
        grid_image = Image.new("RGB", (grid_width, grid_height), (255, 255, 255))
        
        try:
            font = ImageFont.truetype("simhei.ttf", 14)
        except:
            font = ImageFont.load_default()
        
        for index, info in enumerate(qq_info_list):
            qq_number = info.get("qq", "")
            nickname = info.get("nickname", "")
            
            if not qq_number:
                continue
                
            row = index // items_per_row
            col = index % items_per_row
            x_offset = col * single_width
            y_offset = row * single_height
            
            avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={qq_number}&s=100"
            try:
                avatar_response = requests.get(avatar_url, timeout=5)
                
                if avatar_response.status_code == 200:
                    avatar_img = Image.open(BytesIO(avatar_response.content))
                    
                    # 调整头像大小
                    avatar_img = avatar_img.resize((100, 100))
                    
                    # 将头像放入网格
                    grid_image.paste(avatar_img, (x_offset + 25, y_offset + 10))
                    
                    # 绘制文字
                    draw = ImageDraw.Draw(grid_image)
                    
                    # 绘制QQ号
                    qq_text = f"QQ: {qq_number}"
                    draw.text((x_offset + 10, y_offset + 120), qq_text, font=font, fill=(0, 0, 0))
                    
                    # 绘制昵称
                    nickname_text = f"昵称: {nickname}"
                    draw.text((x_offset + 10, y_offset + 150), nickname_text, font=font, fill=(0, 0, 0))
                else:
                    print(f"获取QQ {qq_number} 的头像失败，状态码: {avatar_response.status_code}")
            except Exception as e:
                print(f"处理QQ {qq_number} 时出错: {e}")
        
        output_path = "C:\mybot\profile_picture\QQ_grid.jpg"
        grid_image.save(output_path)
        
        return output_path
        
    except Exception as e:
        print(f"生成网格图片过程中出错: {e}")
        return None
