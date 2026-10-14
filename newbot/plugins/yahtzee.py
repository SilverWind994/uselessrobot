"""快艇骰子（Yahtzee）—— 移植自 archive/mybot/yahtzee.py。

玩法：群里 1~4 人，每人 12 个计分格，掷 5 颗骰子、最多重投 2 次，选一格计分。
每周记录每位玩家「本周第一次」的分数，跨周结算时按分数排名发放鱼干奖励。
中途可以「放弃」，放弃按当前分数结算（不再依赖强制结束的 stop）。
"""

import json
import os
import re
import random
from datetime import date

from PIL import Image, ImageDraw, ImageFont

from core.command_router import CommandContext, CommandRouter
from core.message_sender import MessageSender, Target

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
_ASSETS_DIR = os.path.join(_BASE_DIR, "assets")
YAHTZEE_DIR = os.path.join(_ASSETS_DIR, "yahtzee")
_STATE_PATH = os.path.join(YAHTZEE_DIR, "state.json")
_WEEKLY_PATH = os.path.join(YAHTZEE_DIR, "weekly.json")

MAX_PLAYERS = 4       # 单局最多人数
MAX_ROLL = 3          # 每回合最多投掷次数（含首投，即可重投 2 次）
CATEGORY_COUNT = 12   # 每人可计分的格子数
# 每周首次得分排行奖励：第1名1000鱼干、第2名900……依次递减，最多发到第10名100
WEEKLY_REWARDS = [1000 - 100 * i for i in range(10)]

# 计分表格行（与 score 数组下标的映射见 _cell_text）
_ROW_NAMES = ["一点", "二点", "三点", "四点", "五点", "六点", "奖励分",
              "全选", "四同", "葫芦", "小顺", "大顺", "快艇", "总分"]

# 子指令别名表：快艇骰子 <子指令> [内容]
_SUB_ALIASES = {
    "加入": "join", "join": "join",
    "开始": "start", "start": "start",
    "重投": "reroll", "reroll": "reroll",
    "计分": "score", "score": "score",
    "放弃": "giveup", "投降": "giveup", "surrender": "giveup",
    "排行榜": "rank", "rank": "rank", "rankinglist": "rank",
    "状态": "status", "status": "status",
    "帮助": "help", "help": "help",
}

# 计分格别名 -> score 数组下标（0-5 点数格，6 全选，7-11 组合格）
_SCORE_ALIASES = {
    "一点": 0, "1点": 0, "1s": 0,
    "二点": 1, "两点": 1, "2点": 1, "2s": 1,
    "三点": 2, "3点": 2, "3s": 2,
    "四点": 3, "4点": 3, "4s": 3,
    "五点": 4, "5点": 4, "5s": 4,
    "六点": 5, "6点": 5, "6s": 5,
    "全选": 6, "chance": 6,
    "四同": 7, "四条": 7, "4k": 7, "4king": 7,
    "葫芦": 8, "fullhouse": 8, "fh": 8,
    "小顺": 9, "smallstraight": 9, "ss": 9,
    "大顺": 10, "largestraight": 10, "ls": 10,
    "快艇": 11, "yahtzee": 11,
}


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _roll5() -> list:
    """掷 5 颗骰子并排序"""
    return sorted(random.randint(1, 6) for _ in range(5))


def _current_week() -> str:
    """当前 ISO 周，形如 2026-W42"""
    y, w, _ = date.today().isocalendar()
    return f"{y}-W{w:02d}"


def _score_of(index: int, dice: list) -> int:
    """按格子下标计算 5 颗骰子（已排序）的得分"""
    if index < 6:
        face = index + 1
        return sum(d for d in dice if d == face)
    if index == 6:                       # 全选
        return sum(dice)
    if index == 7:                       # 四同
        return sum(dice) if (dice[0] == dice[3] or dice[1] == dice[4]) else 0
    if index == 8:                       # 葫芦
        ok = (dice[0] == dice[1] and dice[3] == dice[4]
              and (dice[1] == dice[2] or dice[2] == dice[3]))
        return sum(dice) if ok else 0
    if index == 9:                       # 小顺
        s = set(dice)
        return 15 if (3 in s and 4 in s
                      and ((1 in s and 2 in s) or (2 in s and 5 in s)
                           or (5 in s and 6 in s))) else 0
    if index == 10:                      # 大顺
        s = set(dice)
        return 30 if (s == {1, 2, 3, 4, 5} or s == {2, 3, 4, 5, 6}) else 0
    if index == 11:                      # 快艇
        return 50 if dice[0] == dice[4] else 0
    return 0


def _total(score: list) -> int:
    """单人格子数组的总分（含上区 ≥63 的 35 奖励分）"""
    upper = sum(v for v in score[0:6] if v > 0)
    bonus = 35 if upper >= 63 else 0
    return upper + bonus + sum(v for v in score[6:12] if v > 0)


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


class YahtzeePlugin:
    """快艇骰子：群内多人掷骰计分 + 每周首次得分排行奖励"""

    def __init__(self, sender: MessageSender, cat_plugin=None):
        self._sender = sender
        self._cat = cat_plugin  # 猫猫远征队插件，用于发放鱼干奖励

    # ==================== 注册命令 ====================

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["快艇骰子", "yahtzee", "y", ".y"],
            self.cmd_entry,
            description="快艇骰子·群内掷骰计分（子指令：加入/开始/重投/计分/放弃/排行榜）"
        )

    def cmd_entry(self, ctx: CommandContext) -> None:
        if not ctx.is_group:
            self._sender.reply(ctx, "请在群聊中开启此功能")
            return
        self._ensure_week()

        args = ctx.get_args().strip()
        parts = args.split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if not sub:
            self._show(ctx)
            return

        action = _SUB_ALIASES.get(sub)
        if action is None:
            self._sender.reply(ctx, f"指令有误喵，发送「快艇骰子」查看当前局面")
            return

        if action == "help":
            self._sender.reply(ctx, self._help_text())
        elif action == "join":
            self._cmd_join(ctx)
        elif action == "start":
            self._cmd_start(ctx)
        elif action == "reroll":
            self._cmd_reroll(ctx, rest)
        elif action == "score":
            self._cmd_score(ctx, rest)
        elif action == "giveup":
            self._cmd_giveup(ctx)
        elif action == "rank":
            self.cmd_rank(ctx)
        elif action == "status":
            self._show(ctx)

    def cmd_rank(self, ctx: CommandContext) -> None:
        weekly = self._ensure_week()
        scores = weekly.get("scores") or {}
        week = weekly.get("week", _current_week())
        if not scores:
            self._sender.reply(ctx, f"本周（{week}）还没有人完成快艇骰子喵，快去开一局吧")
            return
        ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
        lines = [f"快艇骰子本周排行榜（{week}）",
                 "每位玩家只计本周第一次的分数，换周后按这份分数排名发鱼干", ""]
        for i, (_, info) in enumerate(ranked[:10]):
            reward = WEEKLY_REWARDS[i] if i < len(WEEKLY_REWARDS) else 0
            lines.append(f"{i + 1}. {info['name']} — {info['score']}分（奖励{reward}鱼干）")
        self._sender.reply(ctx, "\n".join(lines))

    # ==================== 子指令实现 ====================

    def _show(self, ctx: CommandContext) -> None:
        game = self._get_or_create(ctx)
        if not game["started"]:
            names = "、".join(p["name"] for p in game["players"])
            self._sender.reply(
                ctx,
                f"快艇骰子准备中（{len(game['players'])}/{MAX_PLAYERS}）：{names}\n"
                f"发送「快艇骰子 加入」加入，「快艇骰子 开始」开始"
            )
            return
        self._send_board(ctx, game)

    def _cmd_join(self, ctx: CommandContext) -> None:
        game = self._get_or_create(ctx)
        uid = ctx.user_id
        if game["started"]:
            self._sender.reply(ctx, "游戏已经开始了")
            return
        if any(p["id"] == uid for p in game["players"]):
            self._sender.reply(ctx, "你已经加入游戏了")
            return
        if len(game["players"]) >= MAX_PLAYERS:
            self._sender.reply(ctx, "人数已满喵")
            return
        game["players"].append({"id": uid, "name": ctx.user_name, "score": [-1] * CATEGORY_COUNT})
        started = len(game["players"]) >= MAX_PLAYERS
        if started:
            self._start_game(game)
        self._save_game(ctx.group_id, game)
        if started:
            self._sender.reply(ctx, f"{ctx.user_name} 加入游戏，人满自动开始！")
            self._send_board(ctx, game)
        else:
            self._sender.reply(
                ctx, f"{ctx.user_name} 加入游戏（{len(game['players'])}/{MAX_PLAYERS}）"
                     f"\n发送「快艇骰子 开始」立即开始")

    def _cmd_start(self, ctx: CommandContext) -> None:
        game = self._get_or_create(ctx)
        if game["started"]:
            self._sender.reply(ctx, "游戏已经开始了")
            return
        self._start_game(game)
        self._save_game(ctx.group_id, game)
        self._sender.reply(ctx, "游戏开始喵！")
        self._send_board(ctx, game)

    def _cmd_reroll(self, ctx: CommandContext, rest: str) -> None:
        game = self._get_game(ctx.group_id)
        if game is None or not game["started"]:
            self._sender.reply(ctx, "当前没有进行中的游戏喵")
            return
        err = self._check_turn(ctx, game)
        if err:
            self._sender.reply(ctx, err)
            return
        if game["roll"] >= MAX_ROLL:
            self._sender.reply(ctx, "已经没有重投次数了饿")
            return
        raw = re.split(r"[\s,，]+", rest)
        idxs = set()
        for t in raw:
            if not t:
                continue
            if t in ("1", "2", "3", "4", "5"):
                idxs.add(int(t) - 1)
            else:
                self._sender.reply(ctx, "要重投的东西好像不太对喵")
                return
        if not idxs:
            self._sender.reply(ctx, "指令不全喵，例如：快艇骰子 重投 1 2")
            return
        dice = game["dice"]
        for i in idxs:
            dice[i] = random.randint(1, 6)
        game["dice"] = sorted(dice)
        game["roll"] += 1
        self._save_game(ctx.group_id, game)
        self._send_board(ctx, game)

    def _cmd_score(self, ctx: CommandContext, rest: str) -> None:
        game = self._get_game(ctx.group_id)
        if game is None or not game["started"]:
            self._sender.reply(ctx, "当前没有进行中的游戏喵")
            return
        err = self._check_turn(ctx, game)
        if err:
            self._sender.reply(ctx, err)
            return
        index = _SCORE_ALIASES.get(rest.strip().lower())
        if index is None:
            self._sender.reply(ctx, "这是什么？发送「快艇骰子 帮助」查看可计分的格子")
            return
        player = game["players"][game["turn"]]
        if player["score"][index] != -1:
            self._sender.reply(ctx, "这个格子的分已经算了")
            return
        player["score"][index] = _score_of(index, game["dice"])
        gained = player["score"][index]
        if self._advance(game):
            self._finalize(ctx, game, f"{player['name']} 计分 {_ROW_NAMES[index]} +{gained}")
            return
        self._save_game(ctx.group_id, game)
        self._sender.reply(ctx, f"{player['name']} 计分 {_ROW_NAMES[index]} +{gained}")
        self._send_board(ctx, game)

    def _cmd_giveup(self, ctx: CommandContext) -> None:
        game = self._get_game(ctx.group_id)
        if game is None or not game["started"]:
            self._sender.reply(ctx, "当前没有进行中的游戏喵")
            return
        if not any(p["id"] == ctx.user_id for p in game["players"]):
            self._sender.reply(ctx, "你没有参与这局游戏喵")
            return
        self._finalize(ctx, game, f"{ctx.user_name} 放弃本局，按当前分数结算")

    # ==================== 内部逻辑 ====================

    def _get_game(self, group_id: int):
        return _load_json(_STATE_PATH).get(str(group_id))

    def _get_or_create(self, ctx: CommandContext) -> dict:
        """取本群对局，没有则以发起者为第一名玩家新建"""
        game = self._get_game(ctx.group_id)
        if game is not None:
            return game
        game = {
            "started": False,
            "turn": 0,
            "round": 1,
            "roll": 1,
            "dice": [],
            "players": [{"id": ctx.user_id, "name": ctx.user_name,
                         "score": [-1] * CATEGORY_COUNT}],
        }
        self._save_game(ctx.group_id, game)
        return game

    def _save_game(self, group_id: int, game: dict) -> None:
        state = _load_json(_STATE_PATH)
        state[str(group_id)] = game
        _save_json(_STATE_PATH, state)

    def _remove_game(self, group_id: int) -> None:
        state = _load_json(_STATE_PATH)
        if str(group_id) in state:
            del state[str(group_id)]
            _save_json(_STATE_PATH, state)

    def _start_game(self, game: dict) -> None:
        game["started"] = True
        game["turn"] = 0
        game["round"] = 1
        game["roll"] = 1
        game["dice"] = _roll5()

    def _check_turn(self, ctx: CommandContext, game: dict) -> str:
        """非当前玩家返回提示文案，否则返回空串"""
        cur = game["players"][game["turn"]]
        if ctx.user_id != cur["id"]:
            return f"当前玩家是 {cur['name']}"
        return ""

    def _advance(self, game: dict) -> bool:
        """结束当前回合并轮到下一位；整局结束返回 True"""
        game["turn"] += 1
        if game["turn"] >= len(game["players"]):
            game["turn"] = 0
            game["round"] += 1
        if game["round"] > CATEGORY_COUNT:
            return True
        game["roll"] = 1
        game["dice"] = _roll5()
        return False

    def _finalize(self, ctx: CommandContext, game: dict, reason: str) -> None:
        """结算本局：记录各玩家本周首次分数、公布总分、清除对局"""
        weekly = self._ensure_week()
        lines = [reason, ""]
        for p in game["players"]:
            total = _total(p["score"])
            key = str(p["id"])
            if key not in weekly["scores"]:
                weekly["scores"][key] = {"name": p["name"], "score": total}
                note = "（计入本周首次分数）"
            else:
                note = "（本周已有首次分数，不重复计）"
            lines.append(f"{p['name']}：{total}分 {note}")
        _save_json(_WEEKLY_PATH, weekly)
        self._remove_game(ctx.group_id)
        self._sender.reply(ctx, "\n".join(lines))

    def _send_board(self, ctx: CommandContext, game: dict) -> None:
        try:
            path = self._render_board(game, ctx.group_id)
        except Exception as e:
            self._sender.reply(ctx, f"棋盘绘制失败了喵：{e}")
            return
        self._sender.send_image(Target.from_data(ctx.raw_data), path)

    def _ensure_week(self) -> dict:
        """跨周时结算上一周奖励并重置本周榜"""
        weekly = _load_json(_WEEKLY_PATH)
        week = _current_week()
        if weekly.get("week") == week:
            return weekly
        self._settle_week(weekly)
        weekly["week"] = week
        weekly["scores"] = {}
        _save_json(_WEEKLY_PATH, weekly)
        return weekly

    def _settle_week(self, weekly: dict) -> None:
        """按上一周首次得分排名发放鱼干奖励（只结算一次）"""
        prev = weekly.get("week")
        scores = weekly.get("scores") or {}
        if not prev or not scores:
            return
        settled = weekly.setdefault("settled", [])
        if prev in settled:
            return
        ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
        for i, (qq, _info) in enumerate(ranked[:len(WEEKLY_REWARDS)]):
            if self._cat is not None:
                try:
                    self._cat.add_fish(int(qq), WEEKLY_REWARDS[i])
                except Exception:
                    pass
        settled.append(prev)
        weekly["settled"] = settled[-8:]

    @staticmethod
    def _help_text() -> str:
        return (
            "快艇骰子玩法\n"
            "· 快艇骰子 加入 / 开始：组局，1~4人（人满自动开始）\n"
            "· 快艇骰子 重投 1 3：重投第1、3颗骰子（每回合最多重投2次）\n"
            "· 快艇骰子 计分 快艇：把当前骰子记到指定格子\n"
            "· 快艇骰子 放弃：中止本局，按当前分数结算\n"
            "· 快艇骰子 排行榜：查看本周排行\n"
            "格子：一点~六点、全选、四同、葫芦、小顺、大顺、快艇\n"
            "（上区合计≥63分额外+35；每人12格，全填完即结束）\n"
            "【排行与奖励】每周只记录你「本周第一次」的分数（正常打完或放弃都算），同周再玩不刷新；\n"
            f"换周后按这份分数从高到低排名发鱼干：第1名{WEEKLY_REWARDS[0]}，"
            f"逐名-100，发到第10名{WEEKLY_REWARDS[-1]}，第10名之后没有奖励；\n"
            "奖励在换周后第一次用到快艇骰子时自动发放。"
        )

    # ==================== 绘图 ====================

    def _render_board(self, game: dict, group_id: int) -> str:
        players = game["players"]
        n = len(players)
        label_w, col_w = 190, 190
        margin = 20
        width = margin * 2 + label_w + col_w * n
        header_h = 200
        row_h = 44
        table_top = header_h + 46
        height = table_top + row_h * len(_ROW_NAMES) + margin

        img = Image.new("RGB", (width, height), (252, 250, 244))
        draw = ImageDraw.Draw(img)
        draw.rectangle((6, 6, width - 7, height - 7), outline=(205, 196, 180), width=3)

        cur = players[game["turn"]]
        self._center_text(draw, (0, 16, width, 62),
                          f"快艇骰子 · 第{min(game['round'], CATEGORY_COUNT)}轮",
                          self._font(40), (60, 45, 35))
        self._center_text(draw, (0, 60, width, 94),
                          f"当前回合：{cur['name']}（第{game['roll']}/{MAX_ROLL}投）",
                          self._font(26), (168, 96, 40))

        dice = game["dice"] or []
        size, gap = 76, 16
        if dice:
            start_x = (width - (len(dice) * (size + gap) - gap)) // 2
            for i, v in enumerate(dice):
                _draw_die(draw, start_x + i * (size + gap), 108, size, v)

        # 表头
        head_y = table_top - 44
        draw.rectangle((margin, head_y, width - margin, head_y + 40), fill=(234, 228, 214))
        for j, p in enumerate(players):
            cx = margin + label_w + j * col_w
            color = (196, 128, 30) if j == game["turn"] else (60, 52, 44)
            self._center_text(draw, (cx, head_y, cx + col_w, head_y + 40),
                              self._short(p["name"]), self._font(26), color)

        # 计分行
        for r, name in enumerate(_ROW_NAMES):
            ry = table_top + r * row_h
            bg = (247, 243, 233) if r % 2 == 0 else (240, 235, 224)
            draw.rectangle((margin, ry, width - margin, ry + row_h), fill=bg)
            draw.text((margin + 16, ry + 9), name, font=self._font(26), fill=(70, 60, 50))
            for j, p in enumerate(players):
                cx = margin + label_w + j * col_w
                self._center_text(draw, (cx, ry, cx + col_w, ry + row_h),
                                  self._cell_text(p, r), self._font(28), (50, 45, 40))
            draw.line((margin, ry, width - margin, ry), fill=(224, 218, 206))
        draw.line((margin, table_top + row_h * len(_ROW_NAMES), width - margin,
                   table_top + row_h * len(_ROW_NAMES)), fill=(224, 218, 206))

        os.makedirs(YAHTZEE_DIR, exist_ok=True)
        path = os.path.join(YAHTZEE_DIR, f"board_{group_id}.png")
        img.save(path)
        return path

    @staticmethod
    def _cell_text(player: dict, row: int) -> str:
        """棋盘某行某玩家的显示文本"""
        s = player["score"]
        if row < 6:
            return "-" if s[row] < 0 else str(s[row])
        if row == 6:
            upper = sum(v for v in s[0:6] if v > 0)
            return "35" if upper >= 63 else "-"
        if row < 13:
            idx = row - 1
            return "-" if s[idx] < 0 else str(s[idx])
        return str(_total(s))

    @staticmethod
    def _short(name: str, limit: int = 8) -> str:
        return name[:limit]

    @staticmethod
    def _font(size: int) -> ImageFont.FreeTypeFont:
        for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                   r"C:\Windows\Fonts\simsun.ttc"):
            if os.path.exists(fp):
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()

    @staticmethod
    def _center_text(draw: ImageDraw.ImageDraw, box, text: str, fnt, fill) -> None:
        x0, y0, x1, y1 = box
        l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
        x = x0 + (x1 - x0 - (r - l)) / 2 - l
        y = y0 + (y1 - y0 - (b - t)) / 2 - t
        draw.text((x, y), text, font=fnt, fill=fill)
