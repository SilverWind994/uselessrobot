import os
import random
import sys
import uvicorn
from fastapi import FastAPI, Request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from core.message_sender import MessageSender, Target
from core.command_router import CommandRouter, CommandContext
from core.database import Database, JSONRepository
from core.qq_file_manager import QQNumberFileManager
from plugins.simple_functions import SimpleFunctionsPlugin
from plugins.ai_functions import AIFunctionsPlugin
from plugins.cat_expedition import CatExpeditionPlugin
from plugins.avalon_quiz import AvalonQuizPlugin


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
        self._group_chat2 = {
            689886013: [], 385394206: [], 913954208: [],
            949736354: [], 480507946: [], 1080341951: [],
            688132922: [], 343761411: [],
        }
        self._ai_plugin = AIFunctionsPlugin(self._sender, Config.ASSETS)
        self._register_plugins()
        self._register_routes()

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

    def _handle_group_chat(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        instruction = ctx.raw_message

        # --- 特殊群：缓存最近5条 + 自动回复概率触发 ---
        if target.group_id in Config.SPECIAL_GROUPS and "[CQ:" not in instruction:
            chat_list = self._group_chat2.get(target.group_id)
            if chat_list is not None:
                chat_list.append(f"{ctx.sender_nickname}:{instruction}")
                while len(chat_list) > 5:
                    del chat_list[0]

                # 自动回复概率触发
                self._ai_plugin.auto_reply(ctx, chat_list)

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
