"""17步麻将（mahjong17）—— 移植自 archive/mybot/mahjong_17.py。

玩法：群聊 2 人对局。开局者（创建对局的人）需指定本局是否为「猫眼石局」。
开局后双方各自在私聊里查看自己的 34 张牌，从中选出 13 张作为手牌（其余 21 张为舍牌候补），
然后轮流在私聊里打出舍牌候补的牌，也可以「荣和」对手刚打出的牌；17 巡无人和牌即流局。

私聊里直接发送 `17步麻将 <内容>` 即可操作：
· 选牌（游戏刚开始时）：`17步麻将 123m456p789s11z`（共 13 张，红五写作 0，如 0m）
· 打牌：`17步麻将 5m`（只能在「舍牌候补」里的牌中打）
· 荣和：`17步麻将 荣`
· 流局：最后一巡只能「17步麻将 荣」或「17步麻将 流局」

猫眼石结算（仅猫眼石局生效）：
· 赢家得分每满 4000 分，由输家支付 1 猫眼石（役满按 32000 分计，即 8 猫眼石）
· 诈胡（宣布荣和但无役）由诈胡者赔给对方 5 猫眼石
· 猫眼石不足时余额记成负数（欠债），欠债者不能参与猫眼石局
"""

import json
import os
import random
import time
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from core.command_router import CommandContext, CommandRouter
from core.message_sender import MessageSender, Target

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
_ASSETS_DIR = os.path.join(_BASE_DIR, "assets")
MAHJONG17_DIR = os.path.join(_ASSETS_DIR, "mahjong17")     # 运行时：对局状态与合成图
_STATE_PATH = os.path.join(MAHJONG17_DIR, "state.json")
_TILE_DIR = os.path.join(_ASSETS_DIR, "mahjong")           # 牌面素材 mj0.png ~ mj37.png

IDLE_SECONDS = 6 * 60 * 60   # 对局闲置超过该时长自动作废，避免卡住之后的开局
STONES_PER_SCORE = 4000      # 每 4000 分折算 1 猫眼石
MIN_WIN_SCORE = 8000         # 结算分数门槛：赢家得分不足此分数不赢猫眼石
FALSE_WIN_PENALTY = 5        # 诈胡赔给对方 5 猫眼石
PLAYER_NUM = 2               # 固定两人
LAST_TURN = 17               # 17 巡之后只能选择荣和或流局

# 指示牌 -> 宝牌（0~37 的牌编号：0/10/20 为红五，5/15/25 为普通五）
DORA_TO = {0: 6, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 1,
           10: 16, 11: 12, 12: 13, 13: 14, 14: 15, 15: 16, 16: 17, 17: 18, 18: 19, 19: 11,
           20: 26, 21: 22, 22: 23, 23: 24, 24: 25, 25: 26, 26: 27, 27: 28, 28: 29, 29: 21,
           31: 32, 32: 33, 33: 34, 34: 31, 35: 36, 36: 37, 37: 35}

_RON_WORDS = ("荣", "和", "荣和", "rong")
_PASS_WORDS = ("过", "流局", "pass")

# 群聊子指令别名
_STONE_WORDS = {"猫眼石", "猫眼石局", "有猫眼石", "stones"}
_PLAIN_WORDS = {"普通", "普通局", "无猫眼石", "plain", "free"}
_JOIN_WORDS = {"加入", "join"}
_HELP_WORDS = {"帮助", "help"}
_STATUS_WORDS = {"状态", "status", "查看", "info", ""}
_CANCEL_WORDS = {"取消", "解散", "退出", "quit", "cancel"}

_SUIT_BASE = {"m": 0, "p": 10, "s": 20, "z": 30}


# ==================== 通用小工具 ====================

def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
               r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


@lru_cache(maxsize=64)
def _tile_image(index: int):
    return Image.open(os.path.join(_TILE_DIR, f"mj{index}.png"))


def _tile_pos(x0: int, y0: int, loc: int, wrap_after, row_h: int):
    """按位置摆放牌面；wrap_after 表示每行放几张（None 表示不换行）"""
    if wrap_after is not None and loc >= wrap_after:
        return x0 + 43 * (loc - wrap_after), y0 + row_h
    return x0 + 43 * loc, y0


def _paste_tiles(image, counts, x0: int, y0: int, wrap_after=None, row_h: int = 65) -> None:
    """把 38 长度的计数数组画到图上（红五用 mj{i-5}.png 表示）"""
    loc = 0
    for i in range(38):
        if i % 10 == 0:
            continue
        if i % 10 == 5 and counts[i - 5] == 1:
            image.paste(_tile_image(i - 5), _tile_pos(x0, y0, loc, wrap_after, row_h))
            loc += 1
        for _ in range(counts[i]):
            image.paste(_tile_image(i), _tile_pos(x0, y0, loc, wrap_after, row_h))
            loc += 1


def _paste_discards(image, tiles, x0: int, y0: int) -> None:
    """画一行舍牌（数组以 -1 结尾）"""
    loc = 0
    for t in tiles:
        if t == -1:
            break
        image.paste(_tile_image(t), (x0 + 43 * loc, y0))
        loc += 1


# ==================== 算番（移植自旧版 GetType / GetQidui / GetFu / GetPoints） ====================

def _get_type(tiles, shunzi, kezi, quetou):
    if len(shunzi) + len(kezi) + len(quetou) == 5:
        return [[shunzi, kezi, quetou]]
    result = []
    for i in range(38):
        if tiles[i] != 0:
            if tiles[i] >= 3:
                t = tiles.copy()
                t[i] -= 3
                result += _get_type(t, shunzi, kezi + [i], quetou)
            if tiles[i] >= 2 and len(quetou) == 0:
                t = tiles.copy()
                t[i] -= 2
                result += _get_type(t, shunzi, kezi, quetou + [i])
            if i < 28 and tiles[i] != 0 and tiles[i + 1] != 0 and tiles[i + 2] != 0:
                t = tiles.copy()
                t[i] -= 1
                t[i + 1] -= 1
                t[i + 2] -= 1
                result += _get_type(t, shunzi + [i], kezi, quetou)
            break
    return result


def _get_qidui(tiles):
    qidui = []
    for v in tiles:
        if v == 0:
            continue
        if v == 2:
            qidui.append(v)
        else:
            return []
    return qidui


def _get_fu(shunzi, kezi, quetou, cut):
    fu = 30
    for i in kezi:
        if i % 10 == 1 or i % 10 == 9 or i > 30:
            fu += 8
            if cut == i:
                fu -= 4
                for j in shunzi:
                    if j == cut or j == cut - 1 or j == cut - 2:
                        fu += 4
        else:
            fu += 4
            if cut == i:
                fu -= 2
                for j in shunzi:
                    if j == cut or j == cut - 1 or j == cut - 2:
                        fu += 2
    if quetou[0] == cut:
        fu += 2
    else:
        for i in shunzi:
            if i == cut - 2 or (i % 10 == 1 and i == cut) or (i % 10 == 7 and i == cut):
                fu += 2
                break
    if quetou[0] in (31, 32, 35, 36, 37):
        fu += 2
    return fu + 9 - (fu + 9) % 10


def _score_hand(handtiles, cut, dora):
    """计算和牌得分，返回 (score, fu, fan, fans)。

    fan == 0 表示诈胡（无役）；fan >= 100 为役满（100 役满 / 200 两倍役满……）。
    """
    handtiles = handtiles.copy()   # 不改动调用方的存档
    handtiles_draw = handtiles.copy()
    tiles = handtiles.copy()
    tiles[cut] += 1
    redDoraNum = 0
    if tiles[0] == 1:
        tiles[0] = 0
        tiles[5] += 1
        redDoraNum += 1
    if tiles[10] == 1:
        tiles[10] = 0
        tiles[15] += 1
        redDoraNum += 1
    if tiles[20] == 1:
        tiles[20] = 0
        tiles[25] += 1
        redDoraNum += 1

    if handtiles[0] == 1:
        handtiles[0] = 0
        handtiles[5] += 1
    if handtiles[10] == 1:
        handtiles[10] = 0
        handtiles[15] += 1
    if handtiles[20] == 1:
        handtiles[20] = 0
        handtiles[25] += 1
    oDora = DORA_TO[dora[0]]
    oDoraNum = tiles[oDora]
    iDora = DORA_TO[dora[1]]
    iDoraNum = tiles[iDora]
    types = _get_type(tiles, [], [], [])
    qidui = _get_qidui(tiles)

    maxScore = 0
    maxFu = 0
    maxFan = 0
    maxFans = []

    if tiles[1] * tiles[9] * tiles[11] * tiles[19] * tiles[21] * tiles[29] * tiles[31] * tiles[32] * tiles[33] * tiles[34] * tiles[35] * tiles[36] * tiles[37] == 2:
        if tiles[cut] == 1:
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
        fu = _get_fu(shunzi, kezi, quetou, cut)
        fan = 0
        fans = []

        if (35 in kezi) and (36 in kezi) and (37 in kezi):
            score += 32000
            fan += 100
            fans.append("大三元")
        for i in range(0, 21, 10):
            leave = abs(handtiles[1 + i] - 3) + abs(handtiles[9 + i] - 3) + abs(handtiles[2 + i] - 1) + abs(handtiles[3 + i] - 1) + abs(handtiles[4 + i] - 1) + abs(handtiles[5 + i] - 1) + abs(handtiles[6 + i] - 1) + abs(handtiles[7 + i] == 1) + abs(handtiles[8 + i] - 1)
            if (leave == 0) and (cut > i) and (cut <= i + 9):
                score += 64000
                fan += 200
                fans.append("纯正九莲宝灯")
            if (leave == 2) and (handtiles[1 + i] + handtiles[2 + i] + handtiles[3 + i] + handtiles[4 + i] + handtiles[5 + i] + handtiles[6 + i] + handtiles[7 + i] + handtiles[8 + i] + handtiles[9 + i] == 13):
                if (cut - i == 1) or (cut - i == 9):
                    if handtiles[cut] == 2:
                        score += 32000
                        fan += 100
                        fans.append("九莲宝灯")
                else:
                    if handtiles[cut] == 0:
                        score += 32000
                        fan += 100
                        fans.append("九莲宝灯")
        if tiles[31] + tiles[32] + tiles[33] + tiles[34] + tiles[35] + tiles[36] + tiles[37] == 14:
            score += 32000
            fan += 100
            fans.append("字一色")
        if tiles[22] + tiles[23] + tiles[24] + tiles[26] + tiles[28] + tiles[36] == 14:
            score += 32000
            fan += 100
            fans.append("绿一色")
        if tiles[1] + tiles[9] + tiles[11] + tiles[19] + tiles[21] + tiles[29] == 14:
            score += 32000
            fan += 100
            fans.append("清老头")
        if tiles[31] + tiles[32] + tiles[33] + tiles[34] == 11:
            score += 32000
            fan += 100
            fans.append("小四喜")
        if len(kezi) == 4 and tiles[cut] == 2:
            score += 64000
            fan += 200
            fans.append("四暗刻单骑")
        if tiles[31] + tiles[32] + tiles[33] + tiles[34] == 12:
            score += 64000
            fan += 200
            fans.append("大四喜")

        if fan != 0:
            if score > maxScore:
                maxScore = score
                maxFu = fu
                maxFan = fan
                maxFans = fans
            continue

        fan += 1
        fans.append(["立直", "1番"])
        if tiles[1] + tiles[9] + tiles[11] + tiles[19] + tiles[21] + tiles[29] + tiles[31] + tiles[32] + tiles[33] + tiles[34] + tiles[35] + tiles[36] + tiles[37] == 0:
            fan += 1
            fans.append(["断幺九", "1番"])
        if tiles[32] == 3:
            fan += 1
            fans.append(["自风牌：南", "1番"])
        if tiles[31] == 3:
            fan += 1
            fans.append(["场风牌：东", "1番"])
        if tiles[35] == 3:
            fan += 1
            fans.append(["三元牌：白", "1番"])
        if tiles[36] == 3:
            fan += 1
            fans.append(["三元牌：发", "1番"])
        if tiles[37] == 3:
            fan += 1
            fans.append(["三元牌：中", "1番"])
        if len(shunzi) == 4:
            for i in shunzi:
                if ((i == cut) and (i % 10 < 7)) or ((i == cut - 2) and (i % 10 > 1)):
                    if quetou[0] not in (31, 32, 35, 36, 37):
                        fan += 1
                        fans.append(["平和", "1番"])
                        fu = 30
                        break
        yibeikouCount = 0
        for i in range(len(shunzi)):
            for j in range(i + 1, len(shunzi)):
                if shunzi[i] == shunzi[j]:
                    yibeikouCount += 1
        if (yibeikouCount == 1) or (yibeikouCount == 3):
            fan += 1
            fans.append(["一杯口", "1番"])
        if len(kezi) >= 3:
            for i in range(1, 10):
                if (i in kezi) and ((i + 10) in kezi) and ((20 + i) in kezi):
                    fan += 2
                    fans.append(["三色同刻", "2番"])
        if len(kezi) == 4:
            fan += 2
            fans.append(["对对和", "2番"])
            fan += 2
            fans.append(["三暗刻", "2番"])
        if (len(kezi) == 3) and (cut not in kezi):
            fan += 2
            fans.append(["三暗刻", "2番"])
        if tiles[35] + tiles[36] + tiles[37] == 8:
            fan += 2
            fans.append(["小三元", "2番"])

        chunquanJudge = True
        for i in shunzi:
            if i % 10 != 1 and i % 10 != 7:
                chunquanJudge = False
                break
        for i in kezi:
            if ((i % 10 != 1) and (i % 10 != 9)) or (i > 30):
                chunquanJudge = False
                break
        if ((quetou[0] % 10 != 1) and (quetou[0] % 10 != 9)) or (quetou[0] > 30):
            chunquanJudge = False

        if tiles[1] + tiles[9] + tiles[11] + tiles[19] + tiles[21] + tiles[29] + tiles[31] + tiles[32] + tiles[33] + tiles[34] + tiles[35] + tiles[36] + tiles[37] == 14:
            fan += 2
            fans.append(["混老头", "2番"])
        else:
            judge = True
            if chunquanJudge:
                judge = False
            for i in shunzi:
                if i % 10 != 1 and i % 10 != 7:
                    judge = False
                    break
            for i in kezi:
                if i % 10 != 1 and i % 10 != 9 and i < 30:
                    judge = False
                    break
            if quetou[0] % 10 != 1 and quetou[0] % 10 != 9 and quetou[0] < 30:
                judge = False
            if judge:
                fan += 2
                fans.append(["混全带幺九", "2番"])
        for i in range(0, 21, 10):
            if ((i + 1) in shunzi) and ((i + 4) in shunzi) and ((i + 7) in shunzi):
                fan += 2
                fans.append(["一气通贯", "2番"])
        for i in range(1, 8):
            if (i in shunzi) and ((i + 10) in shunzi) and ((20 + i) in shunzi):
                fan += 2
                fans.append(["三色同顺", "2番"])
        if (yibeikouCount == 2) or (yibeikouCount == 6):
            fan += 3
            fans.append(["二杯口", "3番"])

        if chunquanJudge:
            fan += 3
            fans.append(["纯全带幺九", "3番"])
        for i in range(0, 21, 10):
            if tiles[i + 1] + tiles[i + 2] + tiles[i + 3] + tiles[i + 4] + tiles[i + 5] + tiles[i + 6] + tiles[i + 7] + tiles[i + 8] + tiles[i + 9] == 14:
                fan += 6
                fans.append(["清一色", "6番"])
            elif tiles[i + 1] + tiles[i + 2] + tiles[i + 3] + tiles[i + 4] + tiles[i + 5] + tiles[i + 6] + tiles[i + 7] + tiles[i + 8] + tiles[i + 9] + tiles[31] + tiles[32] + tiles[33] + tiles[34] + tiles[35] + tiles[36] + tiles[37] == 14:
                fan += 3
                fans.append(["混一色", "3番"])
        if oDoraNum != 0:
            fan += oDoraNum
            fans.append(["宝牌", str(oDoraNum) + "番"])
        if redDoraNum != 0:
            fan += redDoraNum
            fans.append(["红宝牌", str(redDoraNum) + "番"])
        if iDoraNum != 0:
            fan += iDoraNum
            fans.append(["里宝牌", str(iDoraNum) + "番"])

        if fan == 1:
            if fu == 30:
                score = 1000
            if fu == 40:
                score = 1300
            if fu == 50:
                score = 1600
            if fu == 60:
                score = 2000
            if fu == 70:
                score = 2300
        if fan == 2:
            if fu == 30:
                score = 2000
            if fu == 40:
                score = 2600
            if fu == 50:
                score = 3200
            if fu == 60:
                score = 3900
            if fu == 70:
                score = 4500
        if fan == 3:
            if fu == 30:
                score = 3900
            if fu == 40:
                score = 5200
            if fu == 50:
                score = 6400
            if fu == 60:
                score = 8000
            if fu == 70:
                score = 8000
        if fan == 4:
            if fu == 30:
                score = 8000
            else:
                score = 8000
        if fan == 5:
            score = 8000
        if fan >= 6:
            score = 12000
        if fan >= 8:
            score = 16000
        if fan >= 11:
            score = 24000
        if fan >= 13:
            score = 32000
        if score > maxScore:
            maxScore = score
            maxFu = fu
            maxFan = fan
            maxFans = fans

    if len(qidui) != 0:
        if qidui[0] == 31:
            maxScore = 32000
            maxFu = 25
            maxFan = 100
            maxFans = ["字一色"]

        score = 0
        fu = 25
        fan = 0
        fans = []

        fan += 1
        fans.append(["立直", "1番"])
        if tiles[1] + tiles[9] + tiles[11] + tiles[19] + tiles[21] + tiles[29] + tiles[31] + tiles[32] + tiles[33] + tiles[34] + tiles[35] + tiles[36] + tiles[37] == 0:
            fan += 1
            fans.append(["断幺九", "1番"])
        fan += 2
        fans.append(["七对", "2番"])
        if tiles[1] + tiles[9] + tiles[11] + tiles[19] + tiles[21] + tiles[29] + tiles[31] + tiles[32] + tiles[33] + tiles[34] + tiles[35] + tiles[36] + tiles[37] == 14:
            fan += 2
            fans.append(["混老头", "2番"])
        for i in range(0, 21, 10):
            if tiles[i + 1] + tiles[i + 2] + tiles[i + 3] + tiles[i + 4] + tiles[i + 5] + tiles[i + 6] + tiles[i + 7] + tiles[i + 8] + tiles[i + 9] == 14:
                fan += 6
                fans.append(["清一色", "6番"])
            elif tiles[i + 1] + tiles[i + 2] + tiles[i + 3] + tiles[i + 4] + tiles[i + 5] + tiles[i + 6] + tiles[i + 7] + tiles[i + 8] + tiles[i + 9] + tiles[31] + tiles[32] + tiles[33] + tiles[34] + tiles[35] + tiles[36] + tiles[37] == 14:
                fan += 3
                fans.append(["混一色", "3番"])
        if oDoraNum != 0:
            fan += oDoraNum
            fans.append(["宝牌", str(oDoraNum) + "番"])
        if redDoraNum != 0:
            fan += redDoraNum
            fans.append(["红宝牌", str(redDoraNum) + "番"])
        if iDoraNum != 0:
            fan += iDoraNum
            fans.append(["里宝牌", str(iDoraNum) + "番"])

        if fan == 3:
            score = 3200
        if fan == 4:
            score = 6400
        if fan == 5:
            score = 8000
        if fan >= 6:
            score = 12000
        if fan >= 8:
            score = 16000
        if fan >= 11:
            score = 24000
        if fan >= 13:
            score = 32000
        if score > maxScore:
            maxScore = score
            maxFu = fu
            maxFan = fan
            maxFans = fans

    return maxScore, maxFu, maxFan, maxFans


# ==================== 插件 ====================

class Mahjong17Plugin:
    """17步麻将：群聊两人对局 + 可选的猫眼石局"""

    def __init__(self, sender: MessageSender, cat_plugin=None):
        self._sender = sender
        self._cat = cat_plugin  # 猫猫远征队插件，用于猫眼石结算
        self._result_reporter = None

    def set_result_reporter(self, reporter) -> None:
        """锦标赛等外部编排器注册结果回调：reporter(group_id, result)"""
        self._result_reporter = reporter

    def _report_result(self, gid: int, result: dict) -> None:
        """对局结束时把结果上报给外部编排器（未注册则忽略）"""
        if self._result_reporter is not None:
            self._result_reporter(gid, result)

    def start_tournament_match(self, gid: int, players) -> bool:
        """锦标赛直接开局：用指定两位选手创建并开始一局普通（无猫眼石）17步麻将。

        成功返回 True；本群已有未结束的对局、或某位选手已在别的对局中时返回 False。
        """
        if self._load_game(gid) is not None:
            return False
        for uid, _name in players:
            other, _ = self._find_player_game(uid)
            if other is not None:
                return False
        game = {
            "stones": False,
            "started": True,
            "player_id": [players[0][0], players[1][0]],
            "player_name": [players[0][1], players[1][1]],
            "turn": -1,
            "player_turn": 0,
            "furiten": [False, False],
            "dora": [-1, -1],
            "tiles": [[0] * 38, [0] * 38],
            "hand_tiles": [[-1] + [0] * 37, [-1] + [0] * 37],
            "left_tiles": [[0] * 38, [0] * 38],
            "take_tiles": [[-1] * LAST_TURN, [-1] * LAST_TURN],
        }
        self._deal(game)
        self._save_game(gid, game)
        self._send_initial_tiles(game)
        self._send_group_text(
            gid, f"🀄 锦标赛17步麻将：{players[0][1]} 与 {players[1][1]} 对局，"
                 f"双方请在私聊组建手牌并出牌")
        return True

    # ==================== 注册命令 ====================

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["17步麻将", "mahjong17", ".mj17"],
            self.cmd_entry,
            description="17步麻将·群聊两人对局（可选猫眼石局）"
        )

    def cmd_entry(self, ctx: CommandContext) -> None:
        if ctx.is_group:
            self._cmd_group(ctx)
        else:
            self._cmd_private(ctx)

    # ==================== 群聊：开局 / 加入 / 状态 ====================

    def _cmd_group(self, ctx: CommandContext) -> None:
        self._drop_stale(ctx)
        args = ctx.get_args().strip()
        parts = args.split(None, 1)
        sub = parts[0] if parts else ""

        if sub in _JOIN_WORDS:
            self._cmd_join(ctx)
        elif sub in _STONE_WORDS:
            self._cmd_create(ctx, stones=True)
        elif sub in _PLAIN_WORDS:
            self._cmd_create(ctx, stones=False)
        elif sub in _HELP_WORDS:
            self._sender.reply(ctx, self._help_text())
        elif sub in _STATUS_WORDS:
            self._show(ctx)
        elif sub in _CANCEL_WORDS:
            self._cmd_cancel(ctx)
        else:
            self._sender.reply(ctx, "指令有误喵，发送「17步麻将 帮助」查看玩法")

    def _cmd_create(self, ctx: CommandContext, stones: bool) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is not None:
            self._sender.reply(ctx, "本群已经有一局17步麻将了，等它结束后再开新局喵")
            return
        other, _ = self._find_player_game(ctx.user_id)
        if other is not None:
            self._sender.reply(ctx, "你已经在另一局17步麻将中喵")
            return
        if stones and self._debt_of(ctx.user_id) > 0:
            self._sender.reply(
                ctx, f"你还有 {self._debt_of(ctx.user_id)} 个猫眼石欠债，不能开猫眼石局喵")
            return
        game = {
            "stones": stones,
            "started": False,
            "player_id": [ctx.user_id, 0],
            "player_name": [ctx.user_name, ""],
            "turn": -1,
            "player_turn": 0,
            "furiten": [False, False],
            "dora": [-1, -1],
            "tiles": [[0] * 38, [0] * 38],
            "hand_tiles": [[-1] + [0] * 37, [-1] + [0] * 37],
            "left_tiles": [[0] * 38, [0] * 38],
            "take_tiles": [[-1] * LAST_TURN, [-1] * LAST_TURN],
        }
        self._save_game(gid, game)
        match_text = "猫眼石局（每4000分=1猫眼石）" if stones else "普通局"
        self._sender.reply(
            ctx, f"准备十七步麻将，{ctx.user_name}加入游戏，当前1名玩家。本局{match_text}。\n"
                 f"另一位玩家发送「17步麻将 加入」即可开局")

    def _cmd_join(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None:
            self._sender.reply(
                ctx, "还没有对局喵，请先发送「17步麻将 猫眼石」或「17步麻将 普通」创建对局")
            return
        if game["started"] or game["player_id"][1] != 0:
            self._sender.reply(ctx, "游戏已经开始了")
            return
        if game["player_id"][0] == ctx.user_id:
            self._sender.reply(ctx, "你已经在准备中")
            return
        other, _ = self._find_player_game(ctx.user_id)
        if other is not None:
            self._sender.reply(ctx, "你已经在另一局17步麻将中喵")
            return
        if game.get("stones") and self._debt_of(ctx.user_id) > 0:
            self._sender.reply(
                ctx, f"你还有 {self._debt_of(ctx.user_id)} 个猫眼石欠债，"
                     f"不能加入猫眼石局喵")
            return

        game["player_id"][1] = ctx.user_id
        game["player_name"][1] = ctx.user_name
        self._deal(game)
        game["started"] = True
        self._save_game(gid, game)

        dora_text = self._tile_text(game["dora"][0])
        self._send_initial_tiles(game)
        self._sender.reply(
            ctx,
            f"十七步麻将开始，双方请在私聊中组建手牌。本局宝牌指示牌为{dora_text}"
            + ("（本局为猫眼石局）" if game.get("stones") else ""))

    def _cmd_cancel(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None:
            self._sender.reply(ctx, "本群没有进行中的17步麻将喵")
            return
        if game["started"]:
            self._sender.reply(ctx, "对局已经开始了，开局后必须打完整局喵")
            return
        if game["player_id"][0] != ctx.user_id:
            self._sender.reply(ctx, "只有开局的人才能取消这局喵")
            return
        self._remove_game(gid)
        self._sender.reply(ctx, f"{ctx.user_name} 取消了还没开局的17步麻将")

    def _show(self, ctx: CommandContext) -> None:
        game = self._load_game(ctx.group_id)
        if game is None:
            self._sender.reply(
                ctx, "本群还没有17步麻将对局喵，发送「17步麻将 猫眼石」或「17步麻将 普通」创建")
            return
        if not game["started"]:
            self._sender.reply(
                ctx, f"17步麻将准备中（1/2）：{game['player_name'][0]}\n"
                     f"发送「17步麻将 加入」加入，或「17步麻将 取消」解散"
                     + ("（本局为猫眼石局）" if game.get("stones") else "（本局为普通局）"))
            return
        self._send_table(ctx.group_id, game)

    # ==================== 私聊：选牌 / 打牌 / 荣和 / 流局 ====================

    def _cmd_private(self, ctx: CommandContext) -> None:
        args = ctx.get_args().strip()
        head = args.split(None, 1)[0] if args else ""
        if head in _HELP_WORDS:
            self._sender.reply(ctx, self._help_text())
            return

        game, gid = self._find_player_game(ctx.user_id)
        if game is None:
            self._sender.reply(ctx, "你当前没有进行中的17步麻将对局喵，请在群聊里开局或加入")
            return
        if not game["started"]:
            self._sender.reply(ctx, "游戏暂未开始")
            return
        if not args:
            self._sender.reply(ctx, "缺少需要整理或者打出的牌")
            return

        pid = 0 if game["player_id"][0] == ctx.user_id else 1
        if game["turn"] == -1:
            self._handle_select(ctx, game, gid, pid, args)
        else:
            self._handle_play(ctx, game, gid, pid, args)

    def _handle_select(self, ctx: CommandContext, game: dict, gid: int, pid: int, text: str) -> None:
        if game["hand_tiles"][pid][0] != -1:
            self._sender.reply(ctx, "已经选好牌了，请等待对手选牌")
            return
        select_num = [0] * 10
        select_tile = [0] * 38
        for c in text:
            if c.isdecimal():
                select_num[int(c)] += 1
            elif c in _SUIT_BASE:
                if c == "z" and select_num[0] + select_num[8] + select_num[9] > 0:
                    self._sender.reply(ctx, "有不认识的字牌")
                    return
                base = _SUIT_BASE[c]
                for i in range(10):
                    if select_num[i] == 0:
                        continue
                    select_tile[i + base] += select_num[i]
                    select_num[i] = 0
            else:
                self._sender.reply(ctx, "选择牌的格式不正确")
                return
        if text[-1] not in _SUIT_BASE:
            self._sender.reply(ctx, "选择牌的格式不正确")
            return
        if sum(select_tile) != 13:
            self._sender.reply(ctx, "选择的牌数需要为13张")
            return
        for i in range(38):
            if game["tiles"][pid][i] < select_tile[i]:
                self._sender.reply(ctx, "选择了自己未拥有的牌")
                return
            game["left_tiles"][pid][i] = game["tiles"][pid][i] - select_tile[i]
            game["hand_tiles"][pid][i] = select_tile[i]

        if game["hand_tiles"][1 - pid][0] != -1:
            game["turn"] = 0
            self._send_private_text(game["player_id"][game["player_turn"]], "请打出第一张牌")
            self._save_game(gid, game)
            self._send_view(gid, game, 0)
            self._send_table(gid, game)
        else:
            self._save_game(gid, game)
        self._sender.reply(ctx, "选牌完毕")

    def _handle_play(self, ctx: CommandContext, game: dict, gid: int, pid: int, text: str) -> None:
        if pid != game["player_turn"]:
            self._sender.reply(ctx, "当前不是你的回合")
            return

        if text in _RON_WORDS:
            self._handle_ron(ctx, game, gid, pid)
            return
        if game["turn"] == LAST_TURN:
            if text in _PASS_WORDS:
                self._send_group_text(gid, "流局")
                self._send_private_text(game["player_id"][1 - pid], "流局")
                self._send_end_table(gid, game)
                self._report_result(gid, {
                    "game": "mahjong17",
                    "players": [{"id": int(game["player_id"][i]),
                                 "name": game["player_name"][i]}
                                for i in range(PLAYER_NUM)],
                    "winner": None,
                    "reason": "流局",
                })
                self._remove_game(gid)
                return
            self._sender.reply(ctx, "当前只能选择荣和或者流局")
            return

        if len(text) != 2 or not text[0].isdecimal() or text[1] not in _SUIT_BASE:
            self._sender.reply(ctx, "无法识别打出的牌")
            return
        tile = int(text[0])
        if text[1] == "p":
            tile += 10
        if text[1] == "s":
            tile += 20
        if text[1] == "z":
            if tile == 0 or tile == 8 or tile == 9:
                self._sender.reply(ctx, "无法识别打出的牌")
                return
            tile += 30
        if game["left_tiles"][pid][tile] == 0:
            self._sender.reply(ctx, "剩余手牌中没有这张牌")
            return
        # 振听（对手舍牌）：本回合对手打出的是自己的和了牌，不荣和就进入振听
        cut = self._last_discard(game, pid)
        if (cut is not None and not game["furiten"][pid]
                and _score_hand(game["hand_tiles"][pid], cut, game["dora"])[2] > 0):
            game["furiten"][pid] = True
            self._send_private_text(
                game["player_id"][pid], "你放过了可以荣和的牌，本局进入振听，之后再荣和算诈和")
        game["left_tiles"][pid][tile] -= 1
        game["take_tiles"][pid][game["turn"]] = tile
        # 振听（自己舍牌）：打出的恰好是自己的和了牌，同样进入振听
        if (not game["furiten"][pid]
                and _score_hand(game["hand_tiles"][pid], tile, game["dora"])[2] > 0):
            game["furiten"][pid] = True
            self._send_private_text(
                game["player_id"][pid], "你打出了自己的和了牌，本局进入振听，之后再荣和算诈和")
        game["player_turn"] += 1
        if game["player_turn"] == PLAYER_NUM:
            game["player_turn"] = 0
            game["turn"] += 1
        self._send_private_text(game["player_id"][game["player_turn"]], "对手打出" + text)
        self._save_game(gid, game)
        self._send_view(gid, game, game["player_turn"])
        self._send_table(gid, game)
        self._sender.reply(ctx, "你打出了" + text)

    @staticmethod
    def _last_discard(game: dict, pid: int):
        """当前玩家面对的那张对手舍牌（庄家首巡还没人打牌则返回 None）"""
        if pid == 0:
            if game["turn"] == 0:
                return None
            return game["take_tiles"][1][game["turn"] - 1]
        return game["take_tiles"][0][game["turn"]]

    def _handle_ron(self, ctx: CommandContext, game: dict, gid: int, pid: int) -> None:
        if pid == 0 and game["turn"] == 0:
            # 庄家还没打牌，没有可荣和的牌：不算和牌，对局照常继续
            self._sender.reply(ctx, "还没有人打牌，无法荣和")
            return
        self._send_group_text(gid, game["player_name"][pid] + "宣布荣和")
        self._send_end_table(gid, game)
        self._send_private_text(game["player_id"][1 - pid], "对手宣布荣和")
        if game["furiten"][pid]:
            # 振听后不能再荣和，宣布荣和按诈和处理（赔对方 5 猫眼石）
            self._send_group_text(gid, game["player_name"][pid] + "已经振听，宣布荣和算诈和！")
            for line in self._settle(game, pid, 0, 0):
                self._send_group_text(gid, line)
            self._report_result(gid, {
                "game": "mahjong17",
                "players": [{"id": int(game["player_id"][i]),
                             "name": game["player_name"][i]}
                            for i in range(PLAYER_NUM)],
                "winner": int(game["player_id"][1 - pid]),
                "reason": "诈胡判负",
            })
            self._remove_game(gid)
            return
        if pid == 0:
            cut = game["take_tiles"][1][game["turn"] - 1]
        else:
            cut = game["take_tiles"][0][game["turn"]]

        score, fu, fan, fans = _score_hand(game["hand_tiles"][pid], cut, game["dora"])
        self._send_result(gid, game["hand_tiles"][pid], cut, game["dora"], score, fu, fan, fans)
        if fan == 0:
            # 无役不成和：宣布荣和按诈胡处理，宣布者判负
            self._report_result(gid, {
                "game": "mahjong17",
                "players": [{"id": int(game["player_id"][i]),
                             "name": game["player_name"][i]}
                            for i in range(PLAYER_NUM)],
                "winner": int(game["player_id"][1 - pid]),
                "reason": "诈胡判负",
            })
        else:
            self._report_result(gid, {
                "game": "mahjong17",
                "players": [{"id": int(game["player_id"][i]),
                             "name": game["player_name"][i]}
                            for i in range(PLAYER_NUM)],
                "winner": int(game["player_id"][pid]),
                "reason": "荣和",
            })
        for line in self._settle(game, pid, score, fan):
            self._send_group_text(gid, line)
        self._remove_game(gid)

    # ==================== 猫眼石结算 ====================

    def _settle(self, game: dict, winner_pid: int, score: int, fan: int) -> list:
        """按猫眼石结算，返回需要发到群里的说明行"""
        if not game.get("stones"):
            return []
        if self._cat is None:
            return ["（猫眼石结算失败：猫眼石系统不可用）"]
        winner = game["player_id"][winner_pid]
        loser = game["player_id"][1 - winner_pid]
        if fan == 0:
            # 诈胡：宣布荣和的人赔对方 5 猫眼石
            amount = FALSE_WIN_PENALTY
            payer, receiver = winner, loser
        else:
            if score < MIN_WIN_SCORE:
                return [f"本局赢家得分 {score} 分，不足 {MIN_WIN_SCORE} 分，不赢猫眼石"]
            amount = score // STONES_PER_SCORE
            payer, receiver = loser, winner

        before = self._cat.get_eye_stones(payer)
        self._cat.add_eye_stones(receiver, amount)
        after = self._cat.add_eye_stones(payer, -amount)

        lines = []
        if fan == 0:
            lines.append(f"诈胡！{game['player_name'][winner_pid]} 赔给 "
                         f"{game['player_name'][1 - winner_pid]} {amount} 猫眼石"
                         f"（余额 {before} → {after}）")
        else:
            lines.append(f"{game['player_name'][winner_pid]} 得分 {score} 分，"
                         f"{game['player_name'][1 - winner_pid]} 支付 {amount} 猫眼石"
                         f"（余额 {before} → {after}）")
        if after < 0:
            lines.append(f"猫眼石不足，现有欠债 {-after} 个，还清前不能参与猫眼石局")
        return lines

    def _debt_of(self, user_id: int) -> int:
        """玩家的猫眼石欠债数量（余额为负时为其绝对值）"""
        if self._cat is None:
            return 0
        balance = self._cat.get_eye_stones(user_id)
        return -balance if balance < 0 else 0

    # ==================== 发牌 ====================

    @staticmethod
    def _deal(game: dict) -> None:
        """洗牌并发牌：每人 34 张，另定两张指示牌（红五在 0/10/20 号位）"""
        mountain = []
        for base in (0, 10, 20):
            for i in range(1, 10):
                mountain += [base + i] * 4       # 万/筒/索各 1~9
        for i in range(31, 38):
            mountain += [i] * 4                  # 字牌东南西北白发中（共 136 张）
        mountain[16] = 0
        mountain[52] = 10
        mountain[88] = 20
        for i in range(136):
            change = random.randint(i, 135)
            mountain[i], mountain[change] = mountain[change], mountain[i]
        for i in range(34):
            game["tiles"][0][mountain[i]] += 1
            game["tiles"][1][mountain[i + 34]] += 1
        game["dora"] = [mountain[68], mountain[69]]

    # ==================== 状态存取 ====================

    def _load_game(self, group_id: int):
        game = _load_json(_STATE_PATH).get(str(group_id))
        if game is not None:
            game.setdefault("furiten", [False, False])   # 兼容旧存档
        return game

    def _save_game(self, group_id: int, game: dict) -> None:
        game["updated_at"] = time.time()
        state = _load_json(_STATE_PATH)
        state[str(group_id)] = game
        _save_json(_STATE_PATH, state)

    def _remove_game(self, group_id: int) -> None:
        state = _load_json(_STATE_PATH)
        if str(group_id) in state:
            del state[str(group_id)]
            _save_json(_STATE_PATH, state)

    def _find_player_game(self, user_id: int):
        """按玩家 QQ 反查其所在对局，返回 (game, group_id)，没有则 (None, None)"""
        state = _load_json(_STATE_PATH)
        found = [(g, int(k)) for k, g in state.items()
                 if user_id in g.get("player_id", [])]
        started = [x for x in found if x[0].get("started")]
        pool = started or found
        if not pool:
            return None, None
        pool.sort(key=lambda x: x[0].get("updated_at", 0))
        return pool[-1]

    def _drop_stale(self, ctx: CommandContext) -> None:
        game = self._load_game(ctx.group_id)
        if game is None:
            return
        if time.time() - game.get("updated_at", 0) <= IDLE_SECONDS:
            return
        self._remove_game(ctx.group_id)
        self._sender.reply(
            ctx, f"上一局17步麻将闲置超过 {IDLE_SECONDS // 3600} 小时，已自动作废喵")

    # ==================== 消息发送 ====================

    def _send_group_text(self, group_id: int, text: str) -> None:
        self._sender.send_text(Target(user_id=0, group_id=group_id, is_group=True), text)

    def _send_private_text(self, user_id: int, text: str) -> None:
        self._sender.send_text(Target(user_id=user_id, is_group=False), text)

    def _send_group_image(self, group_id: int, path: str) -> None:
        self._sender.send_image(Target(user_id=0, group_id=group_id, is_group=True), path)

    def _send_private_image(self, user_id: int, path: str) -> None:
        self._sender.send_image(Target(user_id=user_id, is_group=False), path)

    @staticmethod
    def _tile_text(tile: int) -> str:
        """牌编号 -> 文本（如 5m / 0p / 35 -> 白）"""
        head = tile % 10
        zone = tile // 10
        return str(head) + ("mpsz"[zone] if zone < 4 else "")

    # ==================== 绘图 ====================

    def _send_initial_tiles(self, game: dict) -> None:
        """开局时把双方各自的 34 张牌私聊发过去，并提示宝牌指示牌"""
        dora_text = self._tile_text(game["dora"][0])
        for pid in range(PLAYER_NUM):
            try:
                path = self._render_34(game, pid)
            except Exception as e:
                self._send_private_text(game["player_id"][pid], f"手牌绘制失败了喵：{e}")
                continue
            self._send_private_image(game["player_id"][pid], path)
            self._send_private_text(
                game["player_id"][pid],
                f"本局宝牌指示牌为{dora_text}；发送「17步麻将 123m456p789s11z」选13张手牌"
                f"（红五写作0，如 0m）")

    def _send_view(self, gid: int, game: dict, pid: int) -> None:
        try:
            path = self._render_view(game, pid)
        except Exception as e:
            self._send_private_text(game["player_id"][pid], f"手牌绘制失败了喵：{e}")
            return
        self._send_private_image(game["player_id"][pid], path)

    def _send_table(self, gid: int, game: dict) -> None:
        try:
            path = self._render_table(game)
        except Exception as e:
            self._send_group_text(gid, f"牌桌绘制失败了喵：{e}")
            return
        self._send_group_image(gid, path)

    def _send_end_table(self, gid: int, game: dict) -> None:
        try:
            path = self._render_end_table(game)
        except Exception as e:
            self._send_group_text(gid, f"牌桌绘制失败了喵：{e}")
            return
        self._send_group_image(gid, path)

    def _send_result(self, gid: int, hand, cut: int, dora, score: int,
                     fu: int, fan: int, fans: list) -> None:
        try:
            path = self._render_result(gid, hand, cut, dora, score, fu, fan, fans)
        except Exception as e:
            self._send_group_text(gid, f"算分图绘制失败了喵：{e}")
            return
        self._send_group_image(gid, path)

    def _render_34(self, game: dict, pid: int) -> str:
        """单方 34 张牌（私聊用）"""
        image = Image.new(mode="RGB", size=(734, 135), color="SteelBlue")
        _paste_tiles(image, game["tiles"][pid], 3, 5, wrap_after=17, row_h=65)
        os.makedirs(MAHJONG17_DIR, exist_ok=True)
        path = os.path.join(MAHJONG17_DIR, f"tiles_{pid}_{game['player_id'][pid]}.png")
        image.save(path)
        return path

    def _render_view(self, game: dict, pid: int) -> str:
        """玩家的私聊视图：对手舍牌 / 己方舍牌 / 舍牌候补 / 己方手牌"""
        image = Image.new(mode="RGB", size=(1020, 270), color="SteelBlue")
        draw = ImageDraw.Draw(image)
        font = _font(25)
        draw.text((5, 5), "对手舍牌", "BLACK", font)
        draw.text((5, 70), "己方舍牌", "BLACK", font)
        draw.text((5, 135), "舍牌候补", "BLACK", font)
        draw.text((5, 200), "己方手牌", "BLACK", font)

        _paste_discards(image, game["take_tiles"][1 - pid], 110, 5)
        _paste_discards(image, game["take_tiles"][pid], 110, 70)
        _paste_tiles(image, game["left_tiles"][pid], 110, 135)
        _paste_tiles(image, game["hand_tiles"][pid], 110, 200)

        os.makedirs(MAHJONG17_DIR, exist_ok=True)
        path = os.path.join(MAHJONG17_DIR, f"view_{pid}_{game['player_id'][pid]}.png")
        image.save(path)
        return path

    def _render_table(self, game: dict) -> str:
        """群聊牌桌：双方舍牌"""
        l = game["turn"] if game["turn"] > 0 else 0
        image = Image.new(mode="RGB", size=(260 + 43 * l, 135), color="SteelBlue")
        draw = ImageDraw.Draw(image)
        font = _font(25)
        draw.text((5, 5), game["player_name"][0], "BLACK", font)
        draw.text((5, 70), game["player_name"][1], "BLACK", font)
        _paste_discards(image, game["take_tiles"][0], 210, 5)
        _paste_discards(image, game["take_tiles"][1], 210, 70)
        os.makedirs(MAHJONG17_DIR, exist_ok=True)
        path = os.path.join(MAHJONG17_DIR, f"table_{game['updated_at']}.png")
        image.save(path)
        return path

    def _render_end_table(self, game: dict) -> str:
        """结算时公开双方全部牌"""
        image = Image.new(mode="RGB", size=(1020, 460), color="SteelBlue")
        draw = ImageDraw.Draw(image)
        font = _font(25)
        for pid, top in ((0, 5), (1, 230)):
            draw.text((5, top), game["player_name"][pid], "BLACK", font)
            draw.text((5, top + 30), "舍牌", "BLACK", font)
            draw.text((5, top + 95), "候补", "BLACK", font)
            draw.text((5, top + 160), "手牌", "BLACK", font)
            _paste_discards(image, game["take_tiles"][pid], 60, top + 30)
            _paste_tiles(image, game["left_tiles"][pid], 60, top + 95)
            _paste_tiles(image, game["hand_tiles"][pid], 60, top + 160)
        os.makedirs(MAHJONG17_DIR, exist_ok=True)
        path = os.path.join(MAHJONG17_DIR, f"end_{game['updated_at']}.png")
        image.save(path)
        return path

    def _render_result(self, gid: int, hand, cut: int, dora, score: int,
                       fu: int, fan: int, fans: list) -> str:
        """算分结果图：宝牌指示牌 + 手牌 + 和了牌 + 符/番/点 + 役种列表"""
        minSize = 190
        if fan < 100 and fan > 0:
            minSize = 230
        image = Image.new(mode="RGB", size=(660, max(minSize, 150 + len(fans) * 40)),
                          color="SteelBlue")
        draw = ImageDraw.Draw(image)
        font = _font(25)
        draw.text((20, 5), "宝牌指示牌", "BLACK", font)
        draw.text((200, 5), "里宝指示牌", "BLACK", font)
        image.paste(_tile_image(dora[0]), (150, 5))
        image.paste(_tile_image(dora[1]), (330, 5))

        _paste_tiles(image, hand, 20, 70, wrap_after=14, row_h=65)
        image.paste(_tile_image(cut), (600, 70))

        if fan >= 100:
            for loc, name in enumerate(fans):
                draw.text((20, 140 + loc * 40), name, "BLACK", font)
        else:
            for loc, item in enumerate(fans):
                draw.text((20, 140 + loc * 40), item[0], "BLACK", font)
                draw.text((180, 140 + loc * 40), item[1], "BLACK", font)
        if fan < 100 and fan > 0:
            draw.text((350, 140), str(fu) + "符" + str(fan) + "番", "BLACK", font)
            draw.text((350, 180), str(score) + "点", "BLACK", font)
        else:
            label = {100: "役满", 200: "两倍役满", 300: "三倍役满",
                     400: "四倍役满", 500: "五倍役满"}.get(fan)
            if label:
                draw.text((350, 140), label, "BLACK", font)
                draw.text((350, 180), str(score) + "点", "BLACK", font)
        if fan == 0:
            draw.text((350, 140), "诈胡", "BLACK", font)

        os.makedirs(MAHJONG17_DIR, exist_ok=True)
        path = os.path.join(MAHJONG17_DIR, f"result_{gid}.png")
        image.save(path)
        return path

    # ==================== 帮助 ====================

    @staticmethod
    def _help_text() -> str:
        return (
            "17步麻将玩法（群聊两人对局）\n"
            "· 开局者发送「17步麻将 猫眼石」或「17步麻将 普通」创建对局\n"
            "· 另一位发送「17步麻将 加入」开局；「17步麻将」查看牌桌\n"
            "· 开局前反悔可发送「17步麻将 取消」解散对局；开局后必须打完整局\n"
            "· 开局后双方在【私聊】里操作（群聊只看牌桌）：\n"
            "   选牌：17步麻将 123m456p789s11z（共13张，红五写作0，如 0m）\n"
            "   打牌：17步麻将 5m（只能打「舍牌候补」里有的牌）\n"
            "   荣和：17步麻将 荣（对手刚打出的牌成和即可）\n"
            "· 双方各打17巡，最后一巡只能「荣」或「流局」\n"
            "· 振听：自己打出的或对手打出的牌里有能和牌的牌，本局之后不能再荣和，再荣和算诈和\n"
            "【猫眼石结算】仅猫眼石局生效：\n"
            "· 赢家得分不足 8000 分不赢猫眼石；满 8000 分后每 4000 分由输家支付 1 猫眼石"
            "（役满按32000分计=8猫眼石）\n"
            "· 诈胡（宣布荣和但不成和，含振听后硬和）由诈胡者赔给对方 5 猫眼石\n"
            "· 猫眼石不够则余额记成负数（欠债），欠债者不能参与猫眼石局，"
            "还清（余额≥0）后才能再玩\n"
            "· 流局不结算"
        )
