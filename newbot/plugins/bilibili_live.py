"""B 站开播 / 下播提醒。

轮询订阅列表里的直播间，状态从「未开播」变成「直播中」时通知订阅者，反向变化时同样提醒。
每个直播间可以单独配置接收方（群 / 私聊 QQ）和推送内容（主播、标题、链接、开播时间、下播提醒）。

订阅只存在 assets/bilibili_live_subs.json（启动时自动创建，运行时数据，不入库），
不再读 config 里的房间号/通知 QQ。

指令（只有 BILIBILI_LIVE_ADMIN_QQ 能用，其他人触发会被静默忽略，不会暴露订阅内容）：
    直播提醒                        查看订阅：群里只看本群订的，私聊看全部
    直播提醒 添加房间 <房间号>        在当前群/私聊新建订阅，开播发到这里
    直播提醒 移除房间 <房间号>        取消整个直播间的订阅

开播状态落在 assets/bilibili_live.json，拉取失败、风控返回码、每次提醒都写到
assets/bilibili_live.log（超过 1MB 轮转）。

配置项（写进 newbot/config_local.py，该文件已在 .gitignore 中忽略）：
    BILIBILI_LIVE_ADMIN_QQ = 2544910201       # 唯一能用「直播提醒」指令的 QQ
    BILIBILI_LIVE_POLL_SECONDS = 60           # 轮询间隔（秒）
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Optional

import requests

from config import Config
from core.command_router import CommandContext, CommandRouter
from core.message_sender import MessageSender, Target

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
_STATE_PATH = os.path.join(_BASE_DIR, "assets", "bilibili_live.json")
_SUBS_PATH = os.path.join(_BASE_DIR, "assets", "bilibili_live_subs.json")
_LOG_PATH = os.path.join(_BASE_DIR, "assets", "bilibili_live.log")
_LOG_MAX_BYTES = 1000 * 1000   # 超过 1MB 轮转成 bilibili_live.log.1

FETCH_TIMEOUT = 10           # 单次请求超时（秒）
_ROOM_INFO_URL = "https://api.live.bilibili.com/room/v1/Room/get_info"
_ANCHOR_URL = "https://api.live.bilibili.com/live_user/v1/UserInfo/get_anchor_in_room"
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Referer": "https://live.bilibili.com/",
}

# 推送内容开关：默认只在开播时发主播、标题、链接和下播提醒
DEFAULT_OPTIONS = {
    "anchor": True,    # 主播昵称
    "title": True,     # 直播标题
    "link": True,      # 直播间链接
    "time": False,     # 开播时间
    "offline": True,   # 是否也推送下播提醒
}
OPTION_LABELS = {
    "anchor": "主播",
    "title": "标题",
    "link": "链接",
    "time": "开播时间",
    "offline": "下播提醒",
}


def _read_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_state() -> dict:
    data = _read_json(_STATE_PATH)
    if not isinstance(data, dict):
        return {"rooms": {}}
    data.setdefault("rooms", {})
    return data


def _save_state(state: dict) -> None:
    _write_json(_STATE_PATH, state)


def _load_subs() -> Optional[dict]:
    """返回 None 表示文件不存在（需要从旧配置迁移）"""
    data = _read_json(_SUBS_PATH)
    if not isinstance(data, dict):
        return None
    rooms = data.get("rooms")
    if not isinstance(rooms, dict):
        rooms = {}
    data["rooms"] = {str(k): _normalize_room(v) for k, v in rooms.items()}
    return data


def _save_subs(subs: dict) -> None:
    _write_json(_SUBS_PATH, subs)


def _normalize_room(entry) -> dict:
    """补全单个直播间的订阅结构，容忍手改 JSON 时的缺字段"""
    entry = entry if isinstance(entry, dict) else {}
    groups, users = [], []
    for value in entry.get("groups") or []:
        try:
            groups.append(int(value))
        except (TypeError, ValueError):
            continue
    for value in entry.get("users") or []:
        try:
            users.append(int(value))
        except (TypeError, ValueError):
            continue
    options = dict(DEFAULT_OPTIONS)
    raw_options = entry.get("options")
    if isinstance(raw_options, dict):
        for key in DEFAULT_OPTIONS:
            if key in raw_options:
                options[key] = bool(raw_options[key])
    return {
        "groups": sorted(set(groups)),
        "users": sorted(set(users)),
        "options": options,
    }


def _log(text: str) -> None:
    """同时写到控制台和 assets/bilibili_live.log，超过 1MB 轮转一次"""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [bilibili_live] {text}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        if os.path.exists(_LOG_PATH) and os.path.getsize(_LOG_PATH) > _LOG_MAX_BYTES:
            os.replace(_LOG_PATH, _LOG_PATH + ".1")
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _parse_live_time(value) -> int:
    """live_time 可能是时间戳、日期字符串，未开播时是 '0000-00-00 00:00:00'"""
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    try:
        stamp = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return 0
    return int(stamp.timestamp()) if stamp.year > 1970 else 0


class BilibiliLivePlugin:
    """B 站开播 / 下播提醒"""

    def __init__(self, sender: MessageSender):
        self._sender = sender
        self._lock = threading.Lock()
        self._state = _load_state()
        subs = _load_subs()
        if subs is None:
            subs = {"rooms": {}}
            _save_subs(subs)   # 启动就落盘，方便直接查看/手改
        self._subs = subs
        self._rooms = self._room_ids()

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["喵直播", "直播提醒", "bili"],
            self.cmd_live,
            description="[隐藏]B 站开播/下播提醒：按直播间配置接收群、接收人与推送内容"
        )
        self._start_scheduler()

    # ==================== 订阅数据 ====================

    def _room_ids(self) -> list:
        with self._lock:
            rooms = list((self._subs.get("rooms") or {}).keys())
        return sorted(room for room in rooms if str(room).isdigit())

    def _get_room(self, room_id: str) -> Optional[dict]:
        with self._lock:
            entry = (self._subs.get("rooms") or {}).get(room_id)
            return entry

    def _save(self) -> None:
        with self._lock:
            _save_subs(self._subs)

    # ==================== 定时轮询 ====================

    def _start_scheduler(self) -> None:
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self) -> None:
        while True:
            try:
                self._check_once()
            except Exception as e:
                _log(f"poll error: {e}")
            seconds = int(getattr(Config, "BILIBILI_LIVE_POLL_SECONDS", 60) or 60)
            time.sleep(max(20, seconds))

    def _fetch_room(self, room_id: str) -> Optional[dict]:
        """拉取直播间状态；直播中为 True，轮播与未开播都算 False"""
        try:
            resp = requests.get(_ROOM_INFO_URL, params={"room_id": room_id},
                                headers=_HEADERS, timeout=FETCH_TIMEOUT)
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            _log(f"fetch {room_id} failed: {e}")
            return None
        if data.get("code") != 0:
            _log(f"fetch {room_id} code={data.get('code')}")
            return None
        info = data.get("data") or {}
        status = int(info.get("live_status", 0) or 0)
        return {
            "live": status == 1,
            "title": str(info.get("title") or ""),
            "uid": int(info.get("uid", 0) or 0),
            "room_id": str(info.get("room_id") or room_id),
            "live_time": _parse_live_time(info.get("live_time")),
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
        self._rooms = self._room_ids()
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
            try:
                info = self._fetch_room(room_id)
            except Exception as e:   # 单个房间异常不影响其他房间
                _log(f"fetch {room_id} error: {e}")
                continue
            if not info:
                continue
            was = old.get("live")
            now = info["live"]
            name = old.get("name") or ""
            if not name:
                name = self._anchor_name(room_id)   # 昵称缺失才取，取到后一直复用
            if was is not None and was != now:
                _log(f"room {room_id} live {was} -> {now}")
            if now and was is False:
                self._notify_room(room_id, "start", info, name)
            elif was is True and not now:
                info["title"] = info["title"] or old.get("title") or ""
                info["live_time"] = old.get("live_time") or 0
                self._notify_room(room_id, "end", info, name)
            with self._lock:
                entry = self._state.setdefault("rooms", {}).setdefault(room_id, {})
                entry.update(info)
                if name:
                    entry["name"] = name
                changed = True
        if changed:
            with self._lock:
                _save_state(self._state)

    # ==================== 消息组装与发送 ====================

    def _format(self, kind: str, info: dict, name: str, options: dict) -> str:
        room_id = str(info.get("room_id") or "")
        title_name = name or f"直播间 {room_id}"
        link = f"https://live.bilibili.com/{room_id}"
        if kind == "start":
            lines = ["【B站开播】" + (title_name if options.get("anchor") else "有主播开播了")]
            if options.get("title") and info.get("title"):
                lines.append(f"标题：{info['title']}")
            if options.get("time"):
                start_at = info.get("live_time") or 0
                stamp = time.strftime("%m-%d %H:%M", time.localtime(start_at)) if start_at else "刚刚"
                lines.append(f"开播时间：{stamp}")
            if options.get("link"):
                lines.append(link)
        else:
            lines = ["【B站下播】" + (title_name if options.get("anchor") else "一场直播结束了")]
            lines.append("本次直播已结束")
            if options.get("link"):
                lines.append(link)
        return "\n".join(line for line in lines if line.strip())

    def _notify_room(self, room_id: str, kind: str, info: dict, name: str) -> tuple:
        """把消息发给该直播间配置的群和私聊，返回 (群数, 人数)"""
        room = self._get_room(room_id)
        if not room:
            return (0, 0)
        options = room.get("options") or dict(DEFAULT_OPTIONS)
        if kind == "end" and not options.get("offline", True):
            return (0, 0)
        text = self._format(kind, info, name, options)
        groups = list(room.get("groups") or [])
        users = list(room.get("users") or [])
        if not groups and not users:
            _log(f"room {room_id} no subscriber, skip {kind}")
            return (0, 0)
        for group_id in groups:
            at_all = kind == "start" and self._can_at_all(group_id)
            self._send(Target(user_id=0, group_id=group_id, is_group=True), text,
                       f"群 {group_id}", at_all=at_all)
        for user_id in users:
            self._send(Target(user_id=user_id), text, f"私聊 {user_id}")
        return (len(groups), len(users))

    def _can_at_all(self, group_id: int) -> bool:
        """机器人是群主/管理员才能 @全体，查不到就当没权限"""
        bot_qq = int(getattr(Config, "BOT_QQ", 0) or 0)
        if not bot_qq:
            return False
        try:
            resp = self._sender.get_group_member_info(group_id, bot_qq)
            if resp is None:
                return False
            data = resp.json() or {}
        except Exception as e:
            _log(f"check role in {group_id} failed: {e}")
            return False
        role = str((data.get("data") or {}).get("role") or "")
        return role in ("owner", "admin")

    def _send(self, target: Target, text: str, label: str, at_all: bool = False) -> None:
        head = text.splitlines()[0]
        resp = self._sender.send_text(target, text, at_all=at_all)
        if resp is None:
            _log(f"notify {label} failed: no response | {head}")
            return
        body = (resp.text or "").replace("\n", " ")[:160]
        _log(f"notify {label} [{resp.status_code}] {head} | {body}")

    # ==================== QQ 指令 ====================

    def cmd_live(self, ctx: CommandContext) -> None:
        # 只有指定管理员能用：其他人连订阅列表都看不到，直接静默忽略
        if not self._is_owner(ctx):
            _log(f"ignore command from {ctx.user_id} in {ctx.message_type or 'unknown'}")
            return

        parts = ctx.get_args().split()
        action = parts[0] if parts else ""
        rest = parts[1:]

        if action in ("", "列表", "查看", "订阅"):
            self._show_list(ctx)
            return
        if action in ("帮助", "help", "?"):
            self._show_help(ctx)
            return

        if action in ("添加房间", "新增房间"):
            self._add_room(ctx, rest)
        elif action in ("移除房间", "删除房间", "取消房间"):
            self._remove_room(ctx, rest)
        else:
            self._show_help(ctx)

    def _show_help(self, ctx: CommandContext) -> None:
        self._sender.reply(ctx, "\n".join([
            "开播提醒用法：",
            "直播提醒 —— 查看订阅（群里只看本群，私聊看全部）",
            "直播提醒 添加房间 <房间号>",
            "直播提醒 移除房间 <房间号>",
            "改订阅只有指定管理员可用；新建订阅默认发给当前会话。",
            "数据文件：newbot/assets/bilibili_live_subs.json",
        ]))

    def _show_list(self, ctx: CommandContext) -> None:
        scoped = ctx.is_group
        group_id = int(ctx.group_id) if scoped else 0
        with self._lock:
            state = dict(self._state.get("rooms") or {})
            rooms = dict(self._subs.get("rooms") or {})
        entries = []
        for room_id in sorted(rooms):
            entry = _normalize_room(rooms[room_id])
            if scoped and group_id not in entry["groups"]:
                continue
            entries.append((room_id, entry))
        if not entries:
            if scoped:
                self._sender.reply(ctx, "本群还没订阅任何直播间喵。"
                                        "发「直播提醒 添加房间 房间号」可以把直播间订阅到本群。")
            else:
                self._sender.reply(ctx, "还没订阅任何直播间喵。"
                                        "发「直播提醒 添加房间 房间号」在当前会话新建一个订阅。")
            return
        head = (f"本群订阅的直播间（{len(entries)} 个）：" if scoped
                else f"开播提醒订阅（{len(entries)} 个直播间）：")
        lines = [head]
        for room_id, entry in entries:
            info = state.get(room_id) or {}
            name = info.get("name") or ""
            status = "直播中" if info.get("live") else "未开播"
            groups = entry.get("groups") or []
            users = entry.get("users") or []
            options = entry.get("options") or dict(DEFAULT_OPTIONS)
            label = f"{name}（{room_id}）" if name else f"直播间 {room_id}"
            lines.append(f"· {label}｜{status}")
            if scoped:
                lines.append(f"  群：{group_id}（本群）")
            else:
                lines.append("  群：" + ("、".join(str(g) for g in groups) if groups else "无"))
                lines.append("  人：" + ("、".join(str(u) for u in users) if users else "无"))
            on = [OPTION_LABELS[k] for k in DEFAULT_OPTIONS if options.get(k)]
            off = [OPTION_LABELS[k] for k in DEFAULT_OPTIONS if not options.get(k)]
            lines.append("  推送：" + "/".join(on) + (f"（关：{'/'.join(off)}）" if off else ""))
        if not scoped:
            lines.append("数据文件：newbot/assets/bilibili_live_subs.json")
        self._sender.reply(ctx, "\n".join(lines))

    # ---------- 各种修改 ----------

    def _add_room(self, ctx: CommandContext, rest: list) -> None:
        room_id = self._pick_room_arg(ctx, rest)
        if not room_id:
            return
        key = "groups" if ctx.is_group else "users"
        target = int(ctx.group_id) if ctx.is_group else int(ctx.user_id)
        where = f"本群 {target}" if ctx.is_group else f"你的私聊 {target}"
        with self._lock:
            rooms = self._subs.setdefault("rooms", {})
            entry = _normalize_room(rooms.get(room_id))
            exists = target in entry[key]
            if not exists:
                entry[key] = sorted(entry[key] + [target])
                rooms[room_id] = entry
        if exists:
            self._sender.reply(ctx, f"直播间 {room_id} 已经会发到 {where} 了。")
            return
        self._save()
        self._sender.reply(ctx, f"已订阅直播间 {room_id}，开播会发到{where}。")

    def _remove_room(self, ctx: CommandContext, rest: list) -> None:
        room_id = self._pick_room_arg(ctx, rest, must_exist=True)
        if not room_id:
            return
        with self._lock:
            (self._subs.get("rooms") or {}).pop(room_id, None)
        self._save()
        self._sender.reply(ctx, f"已取消直播间 {room_id} 的全部提醒。")

    # ---------- 解析小工具 ----------

    @staticmethod
    def _is_owner(ctx: CommandContext) -> bool:
        """只有 BILIBILI_LIVE_ADMIN_QQ 能改订阅"""
        try:
            owner = int(getattr(Config, "BILIBILI_LIVE_ADMIN_QQ", 0) or 0)
            return owner != 0 and int(ctx.user_id or 0) == owner
        except (TypeError, ValueError):
            return False

    def _pick_room_arg(self, ctx: CommandContext, rest: list, must_exist: bool = False):
        if not rest or not str(rest[0]).isdigit():
            self._sender.reply(ctx, "要带上直播间号（数字，不是 UID）喵，例如："
                                    "直播提醒 添加房间 123456")
            return None
        room_id = str(rest[0])
        if must_exist and not self._get_room(room_id):
            self._sender.reply(ctx, f"直播间 {room_id} 还没订阅，先用「添加房间」建一个。")
            return None
        return room_id
