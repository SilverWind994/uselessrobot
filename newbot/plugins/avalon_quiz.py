import json
import os
import re
from datetime import datetime

import requests

from config import Config
from core.command_router import CommandContext, CommandRouter
from core.message_sender import MessageSender, Target


def _ensure_dirs():
    os.makedirs(Config.AVALON_DIR, exist_ok=True)


def _load_data() -> dict:
    _ensure_dirs()
    if not os.path.exists(Config.AVALON_DATA_PATH):
        return {}
    with open(Config.AVALON_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_data(data: dict) -> None:
    _ensure_dirs()
    with open(Config.AVALON_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_time(s):
    """解析时间字符串，支持 None 和空字符串，返回 datetime 或 None"""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _format_duration(seconds: float) -> str:
    """秒数转中文时长，如 125.3 -> 2分5秒"""
    if seconds < 0:
        seconds = 0
    sec = int(seconds)
    if sec < 60:
        return f"{sec}秒"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m}分{s}秒"
    h, m = divmod(m, 60)
    return f"{h}小时{m}分{s}秒"


_IMAGE_CQ_RE = re.compile(r"\[CQ:image,[^\]]*\]")
_IMAGE_URL_RE = re.compile(r"url=([^,\]]+)")


def _extract_image_url(raw_message: str):
    """从消息里提取第一张图片的 URL（CQ 码），没有图片返回 None"""
    cq = _IMAGE_CQ_RE.search(raw_message)
    if not cq:
        return None
    m = _IMAGE_URL_RE.search(cq.group(0))
    return m.group(1) if m else None


class AvalonQuizPlugin:
    """何切阿瓦隆：出题人发图出题，其他人看题并作答，记录答题情况"""

    def __init__(self, sender: MessageSender):
        self._sender = sender
        self._pending = None  # 出题人发完「出题」后等待其发送题目图片：{"user_id":..., "target":...}
        self._data = _load_data()

    # ==================== 注册命令 ====================

    # 子指令别名表：何切阿瓦隆 <子指令> [内容]
    _SUB_ALIASES = {
        "帮助": "help", "help": "help",
        "出题": "create",
        "取消": "cancel", "取消出题": "cancel",
        "看题": "show",
        "答题": "answer",
        "答题情况": "status", "情况": "status",
    }

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["何切阿瓦隆", "何切"],
            self.cmd_entry,
            description="何切阿瓦隆·问答（子指令：出题/看题/答题/答题情况/取消）"
        )

    def cmd_entry(self, ctx: CommandContext) -> None:
        """单一入口：解析子指令并分发"""
        args = ctx.get_args().strip()
        parts = args.split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        action = self._SUB_ALIASES.get(sub)
        if action is None:
            if sub:
                self._sender.reply(ctx, f"未知的子指令「{sub}」，发送「何切阿瓦隆」查看玩法")
            else:
                self.cmd_help(ctx)
            return
        if action == "help":
            self.cmd_help(ctx)
        elif action == "create":
            self.cmd_create(ctx)
        elif action == "cancel":
            self.cmd_cancel(ctx)
        elif action == "show":
            self.cmd_show(ctx)
        elif action == "answer":
            self.cmd_answer(ctx, rest)
        elif action == "status":
            self.cmd_status(ctx)

    # ==================== 消息钩子（捕获出题图片） ====================

    def handle_message(self, ctx: CommandContext) -> bool:
        """主循环在指令路由前调用。出题人处于待发图状态时，拦截其含图消息作为题目。
        返回 True 表示消息已被消费。"""
        if not self._pending:
            return False
        if ctx.user_id != self._pending["user_id"]:
            return False
        url = _extract_image_url(ctx.raw_message)
        if url is None:
            return False  # 不是图片，放行走正常流程
        self._pending = None
        self._set_question(ctx, url)
        return True

    # ==================== 内部逻辑 ====================

    def _set_question(self, ctx: CommandContext, url: str) -> None:
        target = Target.from_data(ctx.raw_data)
        data = self._data

        # 优先下载到本地，失败则回退用 URL 发送
        image_path = ""
        try:
            resp = requests.get(url, timeout=15,
                                headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            with open(Config.AVALON_QUESTION_IMG, "wb") as f:
                f.write(resp.content)
            image_path = Config.AVALON_QUESTION_IMG
        except Exception as e:
            print(f"[AvalonQuiz] 题目图片下载失败，改用链接记录: {e}")

        data["current"] = {
            "image_path": image_path,
            "image_url": url,
            "setter_id": ctx.user_id,
            "setter_name": ctx.sender_nickname,
            "set_time": _now(),
            "viewers": {},   # qq(str) -> {"name":..., "view_time":...} 首次看题时间
            "answers": [],   # {"user_id":..., "name":..., "answer":..., "answer_time":..., "view_time":...}
        }
        _save_data(data)
        self._sender.reply(ctx, "📝 何切阿瓦隆新题目已发布！"
                                "发送「看题」查看题目，「答题 + 你的答案」参与作答")

    def _get_current(self) -> dict | None:
        return self._data.get("current")

    def _question_image_target(self, q: dict, target: Target) -> None:
        """把题目图片发给 target：本地文件优先（转 file:// URI），回退 URL"""
        path = q.get("image_path") or ""
        if path and os.path.exists(path):
            # NapCat/OneBot 要求本地文件用 file:/// URI
            uri = "file:///" + os.path.abspath(path).replace("\\", "/")
            self._sender.send_image(target, uri)
        else:
            self._sender.send_image(target, q.get("image_url", ""))

    # ==================== 命令实现 ====================

    def cmd_help(self, ctx: CommandContext) -> None:
        self._sender.reply(
            ctx,
            "🎴 何切阿瓦隆 · 问答玩法\n"
            "出题：何切阿瓦隆 出题 → 发送一张题目图片（仅出题人）\n"
            "看题：何切阿瓦隆 看题（记录首次看题时间）\n"
            "答题：何切阿瓦隆 答题 + 答案（例：何切阿瓦隆 答题 打6筒）\n"
            "情况：何切阿瓦隆 答题情况（仅出题人）\n"
            "取消：何切阿瓦隆 取消出题（出题人取消待发图状态）"
        )

    def cmd_create(self, ctx: CommandContext) -> None:
        if ctx.user_id not in Config.AVALON_SETTERS:
            self._sender.reply(ctx, "只有出题人才能出题哦~")
            return
        # 指令本身带图则直接发布
        url = _extract_image_url(ctx.raw_message)
        if url:
            self._set_question(ctx, url)
            return
        self._pending = {"user_id": ctx.user_id}
        self._sender.reply(ctx, "请发送本题的题目图片（发送「何切阿瓦隆 取消出题」可取消）")

    def cmd_cancel(self, ctx: CommandContext) -> None:
        if ctx.user_id not in Config.AVALON_SETTERS:
            self._sender.reply(ctx, "只有出题人才能取消出题哦~")
            return
        if not self._pending:
            self._sender.reply(ctx, "当前没有等待发送的出题图片~")
            return
        self._pending = None
        self._sender.reply(ctx, "已取消本次出题")

    def cmd_show(self, ctx: CommandContext) -> None:
        q = self._get_current()
        if not q:
            self._sender.reply(ctx, "当前没有题目，等待出题人出题~")
            return
        self._question_image_target(q, Target.from_data(ctx.raw_data))
        viewers = q.setdefault("viewers", {})
        key = str(ctx.user_id)
        if key not in viewers:
            viewers[key] = {"name": ctx.sender_nickname, "view_time": _now()}
            _save_data(self._data)
            self._sender.reply(ctx, f"已记录 {ctx.sender_nickname} 的看题时间，祝你顺利！")
        else:
            self._sender.reply(ctx, "这是当前题目，加油！")

    def cmd_answer(self, ctx: CommandContext, answer: str) -> None:
        q = self._get_current()
        if not q:
            self._sender.reply(ctx, "当前没有题目，无法作答~")
            return
        # 去掉答案里误带的 CQ 码
        answer = re.sub(r"\[CQ:[^\]]+\]", "", answer).strip()
        if not answer:
            self._sender.reply(ctx, "请在「答题」后附上答案，例如：何切阿瓦隆 答题 打6筒")
            return
        viewers = q.get("viewers", {})
        view_time = viewers.get(str(ctx.user_id), {}).get("view_time")

        answers = q.setdefault("answers", [])
        updated = False
        for item in answers:
            if item["user_id"] == ctx.user_id:
                item.update({"name": ctx.sender_nickname, "answer": answer,
                             "answer_time": _now(), "view_time": view_time})
                updated = True
                break
        if not updated:
            answers.append({"user_id": ctx.user_id, "name": ctx.sender_nickname,
                            "answer": answer, "answer_time": _now(),
                            "view_time": view_time})
        _save_data(self._data)
        self._sender.reply(ctx,
                           f"已{'更新' if updated else '收到'} {ctx.sender_nickname} 的答案：{answer}")

    def cmd_status(self, ctx: CommandContext) -> None:
        if ctx.user_id not in Config.AVALON_SETTERS:
            self._sender.reply(ctx, "只有出题人才能查看答题情况哦~")
            return
        q = self._get_current()
        if not q:
            self._sender.reply(ctx, "当前还没有发布过题目")
            return
        # 重发一遍题目图片，方便对照
        self._question_image_target(q, Target.from_data(ctx.raw_data))

        viewers = q.get("viewers", {})
        answers = q.get("answers", [])
        lines = ["📋 何切阿瓦隆 当前题目",
                 f"出题人：{q.get('setter_name')}（{q.get('setter_id')}）",
                 f"出题时间：{q.get('set_time')}",
                 f"看题 {len(viewers)} 人 · 答题 {len(answers)} 人"]
        if answers:
            lines.append("—— 答题列表 ——")
            for i, a in enumerate(answers, 1):
                # 计算耗时
                at = _parse_time(a.get("answer_time", ""))
                vt = _parse_time(a.get("view_time", ""))
                if at and vt:
                    dur = (at - vt).total_seconds()
                    time_str = f"耗时 {_format_duration(dur)}"
                elif at and not vt:
                    time_str = "未看题直接作答"
                else:
                    time_str = "时间记录异常"
                lines.append(f"{i}. {a['name']}（{a['user_id']}）\n"
                             f"   答案：{a['answer']}\n"
                             f"   {time_str}")
        else:
            lines.append("还没有人作答~")
        self._sender.reply(ctx, "\n".join(lines))
