"""快艇骰子（Yahtzee）网页版游戏引擎。

房间只存在于网页进程的内存里（不落盘）：大厅建房 -> 加入 -> 房主开始 ->
每回合掷 5 颗骰子（含首投最多 3 投），然后必须「计分」一格；12 格填满或
无人能行动时本局结束，比总分。

计分规则（各格分数、上区奖励、总分）全部复用 plugins/yahtzee.py，避免网页端
与机器人规则漂移。快艇骰子不涉及猫眼石结算（机器人端仅有每周排行的鱼干奖励）。
"""

import random
import threading
import time

from plugins.yahtzee import (
    _roll5, _score_of, _total, _CATEGORY_NAMES,
    MAX_PLAYERS, MAX_ROLL, CATEGORY_COUNT, IDLE_SECONDS,
)

_FINISHED_KEEP_SECONDS = 120   # 已结束的房间保留一会儿，供客户端看到结算结果

_ROOMS = {}
_ROOMS_LOCK = threading.RLock()

# 每周挑战记录钩子：由 server.py 注入，把本局各玩家分数记为「本周首次分数」
_weekly_recorder = None


def set_weekly_recorder(recorder) -> None:
    """注册每周挑战记录回调：recorder(entries)，entries 为 [{qq,name,score}]"""
    global _weekly_recorder
    _weekly_recorder = recorder


class Room:
    """一局快艇骰子的完整状态。所有公开方法返回错误文案（None 表示成功）。"""

    def __init__(self, code: str, host_qq: int, host_name: str):
        self.code = code
        self.phase = "waiting"        # waiting / playing / finished
        self.players = [self._new_player(host_qq, host_name)]
        self.turn = 0
        self.roll = 0
        self.dice = []
        self.winner = None
        self.result_lines = []
        self.log = []
        self.chat = []
        self.created_at = time.time()
        self.updated_at = time.time()

    # ==================== 小工具 ====================

    @staticmethod
    def _new_player(qq: int, name: str) -> dict:
        return {"qq": qq, "name": name, "given_up": False, "score": [-1] * CATEGORY_COUNT}

    def _touch(self) -> None:
        self.updated_at = time.time()

    def _log(self, text: str) -> None:
        self.log.append(text)
        if len(self.log) > 120:
            self.log = self.log[-120:]

    def _idx(self, qq: int) -> int:
        for i, p in enumerate(self.players):
            if p["qq"] == qq:
                return i
        return -1

    @staticmethod
    def _has_active_impl(players) -> bool:
        return any((not p["given_up"]) and any(v < 0 for v in p["score"])
                   for p in players)

    def _has_active(self) -> bool:
        return self._has_active_impl(self.players)

    def _progress(self) -> int:
        active = [p for p in self.players if not p["given_up"]]
        if not active:
            return CATEGORY_COUNT
        return max(sum(1 for v in p["score"] if v >= 0) for p in active)

    def _dice_text(self) -> str:
        return " ".join(str(v) for v in self.dice)

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
        return None

    def start(self, qq: int):
        if self.phase != "waiting":
            return "这局已经开始或结束了喵"
        if self.players[0]["qq"] != qq:
            return "只有房主能开始对局喵"
        self.phase = "playing"
        self.turn = 0
        names = "、".join(p["name"] for p in self.players)
        self._log(f"对局开始：{names}（{len(self.players)} 人）")
        self._start_turn()
        return None

    # ==================== 回合 ====================

    def _start_turn(self) -> None:
        """切换到当前玩家并自动进行首投"""
        p = self.players[self.turn]
        self.roll = 1
        self.dice = _roll5()
        self._log(f"—— 轮到 {p['name']} —— 掷出 {self._dice_text()}（第1/{MAX_ROLL}投）")
        self._touch()

    def _next_active(self) -> bool:
        n = len(self.players)
        for _ in range(n):
            self.turn = (self.turn + 1) % n
            p = self.players[self.turn]
            if (not p["given_up"]) and any(v < 0 for v in p["score"]):
                self._start_turn()
                return True
        return False

    def reroll(self, qq: int, indices):
        if self.phase != "playing":
            return "现在没有进行中的对局喵"
        p = self.players[self.turn]
        if qq != p["qq"]:
            return f"当前玩家是 {p['name']}喵"
        if self.roll >= MAX_ROLL:
            return "已经没有重投次数了喵"
        try:
            idxs = sorted({int(i) for i in indices})
        except (TypeError, ValueError):
            return "选择要重投的骰子不对喵"
        if not idxs or idxs[0] < 0 or idxs[-1] >= len(self.dice):
            return "选择要重投的骰子不对喵"
        for i in idxs:
            self.dice[i] = random.randint(1, 6)
        self.dice = sorted(self.dice)
        self.roll += 1
        self._log(f"{p['name']} 重投 {len(idxs)} 颗，掷出 {self._dice_text()}（第{self.roll}/{MAX_ROLL}投）")
        self._touch()
        return None

    def score(self, qq: int, index):
        if self.phase != "playing":
            return "现在没有进行中的对局喵"
        p = self.players[self.turn]
        if qq != p["qq"]:
            return f"当前玩家是 {p['name']}喵"
        try:
            index = int(index)
        except (TypeError, ValueError):
            return "没有这个计分格喵"
        if not (0 <= index < CATEGORY_COUNT):
            return "没有这个计分格喵"
        if p["score"][index] != -1:
            return "这个格子的分已经算了喵"
        gained = _score_of(index, self.dice)
        p["score"][index] = gained
        self._log(f"{p['name']} 计分 {_CATEGORY_NAMES[index]} +{gained}")
        if not self._has_active():
            self._finalize("全员已打完")
            return None
        self._next_active()
        return None

    def giveup(self, qq: int):
        if self.phase == "finished":
            return "本局已经结束了喵"
        me = self._idx(qq)
        if me < 0:
            return "你没有参与这局游戏喵"
        p = self.players[me]
        if self.phase == "waiting":
            # 还没开始时放弃 = 退出大厅；最后一人退出则整局取消
            self.players.pop(me)
            self._log(f"{p['name']} 退出了大厅")
            self._touch()
            return None
        if p["given_up"]:
            return "你已经放弃过了喵"
        # 放弃：剩余未记分的格子按 0 锁定，当前分数立即固定
        for i in range(CATEGORY_COUNT):
            if p["score"][i] < 0:
                p["score"][i] = 0
        p["given_up"] = True
        total = _total(p["score"])
        self._log(f"{p['name']} 放弃本局（{total} 分已锁定）")
        if self.players[self.turn]["qq"] == qq and self._has_active():
            self._next_active()
        if not self._has_active():
            self._finalize("其余人也已结束")
            return None
        self._touch()
        return None

    # ==================== 结算 ====================

    def _finalize(self, reason: str) -> None:
        self.phase = "finished"
        totals = [(p, _total(p["score"])) for p in self.players]
        # 记录本周首次分数（与机器人端一致：同周已有分数则不重复计）
        if _weekly_recorder is not None:
            try:
                _weekly_recorder([
                    {"qq": p["qq"], "name": p["name"], "score": t} for p, t in totals
                ])
            except Exception:
                pass
        best = max(t for _, t in totals)
        top = [p for p, t in totals if t == best]
        if len(top) == 1:
            self.winner = top[0]["qq"]
            head = f"🏆 {top[0]['name']} 获胜（{reason}）"
        else:
            self.winner = None
            head = "🏆 本局平局"
        self.result_lines = [head]
        for p, t in totals:
            tag = "（已放弃）" if p["given_up"] else ""
            self.result_lines.append(f"{p['name']}{tag}：{t} 分")
        self.dice = []
        for line in self.result_lines:
            self._log(line)
        self._touch()

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
        players = []
        for p in self.players:
            upper = sum(v for v in p["score"][0:6] if v > 0)
            players.append({
                "qq": p["qq"],
                "name": p["name"],
                "given_up": p["given_up"],
                "total": _total(p["score"]),
                "score": [None if v < 0 else v for v in p["score"]],
                "bonus": 35 if upper >= 63 else 0,
            })
        return {
            "code": self.code,
            "phase": self.phase,
            "turn": self.turn,
            "roll": self.roll,
            "dice": [{"value": v, "wild": False, "fill": "#fff",
                      "outline": "#b9b2a6"} for v in self.dice],
            "my_index": mine,
            "is_player": mine >= 0,
            "is_turn": mine >= 0 and mine == self.turn and self.phase == "playing",
            "players": players,
            "categories": _CATEGORY_NAMES,
            "progress": self._progress(),
            "winner": self.winner,
            "result_lines": self.result_lines,
            "log": self.log[-30:],
            "chat": self.chat[-30:],
        }


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
    """大厅房间列表：等待中可加入、进行中可观战（已结束的不列出）"""
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
    """执行一步操作，返回 (错误文案, 房间视图)；房间被取消时视图为 None"""
    with _ROOMS_LOCK:
        room = _ROOMS.get(code)
        if room is None:
            return "房间不存在或已结束喵", None
        if action == "start":
            err = room.start(qq)
        elif action == "reroll":
            err = room.reroll(qq, (payload or {}).get("indices") or [])
        elif action == "score":
            err = room.score(qq, (payload or {}).get("index"))
        elif action == "giveup":
            err = room.giveup(qq)
        else:
            err = "未知操作喵"
        if err is None and not room.players:
            _ROOMS.pop(code, None)
            return None, None
        return err, room.view(qq)
