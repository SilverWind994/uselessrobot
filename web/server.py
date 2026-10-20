"""串子小车网页端：登录 + 喵喵远征队 + 小游戏。

启动（在仓库根目录执行）：
    py -3 -m uvicorn web.server:app --host 0.0.0.0 --port 8090

玩家身份 = QQ 号 + 网页密码；密码在 QQ 私聊里用「喵密码 你的密码」设置。
玩家存档沿用 newbot/assets/cat_expedition/players.json。
"""

import json
import os
import sys

from fastapi import Cookie, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_NEWBOT_DIR = os.path.join(_REPO_DIR, "newbot")
_WEB_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (_NEWBOT_DIR, _WEB_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import Config                                            # noqa: E402
from plugins.cat_config import CatConfig                             # noqa: E402
from plugins.yahtzee import (YahtzeePlugin, _WEEKLY_PATH,            # noqa: E402
                             WEEKLY_REWARDS, _save_json)
from core.web_auth import (make_token, parse_token, verify_password,           # noqa: E402
                          check_password_text, hash_password, make_salt)
import cat_web                                                       # noqa: E402
import farkle_web                                                    # noqa: E402
import yahtzee_web                                                   # noqa: E402
import mahjong17_web                                                 # noqa: E402

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
# 麻将牌面素材（mj0.png ~ mj37.png），供 17 步麻将网页版直接引用
_MAHJONG_TILE_DIR = os.path.join(_NEWBOT_DIR, "assets", "mahjong")
_SECRET = Config.WEB_SECRET.encode("utf-8") or os.urandom(32)
_COOKIE_NAME = "cat_token"
_COOKIE_MAX_AGE = 7 * 24 * 60 * 60

app = FastAPI(title="串子小车")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
app.mount("/mahjong", StaticFiles(directory=_MAHJONG_TILE_DIR), name="mahjong")
# 喵喵远征队素材：喵喵立绘 / 职业图标 / 国家旗帜 / 章节插画 / 世界地图（只挂素材目录，不暴露存档）
app.mount("/catexp/cats", StaticFiles(directory=cat_web.CATS_DIR), name="catexp-cats")
app.mount("/catexp/jobs", StaticFiles(directory=cat_web.JOBS_DIR), name="catexp-jobs")
app.mount("/catexp/origins", StaticFiles(directory=cat_web.ORIGINS_DIR), name="catexp-origins")
app.mount("/catexp/expedition", StaticFiles(directory=cat_web.EXPEDITION_IMG_DIR), name="catexp-expedition")
app.mount("/catexp/data", StaticFiles(directory=cat_web.DATA_DIR), name="catexp-data")


@app.middleware("http")
async def _no_cache_static(request, call_next):
    """首页与静态资源始终向浏览器要求校验，避免改版后旧 app.js 被缓存住"""
    resp = await call_next(request)
    path = request.url.path
    if (path == "/" or path.startswith("/static")
            or path.startswith("/api/cat/book") or path.startswith("/api/cat/card")):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def _load_players() -> dict:
    """读取全部玩家存档（不存在则视为空）"""
    if not os.path.exists(CatConfig.CAT_PLAYERS_PATH):
        return {}
    with open(CatConfig.CAT_PLAYERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_players(players: dict) -> None:
    """写回全部玩家存档"""
    os.makedirs(os.path.dirname(CatConfig.CAT_PLAYERS_PATH), exist_ok=True)
    with open(CatConfig.CAT_PLAYERS_PATH, "w", encoding="utf-8") as f:
        json.dump(players, f, ensure_ascii=False, indent=2)


def _player_card(qq: int, player: dict) -> dict:
    """返回给网页的玩家信息（不含任何密码字段）"""
    return {
        "nick": player.get("nick") or "",
        "fish": player.get("fish", 0),
        "eye_stones": player.get("eye_stones", 0),
        "cats": len(player.get("collection", [])),
        "summon_count": player.get("summon_count", 0),
        "signin_total": player.get("signin_total", 0),
        "research_limit": player.get("research_limit", 0),
        # 尚未设置密码时，默认密码就是 QQ 号，登录后需强制改密
        "must_change_pwd": not player.get("web_pwd_hash"),
        # 管理员才会看到「管理」导航页
        "is_admin": Config.is_admin(qq),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


@app.post("/api/login")
def login(payload: dict) -> JSONResponse:
    try:
        qq = int(str(payload.get("qq", "")).strip())
    except ValueError:
        return JSONResponse({"ok": False, "msg": "QQ 号格式不正确喵"}, status_code=400)

    password = str(payload.get("password", ""))
    player = _load_players().get(str(qq))
    if player is None:
        return JSONResponse(
            {"ok": False, "msg": "还没有这个 QQ 的存档喵，先在群里发「喵签到」建档"},
            status_code=404)
    if not player.get("web_pwd_hash"):
        # 还没设过密码：默认密码就是 QQ 号本身，登录后强制跳转改密
        if password != str(qq):
            return JSONResponse(
                {"ok": False, "msg": "QQ 号或密码不对喵（首次登录的默认密码就是你的 QQ 号）"},
                status_code=403)
    elif not verify_password(password, player.get("web_pwd_salt", ""), player["web_pwd_hash"]):
        return JSONResponse({"ok": False, "msg": "QQ 号或密码不对喵"}, status_code=403)

    resp = JSONResponse({"ok": True, "player": _player_card(qq, player)})
    resp.set_cookie(_COOKIE_NAME, make_token(qq, _SECRET), max_age=_COOKIE_MAX_AGE,
                    httponly=True, samesite="lax")
    return resp


@app.post("/api/logout")
def logout() -> JSONResponse:
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(_COOKIE_NAME)
    return resp


@app.get("/api/me")
def me(cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = parse_token(cat_token, _SECRET)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)

    player = _load_players().get(str(qq))
    if player is None:
        return JSONResponse({"ok": False, "msg": "存档不存在喵"}, status_code=404)

    card = _player_card(qq, player)
    card["qq"] = qq
    return JSONResponse({"ok": True, "player": card})


@app.post("/api/change_password")
def change_password(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    """网页端修改密码：需输入原密码；未设密码时原密码即 QQ 号"""
    qq = parse_token(cat_token, _SECRET)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)

    players = _load_players()
    player = players.get(str(qq))
    if player is None:
        return JSONResponse({"ok": False, "msg": "存档不存在喵"}, status_code=404)

    old = str(payload.get("old", ""))
    if player.get("web_pwd_hash"):
        if not verify_password(old, player.get("web_pwd_salt", ""), player["web_pwd_hash"]):
            return JSONResponse({"ok": False, "msg": "原密码不对喵"}, status_code=403)
    elif old != str(qq):
        return JSONResponse(
            {"ok": False, "msg": "原密码不对喵（还没设过密码时，原密码就是你的 QQ 号）"},
            status_code=403)

    new = str(payload.get("new", ""))
    err = check_password_text(new)
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)

    salt = make_salt()
    player["web_pwd_salt"] = salt
    player["web_pwd_hash"] = hash_password(new, salt)
    _save_players(players)
    return JSONResponse({"ok": True, "msg": "密码已更新喵"})


# ==================== Farkle 网页版 ====================

def _auth_qq(cat_token: str):
    """从登录 Cookie 解析 QQ 号，未登录返回 None"""
    return parse_token(cat_token, _SECRET)


def _nick_of(qq: int) -> str:
    player = _load_players().get(str(qq)) or {}
    return player.get("nick") or f"玩家{qq}"


@app.get("/api/farkle/rooms")
def farkle_rooms(cat_token: str = Cookie(default="")) -> JSONResponse:
    if _auth_qq(cat_token) is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    return JSONResponse({"ok": True, "rooms": farkle_web.list_rooms()})


@app.get("/api/farkle/mine")
def farkle_mine(cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    return JSONResponse({"ok": True, "code": farkle_web.my_room(qq)})


@app.post("/api/farkle/create")
def farkle_create(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    code, err = farkle_web.create_room(qq, _nick_of(qq),
                                       payload.get("target"), payload.get("stones"))
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, "code": code})


@app.post("/api/farkle/join")
def farkle_join(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    code = str(payload.get("code", "")).strip()
    err = farkle_web.join_room(code, qq, _nick_of(qq))
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, "code": code})


@app.post("/api/farkle/cancel")
def farkle_cancel(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    err = farkle_web.cancel_room(str(payload.get("code", "")).strip(), qq)
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True})


@app.get("/api/farkle/state")
def farkle_state(code: str, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    room = farkle_web.snapshot(code, qq)
    if room is None:
        return JSONResponse({"ok": False, "msg": "房间不存在或已结束喵"}, status_code=404)
    return JSONResponse({"ok": True, "room": room})


@app.post("/api/farkle/action")
def farkle_action(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    code = str(payload.get("code", "")).strip()
    action = str(payload.get("action", "")).strip()
    err, room = farkle_web.act(code, qq, action, payload)
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, "room": room})


# ==================== 快艇骰子网页版 ====================

@app.get("/api/yahtzee/rooms")
def yahtzee_rooms(cat_token: str = Cookie(default="")) -> JSONResponse:
    if _auth_qq(cat_token) is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    return JSONResponse({"ok": True, "rooms": yahtzee_web.list_rooms()})


@app.get("/api/yahtzee/mine")
def yahtzee_mine(cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    return JSONResponse({"ok": True, "code": yahtzee_web.my_room(qq)})


@app.post("/api/yahtzee/create")
def yahtzee_create(cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    code, err = yahtzee_web.create_room(qq, _nick_of(qq))
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, "code": code})


@app.post("/api/yahtzee/join")
def yahtzee_join(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    code = str(payload.get("code", "")).strip()
    err = yahtzee_web.join_room(code, qq, _nick_of(qq))
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, "code": code})


@app.post("/api/yahtzee/cancel")
def yahtzee_cancel(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    err = yahtzee_web.cancel_room(str(payload.get("code", "")).strip(), qq)
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True})


@app.get("/api/yahtzee/state")
def yahtzee_state(code: str, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    room = yahtzee_web.snapshot(code, qq)
    if room is None:
        return JSONResponse({"ok": False, "msg": "房间不存在或已结束喵"}, status_code=404)
    return JSONResponse({"ok": True, "room": room})


@app.post("/api/yahtzee/action")
def yahtzee_action(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    code = str(payload.get("code", "")).strip()
    action = str(payload.get("action", "")).strip()
    err, room = yahtzee_web.act(code, qq, action, payload)
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, "room": room})


# ==================== 17步麻将网页版 ====================

@app.get("/api/mahjong17/rooms")
def mahjong17_rooms(cat_token: str = Cookie(default="")) -> JSONResponse:
    if _auth_qq(cat_token) is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    return JSONResponse({"ok": True, "rooms": mahjong17_web.list_rooms()})


@app.get("/api/mahjong17/mine")
def mahjong17_mine(cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    return JSONResponse({"ok": True, "code": mahjong17_web.my_room(qq)})


@app.post("/api/mahjong17/create")
def mahjong17_create(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    code, err = mahjong17_web.create_room(qq, _nick_of(qq), payload.get("stones"))
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, "code": code})


@app.post("/api/mahjong17/join")
def mahjong17_join(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    code = str(payload.get("code", "")).strip()
    err = mahjong17_web.join_room(code, qq, _nick_of(qq))
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, "code": code})


@app.post("/api/mahjong17/cancel")
def mahjong17_cancel(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    err = mahjong17_web.cancel_room(str(payload.get("code", "")).strip(), qq)
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True})


@app.get("/api/mahjong17/state")
def mahjong17_state(code: str, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    room = mahjong17_web.snapshot(code, qq)
    if room is None:
        return JSONResponse({"ok": False, "msg": "房间不存在或已结束喵"}, status_code=404)
    return JSONResponse({"ok": True, "room": room})


@app.post("/api/mahjong17/action")
def mahjong17_action(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    code = str(payload.get("code", "")).strip()
    action = str(payload.get("action", "")).strip()
    err, room = mahjong17_web.act(code, qq, action, payload)
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, "room": room})


# ==================== 喵喵远征队（图鉴 / 远征队 / 远征 / 绘图） ====================

@app.get("/api/cat/index")
def cat_index(cat_token: str = Cookie(default="")) -> JSONResponse:
    """图鉴索引：国家表、卡池表、全部喵喵（含本人星级）"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    return JSONResponse({"ok": True, "index": cat_web.cat_index(qq)})


@app.get("/api/cat/detail")
def cat_detail(id: str, cat_token: str = Cookie(default="")) -> JSONResponse:
    """单只喵喵详情（按 id 查询）"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    detail = cat_web.cat_detail(qq, id.strip())
    if detail is None:
        return JSONResponse({"ok": False, "msg": "没有这只喵喵喵"}, status_code=404)
    return JSONResponse({"ok": True, "cat": detail})


@app.get("/api/cat/collection")
def cat_collection(cat_token: str = Cookie(default="")) -> JSONResponse:
    """远征队：本人的基础属性 + 每只喵喵的情况"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    return JSONResponse({"ok": True, "team": cat_web.cat_collection(qq)})


@app.get("/api/expedition/state")
def expedition_state(cat_token: str = Cookie(default="")) -> JSONResponse:
    """当前远征 Boss 情况：血量、奖励、伤害排行"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    state = cat_web.expedition_state(qq)
    if state is None:
        return JSONResponse({"ok": False, "msg": "远征关卡数据异常喵"}, status_code=500)
    return JSONResponse({"ok": True, "state": state})


@app.post("/api/expedition/run")
def expedition_run(cat_token: str = Cookie(default="")) -> JSONResponse:
    """执行一次远征（每人每天一次）"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    lines = cat_web.expedition_run(qq, _nick_of(qq))
    return JSONResponse({"ok": True, "lines": lines, "state": cat_web.expedition_state(qq)})


@app.post("/api/cat/signin")
def cat_signin(cat_token: str = Cookie(default="")) -> JSONResponse:
    """每日签到（复用插件签到逻辑）"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    return JSONResponse({"ok": True, **cat_web.signin(qq)})


@app.post("/api/cat/summon")
def cat_summon(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    """抽卡（复用插件抽卡逻辑）；pool 为空或「全」表示全部卡池"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    err, data = cat_web.summon(qq, payload.get("count", 1), str(payload.get("pool", "")))
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)
    return JSONResponse({"ok": True, **data})


@app.get("/api/cat/book")
def cat_book(code: str, cat_token: str = Cookie(default="")) -> FileResponse:
    """国家图鉴拼图（PIL 合成，含本人收集情况）"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    try:
        path = cat_web.render_book(qq, code.strip().lower())
    except Exception as e:
        return JSONResponse({"ok": False, "msg": f"图鉴图生成失败：{e}"}, status_code=500)
    if path is None:
        return JSONResponse({"ok": False, "msg": "没有这个国家喵"}, status_code=404)
    return FileResponse(path, media_type="image/png")


@app.get("/api/cat/card")
def cat_card(id: str, cat_token: str = Cookie(default="")) -> FileResponse:
    """单只喵喵的队员卡片（PIL 合成；仅本人已拥有的喵喵可出图）"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    try:
        path = cat_web.render_card(qq, id.strip())
    except Exception as e:
        return JSONResponse({"ok": False, "msg": f"详情图生成失败：{e}"}, status_code=500)
    if path is None:
        return JSONResponse({"ok": False, "msg": "这只喵喵还没有解锁喵"}, status_code=404)
    return FileResponse(path, media_type="image/png")


# ==================== 快艇骰子·每周挑战 ====================

# 复用机器人的 YahtzeePlugin（含跨周结算发鱼干）与猫猫插件的 add_fish
_yz_plugin = YahtzeePlugin(cat_web._plugin._sender, cat_plugin=cat_web._plugin)


def _record_weekly(entries: list) -> None:
    """网页端对局结束后：记录各玩家本周的首次分数（同周已有则不覆盖）"""
    weekly = _yz_plugin._ensure_week()
    scores = weekly.setdefault("scores", {})
    changed = False
    for item in entries:
        key = str(item["qq"])
        if key not in scores:
            scores[key] = {"name": item["name"], "score": item["score"]}
            changed = True
    if changed:
        _save_json(_WEEKLY_PATH, weekly)


yahtzee_web.set_weekly_recorder(_record_weekly)


@app.get("/api/yahtzee/weekly")
def yahtzee_weekly(cat_token: str = Cookie(default="")) -> JSONResponse:
    """快艇骰子本周排行榜（每位玩家只计本周首次分数）"""
    if _auth_qq(cat_token) is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    weekly = _yz_plugin._ensure_week()
    scores = weekly.get("scores") or {}
    ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)[:10]
    ranks = [{
        "name": info["name"],
        "score": info["score"],
        "reward": WEEKLY_REWARDS[i] if i < len(WEEKLY_REWARDS) else 0,
    } for i, (_, info) in enumerate(ranked)]
    return JSONResponse({"ok": True, "week": weekly.get("week", ""), "ranks": ranks})


# ==================== 个人中心 / 管理员 ====================

def _check_nick(nick: str) -> str:
    """校验昵称是否合法，返回错误提示（合法时为空串）"""
    if not nick:
        return "昵称不能为空喵"
    if len(nick) > 16:
        return "昵称最多 16 个字喵"
    if any(c in nick for c in "\r\n"):
        return "昵称不能包含换行喵"
    return ""


@app.post("/api/profile/rename")
def profile_rename(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    """修改自己的昵称（只改玩家存档里的 nick 字段）"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)

    nick = str(payload.get("nick", "")).strip()
    err = _check_nick(nick)
    if err:
        return JSONResponse({"ok": False, "msg": err}, status_code=400)

    players = _load_players()
    player = players.get(str(qq))
    if player is None:
        return JSONResponse({"ok": False, "msg": "存档不存在喵"}, status_code=404)

    player["nick"] = nick
    _save_players(players)
    return JSONResponse({"ok": True, "nick": nick, "msg": "改名成功喵"})


@app.post("/api/admin/create_user")
def admin_create_user(payload: dict, cat_token: str = Cookie(default="")) -> JSONResponse:
    """管理员在网页端为新 QQ 开一份空白存档（默认密码即该 QQ 号，首次登录强制改密）"""
    qq = _auth_qq(cat_token)
    if qq is None:
        return JSONResponse({"ok": False, "msg": "未登录喵"}, status_code=401)
    if not Config.is_admin(qq):
        return JSONResponse({"ok": False, "msg": "只有管理员能在网页开新档喵"}, status_code=403)

    try:
        new_qq = int(str(payload.get("qq", "")).strip())
    except ValueError:
        return JSONResponse({"ok": False, "msg": "QQ 号格式不正确喵"}, status_code=400)
    if new_qq <= 0:
        return JSONResponse({"ok": False, "msg": "QQ 号格式不正确喵"}, status_code=400)

    nick = str(payload.get("nick", "")).strip()
    if nick:
        err = _check_nick(nick)
        if err:
            return JSONResponse({"ok": False, "msg": err}, status_code=400)

    if str(new_qq) in _load_players():
        return JSONResponse({"ok": False, "msg": "这个 QQ 已经有存档了喵"}, status_code=400)

    # 复用远征队插件的建档逻辑，保证与机器人端存档结构完全一致
    player = cat_web._plugin._get_player(new_qq)
    if nick:
        player["nick"] = nick
        cat_web._plugin._update_player(new_qq, player)
    return JSONResponse({"ok": True, "msg": f"已创建 {new_qq} 的存档喵，默认密码就是该 QQ 号"})
