"""Farkle 网页版游戏引擎。

房间只存在于网页进程的内存里（不落盘），两人一局：大厅建房 -> 加入 -> 先手拍卖 ->
轮流掷骰/锁定/入账，先到目标分者胜。猫眼石局在对局结束时按余额结算。

规则（骰子、骰组、计分、爆骰判定）全部复用 plugins/farkle.py，避免网页端与
机器人规则漂移；猫眼石结算复用 plugins/cat_expedition.py 的存档接口。
"""

import random
import threading
import time

from plugins.farkle import (
    DICE_NORMAL, DICE_GAMBLER, DICE_KAIJI, DICE_NUM, PLAYER_NUM, DEFAULT_TARGET,
    MIN_TARGET, MAX_TARGET, MAX_STONES, MAX_BOT_STONES, BID_STEP, BID_LIMIT,
    IDLE_SECONDS, DICE_D20_BONUS,
    BOT_ID, BOT_NAME, BOT_DUMB_ID, BOT_DUMB_NAME, BOT_DUMB_MISTAKE_P,
    _bot_best_lock, _bot_should_bank, _bot_fair_bid,
    _bot_mistake, _dumb_lock, _dumb_bank, _dumb_bid,
    _bot_week_rows, _dumb_week_ensure, _dumb_week_record,
    BOT_WEEKLY_MIN_GAMES, BOT_WEEKLY_REWARDS,
    _bot_stats_rows, _record_bot_stats, _load_bot_stats,
    _roll_dice_hand, _is_wild, _new_die, _faces_text, _dice_set_desc,
    _random_dice_set, _score_dice, _DIE_NAMES, _DIE_COLORS,
    DICE_LOADOUTS,
)

_FINISHED_KEEP_SECONDS = 120   # 已结束的房间保留一会儿，供客户端看到结算结果

_ROOMS = {}
_ROOMS_LOCK = threading.RLock()

_cat_plugin = None
_cat_lock = threading.Lock()


def _cat():
    """惰性创建猫眼石插件实例（只用存档读写，不依赖 sender）"""
    global _cat_plugin
    if _cat_plugin is None:
        with _cat_lock:
            if _cat_plugin is None:
                from plugins.cat_expedition import CatExpeditionPlugin
                _cat_plugin = CatExpeditionPlugin(None)
    return _cat_plugin


def _debt_of(qq: int) -> int:
    """猫眼石欠债（余额为负时为其绝对值）"""
    try:
        balance = _cat().get_eye_stones(qq)
    except Exception:
        return 0
    return -balance if balance < 0 else 0


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb)


def _die_view(die: dict) -> dict:
    kind = die.get("kind", DICE_NORMAL)
    colors = _DIE_COLORS.get(kind, _DIE_COLORS[DICE_NORMAL])
    return {
        "value": die.get("value", 0),
        "raw": die.get("raw", 0),
        "kind": kind,
        "name": _DIE_NAMES.get(kind, "普通"),
        "wild": _is_wild(die),
        "fill": _hex(colors["fill"]),
        "outline": _hex(colors["outline"]),
    }


class Room:
    """一局 Farkle 的完整状态。所有公开方法返回错误文案（None 表示成功）。"""

    def __init__(self, code: str, host_qq: int, host_name: str, target: int, stones: int,
                 bot: bool = False, bot_dumb: bool = False):
        self.code = code
        self.target = target
        self.stones = stones
        self.bot = bot              # 人机局：第二位玩家是机器人，只结算玩家一侧猫眼石
        self.bot_dumb = bool(bot_dumb)   # 笨笨机器人：每一步有 5% 概率不走最优
        self.bot_id = BOT_DUMB_ID if self.bot_dumb else BOT_ID
        self.bot_name = BOT_DUMB_NAME if self.bot_dumb else BOT_NAME
        self.phase = "waiting"        # waiting / auction / keep / decide / finished
        self.players = [self._new_player(host_qq, host_name)]
        self.seat_dice = []
        self.turn = 0
        self.hand = []
        self.locked = []
        self.turn_score = 0
        self.auction = None
        self.winner = None
        self.settle_lines = []
        self.log = []
        self.chat = []
        self.created_at = time.time()
        self.updated_at = time.time()

    # ==================== 小工具 ====================

    @staticmethod
    def _new_player(qq: int, name: str) -> dict:
        return {"qq": qq, "name": name, "total": 0, "dice": [DICE_NORMAL] * DICE_NUM}

    def _touch(self) -> None:
        self.updated_at = time.time()

    def _log(self, text: str) -> None:
        self.log.append(text)
        if len(self.log) > 80:
            self.log = self.log[-80:]

    def _idx(self, qq: int) -> int:
        for i, p in enumerate(self.players):
            if p["qq"] == qq:
                return i
        return -1

    def _guard_turn(self, qq: int):
        """非当前行动玩家返回 (错误文案, None)，否则返回 (None, 当前玩家)"""
        if self.phase == "finished":
            return "本局已经结束了喵", None
        if self.phase == "auction":
            return "先手拍卖还没结束喵", None
        cur = self.players[self.turn]
        if qq != cur["qq"]:
            return f"当前该 {cur['name']} 行动喵", None
        return None, cur

    # ==================== 开局 / 加入 ====================

    def join(self, qq: int, name: str):
        if self.phase != "waiting":
            return "这局已经开始或结束了喵"
        if self._idx(qq) >= 0:
            return "你已经在房间里了喵"
        self.players.append(self._new_player(qq, name))
        self.seat_dice = [_random_dice_set(), _random_dice_set()]
        self.phase = "auction"
        self.auction = {"bid": None, "holder": None, "turn": 1}
        self._log(f"{name} 加入了房间，两人到齐")
        self._log(self.seat_text())
        self._log(f"先手拍卖：由后加入的 {self.players[1]['name']} 先出价")
        self._touch()
        return None

    def seat_text(self) -> str:
        seat = self.seat_dice or [[DICE_NORMAL] * DICE_NUM] * 2
        return ("骰组分配（竞价决定归属）：先手位 " + _dice_set_desc(seat[0])
                + "；后手位 " + _dice_set_desc(seat[1]))

    # ==================== 先手拍卖 ====================

    def bid(self, qq: int, val):
        if self.phase != "auction":
            return "现在不是先手拍卖阶段喵"
        au = self.auction
        cur = self.players[au["turn"]]
        if qq != cur["qq"]:
            return f"现在轮到 {cur['name']} 出价喵"
        try:
            val = int(val)
        except (TypeError, ValueError):
            # 省略分数 = 默认加价到「对方出价 + 50」
            if au["bid"] is None:
                return f"首个出价要填分数喵，且必须是 {BID_STEP} 的倍数"
            val = au["bid"] + BID_STEP
        if val % BID_STEP != 0:
            return f"出价必须是 {BID_STEP} 的倍数喵"
        if not (-BID_LIMIT <= val <= BID_LIMIT):
            return f"出价要在 ±{BID_LIMIT} 之内喵"
        if au["bid"] is not None and val <= au["bid"]:
            return f"加价要高于当前出价 {au['bid']} 分喵"
        au["bid"] = val
        au["holder"] = au["turn"]
        au["turn"] = (au["turn"] + 1) % PLAYER_NUM
        self._log(f"{cur['name']} 出价 {val} 分（先手以 {-val:+d} 分开局）")
        self._touch()
        return None

    def accept(self, qq: int):
        if self.phase != "auction":
            return "现在不是先手拍卖阶段喵"
        au = self.auction
        if au["bid"] is None:
            return "还没有人出价，没有可接受的价格喵"
        cur = self.players[au["turn"]]
        if qq != cur["qq"]:
            return f"现在轮到 {cur['name']} 应对喵"
        holder = self.players[au["holder"]]
        bid = au["bid"]
        holder["total"] = -bid
        seat = self.seat_dice or [[DICE_NORMAL] * DICE_NUM] * 2
        holder["dice"] = list(seat[0])
        self.players[1 - au["holder"]]["dice"] = list(seat[1])
        self.auction = None
        self.turn = au["holder"]
        self._log(f"{cur['name']} 接受：{holder['name']} 以 {-bid:+d} 分开局并获得先手，"
                  f"{cur['name']} 以 0 分开局")
        self._start_turn()
        return None

    # ==================== 机器人自动行动 ====================

    def start_as_bot(self) -> None:
        """把机器人作为第二位玩家加入并直接进入先手拍卖（机器人先出价）"""
        self.players.append(self._new_player(self.bot_id, self.bot_name))
        self.seat_dice = [_random_dice_set(), _random_dice_set()]
        self.phase = "auction"
        self.auction = {"bid": None, "holder": None, "turn": 1}
        style = (f"（每一步有 {BOT_DUMB_MISTAKE_P * 100:g}% 概率不走最优）"
                 if self.bot_dumb else "")
        self._log(f"{self.players[0]['name']} 向 {self.bot_name}{style} 发起挑战")
        self._log(self.seat_text())
        self._touch()
        self._run_bot()

    def _run_bot(self) -> None:
        """当前该机器人行动时让它自动走完：拍卖出价/接受，或整轮掷骰、锁定与入账。

        人机局的所有交互都由玩家触发，机器人不会同时留在多个回合里，
        所以这里循环到「轮到玩家」或「本局结束」为止即可。
        """
        if not self.bot or self.phase == "finished":
            return
        bot_id = self.bot_id
        for _ in range(400):        # 防死循环兜底
            if self.phase == "finished":
                return
            if self.phase == "auction":
                au = self.auction
                if au is None or self.players[au["turn"]]["qq"] != bot_id:
                    return
                if self.bot_dumb and _bot_mistake():
                    value = _dumb_bid(self.target, au["bid"])
                    if value is not None:
                        self.bid(bot_id, value)
                        continue
                fair = _bot_fair_bid(self.seat_dice, self.target)
                if au["bid"] is not None and au["bid"] >= fair:
                    self.accept(bot_id)             # 对手已出到公允价，让先手给对方
                else:
                    # 未到公允价时只加一个最小加价档，避免直接跳到心理价位多付
                    val = fair if au["bid"] is None else min(fair, au["bid"] + BID_STEP)
                    self.bid(bot_id, val)           # 加价抢下先手位
                continue
            if self.players[self.turn]["qq"] != bot_id:
                return
            if self.phase == "keep":
                p = self.players[self.turn]
                opp = self.players[1 - self.turn]
                pick = _bot_best_lock(self.hand, self.turn_score, p["total"], self.target,
                                      p["dice"], opp["dice"], opp["total"])
                if pick is not None and self.bot_dumb and _bot_mistake():
                    pick = _dumb_lock(self.hand, pick)
                if pick is None:    # 兜底：无任何可计分组合时按爆骰处理
                    self._log(f"{p['name']} 掷出 {_faces_text(self.hand)}，无法计分——爆骰！"
                              "本回合没有得分")
                    self.turn = (self.turn + 1) % PLAYER_NUM
                    self._start_turn()
                    continue
                gained, idx = pick
                if self.lock(bot_id, idx):
                    return          # 理论不会发生；出错就交回玩家，避免卡死
                continue
            if self.phase == "decide":
                p = self.players[self.turn]
                opp = self.players[1 - self.turn]
                bank = _bot_should_bank(p["total"], self.target, p["dice"], opp["dice"],
                                        opp["total"], self.hand, self.turn_score)
                if self.bot_dumb and _bot_mistake():
                    bank = _dumb_bank(bank, p["total"] + self.turn_score >= self.target,
                                      self.hand)
                if bank:
                    self.bank(bot_id)
                else:
                    self.roll(bot_id)
                # 入账/爆骰后可能又轮回到机器人（玩家首掷即爆骰），所以继续判定
                continue
            return

    # ==================== 回合流转 ====================

    def _start_turn(self) -> None:
        """切换后的新回合：重置状态并自动进行首掷（首掷爆骰则直接换手）"""
        while True:
            p = self.players[self.turn]
            self.locked = []
            self.turn_score = 0
            self.hand = [_new_die(k) for k in p["dice"]]
            self._log(f"—— 轮到 {p['name']} ——")
            bust, jackpot = _roll_dice_hand(self.hand)
            faces = _faces_text(self.hand)
            if jackpot:
                self._apply_jackpot(p, faces)
                break
            if bust:
                self._log(f"{p['name']} 掷出 {faces}，爆骰！本回合没有得分")
                self.turn = (self.turn + 1) % PLAYER_NUM
                continue
            self.phase = "keep"
            self._log(f"{p['name']} 掷出 {faces}，请锁定至少一颗计分骰")
            break
        self._touch()

    def _apply_jackpot(self, p: dict, faces: str) -> None:
        """20 面大成功：加奖励分并拿回整副骰子"""
        self.turn_score += DICE_D20_BONUS
        self.locked = []
        self.hand = [_new_die(k) for k in p["dice"]]
        self.phase = "decide"
        self._log(f"{p['name']} 掷出 {faces}，20面大成功！+{DICE_D20_BONUS} 分"
                  "并拿回全部骰子，可继续掷或入账")
        self._touch()

    def _roll_hand(self) -> tuple:
        """掷当前手牌，返回 (是否爆骰, 是否 20 面大成功)"""
        return _roll_dice_hand(self.hand)

    def roll(self, qq: int):
        """继续掷（当前手牌）"""
        err, p = self._guard_turn(qq)
        if err:
            return err
        if self.phase != "decide":
            return "现在要先锁定至少一颗计分骰喵"
        bust, jackpot = self._roll_hand()
        faces = _faces_text(self.hand)
        if jackpot:
            self._apply_jackpot(p, faces)
            return None
        if bust:
            lost = self.turn_score
            self._log(f"{p['name']} 掷出 {faces}，爆骰！"
                      + (f"本回合 {lost} 分全部作废" if lost else "本回合没有得分"))
            self.turn = (self.turn + 1) % PLAYER_NUM
            self._start_turn()
            return None
        self.phase = "keep"
        self._log(f"{p['name']} 掷出 {faces}，请锁定计分骰")
        self._touch()
        return None

    def lock(self, qq: int, indices):
        """锁定选中下标对应的骰子"""
        err, p = self._guard_turn(qq)
        if err:
            return err
        if self.phase != "keep":
            return "现在没有刚掷出的骰子可以锁定喵"
        try:
            idxs = sorted({int(i) for i in indices})
        except (TypeError, ValueError):
            return "选择的骰子不对喵"
        if not idxs or idxs[0] < 0 or idxs[-1] >= len(self.hand):
            return "选择的骰子不对喵"

        picked = [self.hand[i] for i in idxs]
        # 开司骰每次掷出都必须计分：未选中时自动补选；
        # 若已选了普通 1，则让它让位，保持锁定点数不变
        forced = [i for i in range(len(self.hand))
                  if self.hand[i].get("kind") == DICE_KAIJI and i not in set(idxs)]
        if forced:
            swap = next((i for i in idxs
                         if self.hand[i].get("kind") != DICE_KAIJI
                         and self.hand[i].get("value") == 1), None)
            if swap is not None:
                idxs = [i for i in idxs if i != swap]
            idxs = sorted(list(idxs) + forced)
            picked = [self.hand[i] for i in idxs]
        score = _score_dice(picked)
        if score is None:
            return "这组骰子无法计分喵：散落的 2/3/4/6 要凑成三张及以上才能算"

        keep_set = set(idxs)
        remaining = [d for i, d in enumerate(self.hand) if i not in keep_set]
        self.locked.extend(picked)
        self.turn_score += score
        hot = not remaining
        if hot:
            # 热骰：全部骰子计分用完，拿回全部骰子继续
            self.locked = []
            self.hand = [_new_die(k) for k in p["dice"]]
        else:
            self.hand = remaining
        self.phase = "decide"
        self._log(f"{p['name']} 锁定 {_faces_text(picked)}，+{score} 分，"
                  f"本回合累计 {self.turn_score} 分"
                  + ("；热骰！拿回全部骰子，可继续掷或入账" if hot else ""))
        self._touch()
        return None

    def bank(self, qq: int):
        err, p = self._guard_turn(qq)
        if err:
            return err
        if self.phase != "decide":
            return "要先锁定至少一颗计分骰才能入账喵"
        if any(d.get("kind") == DICE_GAMBLER for d in self.hand):
            return "赌怪骰还留在桌上，本回合不能入账喵；必须先把它一起锁定"
        gained = self.turn_score
        p["total"] += gained
        self._log(f"{p['name']} 入账 +{gained} 分，总分 {p['total']} 分")
        if p["total"] >= self.target:
            self._finish(p, "达成目标分")
            return None
        self.turn = (self.turn + 1) % PLAYER_NUM
        self._start_turn()
        return None

    def surrender(self, qq: int):
        if self.phase in ("waiting", "finished"):
            return "现在不能投降喵"
        me = self.players[self._idx(qq)] if self._idx(qq) >= 0 else None
        if me is None:
            return "你不是本局玩家喵"
        other = next(p for p in self.players if p["qq"] != qq)
        self._finish(other, "投降", headline=f"{me['name']} 投降")
        return None

    # ==================== 结算 ====================

    def _finish(self, winner: dict, reason: str, headline: str = None) -> None:
        self.phase = "finished"
        self.winner = winner["qq"]
        self.hand = []
        self.locked = []
        self.auction = None
        self._log(headline or f"{winner['name']} 获胜（{reason}）")
        for p in self.players:
            self._log(f"{p['name']}：{p['total']} 分")
        self.settle_lines, moved = self._settle(winner)
        for line in self.settle_lines:
            self._log(line)
        if self.bot:
            _record_bot_result(self, winner, moved)
        self._touch()

    def _settle(self, winner: dict):
        """返回 (说明行, 玩家实际结算的猫眼石（正=赢）)"""
        if self.stones <= 0:
            return [], 0
        try:
            cat = _cat()
            if self.bot:
                # 机器人没有猫眼石账户，只结算玩家一侧，机器人盈亏记在战绩里
                human = next(p for p in self.players if p["qq"] != self.bot_id)
                delta = self.stones if human["qq"] == winner["qq"] else -self.stones
                before = cat.get_eye_stones(human["qq"])
                after = cat.add_eye_stones(human["qq"], delta)
                payer, payee = ((self.bot_name, human["name"]) if delta > 0
                                else (human["name"], self.bot_name))
                lines = [f"{payer} 支付 {self.stones} 猫眼石给 {payee}"
                         f"（{human['name']} {before}→{after}）"]
                if after < 0:
                    lines.append(f"{human['name']} 猫眼石不足，现有欠债 {-after} 个")
                return lines, delta
            loser = next(p for p in self.players if p["qq"] != winner["qq"])
            before_w = cat.get_eye_stones(winner["qq"])
            before_l = cat.get_eye_stones(loser["qq"])
            after_w = cat.add_eye_stones(winner["qq"], self.stones)
            after_l = cat.add_eye_stones(loser["qq"], -self.stones)
        except Exception as e:
            return [f"（猫眼石结算失败：{e}）"], 0
        lines = [f"{loser['name']} 支付 {self.stones} 猫眼石给 {winner['name']}"
                 f"（{winner['name']} {before_w}→{after_w}，{loser['name']} {before_l}→{after_l}）"]
        if after_l < 0:
            lines.append(f"{loser['name']} 猫眼石不足，现有欠债 {-after_l} 个")
        return lines, self.stones

    # ==================== 房间发言 ====================

    def say(self, qq: int, text, name: str = ""):
        """房间内发言（对局双方与观众都能说话），返回错误文案（None 表示成功）"""
        body = str(text or "").strip()
        if not body:
            return "说点什么喵"
        idx = self._idx(qq)
        speaker = self.players[idx]["name"] if idx >= 0 else (name or f"观众{qq}")
        self.chat.append({"name": speaker, "text": body[:80], "time": int(time.time())})
        if len(self.chat) > 40:
            self.chat = self.chat[-40:]
        self._touch()
        return None

    # ==================== 视图 ====================

    def view(self, qq: int) -> dict:
        mine = self._idx(qq)
        return {
            "code": self.code,
            "phase": self.phase,
            "target": self.target,
            "stones": self.stones,
            "bot": self.bot,
            "bot_dumb": self.bot_dumb,
            "bot_name": self.bot_name if self.bot else "",
            "turn": self.turn,
            "my_index": mine,
            "is_player": mine >= 0,
            "is_turn": mine >= 0 and mine == self.turn,
            "players": [
                {"qq": p["qq"], "name": p["name"], "total": p["total"],
                 "dice_desc": _dice_set_desc(p["dice"])}
                for p in self.players
            ],
            "seat": [_dice_set_desc(s) for s in self.seat_dice],
            "auction": self.auction,
            "hand": [_die_view(d) for d in self.hand],
            "locked": [_die_view(d) for d in self.locked],
            "turn_score": self.turn_score,
            "can_bank": (self.phase == "decide"
                         and not any(d.get("kind") == DICE_GAMBLER for d in self.hand)),
            "winner": self.winner,
            "settle_lines": self.settle_lines,
            "log": self.log[-30:],
            "chat": self.chat[-30:],
        }


# ==================== 房间管理 ====================

def _add_fish(qq: int, amount: int) -> None:
    """发放鱼干奖励（猫猫系统不可用时静默跳过）"""
    try:
        _cat().add_fish(qq, amount)
    except Exception:
        pass


def _record_bot_result(room: Room, winner: dict, stones: int = 0) -> None:
    """人机局结束时记录战绩：喵喵机器人记总战绩，笨笨机器人只记本周周榜"""
    human = next((p for p in room.players if p["qq"] != room.bot_id), None)
    if human is None:
        return
    won = human["qq"] == winner["qq"]
    if room.bot_dumb:
        _dumb_week_record(human["qq"], human["name"], won, _add_fish)
    else:
        _record_bot_stats(human["qq"], human["name"], won, stones)


def _new_code() -> str:
    while True:
        code = str(random.randint(1000, 9999))
        if code not in _ROOMS:
            return code


def _reap_locked() -> None:
    """清理闲置超时与已结束一段时间的房间（调用方需持有锁）"""
    now = time.time()
    for code in list(_ROOMS.keys()):
        room = _ROOMS[code]
        idle = now - room.updated_at
        if room.phase == "finished" and idle > _FINISHED_KEEP_SECONDS:
            _ROOMS.pop(code, None)
        elif idle > IDLE_SECONDS:
            _ROOMS.pop(code, None)


def _in_other_room_locked(qq: int, exclude: str = None):
    for code, room in _ROOMS.items():
        if code == exclude:
            continue
        if room.phase != "finished" and room._idx(qq) >= 0:
            return code
    return None


# ==================== 对外接口（供 server.py 调用）====================

def list_rooms() -> list:
    """大厅房间列表：等待中的可加入，进行中的可观战（已结束的不列出）"""
    with _ROOMS_LOCK:
        _reap_locked()
        rooms = []
        for r in _ROOMS.values():
            if r.phase == "finished":
                continue
            rooms.append({
                "code": r.code,
                "host": r.players[0]["name"],
                "target": r.target,
                "stones": r.stones,
                "bot": r.bot,
                "bot_name": r.bot_name if r.bot else "",
                "bot_dumb": r.bot_dumb,
                "phase": r.phase,
                "players": [p["name"] for p in r.players],
            })
        return rooms


def my_room(qq: int):
    with _ROOMS_LOCK:
        _reap_locked()
        return _in_other_room_locked(qq)


def create_room(qq: int, name: str, target, stones):
    """创建房间，返回 (code, 错误文案)"""
    with _ROOMS_LOCK:
        _reap_locked()
        exist = _in_other_room_locked(qq)
        if exist:
            return None, f"你已经在一个房间（{exist}）里了喵"
        try:
            target = int(target) if target not in (None, "") else DEFAULT_TARGET
        except (TypeError, ValueError):
            return None, "目标分要是数字喵"
        if not (MIN_TARGET <= target <= MAX_TARGET):
            return None, f"目标分要在 {MIN_TARGET}~{MAX_TARGET} 之间喵"
        try:
            stones = int(stones) if stones not in (None, "") else 0
        except (TypeError, ValueError):
            return None, "猫眼石数目要是数字喵"
        if not (0 <= stones <= MAX_STONES):
            return None, f"猫眼石数目要在 0~{MAX_STONES} 之间喵"
        if stones > 0:
            debt = _debt_of(qq)
            if debt > 0:
                return None, f"你有 {debt} 个猫眼石欠债，不能开猫眼石局喵"
        code = _new_code()
        _ROOMS[code] = Room(code, qq, name, target, stones)
        return code, None


def create_bot_room(qq: int, name: str, target, stones, dumb: bool = False):
    """人机局：直接建房并把机器人拉进来，返回 (code, 错误文案)。可下注猫眼石。
    dumb=True 时对手是笨笨机器人（每一步有 5% 概率不走最优），固定 4000 分且不能下猫眼石。"""
    with _ROOMS_LOCK:
        _reap_locked()
        exist = _in_other_room_locked(qq)
        if exist:
            return None, f"你已经在一个房间（{exist}）里了喵"
        if dumb:
            target, stones = DEFAULT_TARGET, 0
        try:
            target = int(target) if target not in (None, "") else DEFAULT_TARGET
        except (TypeError, ValueError):
            return None, "目标分要是数字喵"
        if not (MIN_TARGET <= target <= MAX_TARGET):
            return None, f"目标分要在 {MIN_TARGET}~{MAX_TARGET} 之间喵"
        try:
            stones = int(stones) if stones not in (None, "") else 0
        except (TypeError, ValueError):
            return None, "猫眼石数目要是数字喵"
        if not (0 <= stones <= MAX_BOT_STONES):
            return None, f"人机局的猫眼石要在 0~{MAX_BOT_STONES} 之间喵"
        if stones > 0:
            debt = _debt_of(qq)
            if debt > 0:
                return None, f"你有 {debt} 个猫眼石欠债，不能开猫眼石局喵"
        code = _new_code()
        room = Room(code, qq, name, target, stones, bot=True, bot_dumb=dumb)
        _ROOMS[code] = room
        room.start_as_bot()
        return code, None


def rematch(code: str, qq: int):
    """已结束的对局按原配置与玩家重开一局，返回 (新房号, 错误文案)"""
    with _ROOMS_LOCK:
        _reap_locked()
        room = _ROOMS.get(code)
        if room is None or room.phase != "finished":
            return None, "只有已结束的对局才能再来一局喵"
        if room._idx(qq) < 0:
            return None, "你不是本局玩家喵"
        exist = _in_other_room_locked(qq)
        if exist:
            return exist, None
        if room.stones > 0:
            for p in room.players:
                if p["qq"] == room.bot_id:
                    continue
                debt = _debt_of(p["qq"])
                if debt > 0:
                    return None, f"{p['name']} 有 {debt} 个猫眼石欠债，不能开猫眼石局喵"
        if room.bot:
            human = next((p for p in room.players if p["qq"] != room.bot_id), None)
            if human is None:
                return None, "本局没有可再来一局的玩家喵"
            return create_bot_room(human["qq"], human["name"], room.target, room.stones,
                                   dumb=room.bot_dumb)
        order = sorted(room.players, key=lambda p: 0 if p["qq"] == qq else 1)
        new_code = _new_code()
        new_room = Room(new_code, order[0]["qq"], order[0]["name"],
                        room.target, room.stones)
        _ROOMS[new_code] = new_room
        for p in order[1:]:
            new_room.join(p["qq"], p["name"])
        return new_code, None


def bot_rank(qq: int) -> dict:
    """人机排行：胜率 + 猫眼石净收益（含机器人自己，与 QQ 端共用 bot_stats.json）"""
    rows = _bot_stats_rows()
    mine = _load_bot_stats().get(str(qq))
    my_row = None
    if mine is not None:
        wins = int(mine.get("wins", 0))
        losses = int(mine.get("losses", 0))
        games = wins + losses
        my_row = {"wins": wins, "losses": losses, "games": games,
                  "rate": (wins / games) if games else 0.0,
                  "net": int(mine.get("net", 0))}
    return {"name": BOT_NAME, "rows": rows, "mine": my_row}


def dumb_week(qq: int) -> dict:
    """笨笨机器人周榜：本周满 10 局的玩家按胜率排名（与 QQ 端共用 bot_weekly.json）"""
    weekly = _dumb_week_ensure(_add_fish)
    rows = _bot_week_rows(weekly)
    rec = (weekly.get("players") or {}).get(str(qq))
    mine = None
    if isinstance(rec, dict):
        wins = int(rec.get("wins", 0))
        losses = int(rec.get("losses", 0))
        games = wins + losses
        mine = {"wins": wins, "losses": losses, "games": games,
                "rate": (wins / games) if games else 0.0,
                "left": max(0, BOT_WEEKLY_MIN_GAMES - games)}
    return {
        "name": BOT_DUMB_NAME,
        "week": weekly.get("week", ""),
        "min_games": BOT_WEEKLY_MIN_GAMES,
        "mistake_p": BOT_DUMB_MISTAKE_P,
        "rows": [{"name": r["name"], "wins": r["wins"], "losses": r["losses"],
                  "games": r["games"], "rate": r["rate"],
                  "reward": (BOT_WEEKLY_REWARDS[i]
                             if i < len(BOT_WEEKLY_REWARDS) else 0)}
                 for i, r in enumerate(rows[:len(BOT_WEEKLY_REWARDS)])],
        "mine": mine,
        "rewards": BOT_WEEKLY_REWARDS,
    }


def loadouts_info() -> list:
    """所有可用骰组的构成与效果说明（网页大厅展示用）"""
    return [{"key": key, "desc": _dice_set_desc(kinds)}
            for key, kinds in DICE_LOADOUTS.items()]


def join_room(code: str, qq: int, name: str):
    with _ROOMS_LOCK:
        _reap_locked()
        room = _ROOMS.get(code)
        if room is None:
            return "房间不存在或已结束喵"
        if room._idx(qq) >= 0:
            return None    # 已在房里，直接进入
        if room.phase != "waiting":
            return "这局已经开始喵"
        exist = _in_other_room_locked(qq, exclude=code)
        if exist:
            return f"你已经在另一个房间（{exist}）里了喵"
        if room.stones > 0 and _debt_of(qq) > 0:
            return "你有猫眼石欠债，不能加入猫眼石局喵"
        return room.join(qq, name)


def cancel_room(code: str, qq: int):
    with _ROOMS_LOCK:
        room = _ROOMS.get(code)
        if room is None:
            return "房间不存在喵"
        if room.phase != "waiting":
            return "对局已经开始，不能解散喵"
        if room.players[0]["qq"] != qq:
            return "只有房主能解散房间喵"
        _ROOMS.pop(code, None)
        return None


def snapshot(code: str, qq: int):
    with _ROOMS_LOCK:
        room = _ROOMS.get(code)
        if room is None:
            return None
        return room.view(qq)


def say(code: str, qq: int, text, name: str = ""):
    """房间发言，返回 (错误文案, 房间视图)"""
    with _ROOMS_LOCK:
        room = _ROOMS.get(code)
        if room is None:
            return "房间不存在或已结束喵", None
        err = room.say(qq, text, name)
        return err, room.view(qq)


def act(code: str, qq: int, action: str, payload: dict):
    """执行一步操作，返回 (错误文案, 房间视图)"""
    with _ROOMS_LOCK:
        room = _ROOMS.get(code)
        if room is None:
            return "房间不存在或已结束喵", None
        if action == "bid":
            err = room.bid(qq, (payload or {}).get("value"))
        elif action == "accept":
            err = room.accept(qq)
        elif action == "roll":
            err = room.roll(qq)
        elif action == "lock":
            err = room.lock(qq, (payload or {}).get("indices") or [])
        elif action == "bank":
            err = room.bank(qq)
        elif action == "surrender":
            err = room.surrender(qq)
        else:
            err = "未知操作喵"
        if err is None:
            room._run_bot()     # 玩家操作后若轮到机器人，让它自动走完
        return err, room.view(qq)
