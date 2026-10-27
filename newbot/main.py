import os
import random
import re
import sys
import time
import uvicorn
from fastapi import FastAPI, Request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config, ASSETS_DIR
from core.message_sender import MessageSender, Target
from core.command_router import CommandRouter, CommandContext
from core.database import Database, JSONRepository
from core.qq_file_manager import QQNumberFileManager
from core.image_cleanup import cleanup_old_images
from plugins.simple_functions import SimpleFunctionsPlugin
from plugins.ai_functions import AIFunctionsPlugin, AI_SELF_NAME
from plugins.cat_expedition import CatExpeditionPlugin
from plugins.avalon_quiz import AvalonQuizPlugin
from plugins.yahtzee import YahtzeePlugin
from plugins.mahjong17 import Mahjong17Plugin
from plugins.farkle import FarklePlugin
from plugins.tournament import TournamentPlugin


class Bot:
    def __init__(self):
        self.app = FastAPI()
        self._sender = MessageSender(Config.ONE_BOT_URL)
        self._db = Database(Config.DATABASE)
        self._json_repo = JSONRepository(Config.FILES["json_dir"])
        self._router = CommandRouter()
        self._users = QQNumberFileManager(Config.FILES["users_ids"])
        self._groups = QQNumberFileManager(Config.FILES["groups_ids"])
        self._message_ids = [0] * 60
        self._msg_loc = 0
        self._msg_cache = {}
        self._last_cleanup = 0.0  # 上次运行时图片清理的时间戳
        self._group_chat2 = {
            689886013: [], 385394206: [], 913954208: [],
            949736354: [], 480507946: [], 1080341951: [],
            688132922: [], 343761411: [],
        }
        self._ai_plugin = AIFunctionsPlugin(self._sender, Config.ASSETS)
        self._register_plugins()
        self._register_routes()
        # 启动时清理各插件超过 12 小时的运行时合成图，避免堆积
        try:
            n = cleanup_old_images(ASSETS_DIR)
            if n > 0:
                print(f"[cleanup] removed {n} stale runtime images")
        except Exception as e:
            print(f"[cleanup] failed: {e}")

    def _register_plugins(self) -> None:
        simple = SimpleFunctionsPlugin(
            self._sender, self._db, self._json_repo, Config.ASSETS
        )
        simple.register(self._router)
        self._ai_plugin.register(self._router)

        # 猫猫远征队插件
        cat_game = CatExpeditionPlugin(self._sender)
        cat_game.register(self._router)

        # 何切阿瓦隆问答插件
        self._avalon = AvalonQuizPlugin(self._sender)
        self._avalon.register(self._router)

        # 快艇骰子插件（奖励复用猫猫远征队的鱼干）
        self._yahtzee = YahtzeePlugin(self._sender, cat_game)
        self._yahtzee.register(self._router)

        # 17步麻将插件（猫眼石复用猫猫远征队的猫眼石）
        self._mahjong17 = Mahjong17Plugin(self._sender, cat_game)
        self._mahjong17.register(self._router)

        # Farkle 骰子插件（猫眼石复用猫猫远征队的猫眼石）
        self._farkle = FarklePlugin(self._sender, cat_game)
        self._farkle.register(self._router)

        # 锦标赛插件（把上面三种对战游戏当作比赛项目）
        self._tournament = TournamentPlugin(
            self._sender, cat_game, self._yahtzee, self._mahjong17, self._farkle)
        self._tournament.register(self._router)
        # 三个对战游戏对局结束时把结果回调给锦标赛，用于推进赛程
        self._yahtzee.set_result_reporter(self._tournament.on_match_result)
        self._mahjong17.set_result_reporter(self._tournament.on_match_result)
        self._farkle.set_result_reporter(self._tournament.on_match_result)
        # 锦标赛进行期间，禁止在群里手动开这三种游戏的普通对局
        self._yahtzee.set_tournament_checker(self._tournament.is_active)
        self._mahjong17.set_tournament_checker(self._tournament.is_active)
        self._farkle.set_tournament_checker(self._tournament.is_active)

    def _register_routes(self) -> None:
        self.app.post("/")(self._handle_event)

    async def _handle_event(self, request: Request) -> dict:
        data = await request.json()

        if data.get("post_type") == "notice":
            if data.get("notice_type") == "notify":
                if data.get("sub_type") == "poke":
                    if data.get("target_id") == 1707925198:
                        if data.get("user_id") != 1707925198:
                            self._sender.send_poke_to_group(
                                data["user_id"], data["group_id"]
                            )
            return {}

        if data.get("post_type") not in ("message", "message_sent"):
            return {}

        msg_id = data.get("message_id", 0)
        if self._is_duplicate(msg_id):
            return {}

        instruction = data.get("raw_message", "").lower()
        user_id = data.get("user_id", 0)

        if user_id in Config.SYSTEM_USER_IDS:
            return {}

        # 运行期间每小时尝试清理一次超过 12 小时的运行时合成图
        self._maybe_cleanup_images()

        ctx = CommandContext(data)

        if self._handle_connection(instruction, ctx):
            return {}

        if ctx.is_group and not self._groups.find(ctx.group_id):
            return {}
        if ctx.is_private and not self._users.find(ctx.user_id):
            return {}

        # 何切阿瓦隆：出题人待发图状态下的图片捕获（优先于指令路由）
        if self._avalon.handle_message(ctx):
            return {}

        self._handle_group_chat(ctx)

        if self._router.execute(ctx):
            return {}

        return {}

    def _is_duplicate(self, msg_id) -> bool:
        if msg_id in self._message_ids:
            return True
        self._message_ids[self._msg_loc] = msg_id
        self._msg_loc = (self._msg_loc + 1) % 60
        return False

    def _maybe_cleanup_images(self) -> None:
        """每小时清理一次超过 12 小时的运行时合成图"""
        now = time.time()
        if now - self._last_cleanup < 3600:
            return
        self._last_cleanup = now
        try:
            n = cleanup_old_images(ASSETS_DIR)
            if n > 0:
                print(f"[cleanup] removed {n} stale runtime images")
        except Exception as e:
            print(f"[cleanup] failed: {e}")

    def _handle_connection(self, instruction: str, ctx: CommandContext) -> bool:
        target = Target.from_data(ctx.raw_data)

        if instruction == "__connecttouselessrobot__":
            if target.is_group:
                self._groups.add(target.group_id)
            else:
                self._users.add(target.user_id)
            self._sender.send_text(target, "机器人链接已建立")
            return True

        if instruction == "__disconnecttouselessrobot__":
            if target.is_group:
                self._groups.remove(target.group_id)
            else:
                self._users.remove(target.user_id)
            self._sender.send_text(target, "已断开机器人链接")
            return True

        return False

    def _is_at_bot(self, data) -> bool:
        """判断这条消息是否 @ 了机器人本人"""
        raw = data.get("raw_message") or ""
        bot_qq = str(data.get("self_id") or Config.BOT_QQ or "")
        if bot_qq and f"[CQ:at,qq={bot_qq}" in raw:
            return True
        # 有些 OneBot 实现只给 message 段数组，不保证 raw_message 里有 CQ 码
        message = data.get("message")
        if isinstance(message, list):
            for seg in message:
                if (isinstance(seg, dict) and seg.get("type") == "at"
                        and str((seg.get("data") or {}).get("qq", "")) == bot_qq):
                    return True
        return f"@{AI_SELF_NAME}" in raw

    def _handle_group_chat(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        instruction = ctx.raw_message
        at_me = self._is_at_bot(ctx.raw_data)

        if not target.is_group:
            return

        # --- 特殊群：缓存最近5条 + 自动回复概率触发 ---
        # 被 @ 时不受群白名单、CQ 码过滤与概率限制，任何已连接群都尽可能回复
        special = target.group_id in Config.SPECIAL_GROUPS
        if not (at_me or (special and "[CQ:" not in instruction)):
            return

        # 非特殊群第一次被 @ 时也建立聊天上下文
        chat_list = self._group_chat2.setdefault(target.group_id, [])

        # 去掉 CQ 码再进上下文，避免模型看到 [CQ:at,qq=...] 这种裸代码
        clean = re.sub(r"\[CQ:[^\]]+\]", "", instruction).strip()
        chat_list.append(f"{ctx.sender_nickname}:{clean}")
        while len(chat_list) > 5:
            del chat_list[0]

        # 自动回复概率触发（@ 机器人时强制触发）
        self._ai_plugin.auto_reply(ctx, chat_list, force=at_me)

        # 选图回复（低概率：约1%）
        if random.randint(0, 10000) >= 9900:
            self._ai_plugin.choose_image(ctx, chat_list)

    def run(self, host: str = None, port: int = None) -> None:
        if not host:
            host = Config.BOT_HOST
        if not port:
            port = Config.BOT_PORT
        uvicorn.run(self.app, host=host, port=port)


if __name__ == "__main__":
    bot = Bot()
    bot.run()
