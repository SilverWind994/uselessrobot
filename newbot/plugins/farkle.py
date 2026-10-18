"""Farkle 骰子（farkle）—— 群里双人对战，规则取自《天国：拯救》。

每回合掷出当前剩余的骰子，掷完后必须至少锁定一颗能计分的骰子；锁定后可以选择
「继续掷」博更多分（有爆骰风险），或「入账」把本回合累计分加进总分。
若掷出的骰子完全无法计分即「爆骰」，本回合已累计的分数全部作废并换手；
6 颗骰子全部计分用完可拿回全部骰子继续掷（热骰），回合延续。

计分：单颗 1=100、单颗 5=50；三张同点为「点数×100」（三个 1 特殊，计 1000）；
四张及以上在三张基础上逐级翻倍（4 个 1=2000、5 个 1=4000、6 个 1=8000）；
顺子(1,2,3,4,5,6)=1500、小顺子(1,2,3,4,5)=500、小顺子(2,3,4,5,6)=750。

开局者可在开局时指定分数目标与猫眼石数目（猫眼石 0 即普通局）。
"""

import json
import os
import random
import re
import time
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

from core.command_router import CommandContext, CommandRouter
from core.message_sender import MessageSender, Target

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
_ASSETS_DIR = os.path.join(_BASE_DIR, "assets")
FARKLE_DIR = os.path.join(_ASSETS_DIR, "farkle")     # 运行时：对局状态与合成图
_STATE_PATH = os.path.join(FARKLE_DIR, "state.json")

IDLE_SECONDS = 6 * 60 * 60   # 对局闲置超过该时长自动作废，避免卡住之后的开局
PLAYER_NUM = 2               # 固定两人
DICE_NUM = 6                 # 每回合掷的骰子数
DEFAULT_TARGET = 4000        # 未指定分数目标时的默认值
TOURNAMENT_TARGETS = (2000, 4000)   # 锦标赛随机分数目标（二选一）
MIN_TARGET = 500             # 分数目标下限
MAX_TARGET = 10000           # 分数目标上限
MAX_STONES = 20              # 猫眼石数目上限

# 先手拍卖规则
BID_STEP = 50                # 出价必须为该数的倍数
BID_LIMIT = 1000000          # 出价绝对值上限（基本等同无上限）

# 三张同点的基础分（点数×100，三个 1 特殊计 1000）
_TRIPLE_BASE = {1: 1000, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}
_STRAIGHT_SCORE = 1500       # 顺子 1,2,3,4,5,6
_SMALL_STRAIGHT_LOW_SCORE = 500   # 小顺子 1,2,3,4,5
_SMALL_STRAIGHT_HIGH_SCORE = 750  # 小顺子 2,3,4,5,6

# 子指令别名：farkle <子指令> [内容]
_SUB_ALIASES = {
    "开局": "create", "创建": "create", "create": "create",
    "加入": "join", "join": "join",
    "取消": "cancel", "解散": "cancel", "cancel": "cancel",
    "投降": "surrender", "认输": "surrender", "弃权": "surrender",
    "surrender": "surrender", "forfeit": "surrender",
    "出价": "bid", "竞叫": "bid", "bid": "bid",
    "接受": "accept", "成交": "accept", "accept": "accept",
    "掷": "roll", "掷骰": "roll", "roll": "roll",
    "留": "keep", "锁定": "keep", "keep": "keep",
    "入账": "bank", "收": "bank", "收分": "bank", "停": "bank", "bank": "bank",
    "状态": "status", "查看": "status", "status": "status",
    "帮助": "help", "help": "help",
}

# 留骰子时可紧跟的下一步动作：r=继续掷，b=入账
_KEEP_FOLLOWUP = {
    "r": "roll", "roll": "roll", "掷": "roll", "继续": "roll",
    "b": "bank", "bank": "bank", "入账": "bank", "收": "bank", "收分": "bank", "停": "bank",
}

# ==================== 骰子与骰组 ====================
# 新增骰子类型：在 _roll_die 加分支、_DIE_NAMES/_DICE_INFO/_DIE_COLORS 各补一条即可；
# 新增作弊骰组：在 CHEAT_LOADOUTS 登记。玩家骰子存档为 kind 字符串列表。

DICE_NORMAL = "normal"   # 普通骰：各面等概率
DICE_ODD = "odd"         # 奇数骰：80% 出奇数，20% 出偶数
DICE_EVEN = "even"       # 偶数骰：80% 出偶数，20% 出奇数
DICE_DEVIL = "devil"     # 恶魔骰：掷出 1 即万能面，可顶替任意点数
DICE_LOADED = "loaded"   # 灌铅骰：2/3 概率出 1，其余均分 2~6

_DIE_ODD_FACES = (1, 3, 5)
_DIE_EVEN_FACES = (2, 4, 6)

_DIE_NAMES = {
    DICE_NORMAL: "普通", DICE_ODD: "奇数", DICE_EVEN: "偶数",
    DICE_DEVIL: "恶魔", DICE_LOADED: "灌铅",
}

# 作弊骰子的效果说明（公告与图例用）
DICE_INFO = {
    DICE_ODD: "奇数骰80%出奇数",
    DICE_EVEN: "偶数骰80%出偶数",
    DICE_DEVIL: "恶魔骰掷出1=万能面（锁定时可顶替任意点数）",
    DICE_LOADED: "灌铅骰2/3概率出1",
}

# 作弊骰组（方便以后加：直接在此登记新的组合）
CHEAT_LOADOUTS = {
    "even6":   [DICE_EVEN] * 6,                       # 6偶数
    "loaded1": [DICE_LOADED] + [DICE_NORMAL] * 5,     # 1灌铅+5普通
    "devil1":  [DICE_DEVIL] + [DICE_NORMAL] * 5,      # 1恶魔+5普通
    "odd3":    [DICE_ODD] * 3 + [DICE_NORMAL] * 3,    # 3奇数+3普通
}
CHEAT_CHANCE = 0.5   # 每位玩家拿到作弊骰组的概率

# 渲染配色（棋盘上按骰子类型着色）
_DIE_COLORS = {
    DICE_NORMAL: {"fill": (252, 252, 250), "outline": (190, 186, 176)},
    DICE_ODD:    {"fill": (208, 226, 250), "outline": (110, 155, 215)},
    DICE_EVEN:   {"fill": (208, 244, 216), "outline": (100, 185, 125)},
    DICE_DEVIL:  {"fill": (250, 212, 212), "outline": (215, 100, 100)},
    DICE_LOADED: {"fill": (248, 232, 185), "outline": (205, 165, 75)},
}


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


def _center_text(draw: ImageDraw.ImageDraw, box, text: str, fnt, fill) -> None:
    x0, y0, x1, y1 = box
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    x = x0 + (x1 - x0 - (r - l)) / 2 - l
    y = y0 + (y1 - y0 - (b - t)) / 2 - t
    draw.text((x, y), text, font=fnt, fill=fill)


def _draw_die(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, value: int,
              kind: str = DICE_NORMAL, wild: bool = False) -> None:
    """画一颗骰子（圆角底 + 点数），底色按骰子类型区分；万能面中央画「万」"""
    colors = _DIE_COLORS.get(kind, _DIE_COLORS[DICE_NORMAL])
    draw.rounded_rectangle((x, y, x + size, y + size), radius=int(size * 0.18),
                           fill=colors["fill"], outline=colors["outline"], width=2)
    if wild:
        # 恶魔骰的万能面：中央一个「万」字
        _center_text(draw, (x, y, x + size, y + size), "万",
                     _font(int(size * 0.5)), (160, 30, 30))
        return
    gx = [x + size * 0.26, x + size * 0.5, x + size * 0.74]
    gy = [y + size * 0.26, y + size * 0.5, y + size * 0.74]
    patterns = {
        1: [(1, 1)],
        2: [(0, 0), (2, 2)],
        3: [(0, 0), (1, 1), (2, 2)],
        4: [(0, 0), (0, 2), (2, 0), (2, 2)],
        5: [(0, 0), (0, 2), (1, 1), (2, 0), (2, 2)],
        6: [(0, 0), (0, 2), (1, 0), (1, 2), (2, 0), (2, 2)],
    }
    r = size * 0.075
    for row, col in patterns.get(value, []):
        cx, cy = gx[col], gy[row]
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(45, 42, 38))


def _faces_text(dice) -> str:
    """骰子点数的展示文本（骰子对象列表），万能面标注「万」，如 1万 3 5"""
    parts = []
    for d in sorted(dice, key=lambda x: x.get("value", 0)):
        if _is_wild(d):
            parts.append(f"{d['value']}万")
        else:
            parts.append(str(d.get("value", 0)))
    return " ".join(parts)


def _roll_die(kind: str) -> int:
    """按骰子类型掷出 1~6 点"""
    if kind == DICE_ODD:
        if random.random() < 0.8:
            return random.choice(_DIE_ODD_FACES)
        return random.choice(_DIE_EVEN_FACES)
    if kind == DICE_EVEN:
        if random.random() < 0.8:
            return random.choice(_DIE_EVEN_FACES)
        return random.choice(_DIE_ODD_FACES)
    if kind == DICE_LOADED:
        if random.random() < 2 / 3:
            return 1
        return random.randint(2, 6)
    return random.randint(1, 6)   # 普通骰（未知类型也按普通处理）


def _is_wild(die: dict) -> bool:
    """恶魔骰掷出的 1 是万能面，锁定时可顶替任意点数"""
    return die.get("kind") == DICE_DEVIL and die.get("value") == 1


def _new_die(kind: str) -> dict:
    """未掷状态的骰子对象"""
    return {"kind": kind, "value": 0}


def _loadout_summary(dice) -> str:
    """骰组构成摘要，如「1灌铅+5普通」"""
    counts = Counter(dice)
    order = (DICE_DEVIL, DICE_LOADED, DICE_ODD, DICE_EVEN, DICE_NORMAL)
    return "+".join(f"{counts[k]}{_DIE_NAMES[k]}" for k in order if counts.get(k))


def _dice_set_desc(dice) -> str:
    """骰组完整描述：构成 + 作弊骰效果说明"""
    if all(k == DICE_NORMAL for k in dice):
        return "普通骰组（6普通）"
    cheats = [k for k in (DICE_DEVIL, DICE_LOADED, DICE_ODD, DICE_EVEN) if k in dice]
    explain = "；".join(DICE_INFO[k] for k in cheats)
    return f"{_loadout_summary(dice)}｜{explain}"


def _random_dice_set() -> list:
    """随机分配一人的骰子：CHEAT_CHANCE 概率拿作弊骰组，否则全普通"""
    if random.random() < CHEAT_CHANCE:
        return list(random.choice(list(CHEAT_LOADOUTS.values())))
    return [DICE_NORMAL] * DICE_NUM


# ==================== 计分 ====================

def _score_selection(counts: dict) -> int:
    """计算一组锁定骰子的得分；含无法计分的骰子返回 None。

    支持：顺子 1~6；小顺子 1~5 / 2~6（可与额外的 1、5 单张一起锁定）；
    三张及以上同点；单张 1、5。
    """
    total = sum(counts.values())
    # 顺子：6 颗点数各不相同且铺满 1~6
    if total == 6 and all(counts.get(f, 0) == 1 for f in range(1, 7)):
        return _STRAIGHT_SCORE

    score = 0
    rest = dict(counts)
    # 小顺子：扣掉一套 1~5 或 2~6（优先分值更高的 2~6），余下的骰子再单独计分
    for rng, base in ((range(2, 7), _SMALL_STRAIGHT_HIGH_SCORE),
                      (range(1, 6), _SMALL_STRAIGHT_LOW_SCORE)):
        if all(rest.get(f, 0) >= 1 for f in rng):
            for f in rng:
                rest[f] -= 1
            score += base
            break

    for face in range(1, 7):
        c = rest.get(face, 0)
        if c == 0:
            continue
        if c >= 3:
            # 三张基础分，四张及以上每多一张翻一倍
            score += _TRIPLE_BASE[face] * (2 ** (c - 3))
        elif face == 1:
            score += 100 * c
        elif face == 5:
            score += 50 * c
        else:
            return None  # 散落的 2/3/4/6 不能单独计分
    return score


def _roll_has_score(dice) -> bool:
    """这一把骰子是否存在任何可计分的组合（没有则爆骰）。

    dice 为骰子对象列表；万能面必可当 1 计分。"""
    if any(_is_wild(d) for d in dice):
        return True
    counts = Counter(d["value"] for d in dice)
    # 只要有 1 或 5，或有任意三张同点，就一定能计分（顺子必然含 1，已被覆盖）
    return 1 in counts or 5 in counts or any(c >= 3 for c in counts.values())


# ==================== 插件 ====================

class FarklePlugin:
    """Farkle 骰子：群里两人对战，先达到分数目标者获胜；可选猫眼石局"""

    def __init__(self, sender: MessageSender, cat_plugin=None):
        self._sender = sender
        self._cat = cat_plugin  # 猫猫远征队插件，用于猫眼石结算
        self._result_reporter = None
        self._tournament_checker = None

    def set_result_reporter(self, reporter) -> None:
        """锦标赛等外部编排器注册结果回调：reporter(group_id, result)"""
        self._result_reporter = reporter

    def set_tournament_checker(self, checker) -> None:
        """锦标赛注册：checker(group_id) 返回该群是否正在进行锦标赛"""
        self._tournament_checker = checker

    def _tournament_active(self, gid: int) -> bool:
        return bool(self._tournament_checker) and self._tournament_checker(gid)

    def _report_result(self, gid: int, result: dict) -> None:
        """对局结束时把结果上报给外部编排器（未注册则忽略）"""
        if self._result_reporter is not None:
            self._result_reporter(gid, result)

    def start_tournament_match(self, gid: int, players) -> bool:
        """锦标赛直接开局：用指定两位选手创建并直接进入先手拍卖（不开放加入）。

        成功返回 True；本群已有未结束的对局、或某位选手已在别的对局中时返回 False。
        """
        if self._load_game(gid) is not None:
            return False
        if any(self._player_in_other_game(uid, gid) for uid, _name in players):
            return False
        target_score = random.choice(TOURNAMENT_TARGETS)   # 锦标赛目标分随机 2000 / 4000
        game = self._new_game(target_score, 0)
        game["players"] = [self._new_player(pid, name) for pid, name in players]
        game["started"] = True
        self._assign_dice(game)
        self._reset_turn(game)
        game["phase"] = "auction"
        game["auction"] = {"bid": None, "holder": None, "turn": 1}
        self._save_game(gid, game)
        target = Target(user_id=0, group_id=gid, is_group=True)
        p0, p1 = game["players"]
        self._sender.send_text(
            target,
            f"🎲 锦标赛 Farkle：{p0['name']} vs {p1['name']}，目标 {target_score} 分。\n"
            f"{self._dice_announce(game)}\n"
            f"开局前先拍卖先手：由 {p1['name']} 先出价，"
            f"拿到先手就继承「先手位」骰组。")
        self._sender.send_text(target, self._auction_prompt(game))
        return True

    # ==================== 注册命令 ====================

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["farkle", "骰子对决", ".farkle", "/farkle"],
            self.cmd_entry,
            description="Farkle骰子·群里两人对战（子指令：开局/加入/出价/接受/掷/留/入账/投降）"
        )

    def cmd_entry(self, ctx: CommandContext) -> None:
        if ctx.is_private:
            self._sender.reply(ctx, "Farkle 是群里两人对局的游戏喵，请在群聊里发送指令")
            return
        self._drop_stale(ctx)

        args = ctx.get_args().strip()
        parts = args.split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if not sub:
            self._show(ctx)
            return

        action = _SUB_ALIASES.get(sub)
        if action is None:
            self._sender.reply(ctx, "指令有误喵，发送「farkle 帮助」查看玩法")
            return

        if action in ("create", "join") and self._tournament_active(ctx.group_id):
            self._sender.reply(
                ctx, "本群锦标赛进行中喵，先打完锦标赛再开普通 Farkle 局")
            return

        if action == "help":
            self._sender.reply(ctx, self._help_text())
        elif action == "create":
            self._cmd_create(ctx, rest)
        elif action == "join":
            self._cmd_join(ctx)
        elif action == "cancel":
            self._cmd_cancel(ctx)
        elif action == "surrender":
            self._cmd_surrender(ctx)
        elif action == "bid":
            self._cmd_bid(ctx, rest)
        elif action == "accept":
            self._cmd_accept(ctx)
        elif action == "roll":
            self._cmd_roll(ctx)
        elif action == "keep":
            self._cmd_keep(ctx, rest)
        elif action == "bank":
            self._cmd_bank(ctx)
        elif action == "status":
            self._show(ctx)

    # ==================== 群聊：开局 / 加入 / 取消 / 状态 ====================

    def _cmd_create(self, ctx: CommandContext, rest: str) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is not None:
            self._sender.reply(ctx, "本群已经有一局 Farkle 了，等它结束后再开新局喵")
            return
        if self._player_in_other_game(ctx.user_id, gid):
            self._sender.reply(ctx, "你已经在另一局 Farkle 中喵")
            return

        tokens = rest.split()
        target = DEFAULT_TARGET
        stones = 0
        if tokens:
            if not tokens[0].isdigit():
                self._sender.reply(ctx, "分数目标要是数字喵，例如「farkle 开局 5000 10」")
                return
            target = int(tokens[0])
        if len(tokens) > 1:
            if not tokens[1].isdigit():
                self._sender.reply(ctx, "猫眼石数目要是数字喵，例如「farkle 开局 5000 10」")
                return
            stones = int(tokens[1])
        if not (MIN_TARGET <= target <= MAX_TARGET):
            self._sender.reply(
                ctx, f"分数目标要在 {MIN_TARGET}~{MAX_TARGET} 之间喵")
            return
        if not (0 <= stones <= MAX_STONES):
            self._sender.reply(ctx, f"猫眼石数目要在 0~{MAX_STONES} 之间喵")
            return
        if stones > 0 and self._debt_of(ctx.user_id) > 0:
            self._sender.reply(
                ctx, f"你还有 {self._debt_of(ctx.user_id)} 个猫眼石欠债，"
                     f"不能开猫眼石局喵")
            return

        game = self._new_game(target, stones)
        game["players"].append(self._new_player(ctx.user_id, ctx.user_name))
        self._save_game(gid, game)
        match_text = (f"猫眼石局（{stones} 猫眼石）" if stones > 0 else "普通局")
        self._sender.reply(
            ctx, f"已创建 Farkle 对局：目标 {target} 分，{match_text}。\n"
                 f"另一位玩家发送「farkle 加入」即可开局")

    def _cmd_join(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None:
            self._sender.reply(
                ctx, "还没有对局喵，请先发送「farkle 开局 <目标分> [猫眼石]」创建")
            return
        if game["started"]:
            self._sender.reply(ctx, "游戏已经开始了")
            return
        if game["players"] and game["players"][0]["id"] == ctx.user_id:
            self._sender.reply(ctx, "你已经是开局者了，等另一位玩家加入喵")
            return
        if self._player_in_other_game(ctx.user_id, gid):
            self._sender.reply(ctx, "你已经在另一局 Farkle 中喵")
            return
        if game["stones"] > 0 and self._debt_of(ctx.user_id) > 0:
            self._sender.reply(
                ctx, f"你还有 {self._debt_of(ctx.user_id)} 个猫眼石欠债，"
                     f"不能加入猫眼石局喵")
            return

        game["players"].append(self._new_player(ctx.user_id, ctx.user_name))
        game["started"] = True
        self._assign_dice(game)
        self._reset_turn(game)
        # 进入先手拍卖：由后加入的人（下标 1）先出价
        game["phase"] = "auction"
        game["auction"] = {"bid": None, "holder": None, "turn": 1}
        self._save_game(gid, game)
        first_bidder = game["players"][1]["name"]
        self._sender.reply(
            ctx, f"Farkle 两人到齐，目标 {game['target']} 分。\n"
                 f"{self._dice_announce(game)}\n"
                 f"开局前先拍卖先手：由后加入的 {first_bidder} 先出价，"
                 f"拿到先手就继承「先手位」骰组。\n"
                 f"发送「farkle 出价 <分数>」，如「farkle 出价 300」= 拿先手但开局 -300 分")
        self._sender.reply(ctx, self._auction_prompt(game))

    def _cmd_cancel(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None:
            self._sender.reply(ctx, "本群没有进行中的 Farkle 喵")
            return
        if game["started"]:
            self._sender.reply(ctx, "对局已经开始了，开局后必须打完喵")
            return
        if not game["players"] or game["players"][0]["id"] != ctx.user_id:
            self._sender.reply(ctx, "只有开局的人才能取消这局喵")
            return
        self._remove_game(gid)
        self._sender.reply(ctx, f"{ctx.user_name} 取消了还没开局的 Farkle")

    def _cmd_surrender(self, ctx: CommandContext) -> None:
        """投降：认输的一方判负，对方直接获胜并按猫眼石结算"""
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None:
            self._sender.reply(ctx, "本群没有进行中的 Farkle 喵")
            return
        if not game["started"]:
            self._sender.reply(ctx, "对局还没开始喵，发送「farkle 取消」即可解散")
            return
        surrender = next((p for p in game["players"] if p["id"] == ctx.user_id), None)
        if surrender is None:
            self._sender.reply(ctx, "你不是本局 Farkle 的玩家喵")
            return
        winner = next(p for p in game["players"] if p["id"] != ctx.user_id)
        self._finish(
            ctx, game, winner, reason="投降",
            headline=f"🏳️ {surrender['name']} 投降，{winner['name']} 赢下本局 Farkle！")

    def _show(self, ctx: CommandContext) -> None:
        game = self._load_game(ctx.group_id)
        if game is None:
            self._sender.reply(
                ctx, "本群还没有 Farkle 对局喵，发送「farkle 开局 <目标分> [猫眼石]」创建")
            return
        if game["phase"] == "auction":
            self._sender.reply(ctx, self._auction_prompt(game))
            return
        if not game["started"]:
            names = "、".join(p["name"] for p in game["players"])
            match_text = (f"猫眼石局（{game['stones']} 猫眼石）"
                          if game["stones"] > 0 else "普通局")
            self._sender.reply(
                ctx, f"Farkle 准备中（1/2）：{names}，目标 {game['target']} 分，{match_text}\n"
                     f"发送「farkle 加入」加入，或「farkle 取消」解散")
            return
        self._send_board(ctx, game)

    # ==================== 先手拍卖 ====================

    def _assign_dice(self, game: dict) -> None:
        """两人到齐时随机决定「先手位/后手位」的骰子（各 50% 概率为作弊骰组）。
        竞价只决定谁坐先手位：先手拿先手位骰组，后手拿后手位骰组。"""
        game["seat_dice"] = [_random_dice_set(), _random_dice_set()]
        # 竞价前玩家先用普通骰占位，竞价结束后按位置发放
        for p in game["players"]:
            p["dice"] = [DICE_NORMAL] * DICE_NUM

    @staticmethod
    def _dice_announce(game: dict) -> str:
        """骰组分配公告文本（按先手/后手位公告，竞价定归属）"""
        seat = game.get("seat_dice") or [[DICE_NORMAL] * DICE_NUM] * 2
        return ("骰组分配（先手/后手位各 50% 概率为作弊骰组，竞价决定归属）：\n"
                f"· 先手位：{_dice_set_desc(seat[0])}\n"
                f"· 后手位：{_dice_set_desc(seat[1])}")

    @staticmethod
    def _fmt_open_score(bid: int) -> str:
        """出价对应的开局分：出价 300 → -300，出价 -300 → +300"""
        return f"{-bid:+d}"

    def _auction_prompt(self, game: dict) -> str:
        """当前拍卖进度与下一步操作的说明"""
        au = game["auction"]
        cur = game["players"][au["turn"]]
        if au["bid"] is None:
            return (f"先手拍卖（目标 {game['target']} 分）：由 {cur['name']} 先出价，"
                    f"出价必须是 {BID_STEP} 的倍数，可为 0 或负数。\n"
                    f"正数 = 拿先手但以该负分开局（如「farkle 出价 300」= 开局 -300 分）；"
                    f"负数 = 拿先手还能以正分开局（如「farkle 出价 -300」= 开局 +300 分）")
        holder = game["players"][au["holder"]]
        return (f"当前最高出价：{holder['name']} 出 {au['bid']}"
                f"（先手以 {self._fmt_open_score(au['bid'])} 分开局）。\n"
                f"{cur['name']} 请选择：「farkle 出价 <高于 {au['bid']}>」加价抢先手，"
                f"或「farkle 接受」让 {holder['name']} "
                f"以 {self._fmt_open_score(au['bid'])} 分先手开局")

    def _cmd_bid(self, ctx: CommandContext, rest: str) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None or game["phase"] != "auction":
            self._sender.reply(ctx, "现在不是先手拍卖阶段喵")
            return
        au = game["auction"]
        cur = game["players"][au["turn"]]
        if ctx.user_id != cur["id"]:
            self._sender.reply(ctx, f"现在轮到 {cur['name']} 出价喵")
            return
        rest = rest.strip()
        try:
            val = int(rest)
        except ValueError:
            self._sender.reply(
                ctx, f"出价要填整数分喵，且必须是 {BID_STEP} 的倍数，"
                     f"如「farkle 出价 300」或「farkle 出价 -300」")
            return
        if val % BID_STEP != 0:
            self._sender.reply(ctx, f"出价必须是 {BID_STEP} 的倍数喵")
            return
        if not (-BID_LIMIT <= val <= BID_LIMIT):
            self._sender.reply(ctx, f"出价要在 ±{BID_LIMIT} 之内喵")
            return
        if au["bid"] is not None and val <= au["bid"]:
            self._sender.reply(
                ctx, f"加价要高于当前出价 {au['bid']} 分喵（出价越高越有资格拿先手）")
            return

        au["bid"] = val
        au["holder"] = au["turn"]
        au["turn"] = (au["turn"] + 1) % PLAYER_NUM
        self._save_game(gid, game)
        self._sender.reply(
            ctx, f"{cur['name']} 出价 {val} 分（先手以 {self._fmt_open_score(val)} 分开局）。\n"
                 + self._auction_prompt(game))

    def _cmd_accept(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None or game["phase"] != "auction":
            self._sender.reply(ctx, "现在不是先手拍卖阶段喵")
            return
        au = game["auction"]
        if au["bid"] is None:
            self._sender.reply(ctx, "还没有人出价，没有可接受的价格喵。\n"
                                    + self._auction_prompt(game))
            return
        cur = game["players"][au["turn"]]
        if ctx.user_id != cur["id"]:
            self._sender.reply(ctx, f"现在轮到 {cur['name']} 应对喵")
            return
        holder = game["players"][au["holder"]]
        bid = au["bid"]
        holder["total"] = -bid       # 中标者按出价结算开局分（负出价=正分开局）
        # 按最终先后手归属发放对应位置的骰组
        seat = game.get("seat_dice") or [[DICE_NORMAL] * DICE_NUM] * 2
        holder["dice"] = list(seat[0])
        game["players"][1 - au["holder"]]["dice"] = list(seat[1])
        game["auction"] = None
        game["turn"] = au["holder"]
        self._reset_turn(game)
        self._save_game(gid, game)
        self._sender.reply(
            ctx, f"{cur['name']} 接受。{holder['name']} 以 "
                 f"{self._fmt_open_score(bid)} 分开局并获得先手，"
                 f"{cur['name']} 以 0 分开局。")
        self._do_roll(ctx, gid, game)

    # ==================== 对局操作：掷 / 留 / 入账 ====================

    def _play_guard(self, ctx: CommandContext, game: dict) -> str:
        """掷/留/入账 的公共前置校验，返回提示文案（空串=可继续）"""
        if game["phase"] == "auction":
            return "先手拍卖还没结束喵。\n" + self._auction_prompt(game)
        return self._check_turn(ctx, game)

    def _do_roll(self, ctx: CommandContext, gid: int, game: dict) -> None:
        """掷手中剩余的骰子；爆骰则作废并换手（换手后自动进行新回合的首掷）"""
        player = game["players"][game["turn"]]
        hand = game["hand"]
        for die in hand:
            die["value"] = _roll_die(die["kind"])

        if not _roll_has_score(hand):
            lost = game["turn_score"]
            self._sender.reply(
                ctx, f"{player['name']} 掷出 {_faces_text(hand)}，无法计分——爆骰！"
                     + (f"本回合累计的 {lost} 分全部作废" if lost > 0 else "本回合没有得分"))
            self._end_turn(ctx, gid, game)
            return

        game["phase"] = "keep"
        self._save_game(gid, game)
        self._sender.reply(
            ctx, f"{player['name']} 掷出 {_faces_text(hand)}。\n"
                 f"发送「farkle 留 <点数>」锁定至少一颗计分骰，例如「farkle 留 15」；"
                 f"也可在点数后直接加 r（继续掷）或 b（入账），如「farkle 留 14445 b」；"
                 f"点数不够的部分会自动用恶魔骰的万能面顶替")
        self._send_board(ctx, game)

    def _cmd_roll(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None or not game["started"]:
            self._sender.reply(ctx, "当前没有进行中的 Farkle 喵")
            return
        err = self._play_guard(ctx, game)
        if err:
            self._sender.reply(ctx, err)
            return
        if game["phase"] not in ("roll", "decide"):
            self._sender.reply(ctx, "现在要先发「farkle 留 <点数>」锁定计分骰喵")
            return
        self._do_roll(ctx, gid, game)

    def _cmd_keep(self, ctx: CommandContext, rest: str) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None or not game["started"]:
            self._sender.reply(ctx, "当前没有进行中的 Farkle 喵")
            return
        err = self._play_guard(ctx, game)
        if err:
            self._sender.reply(ctx, err)
            return
        if game["phase"] != "keep":
            self._sender.reply(ctx, "现在没有刚掷出的骰子可以锁定喵")
            return

        # 允许把点数和后续动作写在一起，如「farkle 留 14445 b」
        # 末尾若是动作字（r/掷/继续 = 继续掷，b/入账/收/停 = 入账）则拆出执行
        tokens = rest.split()
        followup = None
        if tokens:
            last = tokens[-1].lower()
            if last in _KEEP_FOLLOWUP:
                followup = _KEEP_FOLLOWUP[last]
                tokens = tokens[:-1]
        dice_str = " ".join(tokens)

        counts, perr = self._parse_keep(dice_str)
        if perr:
            self._sender.reply(ctx, perr)
            return

        # 从手中挑选骰子：优先消耗普通骰，其次作弊骰的非万能面，最后才用万能面顶替；
        # 未被指定的万能面留在手中（下一轮重掷）
        hand = list(game["hand"])

        def _take(matcher, n):
            """从 hand 取出 n 颗满足条件的骰子，返回 (取出的, 剩余的, 还缺几颗)"""
            taken, left = [], []
            for d in hand:
                if n > 0 and matcher(d):
                    taken.append(d)
                    n -= 1
                else:
                    left.append(d)
            return taken, left, n

        selected = []
        for face in sorted(counts, reverse=True):
            taken, hand, lack = _take(
                lambda d, f=face: d.get("kind") == DICE_NORMAL and d["value"] == f,
                counts[face])
            selected += taken
            if lack:
                taken, hand, lack = _take(
                    lambda d, f=face: not _is_wild(d) and d["value"] == f, lack)
                selected += taken
            if lack:
                taken, hand, lack = _take(_is_wild, lack)
                if lack:
                    self._sender.reply(
                        ctx, f"掷出的骰子（含万能面）凑不出 {counts[face]} 个 {face} 点喵"
                             f"（本次掷出 {_faces_text(game['hand'])}）")
                    return
                selected += taken
        game["hand"] = hand

        score = _score_selection(counts)
        if score is None:
            self._sender.reply(
                ctx, "这组骰子无法计分喵：散落的 2/3/4/6 点要凑成三张及以上才能算")
            return

        player = game["players"][game["turn"]]
        game["locked"] += selected
        game["turn_score"] += score

        hot = not game["hand"]
        if hot:
            # 热骰：全部骰子计分用完，拿回全部骰子继续
            game["locked"] = []
            game["hand"] = [_new_die(k) for k in player.get("dice") or [DICE_NORMAL] * DICE_NUM]
        game["phase"] = "decide"
        self._save_game(gid, game)

        self._sender.reply(
            ctx, f"{player['name']} 锁定 {_faces_text(selected)}，本次 +{score} 分，"
                 f"本回合累计 {game['turn_score']} 分（剩余可掷 {len(game['hand'])} 颗）"
                 + ("\n热骰！骰子全部计分用完，拿回全部骰子，可继续或入账" if hot else ""))
        self._send_board(ctx, game)

        # 紧跟的动作：继续掷 / 入账
        if followup == "roll":
            self._cmd_roll(ctx)
        elif followup == "bank":
            self._cmd_bank(ctx)

    def _cmd_bank(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        game = self._load_game(gid)
        if game is None or not game["started"]:
            self._sender.reply(ctx, "当前没有进行中的 Farkle 喵")
            return
        err = self._play_guard(ctx, game)
        if err:
            self._sender.reply(ctx, err)
            return
        if game["phase"] != "decide":
            self._sender.reply(ctx, "要先锁定至少一颗计分骰才能入账喵")
            return

        player = game["players"][game["turn"]]
        gained = game["turn_score"]
        player["total"] += gained
        self._sender.reply(
            ctx, f"{player['name']} 入账 +{gained} 分，总分 {player['total']} 分")

        if player["total"] >= game["target"]:
            self._finish(ctx, game, player)
            return
        self._end_turn(ctx, gid, game)

    # ==================== 回合流转与结算 ====================

    def _reset_turn(self, game: dict) -> None:
        """重置当前玩家的回合状态（不改动 turn 下标）：手牌重置为该玩家的骰组"""
        player = game["players"][game["turn"]]
        game["phase"] = "roll"
        game["locked"] = []
        game["turn_score"] = 0
        game["hand"] = [_new_die(k) for k in player.get("dice") or [DICE_NORMAL] * DICE_NUM]

    def _end_turn(self, ctx: CommandContext, gid: int, game: dict) -> None:
        """换手给另一位玩家并重置回合状态，随后自动进行新回合的首掷"""
        game["turn"] = (game["turn"] + 1) % PLAYER_NUM
        self._reset_turn(game)
        self._save_game(gid, game)
        self._do_roll(ctx, gid, game)

    def _finish(self, ctx: CommandContext, game: dict, winner: dict,
                headline: str = None, reason: str = "达成目标分") -> None:
        """结算本局：公布总分，按猫眼石数目结算后清除对局"""
        lines = [headline or f"🏆 {winner['name']} 达到 {game['target']} 分，赢下本局 Farkle！"]
        for p in game["players"]:
            lines.append(f"{p['name']}：{p['total']} 分")
        lines += self._settle(game, winner)
        self._remove_game(ctx.group_id)   # 先清状态，锦标赛回调才能紧接着开下一局
        self._report_result(ctx.group_id, {
            "game": "farkle",
            "players": [{"id": int(p["id"]), "name": p["name"]} for p in game["players"]],
            "winner": int(winner["id"]),
            "reason": reason,
        })
        self._sender.reply(ctx, "\n".join(lines))

    def _settle(self, game: dict, winner: dict) -> list:
        """按猫眼石数目结算，返回说明行"""
        stones = game["stones"]
        if stones <= 0:
            return []
        if self._cat is None:
            return ["（猫眼石结算失败：猫眼石系统不可用）"]
        loser = next(p for p in game["players"] if p["id"] != winner["id"])

        before_win = self._cat.get_eye_stones(winner["id"])
        before_lose = self._cat.get_eye_stones(loser["id"])
        after_win = self._cat.add_eye_stones(winner["id"], stones)
        after_lose = self._cat.add_eye_stones(loser["id"], -stones)

        lines = [f"{loser['name']} 支付 {stones} 猫眼石给 {winner['name']}"
                 f"（{winner['name']} 余额 {before_win} → {after_win}，"
                 f"{loser['name']} 余额 {before_lose} → {after_lose}）"]
        if after_lose < 0:
            lines.append(
                f"{loser['name']} 猫眼石不足，现有欠债 {-after_lose} 个，还清前不能参与猫眼石局")
        return lines

    def _debt_of(self, user_id: int) -> int:
        """玩家的猫眼石欠债数量（余额为负时为其绝对值）"""
        if self._cat is None:
            return 0
        balance = self._cat.get_eye_stones(user_id)
        return -balance if balance < 0 else 0

    # ==================== 内部逻辑 ====================

    @staticmethod
    def _new_game(target: int, stones: int) -> dict:
        return {
            "stones": stones,
            "target": target,
            "started": False,
            "turn": 0,
            "phase": "roll",
            "auction": None,
            "seat_dice": [],
            "locked": [],
            "turn_score": 0,
            "hand": [],
            "players": [],
        }

    @staticmethod
    def _new_player(uid: int, name: str) -> dict:
        return {"id": uid, "name": name, "total": 0,
                "dice": [DICE_NORMAL] * DICE_NUM}

    def _load_game(self, gid: int):
        raw = _load_json(_STATE_PATH).get(str(gid))
        if raw is None:
            return None
        return self._migrate_game(raw)

    @staticmethod
    def _migrate_game(g: dict) -> dict:
        """旧版存档补骰子字段：玩家骰组默认全普通，手牌/锁定转成骰子对象"""
        if "seat_dice" not in g:
            g["seat_dice"] = [[DICE_NORMAL] * DICE_NUM, [DICE_NORMAL] * DICE_NUM]
        for p in g.get("players", []):
            if "dice" not in p:
                p["dice"] = [DICE_NORMAL] * DICE_NUM
        if "hand" not in g:
            if g.get("phase") == "keep" and g.get("pool"):
                # 旧 keep 阶段：掷出的骰子（点数列表）转成普通骰对象作为手牌
                g["hand"] = [{"kind": DICE_NORMAL, "value": v} for v in g["pool"]]
            else:
                g["hand"] = [{"kind": DICE_NORMAL, "value": 0}
                             for _ in range(g.get("remaining", DICE_NUM))]
        g.pop("pool", None)
        g.pop("remaining", None)
        locked = g.get("locked", [])
        if locked and isinstance(locked[0], int):
            g["locked"] = [{"kind": DICE_NORMAL, "value": v} for v in locked]
        return g

    def _save_game(self, gid: int, game: dict) -> None:
        game["updated_at"] = time.time()
        state = _load_json(_STATE_PATH)
        state[str(gid)] = game
        _save_json(_STATE_PATH, state)

    def _remove_game(self, gid: int) -> None:
        state = _load_json(_STATE_PATH)
        if str(gid) in state:
            del state[str(gid)]
            _save_json(_STATE_PATH, state)

    def _player_in_other_game(self, uid: int, gid: int) -> bool:
        """该玩家是否已在别的群的对局中（避免一人同时占两局）"""
        state = _load_json(_STATE_PATH)
        for key, g in state.items():
            if key == str(gid):
                continue
            if any(p["id"] == uid for p in g.get("players", [])):
                return True
        return False

    def _drop_stale(self, ctx: CommandContext) -> None:
        """对局闲置过久则作废，避免卡住后续的开局"""
        game = self._load_game(ctx.group_id)
        if game is None:
            return
        if time.time() - game.get("updated_at", 0) <= IDLE_SECONDS:
            return
        self._remove_game(ctx.group_id)
        self._sender.reply(ctx, f"上一局 Farkle 闲置超过 {IDLE_SECONDS // 3600} 小时，已自动作废喵")

    @staticmethod
    def _check_turn(ctx: CommandContext, game: dict) -> str:
        """非当前玩家返回提示文案，否则返回空串"""
        cur = game["players"][game["turn"]]
        if ctx.user_id != cur["id"]:
            return f"当前该 {cur['name']} 行动喵"
        return ""

    @staticmethod
    def _parse_keep(rest: str):
        """解析锁定的点数，返回 (counts, err)；支持「留 15」「留 1 5 5」等多种写法"""
        cleaned = re.sub(r"[\s,，、]+", "", rest)
        if not cleaned:
            return None, "请指定要锁定的骰子点数，例如「farkle 留 15」"
        counts = {}
        for c in cleaned:
            if c not in "123456":
                return None, "只能锁定 1~6 点的骰子喵"
            counts[int(c)] = counts.get(int(c), 0) + 1
        return counts, None

    # ==================== 展示 ====================

    def _send_board(self, ctx: CommandContext, game: dict) -> None:
        try:
            path = self._render_board(game, ctx.group_id)
        except Exception as e:
            self._sender.reply(ctx, f"棋盘绘制失败了喵：{e}")
            return
        self._sender.send_image(Target.from_data(ctx.raw_data), path)

    def _render_board(self, game: dict, gid: int) -> str:
        width = 700
        height = 380
        img = Image.new("RGB", (width, height), (252, 250, 244))
        draw = ImageDraw.Draw(img)
        draw.rectangle((6, 6, width - 7, height - 7), outline=(205, 196, 180), width=3)

        title = f"Farkle · 目标 {game['target']} 分"
        if game["stones"] > 0:
            title += f" · 猫眼石 {game['stones']}"
        _center_text(draw, (0, 16, width, 58), title, _font(38), (60, 45, 35))

        # 两位玩家总分
        for j, p in enumerate(game["players"]):
            y = 74 + j * 46
            is_cur = j == game["turn"]
            color = (196, 128, 30) if is_cur else (60, 52, 44)
            tag = "（当前）" if is_cur else ""
            _center_text(draw, (0, y, width, y + 40),
                         f"{p['name']}{tag}：{p['total']} 分", _font(30), color)

        # 只画刚投出的那一下（keep 阶段），按骰子类型着色
        if game["phase"] == "keep" and game["hand"]:
            pool = game["hand"]
            size, gap = 76, 16
            row_w = len(pool) * (size + gap) - gap
            x0 = (width - row_w) // 2
            for i, d in enumerate(pool):
                _draw_die(draw, x0 + i * (size + gap), 186, size,
                          d.get("value", 0), d.get("kind", DICE_NORMAL), _is_wild(d))
            # 图例：骰子类型颜色说明
            legend = [(DICE_NORMAL, "普通"), (DICE_ODD, "奇数"), (DICE_EVEN, "偶数"),
                      (DICE_DEVIL, "恶魔(1=万)"), (DICE_LOADED, "灌铅")]
            lx = 60
            for kind, label in legend:
                colors = _DIE_COLORS[kind]
                draw.rounded_rectangle((lx, 284, lx + 20, 304), radius=5,
                                       fill=colors["fill"], outline=colors["outline"], width=2)
                draw.text((lx + 26, 283), label, font=_font(18), fill=(110, 100, 90))
                lx += 26 + _font(18).getlength(label) + 26

        hint = {
            "keep": "「farkle 留 <点数>」锁定，末尾可加 r/b（如 留 15 b）",
            "decide": "「farkle 掷」继续博分，或「farkle 入账」收分",
        }.get(game["phase"], "")
        _center_text(draw, (0, height - 42, width, height - 14), hint, _font(22), (150, 140, 128))

        os.makedirs(FARKLE_DIR, exist_ok=True)
        path = os.path.join(FARKLE_DIR, f"board_{gid}.png")
        img.save(path)
        return path

    # ==================== 帮助 ====================

    @staticmethod
    def _help_text() -> str:
        return (
            "Farkle 骰子玩法（群里两人对战，规则取自《天国：拯救》）\n"
            "指令：farkle（也可用 骰子对决 / .farkle / /farkle）\n"
            "【开局】\n"
            "· 开局者：「farkle 开局 <目标分> [猫眼石]」，如「farkle 开局 5000 10」\n"
            f"   目标分 {MIN_TARGET}~{MAX_TARGET}（缺省 {DEFAULT_TARGET}）；"
            f"猫眼石 0~{MAX_STONES}（缺省 0，即普通局）\n"
            "· 另一位：「farkle 加入」，两人到齐后分配骰组并进入先手拍卖\n"
            "· 开局前可「farkle 取消」解散；两人到齐后必须打完\n"
            "· 有猫眼石的对局，开局者与加入者的猫眼石余额都不能为负（欠债者禁入）\n"
            "【骰组】（先手位/后手位各 50% 概率为作弊骰组，竞价决定归属）\n"
            "· 两人到齐时先公告两个位置的骰组，再进行先手拍卖；\n"
            "  谁最终拿到先手，谁就用「先手位」骰组，后手用「后手位」骰组\n"
            "· 奇数骰：80% 出奇数｜偶数骰：80% 出偶数\n"
            "· 恶魔骰：掷出 1 即万能面，锁定时可顶替任意点数（点数不够的部分自动用万能面补）\n"
            "· 灌铅骰：2/3 概率出 1\n"
            "· 锁定时优先消耗普通骰子，其次作弊骰的非万能面，最后才动用万能面\n"
            "· 现有骰组：6偶数 / 1灌铅+5普通 / 1恶魔+5普通 / 3奇数+3普通\n"
            "· 棋盘图按骰子类型着色：白=普通 蓝=奇数 绿=偶数 红=恶魔 金=灌铅\n"
            "【先手拍卖】（正式掷骰前，骰组公告后进行）\n"
            f"· 由后加入的人先出价；出价必须是 {BID_STEP} 的倍数，可为 0 或负数，"
            f"范围 ±{BID_LIMIT}\n"
            "· 正数 = 拿先手但以该负分开局（如「farkle 出价 300」= 开局 -300 分）\n"
            "· 负数 = 拿先手还能以正分开局（如「farkle 出价 -300」= 开局 +300 分）\n"
            "· 双方轮流出价，每次出价必须高于对方；也可以直接「farkle 接受」\n"
            "· 接受方把先手让给出价方：出价方先手并按出价结算开局分，接受方以 0 分开局\n"
            "【回合作战】（轮到你时）\n"
            "· 轮到你的第一次掷骰会自动进行，不需要手动发送\n"
            "· 「farkle 留 <点数>」：锁定至少一颗能计分的骰子，"
            "如「farkle 留 15」（=锁 1 个 1 点、1 个 5 点）、「farkle 留 1 5 5」\n"
            "· 也可把后续动作写在点数末尾，省一条指令："
            "末尾加 r 继续掷（如「farkle 留 14445 r」）、加 b 入账（如「farkle 留 14445 b」）\n"
            "· 锁定后可「farkle 掷」继续博更多分（有爆骰风险），或「farkle 入账」收分换手\n"
            "【爆骰】\n"
            "· 掷出的骰子完全无法计分 → 爆骰，本回合已累计的分全部作废，回合结束并换手\n"
            "【热骰】\n"
            "· 骰子全部计分用完 → 拿回全部骰子继续掷，回合延续\n"
            "【计分规则】\n"
            "· 单颗 1 = 100；单颗 5 = 50；散落的 2/3/4/6 不能单独计分\n"
            "· 三张同点 = 点数×100（2~6 点依次 200/300/400/500/600）；三个 1 特殊 = 1000\n"
            "· 四张及以上在「三张」基础上逐级翻倍：4 个 1=2000、5 个 1=4000、6 个 1=8000\n"
            "   （如 4 个 4=800、5 个 4=1600、4 个 5=1000、6 个 6=4800）\n"
            "· 顺子（1,2,3,4,5,6）= 1500；小顺子 1~5 = 500、2~6 = 750（如 23456）\n"
            "【结算与作废】\n"
            "· 先达到目标分者获胜；有猫眼石时由输家支付给赢家相应数量\n"
            "· 输家猫眼石不足则余额记成负数（欠债），还清前不能参与猫眼石局\n"
            "· 认输可发送「farkle 投降」（也可「farkle 认输」），投降方判负，"
            "对方直接获胜并按猫眼石结算\n"
            "· 「farkle」查看牌桌；对局闲置超过 "
            f"{IDLE_SECONDS // 3600} 小时自动作废"
        )
