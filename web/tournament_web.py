"""锦标赛网页版：管理员创建，多人淘汰赛，可多场同时进行。

规则与机器人端 plugins/tournament.py 保持一致：
· 人数 4 / 8 / 16，随机分组两两配对，负者淘汰。
· 单项目不固定：每一场从创建时指定的项目池里随机抽一个项目。
· 非决赛单场定胜负，平局加赛一次，仍平局随机晋级；决赛三局两胜。
· 每场的先后手（谁作为房主建局）随机；冠军拿全额奖励，其余名次按对半递减。

与机器人端的最大差别：网页端一轮里的所有对局同时开局（并行进行），
每场对局由本模块直接为两位选手建好对应的网页游戏房间，选手自己进入操作。

项目池：快艇骰子 / Farkle / 17步麻将 / 麻酱宝藏。
麻酱宝藏额外随机补 1~3 个电脑，晋级只看两位正式选手的点棒数，同分算平局。

锦标赛状态只存在于网页进程内存（与其它网页小游戏一致），重启后清空。
"""

import random
import threading
import time

import farkle_web
import yahtzee_web
import mahjong17_web
import mahjong_gold_web

from config import Config

SIZES = (4, 8, 16)              # 参赛人数可选值

# 比赛项目池：与网页游戏引擎一一对应
PROJECTS = (
    ("yahtzee", "快艇骰子"),
    ("farkle", "Farkle"),
    ("mahjong17", "17步麻将"),
    ("mahjong_gold", "麻酱宝藏"),
)
_PROJECT_NAME = {key: name for key, name in PROJECTS}
_MODULES = {
    "yahtzee": yahtzee_web,
    "farkle": farkle_web,
    "mahjong17": mahjong17_web,
    "mahjong_gold": mahjong_gold_web,
}

# 轮次名 / 名次名（除数 = 该轮参赛人数 = size >> round）
_ROUND_NAME = {16: "十六强赛", 8: "八强赛", 4: "四强赛", 2: "决赛"}
_TIER_NAME = {16: "十六强", 8: "八强", 4: "四强", 2: "亚军"}

IDLE_SECONDS = 6 * 60 * 60      # 长时间无人推进的锦标赛自动作废
_DONE_KEEP_SECONDS = 2 * 60 * 60  # 已结束的锦标赛保留一会儿供查看
TICK_SECONDS = 2.0              # 后台推进节奏

_LOCK = threading.RLock()
_TOURNAMENTS = {}
_worker = None


# ==================== 小工具 ====================

def _name_of(t: dict, qq: int) -> str:
    for p in t["players"]:
        if p["qq"] == qq:
            return p["name"]
    return f"玩家{qq}"


def _new_code_locked() -> str:
    while True:
        code = "T" + str(random.randint(1000, 9999))
        if code not in _TOURNAMENTS:
            return code


def _active_tournament_locked(qq: int, exclude: str = None):
    """返回该玩家正在参加的另一场未结束锦标赛的编号"""
    for code, t in _TOURNAMENTS.items():
        if code == exclude:
            continue
        if t["status"] in ("waiting", "playing") and any(p["qq"] == qq for p in t["players"]):
            return code
    return None


# ==================== 赛程构建 ====================

def _final_projects(pool) -> list:
    """决赛三局的项目：优先三个不同项目，不足时按 QQ 端规则补随机项目"""
    if len(pool) >= 3:
        return random.sample(pool, 3)
    if len(pool) == 2:
        return [pool[0], pool[1], random.choice(pool)]
    return [pool[0]] * 3


def _new_match(a: dict, b: dict, pool, is_final: bool) -> dict:
    projects = _final_projects(pool) if is_final else [random.choice(pool)]
    return {
        "p": [a["qq"], b["qq"]],
        "names": [a["name"], b["name"]],
        "seat": [a["qq"], b["qq"]],   # 座位 0 = 房主（先手），座位 1 = 后手
        "winner": None,
        "results": [],
        "room": None,
        "error": None,
        "projects": projects,
        "game_no": 0,
        "starters": {},
        "is_final": is_final,
    }


def _new_round(t: dict, players: list) -> dict:
    shuffled = list(players)
    random.shuffle(shuffled)
    is_final = len(shuffled) == 2
    matches = []
    for i in range(0, len(shuffled), 2):
        matches.append(_new_match(shuffled[i], shuffled[i + 1], t["pool"], is_final))
    round_name = _ROUND_NAME.get(len(shuffled), "对局")
    return {"name": round_name, "matches": matches}


# ==================== 对局结果判定 ====================

def _resolve(m: dict):
    """根据已完成各场结果判定本场是否结束，返回 (胜者qq | None, 是否还需继续)"""
    res = m["results"]
    p = m["p"]
    if m["is_final"]:
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
        return None, True
    if res[1]["winner"] is not None:
        return res[1]["winner"], False
    return random.choice(p), False


def _view_finished(key: str, view: dict) -> bool:
    return bool(view) and view.get("phase") == "finished"


def _winner_of(m: dict, key: str, view: dict):
    """从对局视图里取出胜者 QQ；平局返回 None"""
    if key in ("yahtzee", "farkle"):
        winner = view.get("winner")
        return winner if winner in m["p"] else None
    if key == "mahjong17":
        pid = (view.get("result") or {}).get("winner")
        if pid in (0, 1):
            return m["seat"][pid]
        return None
    if key == "mahjong_gold":
        players = view.get("players") or []
        if len(players) < 2:
            return None
        a = players[0].get("score", 0)
        b = players[1].get("score", 0)
        if a > b:
            return m["seat"][0]
        if b > a:
            return m["seat"][1]
        return None
    return None


# ==================== 建房（把选手放进对应网页游戏） ====================

def _cancel_locked(key: str, code: str, starter: int) -> None:
    mod = _MODULES.get(key)
    if mod is None:
        return
    try:
        mod.cancel_room(code, starter)
    except Exception:
        pass


def _start_room_locked(t: dict, m: dict) -> None:
    """为当前这一局建好网页房间；失败只记录原因，下一拍继续重试"""
    key = m["projects"][m["game_no"]]
    mod = _MODULES.get(key)
    if mod is None:
        m["error"] = f"未知项目「{key}」"
        return

    if m["game_no"] not in m["starters"]:
        m["starters"][m["game_no"]] = random.choice(m["p"])
    starter = m["starters"][m["game_no"]]
    other = m["p"][0] if starter == m["p"][1] else m["p"][1]
    starter_name = _name_of(t, starter)
    other_name = _name_of(t, other)
    m["seat"] = [starter, other]

    try:
        if key == "yahtzee":
            code, err = mod.create_room(starter, starter_name)
            if err:
                raise RuntimeError(err)
            err = mod.join_room(code, other, other_name)
            if err:
                _cancel_locked(key, code, starter)
                raise RuntimeError(err)
            err, _ = mod.act(code, starter, "start", {})
            if err:
                _cancel_locked(key, code, starter)
                raise RuntimeError(err)
        elif key == "farkle":
            target = random.choice([2000, 4000])   # 与 QQ 端一致：锦标赛目标分随机
            code, err = mod.create_room(starter, starter_name, target, 0)
            if err:
                raise RuntimeError(err)
            err = mod.join_room(code, other, other_name)
            if err:
                _cancel_locked(key, code, starter)
                raise RuntimeError(err)
        elif key == "mahjong17":
            code, err = mod.create_room(starter, starter_name, False)
            if err:
                raise RuntimeError(err)
            err = mod.join_room(code, other, other_name)
            if err:
                _cancel_locked(key, code, starter)
                raise RuntimeError(err)
        elif key == "mahjong_gold":
            code, err = mod.create_room(starter, starter_name)
            if err:
                raise RuntimeError(err)
            err = mod.join_room(code, other, other_name)
            if err:
                _cancel_locked(key, code, starter)
                raise RuntimeError(err)
            # 随机补 1~3 名电脑（2~5 人局；补满 5 人会自动开局）
            for _ in range(random.randint(1, 3)):
                err, _ = mod.act(code, starter, "add_bot", {})
                if err:
                    break
            err, _ = mod.act(code, starter, "start", {})
            if err and "已经开始" not in err and "结束了" not in err:
                raise RuntimeError(err)
        else:
            raise RuntimeError(f"未知项目「{key}」")
    except Exception as e:
        m["error"] = str(e)
        return

    m["room"] = code
    m["error"] = None
    t["updated_at"] = time.time()


def _sync_match_locked(t: dict, m: dict) -> bool:
    """推进一场对局，返回是否有变化"""
    code = m["room"]
    if code:
        key = m["projects"][m["game_no"]]
        view = None
        try:
            view = _MODULES[key].snapshot(code, m["p"][0])
        except Exception:
            view = None
        if view is None:
            # 房间已被回收（或不存在）：重新开局，避免整场卡死
            m["room"] = None
            m["error"] = "对局房间已失效，正在重新开局"
            return True
        if not _view_finished(key, view):
            return False
        winner = _winner_of(m, key, view)
        m["results"].append({"winner": winner, "project": key})
        m["room"] = None
        decided, need_more = _resolve(m)
        if need_more:
            m["game_no"] += 1
            if m["game_no"] >= len(m["projects"]):
                # 非决赛加赛：沿用同一个项目
                m["projects"].append(m["projects"][0])
        else:
            m["winner"] = decided
            m["error"] = None
        t["updated_at"] = time.time()
        return True

    _start_room_locked(t, m)
    return bool(m["room"])


# ==================== 奖励 ====================

def _finish_tournament_locked(t: dict) -> None:
    t["status"] = "done"
    final_match = t["rounds"][-1]["matches"][0]
    champ = final_match["winner"]
    t["champion"] = _name_of(t, champ)
    t["updated_at"] = time.time()

    # 名次除数：在某一轮被淘汰者，除数 = 该轮参赛人数 = size >> round
    divisor_of = {}
    for r, rnd in enumerate(t["rounds"]):
        for m in rnd["matches"]:
            if m["winner"] is None:
                continue
            loser = m["p"][0] if m["winner"] == m["p"][1] else m["p"][1]
            divisor_of[loser] = t["size"] >> r

    fish = t["champion_fish"]
    stone = t["champion_stone"]
    lines = ["🏆 锦标赛结束！最终名次与奖励："]
    order = sorted(t["players"],
                   key=lambda p: (0 if p["qq"] == champ
                                  else divisor_of.get(p["qq"], 2).bit_length() - 1))
    try:
        import cat_web
        plugin = cat_web._plugin
    except Exception:
        plugin = None

    for p in order:
        if p["qq"] == champ:
            tier = "冠军"
            rf, rs = fish, stone
        else:
            d = divisor_of.get(p["qq"], 2)
            tier = _TIER_NAME.get(d, "淘汰")
            rf, rs = fish // d, stone // d
        got = []
        if rf > 0:
            got.append(f"{rf} 鱼干")
            if plugin is not None:
                try:
                    plugin.add_fish(p["qq"], rf)
                except Exception:
                    pass
        if rs > 0:
            got.append(f"{rs} 猫眼石")
            if plugin is not None:
                try:
                    plugin.add_eye_stones(p["qq"], rs)
                except Exception:
                    pass
        lines.append(f"{tier} {p['name']}：{'、'.join(got) if got else '无'}")
    if fish == 0 and stone == 0:
        lines.append("（本场为无奖励锦标赛）")
    t["reward_lines"] = lines


# ==================== 后台推进 ====================

def _advance_locked(t: dict) -> None:
    """推进一场进行中的锦标赛；一轮里所有对局并行推进，全部结束后进入下一轮"""
    while t["status"] == "playing":
        cur = t["rounds"][-1]
        all_done = True
        for m in cur["matches"]:
            if m["winner"] is None:
                _sync_match_locked(t, m)
                if m["winner"] is None:
                    all_done = False
        if not all_done:
            return
        if len(cur["matches"]) == 1:
            _finish_tournament_locked(t)
            return
        winners = []
        for m in cur["matches"]:
            winners.append({"qq": m["winner"], "name": _name_of(t, m["winner"])})
        t["rounds"].append(_new_round(t, winners))
        t["updated_at"] = time.time()


def _reap_locked() -> None:
    now = time.time()
    for code in list(_TOURNAMENTS.keys()):
        t = _TOURNAMENTS[code]
        idle = now - t["updated_at"]
        if t["status"] == "done":
            if idle > _DONE_KEEP_SECONDS:
                _TOURNAMENTS.pop(code, None)
        elif idle > IDLE_SECONDS:
            _TOURNAMENTS.pop(code, None)


def sync() -> None:
    with _LOCK:
        _reap_locked()
        for t in list(_TOURNAMENTS.values()):
            if t["status"] == "playing":
                try:
                    _advance_locked(t)
                except Exception:
                    pass


def _ensure_worker() -> None:
    """锦标赛推进放在后台线程里，不依赖有人正在看锦标赛页面"""
    global _worker
    if _worker is not None and _worker.is_alive():
        return
    _worker = threading.Thread(target=_worker_loop, name="tournament-sync", daemon=True)
    _worker.start()


def _worker_loop() -> None:
    while True:
        try:
            sync()
        except Exception:
            pass
        time.sleep(TICK_SECONDS)


# ==================== 对外接口 ====================

def projects_info() -> list:
    return [{"key": key, "name": name} for key, name in PROJECTS]


def create(owner: int, owner_name: str, size, pool, champion_fish, champion_stone):
    """创建锦标赛（调用方需已校验管理员权限），返回 (code, 错误文案)"""
    try:
        size = int(size)
    except (TypeError, ValueError):
        return None, "人数要是数字喵"
    if size not in SIZES:
        return None, "人数只能选 4 / 8 / 16 喵"
    if not isinstance(pool, (list, tuple)):
        return None, "项目格式不对喵"
    keys = []
    for key in pool:
        key = str(key).strip()
        if key not in _PROJECT_NAME:
            return None, f"不认识的项目「{key}」喵"
        if key not in keys:
            keys.append(key)
    if not keys:
        return None, "至少要选一个比赛项目喵"
    try:
        fish = int(champion_fish or 0)
        stone = int(champion_stone or 0)
    except (TypeError, ValueError):
        return None, "奖励要填数字喵"
    if fish < 0 or stone < 0:
        return None, "奖励不能是负数喵"
    # 带奖励的锦标赛只有指定管理员可以开放（与 QQ 端一致）
    if (fish > 0 or stone > 0) and owner != Config.TOURNAMENT_ADMIN_QQ:
        return None, "只有指定管理员可以开放带鱼干 / 猫眼石奖励的锦标赛喵"

    with _LOCK:
        _reap_locked()
        if len(_TOURNAMENTS) >= 20:
            return None, "同时进行的锦标赛太多了，等一些结束再开喵"
        code = _new_code_locked()
        now = time.time()
        _TOURNAMENTS[code] = {
            "code": code,
            "owner": owner,
            "owner_name": owner_name,
            "size": size,
            "pool": keys,
            "champion_fish": fish,
            "champion_stone": stone,
            "champion": "",
            "status": "waiting",
            "players": [],
            "rounds": [],
            "reward_lines": [],
            "created_at": now,
            "updated_at": now,
        }
    _ensure_worker()
    return code, None


def join(code: str, qq: int, name: str):
    with _LOCK:
        t = _TOURNAMENTS.get(code)
        if t is None:
            return "锦标赛不存在或已结束喵"
        if t["status"] != "waiting":
            return "这场锦标赛已经开始或结束了喵"
        if any(p["qq"] == qq for p in t["players"]):
            return "你已经报名了喵"
        if len(t["players"]) >= t["size"]:
            return "人数已满了喵"
        other = _active_tournament_locked(qq, exclude=code)
        if other:
            return f"你已经在另一场锦标赛（{other}）里了喵"
        t["players"].append({"qq": qq, "name": name})
        t["updated_at"] = time.time()
        _ensure_worker()
        return None


def leave(code: str, qq: int):
    with _LOCK:
        t = _TOURNAMENTS.get(code)
        if t is None:
            return "锦标赛不存在喵"
        if t["status"] != "waiting":
            return "这场锦标赛已经开始了，报名后不能退出喵"
        if not any(p["qq"] == qq for p in t["players"]):
            return "你还没有报名这场锦标赛喵"
        t["players"] = [p for p in t["players"] if p["qq"] != qq]
        t["updated_at"] = time.time()
        return None


def start(code: str):
    """报满后任何人都可以开始（与 QQ 端一致）"""
    with _LOCK:
        t = _TOURNAMENTS.get(code)
        if t is None:
            return "锦标赛不存在喵"
        if t["status"] != "waiting":
            return "这场锦标赛已经开始或结束了喵"
        if len(t["players"]) != t["size"]:
            return f"还没报满喵，当前 {len(t['players'])}/{t['size']} 人"
        t["rounds"] = [_new_round(t, t["players"])]
        t["status"] = "playing"
        t["updated_at"] = time.time()
    _ensure_worker()
    return None


def cancel(code: str, qq: int, is_admin: bool = False):
    """报名阶段：创建者或管理员可以取消"""
    with _LOCK:
        t = _TOURNAMENTS.get(code)
        if t is None:
            return "锦标赛不存在喵"
        if t["owner"] != qq and not is_admin:
            return "只有创建者或管理员可以取消锦标赛喵"
        if t["status"] == "playing":
            return "锦标赛已经开始，需要管理员强制结束喵"
        _TOURNAMENTS.pop(code, None)
        return None


def force_end(code: str, qq: int, is_admin: bool) -> str:
    """管理员强制结束（进行中也可），不发放奖励"""
    if not is_admin:
        return "只有管理员可以强制结束锦标赛喵"
    with _LOCK:
        t = _TOURNAMENTS.get(code)
        if t is None:
            return "锦标赛不存在喵"
        _TOURNAMENTS.pop(code, None)
        return None


def _view_locked(t: dict, qq: int, is_admin: bool, my_active) -> dict:
    players = t["players"]
    joined = any(p["qq"] == qq for p in players)
    full = len(players) >= t["size"]

    rounds = []
    for r, rnd in enumerate(t["rounds"]):
        matches = []
        for m in rnd["matches"]:
            game_no = min(m["game_no"], len(m["projects"]) - 1)
            key = m["projects"][game_no]
            winner_idx = -1
            if m["winner"] is not None and m["winner"] in m["p"]:
                winner_idx = m["p"].index(m["winner"])
            matches.append({
                "key": key,
                "project": _PROJECT_NAME.get(key, key),
                "names": list(m["names"]),
                "winner": _name_of(t, m["winner"]) if m["winner"] is not None else None,
                "winner_idx": winner_idx,
                "done": m["winner"] is not None,
                "game_no": m["game_no"] + 1,
                "games": len(m["results"]),
                "active": m["winner"] is None and r == len(t["rounds"]) - 1,
                "room": m["room"] if qq in m["p"] else None,
                "error": m["error"] if qq in m["p"] else None,
            })
        rounds.append({"name": rnd["name"], "matches": matches})

    my_match = None
    if t["status"] == "playing" and t["rounds"]:
        for m in t["rounds"][-1]["matches"]:
            if m["winner"] is None and qq in m["p"]:
                game_no = min(m["game_no"], len(m["projects"]) - 1)
                key = m["projects"][game_no]
                my_match = {
                    "code": t["code"],
                    "room": m["room"],
                    "key": key,
                    "project": _PROJECT_NAME.get(key, key),
                    "names": list(m["names"]),
                    "error": m["error"],
                }
                break

    return {
        "code": t["code"],
        "owner": t["owner"],
        "owner_name": t["owner_name"],
        "size": t["size"],
        "status": t["status"],
        "pool": [{"key": k, "name": _PROJECT_NAME[k]} for k in t["pool"]],
        "champion_fish": t["champion_fish"],
        "champion_stone": t["champion_stone"],
        "champion": t["champion"],
        "players": [{"qq": p["qq"], "name": p["name"]} for p in players],
        "joined": joined,
        "is_owner": t["owner"] == qq,
        "full": full,
        "can_join": (t["status"] == "waiting" and not joined and not full
                     and (my_active is None or my_active == t["code"])),
        "rounds": rounds,
        "my_match": my_match,
        "reward_lines": list(t["reward_lines"]),
    }


def state_for(qq: int, is_admin: bool) -> dict:
    """锦标赛总览：列表 + 当前用户正在参与的锦标赛"""
    with _LOCK:
        _reap_locked()
        my_active = None
        for t in _TOURNAMENTS.values():
            if t["status"] in ("waiting", "playing") and any(
                    p["qq"] == qq for p in t["players"]):
                my_active = t["code"]
                break
        items = [_view_locked(t, qq, is_admin, my_active) for t in _TOURNAMENTS.values()]
    order = {"playing": 0, "waiting": 1, "done": 2}
    items.sort(key=lambda x: (order.get(x["status"], 3), x["code"]))
    return {
        "list": items,
        "my_active": my_active,
        "sizes": list(SIZES),
        "projects": projects_info(),
    }
