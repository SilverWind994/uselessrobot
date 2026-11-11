"""Can't Stop 网页版游戏引擎。

房间只存在于网页进程的内存里（不落盘）：大厅建房 -> 2~4 人加入 -> 房主开始 ->
每人轮流掷 4 颗骰子，把骰子两两配对后落子。每回合最多 3 枚临时标记，可以一直
掷到爆掉或主动收手；某列走到顶格即被占下、对其他人关闭，先占满 3 列者获胜。

爆掉（所有配对都走不了任何一列）时本回合临时进度全部作废。
"""

import random
import threading
import time

MIN_PLAYERS = 2
MAX_PLAYERS = 4
MAX_MARKERS = 3
WIN_COLUMNS = 3
IDLE_SECONDS = 1800
_FINISHED_KEEP_SECONDS = 120

# 列 2~12 各自需要走到的格数：2 与 12 最短，7 最长
SUMS = list(range(2, 13))
HEIGHTS = {2: 3, 3: 5, 4: 7, 5: 9, 6: 11, 7: 13, 8: 11, 9: 9, 10: 7, 11: 5, 12: 3}

_ROOMS = {}
_ROOMS_LOCK = threading.RLock()


class Room:
    """一局 Can't Stop 的完整状态。所有公开方法返回错误文案（None 表示成功）。"""

    def __init__(self, code: str, host_qq: int, host_name: str):
        self.code = code
        self.phase = "waiting"        # waiting / playing / finished
        self.players = [self._new_player(host_qq, host_name)]
        self.turn = 0
        self.stage = "idle"           # idle / rolled / continue
        self.dice = []
        self.moves = []
        self.active = {}              # 本回合临时标记：{列和: 已走到的格}
        self.winner = None
        self.result_lines = []
        self.log = []
        self.created_at = time.time()
        self.updated_at = time.time()

    # ==================== 小工具 ====================

    @staticmethod
    def _new_player(qq: int, name: str) -> dict:
        return {"qq": qq, "name": name, "progress": {}, "claimed": [], "left": False}

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

    def _claimed_by(self, total: int) -> int:
        """返回占下这一列的玩家下标，没人占下则为 -1"""
        for i, p in enumerate(self.players):
            if total in p["claimed"]:
                return i
        return -1

    @staticmethod
    def _pairings(dice) -> list:
        a, b, c, d = dice
        return [[a + b, c + d], [a + c, b + d], [a + d, b + c]]

    def _sim_step(self, active: dict, total: int) -> bool:
        """在给定的临时标记副本上走一格（就地修改 active），走不了返回 False"""
        if self._claimed_by(total) >= 0:
            return False
        if total in active:
            if active[total] >= HEIGHTS[total]:
                return False
            active[total] += 1
            # 到顶就占下这一列，临时标记收回，后面的配对还能继续用
            if active[total] >= HEIGHTS[total]:
                del active[total]
            return True
        if len(active) >= MAX_MARKERS:
            return False
        active[total] = self.players[self.turn]["progress"].get(total, 0) + 1
        if active[total] >= HEIGHTS[total]:
            del active[total]   # 直接封顶也算占下
        return True

    def _simulate(self, order):
        """按顺序模拟落子，全部可行返回结果临时标记，否则返回 None"""
        active = dict(self.active)
        for total in order:
            if not self._sim_step(active, total):
                return None
        return active

    def _moves(self) -> list:
        """当前骰子的所有可用落子：单列 [x] 或双列 [x, y]"""
        moves = []
        seen = set()

        def add(order) -> None:
            key = tuple(sorted(order))
            if key in seen:
                return
            seen.add(key)
            moves.append(sorted(order))

        for a, b in self._pairings(self.dice):
            # 只走一列也允许，所以每个能单独走的列都单独列出来
            for total in ((a,) if a == b else (a, b)):
                if self._simulate([total]) is not None:
                    add([total])
            if a == b:
                continue
            order = [a, b]
            if self._simulate(order) is None:
                order = [b, a]
            if self._simulate(order) is not None:
                add(order)
        moves.sort(key=lambda m: (len(m), m))
        return moves

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
        if len(self.players) < MIN_PLAYERS:
            return f"至少 {MIN_PLAYERS} 人才能开始喵"
        self.phase = "playing"
        self.turn = 0
        self.stage = "idle"
        self.dice = []
        self.moves = []
        self.active = {}
        names = "、".join(p["name"] for p in self.players)
        self._log(f"对局开始：{names}（{len(self.players)} 人）")
        self._log(f"—— 轮到 {self.players[0]['name']} ——")
        self._touch()
        return None

    # ==================== 回合行动 ====================

    def _guard_turn(self, qq: int):
        if self.phase == "finished":
            return "本局已经结束了喵"
        cur = self.players[self.turn]
        if qq != cur["qq"]:
            return f"当前该 {cur['name']} 行动喵"
        return None

    def roll(self, qq: int):
        if self.phase != "playing":
            return "现在没有进行中的对局喵"
        err = self._guard_turn(qq)
        if err:
            return err
        if self.stage == "rolled":
            return "先选一种落子喵"
        p = self.players[self.turn]
        dice = [random.randint(1, 6) for _ in range(4)]
        self.dice = dice
        legal = self._moves()
        if not legal:
            self._log(f"{p['name']} 掷出 {' '.join(str(v) for v in dice)}，"
                      f"配不出可落子的列，本回合临时进度作废")
            self._next_turn()
            return None
        self.moves = legal
        self.stage = "rolled"
        self._log(f"{p['name']} 掷出 {' '.join(str(v) for v in dice)}")
        self._touch()
        return None

    def move(self, qq: int, sums):
        if self.phase != "playing":
            return "现在没有进行中的对局喵"
        err = self._guard_turn(qq)
        if err:
            return err
        if self.stage != "rolled":
            return "现在没有等待落子的选择喵"
        try:
            order = [int(v) for v in sums]
        except (TypeError, ValueError):
            return "落子选择不对喵"
        if len(order) == 2 and order[0] == order[1]:
            order = [order[0]]
        if len(order) not in (1, 2):
            return "落子选择不对喵"
        if sorted(order) not in [sorted(m) for m in self.moves]:
            return "这组落子不能选喵"
        if self._simulate(order) is None and len(order) == 2:
            order = [order[1], order[0]]
        if self._simulate(order) is None:
            return "这组落子不能选喵"
        p = self.players[self.turn]
        done = []
        for total in order:
            if total in self.active:
                self.active[total] += 1
            else:
                self.active[total] = p["progress"].get(total, 0) + 1
            if self.active[total] >= HEIGHTS[total]:
                # 到顶即占下这一列，临时标记收回
                del self.active[total]
                p["progress"][total] = HEIGHTS[total]
                if total not in p["claimed"]:
                    p["claimed"].append(total)
                self._log(f"{p['name']} 走到 {total} 列顶格，占下这一列！")
                done.append(f"{total}（占下）")
            else:
                done.append(f"{total}→第 {self.active[total]} 格")
        self.moves = []
        self.stage = "continue"
        self._log(f"{p['name']} 落子：{'、'.join(done)}")
        if len(p["claimed"]) >= WIN_COLUMNS:
            self._finalize(p, f"占满 {WIN_COLUMNS} 列")
            return None
        self._touch()
        return None

    def stop(self, qq: int):
        if self.phase != "playing":
            return "现在没有进行中的对局喵"
        err = self._guard_turn(qq)
        if err:
            return err
        if self.stage != "continue":
            return "现在还不能收手喵"
        if not self.active:
            return "本回合还没有可落定的进度喵"
        p = self.players[self.turn]
        banked = sorted(self.active.keys())
        for total in banked:
            p["progress"][total] = max(p["progress"].get(total, 0), self.active[total])
        self._log(f"{p['name']} 收手，落定 "
                  + "、".join(f"{t} 列第 {p['progress'][t]} 格" for t in banked))
        self._next_turn()
        return None

    def _next_turn(self) -> None:
        n = len(self.players)
        for _ in range(n):
            self.turn = (self.turn + 1) % n
            if not self.players[self.turn]["left"]:
                break
        self.stage = "idle"
        self.dice = []
        self.moves = []
        self.active = {}
        self._log(f"—— 轮到 {self.players[self.turn]['name']} ——")
        self._touch()

    def leave(self, qq: int):
        idx = self._idx(qq)
        if idx < 0:
            return "你没有参与这局游戏喵"
        p = self.players[idx]
        if self.phase == "waiting":
            self.players.pop(idx)
            self._log(f"{p['name']} 离开了房间")
            self.turn = 0
            self._touch()
            return None
        if self.phase == "finished":
            return "本局已经结束了喵"
        if p["left"]:
            return "你已经离开本局了喵"
        p["left"] = True
        self._log(f"{p['name']} 离开了对局")
        if self.turn == idx:
            self.active = {}
        remaining = [q for q in self.players if not q["left"]]
        if len(remaining) <= 1:
            self._finalize(remaining[0] if remaining else None, "其他玩家都已离开")
        elif self.turn == idx:
            self._next_turn()
        self._touch()
        return None

    def _finalize(self, winner=None, reason: str = "对局结束") -> None:
        self.phase = "finished"
        self.winner = winner["qq"] if winner else None
        self.stage = "idle"
        self.dice = []
        self.moves = []
        self.active = {}
        head = f"🏆 {winner['name']} 获胜（{reason}）" if winner else "🏆 本局结束"
        self.result_lines = [head]
        for p in self.players:
            tag = "（已离开）" if p["left"] else ""
            self.result_lines.append(
                f"{p['name']}{tag}：{len(p['claimed'])}/{WIN_COLUMNS} 列")
        for line in self.result_lines:
            self._log(line)
        self._touch()

    # ==================== 视图 ====================

    def view(self, qq: int) -> dict:
        mine = self._idx(qq)
        players = []
        for p in self.players:
            players.append({
                "qq": p["qq"],
                "name": p["name"],
                "left": p["left"],
                "claimed": sorted(p["claimed"]),
                "progress": {str(k): v for k, v in p["progress"].items()},
                "columns": len(p["claimed"]),
            })
        return {
            "code": self.code,
            "phase": self.phase,
            "turn": self.turn,
            "stage": self.stage,
            "dice": list(self.dice),
            "moves": self.moves,
            "active": {str(k): v for k, v in self.active.items()},
            "my_index": mine,
            "is_player": mine >= 0,
            "is_turn": mine >= 0 and mine == self.turn and self.phase == "playing",
            "players": players,
            "heights": {str(k): v for k, v in HEIGHTS.items()},
            "sums": SUMS,
            "max_markers": MAX_MARKERS,
            "win_columns": WIN_COLUMNS,
            "winner": self.winner,
            "result_lines": self.result_lines,
            "log": self.log[-40:],
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


def rematch(code: str, qq: int):
    """已结束的对局按原班人马重开一局，返回 (新房号, 错误文案)"""
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
        alive = [p for p in room.players if not p["left"]]
        if len(alive) < MIN_PLAYERS:
            return None, f"至少 {MIN_PLAYERS} 人才能再来一局喵"
        order = sorted(alive, key=lambda p: 0 if p["qq"] == qq else 1)
        new_code = _new_code()
        new_room = Room(new_code, order[0]["qq"], order[0]["name"])
        _ROOMS[new_code] = new_room
        for p in order[1:]:
            new_room.join(p["qq"], p["name"])
        new_room.start(new_room.players[0]["qq"])
        return new_code, None


def snapshot(code: str, qq: int):
    with _ROOMS_LOCK:
        room = _ROOMS.get(code)
        if room is None:
            return None
        return room.view(qq)


def act(code: str, qq: int, action: str, payload: dict):
    """执行一步操作，返回 (错误文案, 房间视图)；房间被解散时视图为 None"""
    with _ROOMS_LOCK:
        room = _ROOMS.get(code)
        if room is None:
            return "房间不存在或已结束喵", None
        if action == "start":
            err = room.start(qq)
        elif action == "roll":
            err = room.roll(qq)
        elif action == "move":
            err = room.move(qq, (payload or {}).get("sums") or [])
        elif action == "stop":
            err = room.stop(qq)
        elif action == "leave":
            err = room.leave(qq)
        else:
            err = "未知操作喵"
        if err is None and not room.players:
            _ROOMS.pop(code, None)
            return None, None
        return err, room.view(qq)
