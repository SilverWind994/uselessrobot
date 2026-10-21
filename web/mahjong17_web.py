"""17步麻将（mahjong17）网页版游戏引擎。

房间只存在于网页进程的内存里（不落盘）：大厅建房（猫眼石局 / 普通局）-> 另一位加入 ->
双方各自选 13 张手牌 -> 轮流打出手牌候补的牌，也可以荣和对手刚打出的牌；17 巡无人和牌即流局。

算番与结算全部复用 plugins/mahjong17.py（发牌、算分、猫眼石结算），避免网页端与机器人
规则漂移。与机器人端不同：网页端把「群聊牌桌」与「私聊手牌」合并到同一界面，因此
view(qq) 会按玩家身份裁剪——每人只能看到自己的手牌与候补，对手只看得到舍牌。
"""

import random
import threading
import time

from plugins.mahjong17 import (
    Mahjong17Plugin, _score_hand,
    _RON_WORDS, _PASS_WORDS, _SUIT_BASE,
    LAST_TURN, PLAYER_NUM, STONES_PER_SCORE, MIN_WIN_SCORE, FALSE_WIN_PENALTY, IDLE_SECONDS,
)

_deal = Mahjong17Plugin._deal
_tile_text = Mahjong17Plugin._tile_text

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


# 展示顺序：万/筒/索各 1~9，红五（0/10/20）排在对应花色的 5 之前，字牌 1z~7z
_TILE_ORDER = []
for _base in (0, 10, 20):
    _TILE_ORDER += [_base + 1, _base + 2, _base + 3, _base + 4, _base,
                    _base + 5, _base + 6, _base + 7, _base + 8, _base + 9]
_TILE_ORDER += list(range(31, 38))


def _counts_to_tiles(counts) -> list:
    """把 38 长度的计数数组摊平成牌编号列表（与 QQ 端绘图顺序一致，红五排在 5 位）"""
    out = []
    for i in _TILE_ORDER:
        c = counts[i]
        if c and c > 0:
            out.extend([i] * c)
    return out


def _discards_of(arr) -> list:
    """舍牌数组（以 -1 填充）-> 实际打出的牌编号列表"""
    return [t for t in arr if t != -1]


def _parse_select(text: str, tiles):
    """解析「123m456p789s11z」形式的手牌选择，返回 (计数数组, 错误文案)"""
    select_num = [0] * 10
    select_tile = [0] * 38
    for c in text:
        if c.isdecimal():
            select_num[int(c)] += 1
        elif c in _SUIT_BASE:
            if c == "z" and select_num[0] + select_num[8] + select_num[9] > 0:
                return None, "有不认识的字牌喵"
            base = _SUIT_BASE[c]
            for i in range(10):
                if select_num[i] == 0:
                    continue
                select_tile[i + base] += select_num[i]
                select_num[i] = 0
        else:
            return None, "选择牌的格式不正确喵"
    if not text or text[-1] not in _SUIT_BASE:
        return None, "选择牌的格式不正确喵"
    if sum(select_tile) != 13:
        return None, "选择的牌数需要为13张喵"
    for i in range(38):
        if tiles[i] < select_tile[i]:
            return None, "选择了自己未拥有的牌喵"
    return select_tile, None


class Room:
    """一局 17 步麻将的完整状态。所有公开方法返回错误文案（None 表示成功）。"""

    def __init__(self, code: str, host_qq: int, host_name: str, stones: bool):
        self.code = code
        self.stones = bool(stones)
        self.finished = False
        self.result = None
        self.log = []
        self.chat = []
        self.created_at = time.time()
        self.updated_at = time.time()
        # 对局状态菜单用 dict，便于直接复用 plugins.mahjong17 里的 _deal
        self.g = {
            "stones": bool(stones),
            "started": False,
            "player_id": [host_qq, 0],
            "player_name": [host_name, ""],
            "turn": -1,               # -1 表示还在选牌；>=0 为巡数
            "player_turn": 0,
            "furiten": [False, False],
            "dora": [-1, -1],
            "tiles": [[0] * 38, [0] * 38],
            "hand_tiles": [[-1] + [0] * 37, [-1] + [0] * 37],
            "left_tiles": [[0] * 38, [0] * 38],
            "take_tiles": [[-1] * LAST_TURN, [-1] * LAST_TURN],
        }

    # ==================== 小工具 ====================

    @property
    def phase(self) -> str:
        if self.finished:
            return "finished"
        if not self.g["started"]:
            return "waiting"
        if self.g["turn"] == -1:
            return "selecting"
        return "playing"

    def _touch(self) -> None:
        self.updated_at = time.time()

    def _log(self, text: str) -> None:
        self.log.append(text)
        if len(self.log) > 120:
            self.log = self.log[-120:]

    def _pid(self, qq: int) -> int:
        for i in (0, 1):
            if self.g["player_id"][i] == qq:
                return i
        return -1

    # ==================== 开局 / 加入 ====================

    def join(self, qq: int, name: str):
        g = self.g
        if g["started"] or g["player_id"][1] != 0:
            return "游戏已经开始了喵"
        if g["player_id"][0] == qq:
            return "你已经在准备中喵"
        g["player_id"][1] = qq
        g["player_name"][1] = name
        _deal(g)
        g["started"] = True
        self._log(f"{name} 加入，双方请在各自界面选 13 张手牌")
        self._log(f"本局宝牌指示牌为 {_tile_text(g['dora'][0])}"
                  + ("（本局为猫眼石局）" if self.stones else ""))
        self._touch()
        return None

    # ==================== 选牌 / 打牌 / 荣和 / 流局 ====================

    def select(self, qq: int, text: str):
        g = self.g
        pid = self._pid(qq)
        if pid < 0:
            return "你不是本局玩家喵"
        if self.finished:
            return "本局已经结束了喵"
        if g["turn"] != -1:
            return "已经选好牌了，请等待对手选牌喵"
        if g["hand_tiles"][pid][0] != -1:
            return "已经选好牌了，请等待对手选牌喵"
        select_tile, err = _parse_select(text or "", g["tiles"][pid])
        if err:
            return err
        for i in range(38):
            g["left_tiles"][pid][i] = g["tiles"][pid][i] - select_tile[i]
            g["hand_tiles"][pid][i] = select_tile[i]
        self._log(f"{g['player_name'][pid]} 已选好 13 张手牌")
        if g["hand_tiles"][1 - pid][0] != -1:
            g["turn"] = 0
            g["player_turn"] = 0
            self._log(f"双方选牌完毕，{g['player_name'][0]} 先打牌")
        self._touch()
        return None

    def play(self, qq: int, text: str):
        g = self.g
        pid = self._pid(qq)
        if pid < 0:
            return "你不是本局玩家喵"
        if self.finished:
            return "本局已经结束了喵"
        if g["turn"] == -1:
            return "请先选好 13 张手牌喵"
        if pid != g["player_turn"]:
            return "当前不是你的回合喵"
        text = (text or "").strip()

        if text in _RON_WORDS:
            return self._ron(pid)
        if g["turn"] == LAST_TURN:
            if text in _PASS_WORDS:
                self._draw()
                return None
            return "当前只能选择荣和或者流局喵"

        if len(text) != 2 or not text[0].isdecimal() or text[1] not in _SUIT_BASE:
            return "无法识别打出的牌喵"
        tile = int(text[0])
        if text[1] == "p":
            tile += 10
        if text[1] == "s":
            tile += 20
        if text[1] == "z":
            if tile in (0, 8, 9):
                return "无法识别打出的牌喵"
            tile += 30
        if g["left_tiles"][pid][tile] == 0:
            return "剩余手牌中没有这张牌喵"

        # 振听（对手舍牌）：本回合对手打出的是自己的和了牌，不荣和就进入振听
        cut = self._last_discard(pid)
        if (cut is not None and not g["furiten"][pid]
                and _score_hand(g["hand_tiles"][pid], cut, g["dora"])[2] > 0):
            g["furiten"][pid] = True
            self._log(f"{g['player_name'][pid]} 放过了可以荣和的牌，本局进入振听")
        g["left_tiles"][pid][tile] -= 1
        g["take_tiles"][pid][g["turn"]] = tile
        # 振听（自己舍牌）：打出的恰好是自己的和了牌，同样进入振听
        if (not g["furiten"][pid]
                and _score_hand(g["hand_tiles"][pid], tile, g["dora"])[2] > 0):
            g["furiten"][pid] = True
            self._log(f"{g['player_name'][pid]} 打出了自己的和了牌，本局进入振听")
        g["player_turn"] += 1
        if g["player_turn"] == PLAYER_NUM:
            g["player_turn"] = 0
            g["turn"] += 1
        self._log(f"{g['player_name'][pid]} 打出 {text}")
        self._touch()
        return None

    def _last_discard(self, pid: int):
        """当前玩家面对的那张对手舍牌（庄家首巡还没人打牌则返回 None）"""
        g = self.g
        if pid == 0:
            if g["turn"] == 0:
                return None
            return g["take_tiles"][1][g["turn"] - 1]
        return g["take_tiles"][0][g["turn"]]

    def _ron(self, pid: int):
        g = self.g
        if pid == 0 and g["turn"] == 0:
            # 庄家还没打牌，没有可荣和的牌：不算和牌，对局照常继续
            return "还没有人打牌，无法荣和喵"
        if pid == 0:
            cut = g["take_tiles"][1][g["turn"] - 1]
        else:
            cut = g["take_tiles"][0][g["turn"]]

        if g["furiten"][pid]:
            # 振听后不能再荣和，宣布荣和按诈和处理（赔对方 5 猫眼石）
            self._log(f"{g['player_name'][pid]} 已经振听，宣布荣和算诈胡！")
            lines = self._settle(pid, 0, 0)
            self._finish(1 - pid, "诈胡判负", pid, 0, 0, 0, [], cut, lines)
            return None

        score, fu, fan, fans = _score_hand(g["hand_tiles"][pid], cut, g["dora"])
        self._log(f"{g['player_name'][pid]} 宣布荣和")
        if fan == 0:
            # 无役不成和：宣布荣和按诈胡处理，宣布者判负
            lines = self._settle(pid, score, fan)
            self._finish(1 - pid, "诈胡判负", pid, score, fu, fan, fans, cut, lines)
        elif score < MIN_WIN_SCORE:
            # 荣和但得分不足满贯：视为平局，不判胜负、不结算
            self._finish(None, f"得分不足满贯（{score}）", pid, score, fu, fan, fans, cut, [])
        else:
            lines = self._settle(pid, score, fan)
            self._finish(pid, "荣和", pid, score, fu, fan, fans, cut, lines)
        return None

    def _draw(self) -> None:
        self._log("流局")
        self.finished = True
        self.result = {
            "winner": None, "reason": "流局", "lines": [],
            "pid": None, "score": 0, "fu": 0, "fan": 0, "fans": [],
            "cut": None,
        }
        self._touch()

    def _finish(self, winner_pid, reason, pid, score, fu, fan, fans, cut, lines) -> None:
        g = self.g
        self.finished = True
        self.result = {
            "winner": winner_pid, "reason": reason, "lines": lines,
            "pid": pid, "score": score, "fu": fu, "fan": fan,
            "fans": [f if isinstance(f, (list, tuple)) else [f, ""] for f in (fans or [])],
            "cut": cut,
        }
        for line in lines:
            self._log(line)
        self._log(f"本局结束：{reason}")
        self._touch()

    # ==================== 猫眼石结算 ====================

    def _settle(self, winner_pid: int, score: int, fan: int) -> list:
        """按猫眼石结算，返回需要展示的说明行"""
        if not self.stones:
            return []
        try:
            cat = _cat()
        except Exception as e:
            return [f"（猫眼石结算失败：{e}）"]
        g = self.g
        winner = g["player_id"][winner_pid]
        loser = g["player_id"][1 - winner_pid]
        if fan == 0:
            # 诈胡：宣布荣和的人赔对方 5 猫眼石
            amount = FALSE_WIN_PENALTY
            payer, receiver = winner, loser
        else:
            amount = score // STONES_PER_SCORE
            payer, receiver = loser, winner

        before = cat.get_eye_stones(payer)
        cat.add_eye_stones(receiver, amount)
        after = cat.add_eye_stones(payer, -amount)

        lines = []
        if fan == 0:
            lines.append(f"诈胡！{g['player_name'][winner_pid]} 赔给 "
                         f"{g['player_name'][1 - winner_pid]} {amount} 猫眼石"
                         f"（余额 {before} → {after}）")
        else:
            lines.append(f"{g['player_name'][winner_pid]} 得分 {score} 分，"
                         f"{g['player_name'][1 - winner_pid]} 支付 {amount} 猫眼石"
                         f"（余额 {before} → {after}）")
        if after < 0:
            lines.append(f"猫眼石不足，现有欠债 {-after} 个，还清前不能参与猫眼石局")
        return lines

    # ==================== 房间发言 ====================

    def say(self, qq: int, text, name: str = ""):
        """房间内发言（对局双方与观众都能说话），返回错误文案（None 表示成功）"""
        body = str(text or "").strip()
        if not body:
            return "说点什么喵"
        mine = self._pid(qq)
        speaker = self.g["player_name"][mine] if mine >= 0 else (name or f"观众{qq}")
        self.chat.append({"name": speaker, "text": body[:80], "time": int(time.time())})
        if len(self.chat) > 40:
            self.chat = self.chat[-40:]
        self._touch()
        return None

    # ==================== 视图（按玩家裁剪）====================

    def view(self, qq: int) -> dict:
        g = self.g
        mine = self._pid(qq)
        names = list(g["player_name"])
        out = {
            "code": self.code,
            "stones": self.stones,
            "phase": self.phase,
            "turn": g["turn"],
            "player_turn": g["player_turn"],
            "names": names,
            "my_index": mine,
            "is_player": mine >= 0,
            "is_turn": mine >= 0 and mine == g["player_turn"] and self.phase == "playing",
            # dora[0] 为表宝牌指示牌（对局中公开），dora[1] 为里宝牌指示牌（结算才公开）
            "dora": list(g["dora"]) if self.finished else [g["dora"][0]],
            "discards": [_discards_of(g["take_tiles"][0]), _discards_of(g["take_tiles"][1])],
            "furiten": g["furiten"][mine] if mine >= 0 else False,
            "log": self.log[-30:],
            "chat": self.chat[-30:],
        }
        if mine >= 0:
            if self.phase == "selecting":
                out["my34"] = _counts_to_tiles(g["tiles"][mine])
            out["hand"] = _counts_to_tiles(g["hand_tiles"][mine])
            out["left"] = _counts_to_tiles(g["left_tiles"][mine])
        else:
            # 旁观者：可见双方手牌与待排（selecting 阶段还没有手牌，给出各自发到的 34 张）
            out["spectate"] = [
                {"name": names[i],
                 "hand": _counts_to_tiles(g["hand_tiles"][i]),
                 "left": _counts_to_tiles(g["left_tiles"][i]),
                 "pool": _counts_to_tiles(g["tiles"][i]) if self.phase == "selecting" else []}
                for i in range(PLAYER_NUM)
            ]
        if self.finished:
            out["result"] = dict(self.result or {})
            out["reveal"] = [
                {"name": names[i],
                 "hand": _counts_to_tiles(g["hand_tiles"][i]),
                 "left": _counts_to_tiles(g["left_tiles"][i]),
                 "discards": _discards_of(g["take_tiles"][i])}
                for i in range(PLAYER_NUM)
            ]
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
        if room.finished and idle > _FINISHED_KEEP_SECONDS:
            _ROOMS.pop(code, None)
        elif idle > IDLE_SECONDS:
            _ROOMS.pop(code, None)


def _in_other_room_locked(qq: int, exclude: str = None):
    for code, room in _ROOMS.items():
        if code == exclude:
            continue
        if not room.finished and room._pid(qq) >= 0:
            return code
    return None


# ==================== 对外接口（供 server.py 调用）====================

def list_rooms() -> list:
    """大厅房间列表：等待中可加入、对局中可观战（已结束的不列出）"""
    with _ROOMS_LOCK:
        _reap_locked()
        rooms = []
        for r in _ROOMS.values():
            if r.finished:
                continue
            rooms.append({
                "code": r.code,
                "host": r.g["player_name"][0],
                "stones": r.stones,
                "phase": r.phase,
                "players": [n for n in r.g["player_name"] if n],
            })
        return rooms


def my_room(qq: int):
    with _ROOMS_LOCK:
        _reap_locked()
        return _in_other_room_locked(qq)


def create_room(qq: int, name: str, stones):
    """创建房间，返回 (code, 错误文案)"""
    with _ROOMS_LOCK:
        _reap_locked()
        exist = _in_other_room_locked(qq)
        if exist:
            return None, f"你已经在房间（{exist}）里了喵"
        stones = bool(stones)
        if stones:
            debt = _debt_of(qq)
            if debt > 0:
                return None, f"你有 {debt} 个猫眼石欠债，不能开猫眼石局喵"
        code = _new_code()
        _ROOMS[code] = Room(code, qq, name, stones)
        return code, None


def join_room(code: str, qq: int, name: str):
    with _ROOMS_LOCK:
        _reap_locked()
        room = _ROOMS.get(code)
        if room is None:
            return "房间不存在或已结束喵"
        if room._pid(qq) >= 0:
            return None    # 已在房里，直接进入
        if room.phase != "waiting":
            return "这局已经开始喵"
        exist = _in_other_room_locked(qq, exclude=code)
        if exist:
            return f"你已经在另一个房间（{exist}）里了喵"
        if room.stones and _debt_of(qq) > 0:
            return "你有猫眼石欠债，不能加入猫眼石局喵"
        return room.join(qq, name)


def cancel_room(code: str, qq: int):
    with _ROOMS_LOCK:
        room = _ROOMS.get(code)
        if room is None:
            return "房间不存在喵"
        if room.phase != "waiting":
            return "对局已经开始了，不能解散喵"
        if room.g["player_id"][0] != qq:
            return "只有开局的人能取消这局喵"
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
        if action == "select":
            err = room.select(qq, str((payload or {}).get("text", "")))
        elif action == "play":
            err = room.play(qq, str((payload or {}).get("text", "")))
        else:
            err = "未知操作喵"
        return err, room.view(qq)
