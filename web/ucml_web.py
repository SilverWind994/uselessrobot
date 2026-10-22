"""UCML（UEML）赛事计分 · 网页版。

移植自 archive/mybot/ucml.py：原来的 PostgreSQL 多表结构改成一份 JSON 存档，
所有队伍 / 选手成绩都由比赛记录实时聚合，不再维护冗余的成绩表。

规则要点：
- 每场 4 人、点数总和 100000，同一队伍不能有两人同时出场；
- 单场 pt = (点数 - 25000) / 1000 + 名次分，名次分含并列特殊规则；
- 常规赛 → 半决赛取前 6 队、半决赛 → 决赛取前 4 队，
  晋级队伍继承上一阶段分数的一半（/2 + 0.01 后四舍五入到 1 位）；
- 计分与赛事管理仅限管理员，权限校验在 server.py 里做。
"""

import copy
import json
import os
import threading
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "newbot", "assets", "ucml")
DATA_PATH = os.path.join(DATA_DIR, "ucml.json")

STAGE_NAMES = {0: "准备期", 1: "常规赛", 2: "半决赛", 3: "决赛", 4: "已结束"}
STAGE_MATCH_NAMES = {1: "常规赛", 2: "半决赛", 3: "决赛"}
TOTAL_POINTS = 100000
RANK_KEYS = {1: "first", 2: "second", 3: "third", 4: "forth"}

_LOCK = threading.RLock()


def _blank() -> dict:
    return {
        "version": 1,
        "season": 1,
        "stage": 0,
        "teams": [],        # [{"name": str, "r": int, "g": int, "b": int}]
        "players": [],      # [{"name": str, "team": str}]
        "matches": [],      # [{"id": int, "stage": int, "time": float, "entries": [...]}]
        "inherit": {},      # {"2": {"teams": {队名: pt}, "players": [选手名]}, ...}
        "seasons": [],      # 已归档赛季快照：{season, stage, teams, players, matches, inherit}
    }


def _load() -> dict:
    if not os.path.exists(DATA_PATH):
        return _blank()
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return _blank()
    if not isinstance(data, dict):
        return _blank()
    for key, value in _blank().items():
        data.setdefault(key, value)
    return data


def _save(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_PATH)


# ==================== 基础查询 ====================

def _team_names(data: dict) -> list:
    return [t["name"] for t in data["teams"]]


def _team_color(data: dict, name: str) -> tuple:
    for t in data["teams"]:
        if t["name"] == name:
            return int(t.get("r", 120)), int(t.get("g", 120)), int(t.get("b", 120))
    return 120, 120, 120


def _stage_team_names(data: dict, stage: int) -> list:
    """该阶段有资格出场的队伍"""
    if stage == 1:
        return _team_names(data)
    if stage in (2, 3):
        return list(data["inherit"].get(str(stage), {}).get("teams", {}).keys())
    if stage == 4:
        return list(data["inherit"].get("3", {}).get("teams", {}).keys())
    return []


def _stage_player_names(data: dict, stage: int) -> list:
    """该阶段有资格出场的选手 = 晋级队伍里的现有队员"""
    teams = set(_stage_team_names(data, stage))
    return [p["name"] for p in data["players"] if p["team"] in teams]


def _stage_teams_inherit(data: dict, stage: int) -> dict:
    if stage in (2, 3):
        return data["inherit"].get(str(stage), {}).get("teams", {}) or {}
    return {}


# ==================== 成绩聚合 ====================

def _team_standings(data: dict, stage: int) -> list:
    inherit = _stage_teams_inherit(data, stage)
    rows = {}
    for name in _stage_team_names(data, stage):
        r, g, b = _team_color(data, name)
        rows[name] = {"name": name, "r": r, "g": g, "b": b,
                      "match": 0, "first": 0, "second": 0, "third": 0, "forth": 0,
                      "inherit": round(float(inherit.get(name, 0.0)), 1),
                      "score": 0.0}
    for match in data["matches"]:
        if match.get("stage") != stage:
            continue
        for entry in match.get("entries", []):
            row = rows.get(entry.get("team"))
            if row is None:
                continue
            row["match"] += 1
            key = RANK_KEYS.get(int(entry.get("rank", 4)), "forth")
            row[key] += 1
            row["score"] += float(entry.get("pt", 0.0))
    for row in rows.values():
        row["score"] = round(row["inherit"] + row["score"], 1)
    return sorted(rows.values(), key=lambda r: (-r["score"], r["name"]))


def _player_standings(data: dict, stage: int) -> list:
    team_of = {p["name"]: p["team"] for p in data["players"]}
    rows = {}
    for name in _stage_player_names(data, stage):
        team = team_of.get(name, "")
        r, g, b = _team_color(data, team)
        rows[name] = {"name": name, "team": team, "r": r, "g": g, "b": b,
                      "match": 0, "first": 0, "second": 0, "third": 0, "forth": 0,
                      "score": 0.0}
    for match in data["matches"]:
        if match.get("stage") != stage:
            continue
        for entry in match.get("entries", []):
            row = rows.get(entry.get("player"))
            if row is None:
                continue
            row["match"] += 1
            key = RANK_KEYS.get(int(entry.get("rank", 4)), "forth")
            row[key] += 1
            row["score"] += float(entry.get("pt", 0.0))
    for row in rows.values():
        row["score"] = round(row["score"], 1)
    return sorted(rows.values(), key=lambda r: (-r["score"], r["name"]))


def _total_team_standings(data: dict) -> list:
    rows = {}
    for name in _team_names(data):
        r, g, b = _team_color(data, name)
        rows[name] = {"name": name, "r": r, "g": g, "b": b,
                      "match": 0, "first": 0, "second": 0, "third": 0, "forth": 0,
                      "inherit": None, "score": 0.0}
    for match in data["matches"]:
        for entry in match.get("entries", []):
            row = rows.get(entry.get("team"))
            if row is None:
                continue
            row["match"] += 1
            key = RANK_KEYS.get(int(entry.get("rank", 4)), "forth")
            row[key] += 1
            row["score"] += float(entry.get("pt", 0.0))
    for row in rows.values():
        row["score"] = round(row["score"], 1)
    return sorted(rows.values(), key=lambda r: (-r["score"], r["name"]))


def _total_player_standings(data: dict) -> list:
    team_of = {p["name"]: p["team"] for p in data["players"]}
    rows = {}
    for p in data["players"]:
        r, g, b = _team_color(data, p["team"])
        rows[p["name"]] = {"name": p["name"], "team": p["team"], "r": r, "g": g, "b": b,
                           "match": 0, "first": 0, "second": 0, "third": 0, "forth": 0,
                           "score": 0.0}
    for match in data["matches"]:
        for entry in match.get("entries", []):
            row = rows.get(entry.get("player"))
            if row is None:
                team = entry.get("team", team_of.get(entry.get("player"), ""))
                r, g, b = _team_color(data, team)
                row = {"name": entry.get("player"), "team": team, "r": r, "g": g, "b": b,
                       "match": 0, "first": 0, "second": 0, "third": 0, "forth": 0,
                       "score": 0.0}
                rows[row["name"]] = row
            row["match"] += 1
            key = RANK_KEYS.get(int(entry.get("rank", 4)), "forth")
            row[key] += 1
            row["score"] += float(entry.get("pt", 0.0))
    for row in rows.values():
        row["score"] = round(row["score"], 1)
    return sorted(rows.values(), key=lambda r: (-r["score"], r["name"]))


# ==================== 单场计分 ====================

def _rank_bonus(sorted_scores: list) -> tuple:
    """按原版规则返回 (名次分, 名次标记)；并列的判定顺序与旧实现一致"""
    a, b, c, d = sorted_scores
    if a == d:
        return [0.0, 0.0, 0.0, 0.0], ["FIRST"] * 4
    if a == c:
        return [11.7, 11.7, 11.7, -35.0], ["FIRST", "FIRST", "FIRST", "FORTH"]
    if b == d:
        return [45.0, -15.0, -15.0, -15.0], ["FIRST", "SECOND", "SECOND", "SECOND"]
    if b == c:
        return [45.0, -5.0, -5.0, -35.0], ["FIRST", "SECOND", "SECOND", "FORTH"]
    if a == b and c == d:
        return [25.0, 25.0, -25.0, -25.0], ["FIRST", "FIRST", "THIRD", "THIRD"]
    if a == b:
        return [25.0, 25.0, -15.0, -35.0], ["FIRST", "FIRST", "THIRD", "FORTH"]
    if c == d:
        return [45.0, 5.0, -25.0, -25.0], ["FIRST", "SECOND", "THIRD", "THIRD"]
    return [45.0, 5.0, -15.0, -35.0], ["FIRST", "SECOND", "THIRD", "FORTH"]


def _normalize_match(data: dict, players, scores):
    """校验并计算一场比赛，返回 (错误文案, None) 或 (None, 成绩条目)"""
    stage = int(data.get("stage", 0))
    if stage not in (1, 2, 3):
        return "当前没有正在进行的比赛阶段", None
    if not isinstance(players, list) or not isinstance(scores, list):
        return "参数格式不正确", None
    if len(players) != 4 or len(scores) != 4:
        return "需要 4 位选手和 4 个点数", None

    names = [str(x).strip() for x in players]
    if any(not n for n in names):
        return "选手名称不能为空", None
    if len(set(names)) != 4:
        return "同一场比赛不能重复出现同一选手", None

    try:
        points = [int(x) for x in scores]
    except (TypeError, ValueError):
        return "点数必须是整数", None
    if sum(points) != TOTAL_POINTS:
        return f"点数总和不等于 {TOTAL_POINTS}（当前 {sum(points)}）", None

    allowed = set(_stage_player_names(data, stage))
    for name in names:
        if name not in allowed:
            return f"{name} 不在当前阶段的参赛选手中", None

    team_of = {p["name"]: p["team"] for p in data["players"]}
    teams = [team_of.get(name, "") for name in names]
    if any(not team for team in teams):
        return "存在尚未编入队伍的选手", None
    if len(set(teams)) != 4:
        return "同一队伍不能有两名选手同时出场", None

    order = sorted(range(4), key=lambda i: points[i], reverse=True)
    sorted_points = [points[i] for i in order]
    bonuses, _ = _rank_bonus(sorted_points)

    entries = []
    for pos, idx in enumerate(order):
        pt = round((points[idx] - 25000) / 1000.0 + bonuses[pos], 1)
        entries.append({
            "rank": pos + 1,
            "player": names[idx],
            "team": teams[idx],
            "raw": points[idx],
            "pt": pt,
        })
    return None, entries


def preview_match(players, scores):
    with _LOCK:
        data = _load()
        err, entries = _normalize_match(data, players, scores)
        if err:
            return err, None
        return None, entries


def record_match(players, scores, is_admin=False):
    with _LOCK:
        data = _load()
        err, entries = _normalize_match(data, players, scores)
        if err:
            return err, None
        stage = int(data["stage"])
        next_id = max([int(m.get("id", 0)) for m in data["matches"]] or [0]) + 1
        data["matches"].append({
            "id": next_id,
            "stage": stage,
            "time": time.time(),
            "entries": entries,
        })
        _save(data)
        return None, _overview_locked(data, is_admin)


def undo_match(is_admin=False):
    with _LOCK:
        data = _load()
        if not data["matches"]:
            return "没有可以撤回的比赛", None
        stage = int(data["stage"])
        last = data["matches"][-1]
        if stage not in (1, 2, 3) or int(last.get("stage", 0)) != stage:
            return "只能撤回当前阶段最近的一场比赛", None
        data["matches"].pop()
        _save(data)
        return None, _overview_locked(data, is_admin)


# ==================== 阶段 / 赛季 ====================

def next_stage(is_admin=False):
    with _LOCK:
        data = _load()
        stage = int(data.get("stage", 0))
        if stage == 4:
            return "赛季已经结束，请开始新赛季", None

        if stage == 0:
            teams = data["teams"]
            if len(teams) < 6:
                return f"至少需要 6 支队伍才能开赛（当前 {len(teams)} 支）", None
            empty = [t["name"] for t in teams
                     if not any(p["team"] == t["name"] for p in data["players"])]
            if empty:
                return "存在没有队员的队伍：" + "、".join(empty), None
            data["stage"] = 1
        elif stage == 1:
            top = _team_standings(data, 1)[:6]
            data["inherit"]["2"] = {
                "teams": {r["name"]: round(r["score"] / 2.0 + 0.01, 1) for r in top},
                "players": [p["name"] for p in data["players"]
                            if p["team"] in {r["name"] for r in top}],
            }
            data["stage"] = 2
        elif stage == 2:
            top = _team_standings(data, 2)[:4]
            data["inherit"]["3"] = {
                "teams": {r["name"]: round(r["score"] / 2.0 + 0.01, 1) for r in top},
                "players": [p["name"] for p in data["players"]
                            if p["team"] in {r["name"] for r in top}],
            }
            data["stage"] = 3
        else:
            data["stage"] = 4

        _save(data)
        return None, _overview_locked(data, is_admin)


def new_season(is_admin=False):
    with _LOCK:
        data = _load()
        if int(data.get("stage", 0)) != 4:
            return "当前赛季还没结束，无法开始新赛季", None
        archived = copy.deepcopy(data.get("seasons", []))
        if data["matches"]:
            archived.append({
                "season": int(data.get("season", 1)),
                "stage": 4,
                "teams": copy.deepcopy(data["teams"]),
                "players": copy.deepcopy(data["players"]),
                "matches": copy.deepcopy(data["matches"]),
                "inherit": copy.deepcopy(data["inherit"]),
            })
        fresh = _blank()
        fresh["season"] = int(data.get("season", 1)) + 1
        fresh["seasons"] = archived
        _save(fresh)
        return None, _overview_locked(fresh, is_admin)


# ==================== 队伍 / 选手 ====================

def add_team(name, color, is_admin=False):
    with _LOCK:
        data = _load()
        if int(data.get("stage", 0)) != 0:
            return "比赛已经开始，不能再添加队伍", None
        name = str(name or "").strip()
        if not (1 <= len(name) <= 16):
            return "队名需要 1~16 个字", None
        if name in _team_names(data):
            return "已经有同名的队伍了", None
        try:
            r, g, b = [int(x) for x in color]
        except (TypeError, ValueError):
            return "队伍颜色需要 3 个 0~255 的整数", None
        if not all(0 <= v <= 255 for v in (r, g, b)):
            return "队伍颜色需要 3 个 0~255 的整数", None
        data["teams"].append({"name": name, "r": r, "g": g, "b": b})
        _save(data)
        return None, _overview_locked(data, is_admin)


def delete_team(name, is_admin=False):
    with _LOCK:
        data = _load()
        if int(data.get("stage", 0)) != 0:
            return "比赛已经开始，不能删除队伍", None
        name = str(name or "").strip()
        if name not in _team_names(data):
            return "队伍不存在", None
        data["teams"] = [t for t in data["teams"] if t["name"] != name]
        data["players"] = [p for p in data["players"] if p["team"] != name]
        _save(data)
        return None, _overview_locked(data, is_admin)


def add_player(name, team, is_admin=False):
    with _LOCK:
        data = _load()
        if int(data.get("stage", 0)) >= 4:
            return "赛季已经结束，无法添加选手", None
        name = str(name or "").strip()
        team = str(team or "").strip()
        if not (1 <= len(name) <= 16):
            return "选手名需要 1~16 个字", None
        if team not in _team_names(data):
            return "队伍不存在", None
        if any(p["name"] == name for p in data["players"]):
            return "选手已存在", None
        data["players"].append({"name": name, "team": team})
        _save(data)
        return None, _overview_locked(data, is_admin)


def delete_player(name, is_admin=False):
    with _LOCK:
        data = _load()
        if int(data.get("stage", 0)) >= 4:
            return "赛季已经结束，无法删除选手", None
        name = str(name or "").strip()
        if not any(p["name"] == name for p in data["players"]):
            return "选手不存在", None
        for match in data["matches"]:
            for entry in match.get("entries", []):
                if entry.get("player") == name:
                    return "该选手已有比赛记录，不能删除", None
        data["players"] = [p for p in data["players"] if p["name"] != name]
        _save(data)
        return None, _overview_locked(data, is_admin)


# ==================== 对外快照 ====================

def _overview_locked(data: dict, is_admin: bool, archived: bool = False) -> dict:
    stage = int(data.get("stage", 0))

    stage_tables = {}
    for s in (1, 2, 3):
        if stage != 4 and s > stage:
            break
        stage_tables[str(s)] = {
            "teams": _team_standings(data, s),
            "players": _player_standings(data, s),
        }

    matches = []
    for match in data["matches"]:
        mstage = int(match.get("stage", 0))
        entries = []
        for entry in match.get("entries", []):
            r, g, b = _team_color(data, entry.get("team", ""))
            raw = entry.get("raw")
            entries.append({
                "rank": int(entry.get("rank", 4)),
                "player": entry.get("player", ""),
                "team": entry.get("team", ""),
                "raw": None if raw is None else int(raw),
                "pt": float(entry.get("pt", 0.0)),
                "r": r, "g": g, "b": b,
            })
        matches.append({
            "id": int(match.get("id", 0)),
            "stage": mstage,
            "stage_name": STAGE_MATCH_NAMES.get(mstage, "?"),
            "time": float(match.get("time", 0.0)),
            "entries": entries,
        })

    last_stage = int(data["matches"][-1].get("stage", 0)) if data["matches"] else 0
    payload = {
        "season": int(data.get("season", 1)),
        "stage": stage,
        "stage_name": STAGE_NAMES.get(stage, "?"),
        "archived": bool(archived),
        "is_admin": bool(is_admin) and not archived,
        "teams": [{"name": t["name"], "r": int(t.get("r", 120)),
                   "g": int(t.get("g", 120)), "b": int(t.get("b", 120))}
                  for t in data["teams"]],
        "players": [{"name": p["name"], "team": p["team"]} for p in data["players"]],
        "stage_tables": stage_tables,
        "total_teams": _total_team_standings(data),
        "total_players": _total_player_standings(data),
        "matches": matches,
        "can_undo": (not archived and bool(data["matches"])
                     and last_stage == stage and stage in (1, 2, 3)),
    }
    if not archived:
        payload["seasons"] = _season_numbers(data)
        payload["current_season"] = int(data.get("season", 1))
    return payload


def _season_numbers(data: dict) -> list:
    return sorted({int(s.get("season", 0)) for s in data.get("seasons", [])})


def overview(is_admin: bool = False, season=None) -> dict:
    """season 为 None 时返回当前赛季；传历史赛季号则返回已归档快照。"""
    with _LOCK:
        data = _load()
        numbers = _season_numbers(data)
        if season is not None:
            snap = None
            for item in data.get("seasons", []):
                if int(item.get("season", 0)) == int(season):
                    snap = item
                    break
            if snap is None:
                return None
            payload = _overview_locked(snap, is_admin, archived=True)
        else:
            payload = _overview_locked(data, is_admin, archived=False)
        payload["seasons"] = numbers
        payload["current_season"] = int(data.get("season", 1))
        return payload
