"""B 站开播 / 下播提醒。

轮询 config_local.py 里配置的直播间，状态从「未开播」变成「直播中」时私聊通知，反向变化时同样提醒。
上次状态落在 assets/bilibili_live.json（运行时数据，不入库），重启不会重复播报，也不会漏掉停机期间的变化。

配置项（写进 newbot/config_local.py，该文件已在 .gitignore 中忽略）：
    BILIBILI_LIVE_NOTIFY_QQ = 2544910201      # 提醒发往的 QQ（私聊）
    BILIBILI_LIVE_ROOMS = [123456, 654321]    # 要盯的直播间号（房间号，不是 UID）
    BILIBILI_LIVE_POLL_SECONDS = 60           # 轮询间隔（秒）
"""

import json
import os
import threading
import time
from typing import Optional

import requests

from config import Config
from core.command_router import CommandContext, CommandRouter
from core.message_sender import MessageSender, Target

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
_STATE_PATH = os.path.join(_BASE_DIR, "assets", "bilibili_live.json")

FETCH_TIMEOUT = 10           # 单次请求超时（秒）
_ROOM_INFO_URL = "https://api.live.bilibili.com/room/v1/Room/get_info"
_ANCHOR_URL = "https://api.live.bilibili.com/live_user/v1/UserInfo/get_anchor_in_room"
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Referer": "https://live.bilibili.com/",
}


def _load_state() -> dict:
    if not os.path.exists(_STATE_PATH):
        return {"rooms": {}}
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"rooms": {}}
    if not isinstance(data, dict):
        return {"rooms": {}}
    data.setdefault("rooms", {})
    return data


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


class BilibiliLivePlugin:
    """B 站开播 / 下播提醒"""

    def __init__(self, sender: MessageSender):
        self._sender = sender
        self._lock = threading.Lock()
        self._state = _load_state()
        self._rooms = [
            str(room).strip()
            for room in (getattr(Config, "BILIBILI_LIVE_ROOMS", None) or [])
            if str(room).strip().isdigit()
        ]

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["喵直播", "直播提醒", "bili"],
            self.cmd_live,
            description="B 站开播/下播提醒：查看订阅与测试通知"
        )
        self._start_scheduler()

    # ==================== 定时轮询 ====================

    def _start_scheduler(self) -> None:
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self) -> None:
        while True:
            try:
                self._check_once()
            except Exception as e:
                print(f"[bilibili_live] poll error: {e}")
            seconds = int(getattr(Config, "BILIBILI_LIVE_POLL_SECONDS", 60) or 60)
            time.sleep(max(20, seconds))

    def _fetch_room(self, room_id: str) -> Optional[dict]:
        """拉取直播间状态；直播中为 True，轮播与未开播都算 False"""
        try:
            resp = requests.get(_ROOM_INFO_URL, params={"room_id": room_id},
                                headers=_HEADERS, timeout=FETCH_TIMEOUT)
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            print(f"[bilibili_live] fetch {room_id} failed: {e}")
            return None
        if data.get("code") != 0:
            print(f"[bilibili_live] fetch {room_id} code={data.get('code')}")
            return None
        info = data.get("data") or {}
        status = int(info.get("live_status", 0) or 0)
        return {
            "live": status == 1,
            "title": str(info.get("title") or ""),
            "uid": int(info.get("uid", 0) or 0),
            "room_id": str(info.get("room_id") or room_id),
        }

    def _anchor_name(self, room_id: str) -> str:
        """取主播昵称，取不到就返回空串"""
        try:
            resp = requests.get(_ANCHOR_URL, params={"roomid": room_id},
                                headers=_HEADERS, timeout=FETCH_TIMEOUT)
            info = (resp.json().get("data") or {}).get("info") or {}
            return str(info.get("uname") or "")
        except (requests.RequestException, ValueError):
            return ""

    def _check_once(self) -> None:
        if not self._rooms:
            return
        with self._lock:
            rooms = dict(self._state.get("rooms") or {})
            keep = {room_id: entry for room_id, entry in rooms.items()
                    if room_id in self._rooms}
            if keep != rooms:
                self._state["rooms"] = keep
                _save_state(self._state)
            rooms = keep
        changed = False
        for room_id in self._rooms:
            old = rooms.get(room_id) or {}
            info = self._fetch_room(room_id)
            if not info:
                continue
            was = old.get("live")
            now = info["live"]
            name = old.get("name") or ""
            if now and was is False:
                name = name or self._anchor_name(room_id)
                self._notify(
                    f"【B站开播】{name or ('直播间 ' + room_id)}\n"
                    f"{info['title'] or '（无标题）'}\n"
                    f"https://live.bilibili.com/{info['room_id']}")
            elif was is True and not now:
                self._notify(
                    f"【B站下播】{name or ('直播间 ' + room_id)}\n"
                    f"上次的直播已结束\n"
                    f"https://live.bilibili.com/{info['room_id']}")
            with self._lock:
                entry = self._state.setdefault("rooms", {}).setdefault(room_id, {})
                entry.update(info)
                if name:
                    entry["name"] = name
                changed = True
        if changed:
            with self._lock:
                _save_state(self._state)

    def _notify(self, text: str) -> None:
        qq = int(getattr(Config, "BILIBILI_LIVE_NOTIFY_QQ", 2544910201) or 2544910201)
        self._sender.send_text(Target(user_id=qq), text)

    # ==================== QQ 指令 ====================

    def cmd_live(self, ctx: CommandContext) -> None:
        args = ctx.get_args().strip().lower()
        if args in ("测试", "test"):
            self._notify("【B站提醒测试】这条能收到，就说明私聊通道没问题喵")
            qq = int(getattr(Config, "BILIBILI_LIVE_NOTIFY_QQ", 2544910201) or 2544910201)
            self._sender.reply(ctx, f"已尝试私聊 {qq}，收到就说明通道正常")
            return
        self._show_list(ctx)

    def _show_list(self, ctx: CommandContext) -> None:
        qq = int(getattr(Config, "BILIBILI_LIVE_NOTIFY_QQ", 2544910201) or 2544910201)
        if not self._rooms:
            self._sender.reply(
                ctx, "还没配置直播间喵。在 newbot/config_local.py 里填 "
                     "BILIBILI_LIVE_ROOMS = [房间号, ...]，重启后开播下播会私聊通知 "
                     f"{qq}")
            return
        with self._lock:
            rooms = dict(self._state.get("rooms") or {})
        lines = [f"已配置 {len(self._rooms)} 个直播间（提醒发往 {qq}）："]
        for room_id in self._rooms:
            entry = rooms.get(room_id) or {}
            name = entry.get("name") or f"直播间 {room_id}"
            state = "直播中" if entry.get("live") else "未开播"
            title = entry.get("title") or ""
            lines.append(f"· {name}（{room_id}）｜{state}"
                         + (f"｜{title}" if title else ""))
        lines.append("改订阅请编辑 newbot/config_local.py 的 BILIBILI_LIVE_ROOMS")
        self._sender.reply(ctx, "\n".join(lines))
