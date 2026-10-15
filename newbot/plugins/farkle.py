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
MIN_TARGET = 500             # 分数目标下限
MAX_TARGET = 50000           # 分数目标上限
MAX_STONES = 10              # 猫眼石数目上限

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


def _draw_die(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, value: int) -> None:
    """画一颗骰子（圆角白底 + 点数）"""
    draw.rounded_rectangle((x, y, x + size, y + size), radius=int(size * 0.18),
                           fill=(252, 252, 250), outline=(190, 186, 176), width=2)
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
    """骰子点数的展示文本，如 [1, 5, 5] -> 「1 5 5」"""
    return " ".join(str(d) for d in sorted(dice))


# ==================== 计分 ====================

def _score_selection(counts: dict) -> int:
    """计算一组锁定骰子的得分；含无法计分的骰子（散落的 2/3/4/6）返回 None"""
    total = sum(counts.values())
    # 顺子 / 小顺子（点数各不相同且刚好铺满）
    if total == 6 and all(counts.get(f, 0) == 1 for f in range(1, 7)):
        return _STRAIGHT_SCORE
    if total == 5 and all(counts.get(f, 0) == 1 for f in range(1, 6)):
        return _SMALL_STRAIGHT_LOW_SCORE
    if total == 5 and all(counts.get(f, 0) == 1 for f in range(2, 7)):
        return _SMALL_STRAIGHT_HIGH_SCORE

    score = 0
    for face in range(1, 7):
        c = counts.get(face, 0)
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
    """这一把骰子是否存在任何可计分的组合（没有则爆骰）"""
    counts = Counter(dice)
    # 只要有 1 或 5，或有任意三张同点，就一定能计分（顺子必然含 1，已被覆盖）
    return 1 in counts or 5 in counts or any(c >= 3 for c in counts.values())


# ==================== 插件 ====================

class FarklePlugin:
    """Farkle 骰子：群里两人对战，先达到分数目标者获胜；可选猫眼石局"""

    def __init__(self, sender: MessageSender, cat_plugin=None):
        self._sender = sender
        self._cat = cat_plugin  # 猫猫远征队插件，用于猫眼石结算

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
        self._reset_turn(game)
        # 进入先手拍卖：由后加入的人（下标 1）先出价
        game["phase"] = "auction"
        game["auction"] = {"bid": None, "holder": None, "turn": 1}
        self._save_game(gid, game)
        first_bidder = game["players"][1]["name"]
        self._sender.reply(
            ctx, f"Farkle 两人到齐，目标 {game['target']} 分。\n"
                 f"开局前先拍卖先手：由后加入的 {first_bidder} 先出价，"
                 f"说出愿意以「负多少分」的代价换取先手。\n"
                 f"发送「farkle 出价 <分数>」，如「farkle 出价 300」= 愿意开局 -300 分")
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
            ctx, game, winner,
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

    @staticmethod
    def _auction_prompt(game: dict) -> str:
        """当前拍卖进度与下一步操作的说明"""
        au = game["auction"]
        cur = game["players"][au["turn"]]
        if au["bid"] is None:
            return (f"先手拍卖（目标 {game['target']} 分）：由后加入的 {cur['name']} 先出价，"
                    f"说出愿意以负多少分换取先手。\n"
                    f"发送「farkle 出价 <分数>」，如「farkle 出价 300」= 愿意开局 -300 分")
        holder = game["players"][au["holder"]]
        return (f"当前最高出价：{holder['name']} 愿意开局 -{au['bid']} 分换先手。\n"
                f"{cur['name']} 请选择：「farkle 出价 <高于 {au['bid']} 分>」加价抢先手，"
                f"或「farkle 接受」让 {holder['name']} 以 -{au['bid']} 分先手开局")

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
        if not rest.isdigit():
            self._sender.reply(ctx, "出价要填整数分喵，例如「farkle 出价 300」")
            return
        val = int(rest)
        if not (1 <= val <= game["target"]):
            self._sender.reply(ctx, f"出价要在 1~{game['target']} 分之间喵")
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
            ctx, f"{cur['name']} 出价 {val} 分（愿意开局 -{val} 分换先手）。\n"
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
        holder["total"] = -bid       # 中标者按自己的负分开局
        game["auction"] = None
        game["turn"] = au["holder"]
        self._reset_turn(game)
        self._save_game(gid, game)
        self._sender.reply(
            ctx, f"{cur['name']} 接受。{holder['name']} 以 -{bid} 分开局并获得先手，"
                 f"{cur['name']} 以 0 分开局。")
        self._do_roll(ctx, gid, game)

    # ==================== 对局操作：掷 / 留 / 入账 ====================

    def _play_guard(self, ctx: CommandContext, game: dict) -> str:
        """掷/留/入账 的公共前置校验，返回提示文案（空串=可继续）"""
        if game["phase"] == "auction":
            return "先手拍卖还没结束喵。\n" + self._auction_prompt(game)
        return self._check_turn(ctx, game)

    def _do_roll(self, ctx: CommandContext, gid: int, game: dict) -> None:
        """掷当前剩余的骰子；爆骰则作废并换手（换手后自动进行新回合的首掷）"""
        player = game["players"][game["turn"]]
        pool = sorted(random.randint(1, DICE_NUM) for _ in range(game["remaining"]))

        if not _roll_has_score(pool):
            lost = game["turn_score"]
            self._sender.reply(
                ctx, f"{player['name']} 掷出 {_faces_text(pool)}，无法计分——爆骰！"
                     + (f"本回合累计的 {lost} 分全部作废" if lost > 0 else "本回合没有得分"))
            self._end_turn(ctx, gid, game)
            return

        game["pool"] = pool
        game["phase"] = "keep"
        self._save_game(gid, game)
        self._sender.reply(
            ctx, f"{player['name']} 掷出 {_faces_text(pool)}。\n"
                 f"发送「farkle 留 <点数>」锁定至少一颗计分骰，例如「farkle 留 15」")
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

        pool = game["pool"]
        counts, perr = self._parse_keep(rest)
        if perr:
            self._sender.reply(ctx, perr)
            return
        avail = Counter(pool)
        for face, c in counts.items():
            if c > avail.get(face, 0):
                self._sender.reply(
                    ctx, f"掷出的骰子里没有 {c} 个 {face} 点喵（本次掷出 {_faces_text(pool)}）")
                return
        score = _score_selection(counts)
        if score is None:
            self._sender.reply(
                ctx, "这组骰子无法计分喵：散落的 2/3/4/6 点要凑成三张及以上才能算")
            return

        player = game["players"][game["turn"]]
        kept = []
        for face, c in counts.items():
            kept += [face] * c
        game["locked"] += kept
        game["turn_score"] += score
        game["remaining"] -= len(kept)
        game["pool"] = []

        if game["remaining"] <= 0:
            # 热骰：6 颗全部用完，拿回全部骰子继续
            game["locked"] = []
            game["remaining"] = DICE_NUM
            hot = True
        else:
            hot = False
        game["phase"] = "decide"
        self._save_game(gid, game)

        self._sender.reply(
            ctx, f"{player['name']} 锁定 {_faces_text(kept)}，本次 +{score} 分，"
                 f"本回合累计 {game['turn_score']} 分（剩余可掷 {game['remaining']} 颗）"
                 + ("\n热骰！6 颗骰子全部计分用完，拿回全部骰子，可继续或入账" if hot else ""))
        self._send_board(ctx, game)

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
        """重置当前玩家的回合状态（不改动 turn 下标）"""
        game["phase"] = "roll"
        game["pool"] = []
        game["locked"] = []
        game["turn_score"] = 0
        game["remaining"] = DICE_NUM

    def _end_turn(self, ctx: CommandContext, gid: int, game: dict) -> None:
        """换手给另一位玩家并重置回合状态，随后自动进行新回合的首掷"""
        game["turn"] = (game["turn"] + 1) % PLAYER_NUM
        self._reset_turn(game)
        self._save_game(gid, game)
        self._do_roll(ctx, gid, game)

    def _finish(self, ctx: CommandContext, game: dict, winner: dict,
                headline: str = None) -> None:
        """结算本局：公布总分，按猫眼石数目结算后清除对局"""
        lines = [headline or f"🏆 {winner['name']} 达到 {game['target']} 分，赢下本局 Farkle！"]
        for p in game["players"]:
            lines.append(f"{p['name']}：{p['total']} 分")
        lines += self._settle(game, winner)
        self._remove_game(ctx.group_id)
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
            "pool": [],
            "locked": [],
            "turn_score": 0,
            "remaining": DICE_NUM,
            "players": [],
        }

    @staticmethod
    def _new_player(uid: int, name: str) -> dict:
        return {"id": uid, "name": name, "total": 0}

    def _load_game(self, gid: int):
        return _load_json(_STATE_PATH).get(str(gid))

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
        height = 470
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

        # 当前回合信息
        cur = game["players"][game["turn"]]
        info = (f"{cur['name']} 本回合已累计 {game['turn_score']} 分"
                f"｜已锁定 {len(game['locked'])} 颗｜剩余可掷 {game['remaining']} 颗")
        _center_text(draw, (0, 176, width, 214), info, _font(24), (110, 100, 90))

        # 已锁定的骰子（小图）
        locked = game["locked"]
        if locked:
            size, gap = 44, 10
            row_w = len(locked) * (size + gap) - gap
            x0 = (width - row_w) // 2
            for i, v in enumerate(locked):
                _draw_die(draw, x0 + i * (size + gap), 224, size, v)
            _center_text(draw, (0, 272, width, 296), "已锁定", _font(20), (150, 140, 128))

        # 当前掷出的骰子（大图）
        pool = game["pool"]
        if pool:
            size, gap = 76, 16
            row_w = len(pool) * (size + gap) - gap
            x0 = (width - row_w) // 2
            for i, v in enumerate(pool):
                _draw_die(draw, x0 + i * (size + gap), 306, size, v)

        hint = {
            "keep": "发送「farkle 留 <点数>」锁定计分骰，如 farkle 留 15（锁1个1点、1个5点）",
            "decide": "发送「farkle 掷」继续博分，或「farkle 入账」收分",
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
            "· 另一位：「farkle 加入」，两人到齐后进入先手拍卖\n"
            "· 开局前可「farkle 取消」解散；两人到齐后必须打完\n"
            "· 有猫眼石的对局，开局者与加入者的猫眼石余额都不能为负（欠债者禁入）\n"
            "【先手拍卖】（正式掷骰前）\n"
            "· 两人到齐后先拍卖谁拿先手，由后加入的人先出价\n"
            "· 出价 = 你愿意以「负多少分」的代价换取先手，"
            "如「farkle 出价 300」= 愿意开局 -300 分\n"
            "· 双方轮流出价，每次出价必须高于对方；也可以直接「farkle 接受」\n"
            "· 接受方把先手让给出价方：出价方先手并以自己的出价负分开局，接受方以 0 分开局\n"
            "【回合作战】（轮到你时）\n"
            "· 轮到你的第一次掷骰会自动进行，不需要手动发送\n"
            "· 「farkle 留 <点数>」：锁定至少一颗能计分的骰子，"
            "如「farkle 留 15」（=锁 1 个 1 点、1 个 5 点）、「farkle 留 1 5 5」\n"
            "· 锁定后可「farkle 掷」继续博更多分（有爆骰风险），或「farkle 入账」收分换手\n"
            "【爆骰】\n"
            "· 掷出的骰子完全无法计分 → 爆骰，本回合已累计的分全部作废，回合结束并换手\n"
            "【热骰】\n"
            "· 6 颗骰子全部计分用完 → 拿回全部骰子继续掷，回合延续\n"
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
