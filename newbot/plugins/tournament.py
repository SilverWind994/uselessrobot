"""锦标赛（tournament）—— 群里用现有对战游戏进行的淘汰赛。

参赛人数支持 4 / 8 / 16 三种；奖金按名次阶梯「对半砍」向下取整；
比赛项目由创建者指定（现有：快艇骰子 / 17步麻将 / Farkle），可指定一个或多个。
创建者不自动参赛（想参赛需自己「锦标赛 加入」）；
锦标赛报名中 / 进行中时，本群禁止手动开这三种游戏的普通对局。

赛制：
· 开局按随机分组两两配对，负者淘汰、胜者晋级。
· 单项目模式：全程固定该项目；非决赛单场定胜负，平局（如 17步麻将流局）
  加赛一次，仍平局则随机晋级；决赛三局两胜。
· 多项目模式：每一场从项目池里随机抽取项目；决赛抽取三个不同项目打三局两胜。
· 每一场的「谁先开局」（先手）随机决定。
· 只有管理员可以开出带鱼干 / 猫眼石奖励的锦标赛。

每一场对局由本插件直接为匹配的两位选手开局（不开放手动加入，杜绝外人乱入），
对局真正结束时三个游戏插件会把结果回调给本插件，本插件据此推进赛程并按名次发放奖励。
"""

import json
import os
import random
import time

from PIL import Image, ImageDraw, ImageFont

from config import Config
from core.command_router import CommandContext, CommandRouter
from core.message_sender import MessageSender, Target

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
_ASSETS_DIR = os.path.join(_BASE_DIR, "assets")
TOURNAMENT_DIR = os.path.join(_ASSETS_DIR, "tournament")  # 运行时：锦标赛状态
_STATE_PATH = os.path.join(TOURNAMENT_DIR, "state.json")

IDLE_SECONDS = 6 * 60 * 60   # 锦标赛闲置超过该时长自动作废，避免卡住后续创建
SIZES = (4, 8, 16)           # 参赛人数可选值

# 比赛项目池：与三个对战插件注册的 game 键一一对应
PROJECTS = (
    ("yahtzee", "快艇骰子"),
    ("mahjong17", "17步麻将"),
    ("farkle", "Farkle"),
)
_PROJECT_NAME = {key: name for key, name in PROJECTS}
# 创建时指定项目的名称别名（大小写不敏感）-> 项目 key
_GAME_ALIASES = {
    "快艇骰子": "yahtzee", "快艇": "yahtzee", "yahtzee": "yahtzee", "y": "yahtzee",
    "17步麻将": "mahjong17", "十七步麻将": "mahjong17", "mahjong17": "mahjong17",
    "mj17": "mahjong17",
    "farkle": "farkle", "骰子对决": "farkle",
}

# 轮次名 / 名次名（除数 = 该轮参赛人数 = size >> round）
_ROUND_NAME = {16: "十六强赛", 8: "八强赛", 4: "四强赛", 2: "决赛"}
_TIER_NAME = {16: "十六强", 8: "八强", 4: "四强", 2: "亚军"}

# 子指令别名：锦标赛 <子指令> [内容]
_SUB_ALIASES = {
    "创建": "create", "新建": "create", "create": "create",
    "加入": "join", "报名": "join", "join": "join",
    "退出": "leave", "退赛": "leave", "leave": "leave", "quit": "leave",
    "开始": "start", "start": "start",
    "取消": "cancel", "解散": "cancel", "cancel": "cancel",
    "继续": "resume", "resume": "resume",
    "强制结束": "force_end", "结束": "force_end", "强制取消": "force_end", "force_end": "force_end",
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


def _text_w(draw: ImageDraw.ImageDraw, text: str, fnt) -> float:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0]


def _fit_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: float) -> str:
    """超宽时截断并加省略号"""
    if _text_w(draw, text, fnt) <= max_w:
        return text
    while text and _text_w(draw, text + "…", fnt) > max_w:
        text = text[:-1]
    return text + "…"


def _center_text(draw: ImageDraw.ImageDraw, box, text: str, fnt, fill) -> None:
    x0, y0, x1, y1 = box
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    x = x0 + (x1 - x0 - (r - l)) / 2 - l
    y = y0 + (y1 - y0 - (b - t)) / 2 - t
    draw.text((x, y), text, font=fnt, fill=fill)


# ==================== 插件 ====================

class TournamentPlugin:
    """锦标赛：群里多人淘汰赛，把三种对战游戏当作比赛项目"""

    def __init__(self, sender: MessageSender, cat_plugin=None,
                 yahtzee=None, mahjong17=None, farkle=None):
        self._sender = sender
        self._cat = cat_plugin  # 猫猫远征队插件，用于发放鱼干 / 猫眼石奖励
        # 三个对战游戏插件：锦标赛直接调用它们为匹配的两位选手开局
        self._yahtzee = yahtzee
        self._mahjong17 = mahjong17
        self._farkle = farkle

    # ==================== 作为对战插件的结果接收方 ====================

    def on_match_result(self, gid: int, result: dict) -> None:
        """由快艇骰子 / 17步麻将 / Farkle 插件在对局结束时回调，用于推进赛程"""
        t = self._load(gid)
        if not t or t.get("status") != "playing" or not t.get("pending"):
            return
        pending = t["pending"]
        expect_key = pending["projects"][pending["game_no"]]
        game_key = result.get("game")
        if game_key != expect_key:
            got = _PROJECT_NAME.get(game_key, game_key)
            self._send_group(
                gid, f"⚠️ 本场对局项目应为「{_PROJECT_NAME[expect_key]}」，"
                     f"刚才结束的「{got}」不计入锦标赛")
            return

        ids = [p["id"] for p in result.get("players", [])]
        if not all(pid in ids for pid in pending["p"]):
            return  # 不是本场两位选手的对局，忽略
        winner = result.get("winner")
        if winner is not None and winner not in pending["p"]:
            return  # 旁观者获胜，不计入

        pending["results"].append({
            "winner": winner,
            "project": expect_key,
            "reason": result.get("reason", ""),
        })

        decided, need_more = self._resolve(pending)
        if need_more:
            pending["game_no"] += 1
            if pending["game_no"] >= len(pending["projects"]):
                # 非决赛加赛：沿用同一个项目
                pending["projects"].append(pending["projects"][0])
            t["updated_at"] = time.time()
            self._save(t)
            self._announce_match(t, pending)
            return
        self._finish_match(t, pending, decided)

    # ==================== 注册命令 ====================

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["锦标赛", "tournament", ".tournament", "/tournament"],
            self.cmd_entry,
            description="锦标赛·用对战游戏进行淘汰赛（子指令：创建/加入/开始/取消/强制结束/状态）"
        )

    def cmd_entry(self, ctx: CommandContext) -> None:
        if ctx.is_private:
            self._sender.reply(ctx, "锦标赛是群里玩的喵，请在群聊里发送指令")
            return
        self._drop_stale(ctx)

        args = ctx.get_args().strip()
        parts = args.split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if not sub:
            self._cmd_status(ctx)
            return

        action = _SUB_ALIASES.get(sub)
        if action is None:
            self._sender.reply(ctx, "指令有误喵，发送「锦标赛 帮助」查看玩法")
            return

        if action == "help":
            self._sender.reply(ctx, self._help_text())
        elif action == "create":
            self._cmd_create(ctx, rest)
        elif action == "join":
            self._cmd_join(ctx)
        elif action == "leave":
            self._cmd_leave(ctx)
        elif action == "start":
            self._cmd_start(ctx)
        elif action == "cancel":
            self._cmd_cancel(ctx)
        elif action == "resume":
            self._cmd_resume(ctx)
        elif action == "force_end":
            self._cmd_force_end(ctx)
        elif action == "status":
            self._cmd_status(ctx)

    # ==================== 群聊：创建 / 加入 / 开始 / 取消 / 状态 ====================

    def _cmd_create(self, ctx: CommandContext, rest: str) -> None:
        gid = ctx.group_id
        old = self._load(gid)
        if old is not None and old.get("status") != "done":
            self._sender.reply(ctx, "本群已经有一场锦标赛了，等它结束或取消后再开新的一场喵")
            return

        tokens = rest.split()
        if len(tokens) < 2 or not tokens[0].isdigit():
            self._sender.reply(
                ctx, "用法：「锦标赛 创建 <人数> <项目…> [冠军鱼干] [冠军猫眼石]」\n"
                     f"人数可选 4 / 8 / 16；项目可写一个或多个（现有："
                     f"{'、'.join(name for _, name in PROJECTS)}）\n"
                     "示例：「锦标赛 创建 8 快艇骰子 farkle 1000 10」"
                     "= 8 人、用快艇骰子与 Farkle、冠军 1000 鱼干 + 10 猫眼石")
            return
        size = int(tokens[0])
        if size not in SIZES:
            self._sender.reply(ctx, "人数只能填 4 / 8 / 16 喵")
            return

        # 人数之后的非数字词依次是项目名；遇到数字词起为奖励（先鱼干、后猫眼石）
        pool = []
        numbers = []
        for tok in tokens[1:]:
            if tok.isdigit():
                numbers.append(int(tok))
                continue
            key = _GAME_ALIASES.get(tok.lower())
            if key is None:
                self._sender.reply(
                    ctx, f"不认识的项目「{tok}」喵，现有项目："
                         f"{'、'.join(name for _, name in PROJECTS)}")
                return
            if key in pool:
                self._sender.reply(
                    ctx, f"项目「{_PROJECT_NAME[key]}」重复了喵，每个项目只能写一次")
                return
            pool.append(key)

        if not pool:
            self._sender.reply(
                ctx, "至少要指定一个项目喵，例如「锦标赛 创建 8 快艇骰子 1000 10」")
            return
        if len(numbers) > 2:
            self._sender.reply(ctx, "奖励最多填两项：先冠军鱼干、后冠军猫眼石喵")
            return
        fish = numbers[0] if len(numbers) >= 1 else 0
        stone = numbers[1] if len(numbers) >= 2 else 0

        if (fish > 0 or stone > 0) and not Config.is_admin(ctx.user_id):
            self._sender.reply(
                ctx, "只有管理员可以开出带鱼干 / 猫眼石奖励的锦标赛喵，"
                     "其他人可以把奖励填成 0（空奖励锦标赛）")
            return

        t = {
            "group_id": gid,
            "owner": ctx.user_id,
            "size": size,
            "project_count": len(pool),
            "champion_fish": fish,
            "champion_stone": stone,
            "status": "waiting",
            "players": [],   # 创建者不自动参赛，想参赛需自己「锦标赛 加入」
            "pool": pool,
            "round": 0,
            "matches": [],
            "pending": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self._save(t)
        reward = self._reward_desc(fish, stone)
        pool_text = "、".join(_PROJECT_NAME[k] for k in pool)
        self._sender.reply(
            ctx, f"🏆 已创建锦标赛：{size} 人 · 项目：{pool_text} · {reward}\n"
                 f"创建者不自动参赛，想参赛请自己也发「锦标赛 加入」\n"
                 f"报名用「锦标赛 加入」，报满 {size} 人后任何人发送「锦标赛 开始」即可开始")
        self._sender.reply(ctx, self._status_text(t))

    def _cmd_join(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        t = self._load(gid)
        if t is None:
            self._sender.reply(ctx, "本群还没有锦标赛喵，发送「锦标赛 创建 <人数> <项目…>」创建")
            return
        if t["status"] != "waiting":
            self._sender.reply(ctx, "这场锦标赛已经开始或结束了喵")
            return
        if any(p["id"] == ctx.user_id for p in t["players"]):
            self._sender.reply(ctx, "你已经报名了喵")
            return
        if len(t["players"]) >= t["size"]:
            self._sender.reply(ctx, "人数已满了喵")
            return
        if t["champion_stone"] > 0 and self._debt_of(ctx.user_id) > 0:
            self._sender.reply(
                ctx, f"你还有 {self._debt_of(ctx.user_id)} 个猫眼石欠债，"
                     f"不能参加带猫眼石奖励的锦标赛喵")
            return

        t["players"].append({"id": ctx.user_id, "name": ctx.user_name})
        t["updated_at"] = time.time()
        self._save(t)
        n = len(t["players"])
        if n >= t["size"]:
            self._sender.reply(
                ctx, f"{ctx.user_name} 报名（{n}/{t['size']}）——报名已满！"
                     f"请创建者发送「锦标赛 开始」开始赛程")
        else:
            self._sender.reply(ctx, f"{ctx.user_name} 报名（{n}/{t['size']}）")

    def _cmd_leave(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        t = self._load(gid)
        if t is None:
            self._sender.reply(ctx, "本群还没有锦标赛喵")
            return
        if t["status"] != "waiting":
            self._sender.reply(ctx, "这场锦标赛已经开始了喵，报名后不能退出")
            return
        if not any(p["id"] == ctx.user_id for p in t["players"]):
            self._sender.reply(ctx, "你还没有报名这场锦标赛喵")
            return

        t["players"] = [p for p in t["players"] if p["id"] != ctx.user_id]
        t["updated_at"] = time.time()
        self._save(t)
        self._sender.reply(
            ctx, f"{ctx.user_name} 已退出锦标赛，目前报名 {len(t['players'])}/{t['size']} 人")

    def _cmd_start(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        t = self._load(gid)
        if t is None:
            self._sender.reply(ctx, "本群还没有锦标赛喵")
            return
        if t["status"] != "waiting":
            self._sender.reply(ctx, "这场锦标赛已经开始或结束了喵")
            return
        n = len(t["players"])
        if n != t["size"]:
            self._sender.reply(ctx, f"还没报满喵，当前 {n}/{t['size']}，"
                                    f"再等 {t['size'] - n} 人")
            return

        self._start_tournament(t)
        self._save(t)

    def _cmd_cancel(self, ctx: CommandContext) -> None:
        gid = ctx.group_id
        t = self._load(gid)
        if t is None:
            self._sender.reply(ctx, "本群没有锦标赛喵")
            return
        if t["owner"] != ctx.user_id and not Config.is_admin(ctx.user_id):
            self._sender.reply(ctx, "只有创建者可以取消锦标赛喵")
            return
        if t["status"] == "playing":
            self._sender.reply(ctx, "锦标赛一旦开始就必须打完喵（可让管理员协助处理）")
            return
        self._remove(gid)
        self._sender.reply(ctx, f"{ctx.user_name} 取消了本场锦标赛")

    def _cmd_force_end(self, ctx: CommandContext) -> None:
        """管理员强制结束进行中的锦标赛（避免有人缺席导致卡住）"""
        gid = ctx.group_id
        t = self._load(gid)
        if t is None:
            self._sender.reply(ctx, "本群没有锦标赛喵")
            return
        if not Config.is_admin(ctx.user_id):
            self._sender.reply(ctx, "只有管理员可以强制结束锦标赛喵")
            return
        status_text = {"waiting": "报名中", "playing": "进行中", "done": "已结束"}.get(
            t.get("status"), t.get("status"))
        self._remove(gid)
        self._sender.reply(
            ctx,
            f"🛑 管理员已强制结束本场锦标赛（原状态：{status_text}）。\n"
            f"如还有未打完的对战对局，可由对局双方自行放弃或取消。")

    def _cmd_status(self, ctx: CommandContext) -> None:
        t = self._load(ctx.group_id)
        if t is None:
            self._sender.reply(
                ctx, "本群还没有锦标赛喵，发送「锦标赛 创建 <人数> <项目…>」创建\n"
                     "发送「锦标赛 帮助」查看玩法")
            return
        if t["status"] in ("playing", "done"):
            self._send_bracket(t)   # 进行中/已结束直接发晋级图
            return
        self._sender.reply(ctx, self._status_text(t))

    # ==================== 赛程推进 ====================

    def _start_tournament(self, t) -> None:
        """随机分组、开启第一轮（项目池在创建时已由创建者指定）"""
        size = t["size"]
        shuffled = list(t["players"])
        random.shuffle(shuffled)

        row = []
        for i in range(0, size, 2):
            a, b = shuffled[i], shuffled[i + 1]
            row.append({
                "p": [a["id"], b["id"]],
                "names": [a["name"], b["name"]],
                "winner": None,
                "games": [],
            })
        t["matches"] = [row]
        t["round"] = 0
        t["status"] = "playing"
        t["pending"] = None
        t["updated_at"] = time.time()

        pool_text = "、".join(_PROJECT_NAME[k] for k in t["pool"])
        self._send_group(
            t["group_id"],
            f"🏆 锦标赛开始！{t['size']} 人 · {t['project_count']} 种项目（{pool_text}）\n"
            f"分组与先后手均为随机，两两对局、负者淘汰。")
        self._begin_match(t, 0, 0)
        self._send_bracket(t)

    def _begin_match(self, t, r: int, index: int) -> None:
        """进入第 r 轮第 index 场，随机决定项目与先手并公告"""
        row = t["matches"][r]
        m = row[index]
        is_final = len(row) == 1

        if is_final:
            # 决赛三局两胜：优先抽三个不同项目，项目不足三个时尽量都用上
            if len(t["pool"]) >= 3:
                projects = random.sample(t["pool"], 3)
            elif len(t["pool"]) == 2:
                projects = [t["pool"][0], t["pool"][1], random.choice(t["pool"])]
            else:
                projects = [t["pool"][0]] * 3
        else:
            projects = [random.choice(t["pool"])]

        pending = {
            "round": r,
            "index": index,
            "p": list(m["p"]),
            "names": list(m["names"]),
            "is_final": is_final,
            "projects": projects,
            "game_no": 0,
            "results": [],
        }
        # 先手随机决定，直接作为该项目对局里的开局者（编排器会自动开局）
        pending["starter"] = random.choice(pending["p"])
        t["pending"] = pending
        t["updated_at"] = time.time()
        self._announce_match(t, pending)

    def _announce_match(self, t, pending: dict) -> None:
        """公告当前这一场（哪两位、什么项目），并由编排器直接为两位选手开局"""
        key = pending["projects"][pending["game_no"]]
        name_of = {p["id"]: p["name"] for p in t["players"]}
        a_name = name_of.get(pending["p"][0], pending["names"][0])
        b_name = name_of.get(pending["p"][1], pending["names"][1])

        if pending["is_final"]:
            proj_names = "、".join(
                dict.fromkeys(_PROJECT_NAME[k] for k in pending["projects"]))
            tag = f"（三局两胜，项目：{proj_names}）"
            label = f"第 {pending['game_no'] + 1}/3 局"
        else:
            tag = ""
            label = "本场"

        round_name = _ROUND_NAME.get(t["size"] >> pending["round"], "对局")
        lines = [
            f"🏆 锦标赛 {round_name}：{a_name} vs {b_name}{tag}",
            f"{label}项目：{_PROJECT_NAME[key]}，已自动开局",
        ]
        self._send_group(t["group_id"], "\n".join(lines))
        if not self._start_match(t, pending):
            key = pending["projects"][pending["game_no"]]
            self._send_group(
                t["group_id"],
                f"⚠️ 本群已有未结束的{_PROJECT_NAME[key]}对局，无法为锦标赛自动开局；"
                f"请先打完或取消它，再发送「锦标赛 继续」")

    def _start_match(self, t, pending: dict) -> bool:
        """直接为匹配的两位选手开局：不开放手动加入，杜绝外人乱入。

        成功返回 True；本群已有未结束的同款对局时返回 False（交由调用方提示）。
        """
        gid = t["group_id"]
        name_of = {p["id"]: p["name"] for p in t["players"]}
        starter = pending["starter"]
        other = pending["p"][0] if starter == pending["p"][1] else pending["p"][1]
        players = [(starter, name_of.get(starter, "?")),
                   (other, name_of.get(other, "?"))]
        key = pending["projects"][pending["game_no"]]
        plugin = {"yahtzee": self._yahtzee, "mahjong17": self._mahjong17,
                  "farkle": self._farkle}.get(key)
        if plugin is None:
            return False
        return plugin.start_tournament_match(gid, players)

    def _cmd_resume(self, ctx: CommandContext) -> None:
        """手动继续卡住的场次：为当前 pending 场次重新开局"""
        gid = ctx.group_id
        t = self._load(gid)
        if t is None:
            self._sender.reply(ctx, "本群还没有锦标赛喵")
            return
        if t["status"] != "playing" or not t.get("pending"):
            self._sender.reply(ctx, "现在没有卡住的锦标赛场次喵")
            return

        pending = t["pending"]
        key = pending["projects"][pending["game_no"]]
        if self._start_match(t, pending):
            t["updated_at"] = time.time()
            self._save(t)
            self._sender.reply(
                ctx, f"已为 {pending['names'][0]} vs {pending['names'][1]} "
                     f"重新开局（{_PROJECT_NAME[key]}）")
        else:
            self._sender.reply(
                ctx, f"本群已有未结束的{_PROJECT_NAME[key]}对局，"
                     f"先打完或取消它，再发送「锦标赛 继续」")

    def _resolve(self, pending: dict):
        """根据已完成各场结果判定本场是否结束，返回 (胜者id | None, 是否还需继续)"""
        res = pending["results"]
        p = pending["p"]
        if pending["is_final"]:
            wins = {p[0]: 0, p[1]: 0}
            for r in res:
                if r["winner"] is not None:
                    wins[r["winner"]] = wins.get(r["winner"], 0) + 1
            if wins.get(p[0], 0) >= 2:
                return p[0], False
            if wins.get(p[1], 0) >= 2:
                return p[1], False
            if len(res) >= 3:
                if wins.get(p[0], 0) > wins.get(p[1], 0):
                    return p[0], False
                if wins.get(p[1], 0) > wins.get(p[0], 0):
                    return p[1], False
                return random.choice(p), False
            return None, True

        # 非决赛：单场定胜负；平局加赛一次，仍平局随机
        if res[0]["winner"] is not None:
            return res[0]["winner"], False
        if len(res) == 1:
            return None, True  # 平局，加赛
        if res[1]["winner"] is not None:
            return res[1]["winner"], False
        return random.choice(p), False

    def _finish_match(self, t, pending: dict, winner_id: int) -> None:
        """本场对局结束，记录胜者并推进到下一场 / 下一轮 / 结算"""
        r = pending["round"]
        index = pending["index"]
        m = t["matches"][r][index]
        m["winner"] = winner_id
        m["games"] = pending["results"]
        t["pending"] = None
        t["updated_at"] = time.time()

        name_of = {p["id"]: p["name"] for p in t["players"]}
        loser_id = pending["p"][0] if winner_id == pending["p"][1] else pending["p"][1]
        detail = self._games_detail(pending["results"])
        self._send_group(
            t["group_id"],
            f"✅ {name_of.get(winner_id, '胜者')} 拿下本场，"
            f"{name_of.get(loser_id, '负者')} 淘汰{detail}")

        row = t["matches"][r]
        if index + 1 < len(row):
            self._begin_match(t, r, index + 1)
        elif len(row) == 1:
            self._finish_tournament(t)
        else:
            self._advance_round(t)
        self._save(t)

    def _advance_round(self, t) -> None:
        """本轮全部结束，胜者晋级组成下一轮"""
        r = t["round"]
        row = t["matches"][r]
        name_of = {p["id"]: p["name"] for p in t["players"]}
        winners = []
        for m in row:
            winners.append({"id": m["winner"], "name": name_of.get(m["winner"], "?")})

        new_row = []
        for i in range(0, len(winners), 2):
            a, b = winners[i], winners[i + 1]
            new_row.append({
                "p": [a["id"], b["id"]],
                "names": [a["name"], b["name"]],
                "winner": None,
                "games": [],
            })
        t["matches"].append(new_row)
        t["round"] = r + 1
        t["updated_at"] = time.time()

        round_name = _ROUND_NAME.get(t["size"] >> (r + 1), "对局")
        self._send_group(
            t["group_id"],
            f"🏁 进入{round_name}：" + "；".join(
                f"{m['names'][0]} vs {m['names'][1]}" for m in new_row))
        self._begin_match(t, r + 1, 0)
        self._send_bracket(t)

    def _finish_tournament(self, t) -> None:
        """决赛结束，核算名次并发放奖励"""
        t["status"] = "done"
        t["pending"] = None
        t["updated_at"] = time.time()

        final_match = t["matches"][-1][0]
        champ_id = final_match["winner"]
        name_of = {p["id"]: p["name"] for p in t["players"]}

        # 名次除数：在某一轮被淘汰者，除数 = 该轮参赛人数 = size >> round
        divisor_of = {}
        for r, row in enumerate(t["matches"]):
            for m in row:
                loser = m["p"][0] if m["winner"] == m["p"][1] else m["p"][1]
                divisor_of[loser] = t["size"] >> r

        fish = t["champion_fish"]
        stone = t["champion_stone"]
        lines = ["🏆 锦标赛结束！最终名次与奖励："]
        # 名次从高到低：冠军 → 亚军 → 四强 → 八强 → 十六强
        order = sorted(name_of.items(),
                       key=lambda kv: (0 if kv[0] == champ_id
                                       else divisor_of.get(kv[0], 2).bit_length() - 1))
        for pid, name in order:
            if pid == champ_id:
                tier = "冠军"
                rf, rs = fish, stone
            else:
                d = divisor_of.get(pid, 2)
                tier = _TIER_NAME.get(d, "淘汰")
                rf, rs = fish // d, stone // d
            got = []
            if rf > 0:
                got.append(f"{rf} 鱼干")
                if self._cat is not None:
                    self._cat.add_fish(pid, rf)
            if rs > 0:
                got.append(f"{rs} 猫眼石")
                if self._cat is not None:
                    self._cat.add_eye_stones(pid, rs)
            reward_text = "、".join(got) if got else "无"
            lines.append(f"{tier} {name}：{reward_text}")
        if fish == 0 and stone == 0:
            lines.append("（本场为无奖励锦标赛）")
        self._send_group(t["group_id"], "\n".join(lines))
        self._send_bracket(t)

    # ==================== 展示 ====================

    @staticmethod
    def _reward_desc(fish: int, stone: int) -> str:
        if fish == 0 and stone == 0:
            return "无奖励"
        parts = []
        if fish:
            parts.append(f"冠军 {fish} 鱼干")
        if stone:
            parts.append(f"冠军 {stone} 猫眼石")
        return "奖励 " + " + ".join(parts) + "（亚军减半、四强再减半……向下取整）"

    @staticmethod
    def _games_detail(results) -> str:
        """本场各局的简要结果"""
        if len(results) <= 1:
            reason = results[0].get("reason", "")
            return f"（{reason}）" if reason else ""
        parts = []
        for i, r in enumerate(results):
            w = "平局" if r["winner"] is None else "有胜负"
            parts.append(f"第{i + 1}局{w}")
        return "（" + "、".join(parts) + "）"

    def _status_text(self, t) -> str:
        name_of = {p["id"]: p["name"] for p in t["players"]}
        status = {"waiting": "报名中", "playing": "进行中", "done": "已结束"}.get(
            t["status"], t["status"])
        lines = [
            f"🏆 锦标赛（{status}）",
            f"人数 {t['size']}｜项目 {t['project_count']} 种"
            f"｜{self._reward_desc(t['champion_fish'], t['champion_stone'])}",
        ]
        if t["pool"]:
            lines.append("项目池：" + "、".join(_PROJECT_NAME[k] for k in t["pool"]))

        if t["status"] == "waiting":
            n = len(t["players"])
            lines.append(f"已报名（{n}/{t['size']}）："
                         + "、".join(p["name"] for p in t["players"]))
            if n >= t["size"]:
                lines.append("报名已满，任何人发送「锦标赛 开始」即可开始")
            else:
                lines.append("发送「锦标赛 加入」报名（已报名的可用「锦标赛 退出」取消）")
        elif t["status"] == "playing":
            for r, row in enumerate(t["matches"]):
                round_name = _ROUND_NAME.get(t["size"] >> r, "对局")
                done = all(m["winner"] is not None for m in row)
                mark = "（已完成）" if done else ""
                lines.append(f"{round_name}{mark}：" + "；".join(
                    self._pair_text(m, name_of) for m in row))
            if t["pending"]:
                key = t["pending"]["projects"][t["pending"]["game_no"]]
                lines.append(f"当前进行：{t['pending']['names'][0]} vs "
                             f"{t['pending']['names'][1]}（{_PROJECT_NAME[key]}）")
        else:
            final_match = t["matches"][-1][0] if t["matches"] else None
            if final_match and final_match["winner"] is not None:
                lines.append(f"冠军：{name_of.get(final_match['winner'], '?')}")
        return "\n".join(lines)

    @staticmethod
    def _pair_text(m, name_of) -> str:
        a, b = m["names"]
        if m["winner"] is None:
            return f"{a} vs {b}"
        loser = a if m["winner"] == m["p"][1] else b
        return f"{name_of.get(m['winner'], a)} 胜 {loser}"

    # ==================== 晋级图 ====================

    def _send_bracket(self, t) -> None:
        """把当前赛程画成晋级图发到群里"""
        try:
            path = self._render_bracket(t)
        except Exception as e:
            self._send_group(t["group_id"], f"晋级图绘制失败了喵：{e}")
            return
        self._sender.send_image(
            Target(user_id=0, group_id=t["group_id"], is_group=True), path)

    def _render_bracket(self, t) -> str:
        size = t["size"]
        rounds_n = size.bit_length() - 1            # 轮数：4人2轮、8人3轮、16人4轮
        left, col_w, col_gap = 36, 250, 72
        top, slot_h, box_h = 132, 98, 74
        row_h = box_h // 2

        # 每一轮各场次在竖直方向上的中心：由下一轮的两位选手位置取平均递归得出
        leaf = [top + i * slot_h for i in range(size)]
        centers = [[(leaf[2 * j] + leaf[2 * j + 1]) / 2 for j in range(size // 2)]]
        for r in range(1, rounds_n):
            prev = centers[r - 1]
            centers.append([(prev[2 * j] + prev[2 * j + 1]) / 2
                            for j in range(len(prev) // 2)])

        width = left * 2 + (rounds_n + 1) * col_w + rounds_n * col_gap
        height = int(top + (size - 1) * slot_h + box_h / 2 + 40)
        img = Image.new("RGB", (width, height), (252, 250, 244))
        draw = ImageDraw.Draw(img)
        draw.rectangle((6, 6, width - 7, height - 7),
                       outline=(205, 196, 180), width=3)

        _center_text(draw, (0, 14, width, 56), "锦标赛晋级图", _font(36), (60, 45, 35))
        status = {"waiting": "报名中", "playing": "进行中", "done": "已结束"}.get(
            t["status"], t["status"])
        sub = (f"{status}｜{t['size']} 人｜{t['project_count']} 种项目｜"
               f"{self._reward_desc(t['champion_fish'], t['champion_stone'])}")
        if t["pool"]:
            sub += "｜项目：" + "、".join(_PROJECT_NAME[k] for k in t["pool"])
        _center_text(draw, (0, 58, width, 92),
                     _fit_text(draw, sub, _font(20), width - 40), _font(20),
                     (130, 120, 108))

        # 各轮列名（十六强赛 / 八强赛 / 四强赛 / 决赛）
        for r in range(rounds_n):
            x = left + r * (col_w + col_gap)
            _center_text(draw, (x, 94, x + col_w, 122),
                         _ROUND_NAME.get(size >> r, "对局"), _font(22), (150, 110, 60))

        pending = t.get("pending")
        n_rounds = len(t["matches"])

        # 连接线（先画，被方框盖住一部分）
        for r in range(rounds_n - 1):
            x = left + r * (col_w + col_gap)
            for k in range(size >> (r + 1)):
                sx, sy = x + col_w, centers[r][k]
                px = left + (r + 1) * (col_w + col_gap)
                py = centers[r + 1][k // 2]
                mx = sx + col_gap // 2
                draw.line((sx, sy, mx, sy), fill=(200, 192, 178), width=2)
                draw.line((mx, sy, mx, py), fill=(200, 192, 178), width=2)
                draw.line((mx, py, px, py), fill=(200, 192, 178), width=2)

        # 各轮方框
        fnt = _font(22)
        for r in range(rounds_n):
            x = left + r * (col_w + col_gap)
            row = t["matches"][r] if r < n_rounds else None
            for j in range(size >> (r + 1)):
                cy = centers[r][j]
                y0, y1 = cy - box_h / 2, cy + box_h / 2
                m = row[j] if (row is not None and j < len(row)) else None
                is_pending = (pending is not None and pending["round"] == r
                              and pending["index"] == j)
                if is_pending:
                    outline, ow = (206, 108, 66), 3
                elif m is None:
                    outline, ow = (214, 208, 196), 2
                else:
                    outline, ow = (196, 186, 170), 2
                draw.rounded_rectangle((x, y0, x + col_w, y1), radius=10,
                                       fill=(255, 254, 250), outline=outline, width=ow)

                if m is None:
                    _center_text(draw, (x, y0, x + col_w, y1), "待定",
                                 _font(20), (190, 182, 170))
                    continue
                for k in range(2):
                    ry0, ry1 = y0 + k * row_h, y0 + (k + 1) * row_h
                    won = m["winner"] is not None and m["winner"] == m["p"][k]
                    color = (46, 132, 74) if won else (70, 60, 52)
                    _center_text(draw, (x, ry0, x + col_w, ry1),
                                 _fit_text(draw, m["names"][k], fnt, col_w - 24),
                                 fnt, color)
                    if won:
                        draw.text((x + 8, ry0 + 5), "√", font=_font(20),
                                  fill=(46, 132, 74))
                # 场次项目小字
                if is_pending:
                    projs = pending["projects"]
                    label = ("三局两胜" if len(set(projs)) >= 3
                             else _PROJECT_NAME[projs[0]])
                elif m["games"]:
                    games = m["games"]
                    label = ("三局两胜" if len({g["project"] for g in games}) > 1
                             else _PROJECT_NAME[games[0]["project"]])
                elif len(t["pool"]) == 1:
                    label = _PROJECT_NAME[t["pool"][0]]   # 单项目：未开打的场次也知道项目
                else:
                    label = ""
                if label:
                    _center_text(draw, (x, y1 + 2, x + col_w, y1 + 24),
                                 label, _font(16), (160, 150, 138))

        # 冠军列
        cx = left + rounds_n * (col_w + col_gap)
        cy = centers[rounds_n - 1][0]
        y0, y1 = cy - box_h / 2, cy + box_h / 2
        champ = None
        if (t["status"] == "done" and t["matches"]
                and t["matches"][-1][0]["winner"] is not None):
            fm = t["matches"][-1][0]
            champ = fm["names"][0] if fm["winner"] == fm["p"][0] else fm["names"][1]
        draw.rounded_rectangle((cx, y0, cx + col_w, y1), radius=10,
                               fill=(255, 252, 240), outline=(214, 168, 60), width=3)
        _center_text(draw, (cx, y0, cx + col_w, y1),
                     _fit_text(draw, champ, _font(24), col_w - 24) if champ else "冠军",
                     _font(24), (176, 122, 20) if champ else (200, 178, 130))

        os.makedirs(TOURNAMENT_DIR, exist_ok=True)
        path = os.path.join(TOURNAMENT_DIR, f"bracket_{t['group_id']}.png")
        img.save(path)
        return path

    # ==================== 存取 / 工具 ====================

    def _load(self, gid: int):
        return _load_json(_STATE_PATH).get(str(gid))

    def _save(self, t: dict) -> None:
        state = _load_json(_STATE_PATH)
        state[str(t["group_id"])] = t
        _save_json(_STATE_PATH, state)

    def _remove(self, gid: int) -> None:
        state = _load_json(_STATE_PATH)
        if str(gid) in state:
            del state[str(gid)]
            _save_json(_STATE_PATH, state)

    def is_active(self, gid: int) -> bool:
        """本群是否有报名中/进行中的锦标赛（供对战插件拦截手动开新局）"""
        t = self._load(gid)
        if not t or t.get("status") not in ("waiting", "playing"):
            return False
        if time.time() - t.get("updated_at", 0) > IDLE_SECONDS:
            self._remove(gid)   # 闲置过久自动作废，避免一直卡着不能开新局
            return False
        return True

    def _drop_stale(self, ctx: CommandContext) -> None:
        """锦标赛闲置过久则作废，避免卡住后续创建"""
        t = self._load(ctx.group_id)
        if t is None:
            return
        if time.time() - t.get("updated_at", 0) <= IDLE_SECONDS:
            return
        self._remove(ctx.group_id)
        self._sender.reply(ctx, f"上一场锦标赛闲置超过 {IDLE_SECONDS // 3600} 小时，已自动作废喵")

    def _debt_of(self, user_id: int) -> int:
        """玩家的猫眼石欠债数量（余额为负时为其绝对值）"""
        if self._cat is None:
            return 0
        balance = self._cat.get_eye_stones(user_id)
        return -balance if balance < 0 else 0

    def _send_group(self, gid: int, text: str) -> None:
        self._sender.send_text(Target(user_id=0, group_id=gid, is_group=True), text)

    # ==================== 帮助 ====================

    @staticmethod
    def _help_text() -> str:
        return (
            "锦标赛玩法（在群里用对战游戏进行淘汰赛）\n"
            "指令：锦标赛（也可用 tournament / .tournament / /tournament）\n"
            "【创建】\n"
            "· 「锦标赛 创建 <人数> <项目…> [冠军鱼干] [冠军猫眼石]」\n"
            "   人数：4 / 8 / 16；项目：写一个或多个，从现有游戏里选"
            "（快艇骰子 / 17步麻将 / Farkle）\n"
            "   示例：「锦标赛 创建 8 快艇骰子 farkle 1000 10」\n"
            "· 奖励按名次阶梯「对半砍」向下取整：亚军 = 冠军/2、四强 = 冠军/4、"
            "八强 = 冠军/8、十六强 = 冠军/16\n"
            "· 只有管理员可以开出带鱼干 / 猫眼石奖励的锦标赛；其他玩家请把奖励填 0\n"
            "【报名与开始】\n"
            "· 创建者不自动参赛，想参赛需自己「锦标赛 加入」\n"
            "· 「锦标赛 加入」报名，报满设定人数后任何人「锦标赛 开始」即可开始赛程\n"
            "· 报名期间可用「锦标赛 退出」取消自己的报名；开始后不能再退出\n"
            "· 报名期间创建者可「锦标赛 取消」解散；开始后必须打完整场\n"
            "· 带猫眼石奖励时，欠债（猫眼石为负）的玩家不能报名\n"
            "【赛制】\n"
            "· 开局随机分组两两对局、负者淘汰；每场的「谁先开局」也随机\n"
            "· 只选 1 个项目：全程固定该项目。非决赛单场定胜负，"
            "平局（如17步麻将流局、或荣和得分不足满贯）加赛一次，仍平局则随机晋级；"
            "决赛三局两胜\n"
            "· 选了多个项目：每一场从这些项目里随机抽取；决赛尽量抽不同项目"
            "（够三个就三个不同，只有两个就都用上）打三局两胜\n"
            "【进行方式】\n"
            "· 每场开始时机器人公告对阵与项目，并直接为两位选手自动开局"
            "（不开放手动加入，杜绝外人乱入）\n"
            "· 锦标赛期间本群禁止手动开这三种游戏的普通对局，避免与赛程冲突\n"
            "· 项目为 Farkle 时，本场目标分数随机从 2000 / 4000 中抽取\n"
            "· 若某场开局失败（本群还有未结束的同款对局）：打完或取消那局后，"
            "任何人发「锦标赛 继续」即可为该场重新开局\n"
            "（17步麻将需双方到私聊选牌出牌；对局奖励由锦标赛单独结算，故对局本身按普通局进行）\n"
            "· 「锦标赛」/「锦标赛 状态」可随时查看晋级图与赛程\n"
            "· 锦标赛闲置超过 6 小时自动作废"
        )
