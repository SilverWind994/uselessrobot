"""喵喵远征队网页端：登录 + 主页。

启动（在仓库根目录执行）：
    py -3 -m uvicorn web.server:app --host 0.0.0.0 --port 8090

玩家身份 = QQ 号 + 网页密码；密码在 QQ 私聊里用「喵密码 你的密码」设置。
玩家存档沿用 newbot/assets/cat_expedition/players.json，本服务目前只读。
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
from core.web_auth import (make_token, parse_token, verify_password,           # noqa: E402
                          check_password_text, hash_password, make_salt)
import farkle_web                                                    # noqa: E402
import yahtzee_web                                                   # noqa: E402
import mahjong17_web                                                 # noqa: E402

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
# 麻将牌面素材（mj0.png ~ mj37.png），供 17 步麻将网页版直接引用
_MAHJONG_TILE_DIR = os.path.join(_NEWBOT_DIR, "assets", "mahjong")
_SECRET = Config.WEB_SECRET.encode("utf-8") or os.urandom(32)
_COOKIE_NAME = "cat_token"
_COOKIE_MAX_AGE = 7 * 24 * 60 * 60

app = FastAPI(title="喵喵远征队")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
app.mount("/mahjong", StaticFiles(directory=_MAHJONG_TILE_DIR), name="mahjong")


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


def _player_card(player: dict) -> dict:
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

    resp = JSONResponse({"ok": True, "player": _player_card(player)})
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

    card = _player_card(player)
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
