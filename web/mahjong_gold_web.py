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
        self.created_at = time.time()
        self.updated_at = time.time()

    # ==================== 小工具 ====================

    @staticmethod
    def _new_player(qq: int, name: str) -> dict:
        return {"qq": qq, "name": name, "score": 0}

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
        active = self._active()
        if active and all(self.decided[j] for j in active):
            self._advance()
        return None

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
        elif action in ("continue", "leave"):
            err = room.decide(qq, action)
        else:
            err = "未知操作喵"
        return err, room.view(qq)
