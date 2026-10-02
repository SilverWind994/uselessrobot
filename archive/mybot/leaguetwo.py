import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
import requests
import photo_opt
import send_message as send

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def parse_json_data(json_data):
    table_data = []
    
    for team in json_data['table']:
        team_info = {
            '排名': team['rank'],
            '队伍名称': team['tname'],
            '总分': team['total_score'],
        }
        
        # 处理每个回合的分数细节
        for i, score_detail in enumerate(team['detail_score'], 1):
            team_info[f'第{i}轮PT'] = score_detail['s']
            team_info[f'第{i}轮详情'] = score_detail['d']
        
        table_data.append(team_info)
    
    return pd.DataFrame(table_data)

def create_detailed_table(df, title):
    column_num = len(df.columns)
    turn_num = int((column_num - 3)/2)
    fig, ax = plt.subplots(figsize=(18+3*turn_num, len(df)))
    ax.axis('tight')
    ax.axis('off')
    
    table_data = []
    columns = ['排名', '队伍名称', '总分']
    
    # 添加轮次列
    for i in range(1, turn_num+1):
        #columns.extend([f'第{i}轮PT', f'第{i}轮详情'])
        columns.extend([f'第{i}轮PT'])
    columns.extend([f'第{turn_num}轮详情'])
    # 填充数据
    for _, row in df.iterrows():
        row_data = []
        for col in columns:
            row_data.append(str(row[col]) if pd.notna(row[col]) else "")
        table_data.append(row_data)

    column_widths = {
        '排名': 0.03,
        '队伍名称': 0.14,
        '总分': 0.05,
    }
        # 为每轮的PT和详情列设置宽度
    for i in range(1, turn_num+1):
        column_widths[f'第{i}轮PT'] = 0.06
        #column_widths[f'第{i}轮详情'] = 0.14
    column_widths[f'第{turn_num}轮详情'] = 0.14
    
    # 创建列宽列表，按照columns的顺序
    col_widths_list = [column_widths[col] for col in columns]
    
    # 确保总宽度为1
    total_width = sum(col_widths_list)
    if total_width != 1:
        col_widths_list = [w / total_width for w in col_widths_list]
    
    # 创建表格
    table = ax.table(cellText=table_data,
                    colLabels=columns,
                    cellLoc='center',
                    loc='center',
                    colWidths=col_widths_list,
                    bbox=[0, 0, 1, 1])
    
    # 设置表格样式
    table.auto_set_font_size(False)
    table.set_fontsize(32)
    table.scale(1, 1.2)
    
    # 设置单元格颜色
    for i in range(len(table_data) + 1):
        for j in range(len(columns)):
            if j < 3:  # 前4列（基本信息）设置不同背景色
                table[(i, j)].set_facecolor('#f0f0f0')
            if i == 0:  # 表头
                table[(i, j)].set_facecolor('#4CAF50')
                table[(i, j)].set_text_props(weight='bold', color='white',fontsize = 32)
    
    # 设置标题
    plt.title(title, fontsize=32, fontweight='bold', pad=20)
    
    return fig, ax


def SuperLeagueTeam(user_id,is_group,group_id):
    url = "https://score.hieuzest.xyz/api/ranking_cfg?cid=207"
    LeagueTeam(user_id,is_group,group_id,url)

def LeagueOneTeam(user_id,is_group,group_id):
    url = "https://score.hieuzest.xyz/api/ranking_cfg?cid=208"
    LeagueTeam(user_id,is_group,group_id,url)

def LeagueTwoTeam(user_id,is_group,group_id):
    url = "https://score.hieuzest.xyz/api/ranking_cfg?cid=209"
    LeagueTeam(user_id,is_group,group_id,url)

def LeagueTeam(user_id,is_group,group_id,url):
    # url = "https://score.hieuzest.xyz/api/ranking_cfg?cid=209"
    response = requests.get(url)
    response.raise_for_status()  
    json_data = response.json()
    if(not isinstance(json_data,dict)):
        json_data = json_data[0]
    detailed_df = parse_json_data(json_data)
    
    # 创建详细表格
    fig, ax = create_detailed_table(detailed_df, json_data['cname'])
    filename = photo_opt.getPhotoPath(user_id,is_group,group_id)
    fig.savefig(filename)
    send.sendImg(user_id,is_group,group_id,filename)

def LeaguePlayer(user_id,is_group,group_id,tid):
    url = "https://cdn.r-mj.com/api/data.php?t=team&cid=209"
    response = requests.get(url)
    response.raise_for_status()
    json_data1 = response.json()
    url = "https://cdn.r-mj.com/api/data.php?t=multi_log&cid=209&r=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20" 
    response = requests.get(url)
    response.raise_for_status()
    json_data2 = response.json()
    
    if not tid in json_data1:
        url = "https://cdn.r-mj.com/api/data.php?t=team&cid=208"
        response = requests.get(url)
        response.raise_for_status()
        json_data1 = response.json()
        url = "https://cdn.r-mj.com/api/data.php?t=multi_log&cid=208&r=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20" 
        response = requests.get(url)
        response.raise_for_status()
        json_data2 = response.json()

        if not tid in json_data1:
            url = "https://cdn.r-mj.com/api/data.php?t=team&cid=207"
            response = requests.get(url)
            response.raise_for_status()
            json_data1 = response.json()
            url = "https://cdn.r-mj.com/api/data.php?t=multi_log&cid=207&r=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20" 
            response = requests.get(url)
            response.raise_for_status()
            json_data2 = response.json()

            if not tid in json_data1:
                return "无法查询该队伍id"

    team = json_data1[tid]
    players = team['t_player'].split('\n') + team['t_sub'].split('\n')
    team_name = team["t_name"]
    player_stats = {}
    for player in players:
        player_stats[player] = {
            'total_score': 0,
            'position_1': 0,
            'position_2': 0,
            'position_3': 0,
            'position_4': 0
        }

    # 遍历所有比赛数据
    for match_id, rounds in json_data2.items():
        for round_data in rounds:
            # 获取本局所有玩家的分数
            scores = []
            player_names = []
            for i in range(1, 5):
                scores.append(round_data[f'pint{i}'])
                player_names.append(round_data[f'name{i}'])
            
            # 计算每个玩家的排名
            # 使用argsort获取分数从高到低的索引
            sorted_indices = np.argsort(scores)[::-1]
            
            # 分配顺位
            for rank, idx in enumerate(sorted_indices):
                player_name = player_names[idx]
                if player_name in player_stats:
                    # 记录顺位次数
                    player_stats[player_name][f'position_{rank+1}'] += 1
                    # 累加分数
                    player_stats[player_name]['total_score'] += scores[idx]

    # 创建数据框
    data = []
    for player, stats in player_stats.items():
        data.append([
            player, 
            stats['total_score'], 
            stats['position_1'], 
            stats['position_2'], 
            stats['position_3'], 
            stats['position_4']
        ])

    df = pd.DataFrame(data, columns=['队员', '总分', '1位次数', '2位次数', '3位次数', '4位次数'])
    df = df.sort_values('总分', ascending=False)

    # 创建图片表格
    fig, ax = plt.subplots(figsize=(12, max(8, len(df) * 0.4)))  # 根据行数调整高度
    ax.axis('off')
    ax.axis('tight')

    # 创建表格
    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc='center',
        loc='center',
        bbox=[0, 0, 1, 1]  # 表格占满整个区域
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5) 


    for i in range(len(df.columns)):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')

    for i in range(1, len(df) + 1):
        color = '#F5F5F5' if i % 2 == 0 else '#FFFFFF' 
        for j in range(len(df.columns)):
            table[(i, j)].set_facecolor(color)

    for i in range(1, len(df) + 1):
        table[(i, 1)].set_text_props(weight='bold')  # 总分加粗

    plt.title(team_name+' 队员统计', fontsize=16, fontweight='bold', pad=20)

    filename = photo_opt.getPhotoPath(user_id,is_group,group_id)
    fig.savefig(filename)
    send.sendImg(user_id,is_group,group_id,filename)

