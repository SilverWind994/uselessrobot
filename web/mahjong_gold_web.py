"""麻酱宝藏（mahjong_gold）网页版游戏引擎。

规则移植自 archive/mybot/mahjong_gold.py（印加宝藏的麻将版）：2~5 人，共 5 轮。
每轮牌堆由 15 张点棒牌、若干陷阱牌和 1 张役满牌组成；玩家在每次翻牌前选择继续或下车。
下车可以带走自己本轮累积的点棒；只有一人下车时还能一并带走池中余数与役满池。
同一张陷阱牌第二次出现时本轮立即结束，在场玩家丢失本轮累积的点棒，该陷阱牌下轮少一张。
五轮结束后按总点棒数排名。

与其它网页小游戏一致：房间只存在于进程内存，不落盘；支持观战与房间发言。
"""

import random
import threading
import time
from math import comb

BASIC_CARDS = [1, 2, 3, 4, 5, 5, 7, 7, 9, 11, 11, 13, 14, 15, 17]
MISTAKE_CARDS = [100, 101, 102, 103, 104]
MISTAKE_NAMES = ["舞蹈", "诈立", "错吃", "诈和", "夏哒！"]
MISTAKE_COPIES = 3
YAKUMAN_CARDS = [200, 201, 202, 203, 204]
YAKUMAN_NAMES = ["国士无双", "九莲宝灯", "清老头", "地和", "天和"]
YAKUMAN_SCORES = [5, 7, 8, 10, 12]

ROUNDS = 5
MIN_PLAYERS = 2
MAX_PLAYERS = 5
IDLE_SECONDS = 6 * 3600

# 机器人：名字不同、风险偏好略有差异，避免多个机器人动作完全同步
BOT_NAMES = ["喵机·谨慎", "喵机·稳健", "喵机·激进", "喵机·莽撞"]
BOT_JITTER = [0.20, 0.05, -0.10, -0.22]   # 无差异区间的个体偏向
OPP_LEAVE_P = 0.35                        # 模拟中对其他玩家下车概率的估计
MC_TRIALS = 200                           # 每个决策点的蒙特卡洛模拟局数
_FINISHED_KEEP_SECONDS = 120

_ROOMS = {}
_ROOMS_LOCK = threading.RLock()


def card_view(card: int) -> dict:
    """牌面 -> 前端展示用结构（图片统一走 /mgold/<牌号>.png）"""
    if card >= 200:
        i = card - 200
        return {"id": card, "type": "yakuman", "value": YAKUMAN_SCORES[i],
                "label": YAKUMAN_NAMES[i]}
    if card >= 100:
        i = card - 100
        return {"id": card, "type": "mistake", "value": 0, "label": MISTAKE_NAMES[i]}
    return {"id": card, "type": "gold", "value": card, "label": f"{card} 点棒"}


class Room:
    """一局麻酱宝藏的完整状态。所有公开方法返回错误文案（None 表示成功）。"""

    def __init__(self, code: str, host_qq: int, host_name: str):
        self.code = code
        self.phase = "waiting"        # waiting / exploring / finished
        self.players = [self._new_player(host_qq, host_name)]
        self.round = 0                # 当前轮次（1~5，0 表示还没开始）
        self.deck = []
        self.next_card = 0
        self.revealed = []            # 本轮已翻出的牌
        self.pot_gold = 0             # 池中还没分掉的点棒
        self.pot_yakuman = 0          # 役满池
        self.turn_score = 0           # 在场每个人本轮累积的点棒
        self.mistake_out = [0] * 5    # 每种陷阱已触发的次数
        self.yakuman_in = [False] * 5  # 每种役满牌是否还在牌堆里
        self.left = [False] * MAX_PLAYERS      # 本轮已下车
        self.leaving = [False] * MAX_PLAYERS   # 本轮选择了下车（待结算）
        self.decided = [True] * MAX_PLAYERS    # 本轮当前牌已做决定
        self.log = []
        self.chat = []
        self._bot_running = False
        self._mc_cache = {}
        self.created_at = time.time()
        self.updated_at = time.time()

    # ==================== 小工具 ====================

    @staticmethod
    def _new_player(qq: int, name: str, bot: bool = False, jitter: float = 0.0) -> dict:
        return {"qq": qq, "name": name, "score": 0,
                "bot": bot, "jitter": jitter}

    def _touch(self) -> None:
        self.updated_at = time.time()

    def _log(self, text: str) -> None:
        self.log.append(text)
        if len(self.log) > 150:
            self.log = self.log[-150:]

    def _idx(self, qq: int) -> int:
        for i, p in enumerate(self.players):
            if p["qq"] == qq:
                return i
        return -1

    def _active(self) -> list:
        """本轮还在场上的玩家下标"""
        return [i for i in range(len(self.players)) if not self.left[i]]

    # ==================== 开局 / 加入 ====================

    def join(self, qq: int, name: str):
        if self.phase != "waiting":
            return "这局已经开始或结束了喵"
        if self._idx(qq) >= 0:
            return "你已经在房间里了喵"
        if len(self.players) >= MAX_PLAYERS:
            return "人数已满喵"
        self.players.append(self._new_player(qq, name))
        self._log(f"{name} 加入（{len(self.players)}/{MAX_PLAYERS}）")
        self._touch()
        if len(self.players) >= MAX_PLAYERS:
            self._log("人数已满，自动开始")
            self._start()
        return None

    def start(self, qq: int):
        if self.phase != "waiting":
            return "这局已经开始或结束了喵"
        if self.players[0]["qq"] != qq:
            return "只有房主能开始对局喵"
        if len(self.players) < MIN_PLAYERS:
            return f"至少需要 {MIN_PLAYERS} 人才能开始喵"
        self._start()
        return None

    def add_bot(self, qq: int):
        """房主在等待阶段添加机器人（最多补满 5 人）"""
        if self.phase != "waiting":
            return "对局已经开始或结束，不能添加机器人喵"
        if self.players[0]["qq"] != qq:
            return "只有房主能添加机器人喵"
        if len(self.players) >= MAX_PLAYERS:
            return "人数已满喵"
        k = sum(1 for p in self.players if p.get("bot"))
        bot = self._new_player(-(k + 1), BOT_NAMES[k % len(BOT_NAMES)],
                               bot=True, jitter=BOT_JITTER[k % len(BOT_JITTER)])
        self.players.append(bot)
        self._log(f"{bot['name']} 加入（{len(self.players)}/{MAX_PLAYERS}）")
        self._touch()
        if len(self.players) >= MAX_PLAYERS:
            self._log("人数已满，自动开始")
            self._start()
        return None

    def _start(self) -> None:
        """开始整局：进入第一轮并自动翻开本轮第一张牌"""
        self.phase = "exploring"
        names = "、".join(p["name"] for p in self.players)
        self._log(f"探险开始：{names}（{len(self.players)} 人，共 {ROUNDS} 轮）")
        self._next_round()

    # ==================== 轮次推进 ====================

    def _next_round(self) -> None:
        """开始新的一轮并自动翻开第一张牌；5 轮打完则结算"""
        if self.round >= ROUNDS:
            self._finish()
            return
        self.round += 1
        self.next_card = 0
        self.revealed = []
        self.pot_gold = 0
        self.pot_yakuman = 0
        self.turn_score = 0
        self.left = [False] * MAX_PLAYERS
        self.leaving = [False] * MAX_PLAYERS
        self.decided = [True] * MAX_PLAYERS
        # 每轮新增一张役满牌（按轮次固定：第一轮国士无双 …… 第五轮天和）
        self.yakuman_in[self.round - 1] = True

        cards = list(BASIC_CARDS)
        for i in range(5):
            cards += [MISTAKE_CARDS[i]] * (MISTAKE_COPIES - self.mistake_out[i])
        for i in range(5):
            if self.yakuman_in[i]:
                cards.append(YAKUMAN_CARDS[i])
        random.shuffle(cards)
        self.deck = cards

        parts = [f"{MISTAKE_COPIES - self.mistake_out[i]} 张{MISTAKE_NAMES[i]}"
                 for i in range(5)]
        parts.append(f"1 张{YAKUMAN_NAMES[self.round - 1]}")
        self._log(f"第 {self.round}/{ROUNDS} 轮卡池：15 张点棒牌 · "
                  + " · ".join(parts) + f" · 共 {len(cards)} 张")
        self._advance()

    def _end_round(self) -> None:
        """结束本轮：已翻开的役满牌下轮移除，然后进入下一轮"""
        for card in self.revealed:
            if card >= 200:
                self.yakuman_in[card - 200] = False
        scores = "、".join(f"{p['name']} {p['score']} 根" for p in self.players)
        self._log(f"本轮结束，当前总分：{scores}")
        self._touch()
        self._next_round()

    def _advance(self) -> None:
        """所有在场玩家都做好决定后：先结算下车，再翻开下一张牌"""
        n = len(self.players)
        leavers = [i for i in range(n) if self.leaving[i] and not self.left[i]]

        # 先结算下车的人：他们带走本轮累积的点棒，不参与这张牌的结算
        if leavers:
            names = "、".join(self.players[i]["name"] for i in leavers)
            if len(leavers) == 1:
                gain = self.turn_score + self.pot_gold + self.pot_yakuman
                self._log(f"{names} 下车，带走 {gain} 根点棒"
                          f"（本轮携带 {self.turn_score} · 池中 {self.pot_gold}"
                          f" · 役满池 {self.pot_yakuman}）")
                self.pot_gold = 0
                self.pot_yakuman = 0
                self.players[leavers[0]]["score"] += gain
            else:
                share = self.pot_gold // len(leavers)
                gain = self.turn_score + share
                self._log(f"{names} 一起下车，每人带走 {gain} 根点棒"
                          f"（本轮携带 {self.turn_score} · 池中余数平分 {share}，"
                          f"役满池 {self.pot_yakuman} 留在原地）")
                self.pot_gold -= share * len(leavers)
                for i in leavers:
                    self.players[i]["score"] += gain
            for i in leavers:
                self.left[i] = True
                self.decided[i] = True
                self.leaving[i] = False

        active = self._active()
        if not active:
            self._log("所有人都下车了，本轮结束")
            self._end_round()
            return

        if self.next_card >= len(self.deck):
            self._log("本轮牌堆已经翻完，本轮结束")
            self._end_round()
            return

        card = self.deck[self.next_card]
        self.next_card += 1
        self.revealed.append(card)

        if card < 100:
            share = card // len(active)
            rest = card % len(active)
            self.pot_gold += rest
            self.turn_score += share
            self._log(f"翻开 {card} 点棒牌：在场 {len(active)} 人各得 {share} 根，"
                      f"余数 {rest} 根留在池中（本轮携带 {self.turn_score} 根）")
        elif card < 200:
            i = card - 100
            if card in self.deck[:self.next_card - 1]:
                self.mistake_out[i] += 1
                self._log(f"第二次翻开「{MISTAKE_NAMES[i]}」，在场玩家本轮累积的点棒全部丢失，"
                          f"本轮结束（下轮少一张「{MISTAKE_NAMES[i]}」）")
                self._touch()
                self._end_round()
                return
            self._log(f"翻开「{MISTAKE_NAMES[i]}」陷阱，第一次出现，虚惊一场")
        else:
            i = card - 200
            self.pot_yakuman += YAKUMAN_SCORES[i]
            self._log(f"翻开「{YAKUMAN_NAMES[i]}」役满牌：役满池 +{YAKUMAN_SCORES[i]}"
                      f"（当前 {self.pot_yakuman} 根）")

        # 翻牌完成，在场的人重新做决定
        for i in active:
            self.decided[i] = False
        self._touch()
        self._bots_play()

    def _finish(self) -> None:
        """五轮结束，按总点棒排名"""
        self.phase = "finished"
        self._log("五轮结束，最终成绩："
                  + "、".join(f"{p['name']} {p['score']} 根" for p in self.players))
        self._touch()

    # ==================== 玩家决策 ====================

    def decide(self, qq: int, action: str):
        if self.phase != "exploring":
            return "现在没有进行中的探险喵"
        i = self._idx(qq)
        if i < 0:
            return "你不是本局玩家喵"
        if self.left[i]:
            return "你本轮已经下车了喵"
        if self.decided[i]:
            return "这一张牌你已经做好决定了喵"
        if action == "leave":
            self.leaving[i] = True
        elif action == "continue":
            pass
        else:
            return "未知操作喵"
        self.decided[i] = True
        self._touch()
        self._resolve_if_ready()
        return None

    def _resolve_if_ready(self) -> None:
        """所有在场玩家都决定后推进翻牌"""
        active = self._active()
        if active and all(self.decided[j] for j in active):
            self._advance()

    # ==================== 机器人 ====================

    def _bots_play(self) -> None:
        """让待决策的机器人依次行动；机器人全部行动完会连续翻牌"""
        if self._bot_running:
            return
        self._bot_running = True
        try:
            guard = 0
            while self.phase == "exploring" and guard < 1000:
                guard += 1
                pending = [i for i in self._active()
                           if self.players[i].get("bot") and not self.decided[i]]
                if not pending:
                    break
                for i in pending:
                    action = self._bot_action(i)
                    if action == "leave":
                        self.leaving[i] = True
                    self.decided[i] = True
                    self._log(f"{self.players[i]['name']} 选择"
                              + ("下车" if action == "leave" else "继续"))
                self._touch()
                self._resolve_if_ready()
        finally:
            self._bot_running = False

    def _bot_action(self, i: int) -> str:
        """蒙特卡洛评估：模拟剩余牌堆与对手行为，比较「下车」与「继续」的期望得分

        一步解析近似过于短视：继续之后的分牌、对手陆续下车、第二次陷阱结束
        本轮等交互都被压成一个期望值。这里直接模拟本轮剩余过程，多步前瞻后
        再做决策；同一决策点只计算一次，供该步所有机器人共用。
        """
        active = self._active()
        if not active or self.next_card >= len(self.deck):
            return "leave"

        key = (self.round, self.next_card, self.turn_score, self.pot_gold,
               self.pot_yakuman, len(active), tuple(sorted(set(self.revealed))))
        cached = self._mc_cache.get(key)
        if cached is None:
            cached = self._mc_values(len(active), set(self.revealed))
            self._mc_cache[key] = cached
        ev_leave, ev_continue = cached

        # 期望差距大时直接选优；接近无差异时按个体偏好混合，保留不可预测性
        if ev_continue > ev_leave * 1.03:
            return "continue"
        if ev_leave > ev_continue * 1.03:
            return "leave"
        p = 0.5 + self.players[i].get("jitter", 0.0)
        return "leave" if random.random() < min(0.9, max(0.1, p)) else "continue"

    def _mc_values(self, n_active: int, revealed: set):
        """固定种子模拟，返回 (立即下车期望, 继续期望)"""
        remaining = self.deck[self.next_card:]
        A, G, Y = self.turn_score, self.pot_gold, self.pot_yakuman
        n_opp = n_active - 1
        ev_leave = self._ev_leave_now(A, G, Y, n_opp)
        seed = hash((self.round, self.next_card, A, G, Y, n_active,
                     tuple(sorted(revealed)))) & 0xFFFFFFFF
        total = 0.0
        for t in range(MC_TRIALS):
            rng = random.Random(seed + t)
            order = remaining[:]
            rng.shuffle(order)
            total += self._sim_continue(order, A, G, Y, set(revealed), n_opp, rng)
        return ev_leave, total / MC_TRIALS

    @staticmethod
    def _ev_leave_now(A: int, G: int, Y: int, n_opp: int) -> float:
        """自己下车：只有别人都不下车才能独吞点棒池与役满池"""
        acc = 0.0
        for k in range(n_opp + 1):
            pk = comb(n_opp, k) * (OPP_LEAVE_P ** k) * ((1 - OPP_LEAVE_P) ** (n_opp - k))
            acc += pk * ((A + G + Y) if k == 0 else (A + G // (k + 1)))
        return acc

    @staticmethod
    def _sim_should_leave(A: int, G: int, Y: int, n_opp: int,
                          remaining, revealed) -> bool:
        """模拟中我方的后续策略：风险加权后继续不再划算就下车"""
        total = len(remaining)
        if total <= 0:
            return True
        fatal = 0
        gold_sum = 0
        yak_sum = 0
        for c in remaining:
            if c < 100:
                gold_sum += c
            elif c < 200:
                if c in revealed:
                    fatal += 1
            else:
                yak_sum += YAKUMAN_SCORES[c - 200]
        p = fatal / total
        gain = gold_sum / total / (n_opp + 1) + yak_sum / total
        return p * (A + G + Y) >= (1.0 - p) * gain

    @classmethod
    def _sim_continue(cls, order, A, G, Y, revealed, n_opp, rng) -> float:
        """模拟「本轮继续」后我的最终收益（0 表示本轮血本无归）"""
        pos = 0
        while pos < len(order):
            k = 0
            for _ in range(n_opp):
                if rng.random() < OPP_LEAVE_P:
                    k += 1
            # 首张牌已经翻开，决策从第二次选择开始
            if pos > 0 and cls._sim_should_leave(A, G, Y, n_opp, order[pos:], revealed):
                return (A + G + Y) if k == 0 else (A + G // (k + 1))
            if k > 0:
                if k == 1:          # 对手单走，拿走点棒池与役满池
                    G, Y = 0, 0
                else:
                    G -= (G // k) * k
                n_opp -= k
            c = order[pos]
            pos += 1
            if c < 100:
                n = n_opp + 1
                share = c // n
                A += share
                G += c - share * n
            elif c < 200:
                if c in revealed:   # 同种陷阱第二次出现 -> 本轮结束
                    return 0.0
                revealed.add(c)
            else:
                Y += YAKUMAN_SCORES[c - 200]
        return 0.0

    # ==================== 房间发言 ====================

    def say(self, qq: int, text, name: str = ""):
        """房间内发言（玩家与观众都能说话），返回错误文案（None 表示成功）"""
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
        players = [{
            "name": p["name"],
            "score": p["score"],
            "left": self.left[i],
            "decided": self.decided[i],
            "bot": p.get("bot", False),
        } for i, p in enumerate(self.players)]
        out = {
            "code": self.code,
            "phase": self.phase,
            "round": self.round,
            "rounds": ROUNDS,
            "players": players,
            "names": [p["name"] for p in self.players],
            "my_index": mine,
            "is_player": mine >= 0,
            "is_host": mine == 0 and self.phase == "waiting",
            "pot_gold": self.pot_gold,
            "pot_yakuman": self.pot_yakuman,
            "turn_score": self.turn_score,
            "revealed": [card_view(c) for c in self.revealed],
            "deck_left": max(0, len(self.deck) - self.next_card),
            "mistake_left": [MISTAKE_COPIES - self.mistake_out[i] for i in range(5)],
            "yakuman_card": (card_view(YAKUMAN_CARDS[self.round - 1])
                             if 1 <= self.round <= ROUNDS else None),
            "can_decide": (mine >= 0 and self.phase == "exploring"
                           and not self.left[mine] and not self.decided[mine]),
            "log": self.log[-40:],
            "chat": self.chat[-30:],
        }
        if self.phase == "finished":
            ranked = sorted(range(len(self.players)),
                            key=lambda i: (-self.players[i]["score"], i))
            out["result"] = {
                "ranking": [{"name": self.players[i]["name"],
                             "score": self.players[i]["score"]} for i in ranked],
            }
        return out


# ==================== 房间管理 ====================

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
    """大厅房间列表：等待中可加入、对局中可观战（已结束的不列出）"""
    with _ROOMS_LOCK:
        _reap_locked()
        rooms = []
        for r in _ROOMS.values():
            if r.phase == "finished":
                continue
            rooms.append({
                "code": r.code,
                "host": r.players[0]["name"],
                "phase": r.phase,
                "count": len(r.players),
                "max": MAX_PLAYERS,
                "players": [p["name"] for p in r.players],
            })
        return rooms


def my_room(qq: int):
    with _ROOMS_LOCK:
        _reap_locked()
        return _in_other_room_locked(qq)


def create_room(qq: int, name: str):
    """创建房间，返回 (code, 错误文案)"""
    with _ROOMS_LOCK:
        _reap_locked()
        exist = _in_other_room_locked(qq)
        if exist:
            return None, f"你已经在房间（{exist}）里了喵"
        code = _new_code()
        _ROOMS[code] = Room(code, qq, name)
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
        humans = [p for p in room.players if not p.get("bot")]
        bots = [p for p in room.players if p.get("bot")]
        if not humans:
            return None, "本局没有可再来一局的玩家喵"
        order = sorted(humans, key=lambda p: 0 if p["qq"] == qq else 1)
        new_code = _new_code()
        new_room = Room(new_code, order[0]["qq"], order[0]["name"])
        _ROOMS[new_code] = new_room
        for p in order[1:]:
            new_room.join(p["qq"], p["name"])
        for _ in bots:
            if new_room.phase != "waiting":
                break
            new_room.add_bot(new_room.players[0]["qq"])
        if new_room.phase == "waiting":
            new_room.start(new_room.players[0]["qq"])
        return new_code, None


def join_room(code: str, qq: int, name: str):
    with _ROOMS_LOCK:
        _reap_locked()
        room = _ROOMS.get(code)
        if room is None:
            return "房间不存在或已结束喵"
        if room._idx(qq) >= 0:
            return None    # 已在房里，直接进入
        exist = _in_other_room_locked(qq, exclude=code)
        if exist:
            return f"你已经在另一个房间（{exist}）里了喵"
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
        if action == "start":
            err = room.start(qq)
        elif action == "add_bot":
            err = room.add_bot(qq)
        elif action in ("continue", "leave"):
            err = room.decide(qq, action)
        else:
            err = "未知操作喵"
        return err, room.view(qq)
