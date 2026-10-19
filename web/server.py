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
if _NEWBOT_DIR not in sys.path:
    sys.path.insert(0, _NEWBOT_DIR)

from config import Config                                            # noqa: E402
from plugins.cat_config import CatConfig                             # noqa: E402
from core.web_auth import make_token, parse_token, verify_password   # noqa: E402

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
_SECRET = Config.WEB_SECRET.encode("utf-8") or os.urandom(32)
_COOKIE_NAME = "cat_token"
_COOKIE_MAX_AGE = 7 * 24 * 60 * 60

app = FastAPI(title="喵喵远征队")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


def _load_players() -> dict:
    """读取全部玩家存档（不存在则视为空）"""
    if not os.path.exists(CatConfig.CAT_PLAYERS_PATH):
        return {}
    with open(CatConfig.CAT_PLAYERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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
        return JSONResponse(
            {"ok": False,
             "msg": "这个 QQ 还没设置网页密码喵，请在 QQ 私聊里发送「喵密码 你的密码」"},
            status_code=403)
    if not verify_password(password, player.get("web_pwd_salt", ""), player["web_pwd_hash"]):
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
