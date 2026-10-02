import os
import random
import re
import threading
import requests
from typing import Dict, List

from config import Config
from core.message_sender import MessageSender, Target
from core.command_router import CommandRouter, CommandContext
from core.tts import design_voice

# 默认系统提示词：AI对话时的身份设定
DEFAULT_CHAT_SYSTEM = (
    "你是一个活泼有趣的QQ群聊机器人，名叫「工位划水」。"
    "说话风格：轻松幽默，偶尔带点毒舌，喜欢用颜文字(=w=)、喵~ 等口语化表达。"
    "你可以回答问题、闲聊、吐槽，但不要假装自己是人类，自我介绍时说自己是群里的机器人就好。"
    "回答尽量简洁，除非用户明确要求详细解释。"
)

# 自动回复概率上限（万分比），防止自己回复自己无限循环
MAX_AUTO_REPLY_PROB = 2000


class AIFunctionsPlugin:
    """AI功能插件：AI对话、群自动回复、选图回复、语音合成"""

    def __init__(self, sender: MessageSender, assets_config: dict):
        self._sender = sender
        self._assets = assets_config

        # 上下文存储: key = "user_{id}" 或 "group_{id}", value = [{"role":..., "content":...}]
        self._ai_contexts: Dict[str, List[dict]] = {}
        self._max_context_len = 50

        # 每个群/私聊的 AI 对话 system prompt 覆盖（空则用 DEFAULT_CHAT_SYSTEM）
        self._chat_prompts: Dict[str, str] = {}

        # 自动回复配置: {group_id: {"f": 概率万分比, "s": 性格词}}
        self._ai_response: Dict[int, dict] = {
            gid: {"f": 100, "s": "你是一个群聊回复机器人。"}
            for gid in Config.SPECIAL_GROUPS
        }

        # 语音合成音色描述词
        self._voice_persona: str = Config.AI_VOICE[0]

        # QQ 消息单条上限
        self._max_reply_len = 3000

    # ==================== 注册命令 ====================

    def register(self, router: CommandRouter) -> None:
        # --- AI对话 ---
        router.register(
            ["ai", ".ai", "/ai"],
            self.cmd_ai_chat,
            description="AI对话"
        )
        router.register(
            ["ai清空", "aiclear", ".aiclear", "/aiclear"],
            self.cmd_ai_clear,
            description="清空AI对话上下文"
        )
        router.register(
            ["ai提示", "aiprompt", ".aiprompt", "/aiprompt"],
            self.cmd_ai_set_prompt,
            description="设置AI对话的人格提示词"
        )
        router.register(
            ["ai设置", "aisetup", ".aisetup", "/aisetup"],
            self.cmd_ai_setup,
            description="设置群AI自动回复"
        )

        # --- AI语音 ---
        router.register(
            ["aisetvoice", ".aisetvoice", "/aisetvoice"],
            self.cmd_ai_set_voice,
            description="设置AI语音音色(仅管理员)"
        )
        router.register(
            ["aivoice", ".aivoice", "/aivoice"],
            self.cmd_ai_voice,
            description="AI语音合成预览"
        )

        # --- 暂不可用 ---
        router.register(
            ["群聊总结", ".gc", "/gc", "gc"],
            self.cmd_todo,
            description="[暂不可用] 群聊总结"
        )
        router.register(
            ["dsc", ".dsc", "/dsc"],
            self.cmd_todo,
            description="[暂不可用] Steam游戏品味评价"
        )
        router.register(
            ["dsc2", ".dsc2", "/dsc2"],
            self.cmd_todo,
            description="[暂不可用] Steam游戏品味评价(过滤短时)"
        )
        router.register(
            ["ai图像", "aifig", ".aifig", "/aifig"],
            self.cmd_todo,
            description="[暂不可用] AI文生图"
        )
        router.register(
            ["ai图像2", "aifig2", ".aifig2", "/aifig2"],
            self.cmd_todo,
            description="[暂不可用] AI图生图"
        )
        router.register(
            ["ai图像3", "aifig3", ".aifig3", "/aifig3"],
            self.cmd_todo,
            description="[暂不可用] AI图生图"
        )
        router.register(
            ["ai图像4", "aifig4", ".aifig4", "/aifig4"],
            self.cmd_todo,
            description="[暂不可用] AI图片扩边"
        )

    # ==================== 主动命令处理 ====================

    def cmd_ai_chat(self, ctx: CommandContext) -> None:
        """AI对话：带上下文，按用户/群隔离"""
        args = ctx.get_args()
        if not args:
            self._sender.send_text(
                Target.from_data(ctx.raw_data),
                "请输入你想聊的内容喵~\n也可以用 ai清空 重置对话"
            )
            return

        target = Target.from_data(ctx.raw_data)
        key = f"group_{target.group_id}" if target.is_group else f"user_{target.user_id}"

        if key not in self._ai_contexts:
            system_prompt = self._chat_prompts.get(key, DEFAULT_CHAT_SYSTEM)
            self._ai_contexts[key] = [
                {"role": "system", "content": system_prompt}
            ]

        self._ai_contexts[key].append({"role": "user", "content": args})
        self._trim_context(key)

        threading.Thread(
            target=self._do_ai_chat,
            args=(ctx, key),
            daemon=True
        ).start()
        self._sender.send_text(target, "思考中喵...")

    def cmd_ai_clear(self, ctx: CommandContext) -> None:
        """清空AI对话上下文"""
        target = Target.from_data(ctx.raw_data)
        key = f"group_{target.group_id}" if target.is_group else f"user_{target.user_id}"
        if key in self._ai_contexts:
            del self._ai_contexts[key]
        self._sender.send_text(target, "对话上下文已清空喵~")

    def cmd_ai_set_prompt(self, ctx: CommandContext) -> None:
        """设置当前群/私聊的AI对话人格提示词"""
        target = Target.from_data(ctx.raw_data)
        key = f"group_{target.group_id}" if target.is_group else f"user_{target.user_id}"
        args = ctx.get_args()

        if not args:
            current = self._chat_prompts.get(key, DEFAULT_CHAT_SYSTEM)
            self._sender.send_text(
                target,
                f"当前AI提示词:\n{current}\n\n"
                f"设置新提示词: ai提示 <内容>\n"
                f"恢复默认: ai提示 reset"
            )
            return

        if args.strip().lower() == "reset":
            self._chat_prompts.pop(key, None)
            # 同步更新已有上下文里的 system 消息
            if key in self._ai_contexts and self._ai_contexts[key]:
                self._ai_contexts[key][0]["content"] = DEFAULT_CHAT_SYSTEM
            self._sender.send_text(target, "已恢复默认提示词喵~")
            return

        self._chat_prompts[key] = args.strip()
        # 同步更新已有上下文里的 system 消息
        if key in self._ai_contexts and self._ai_contexts[key]:
            self._ai_contexts[key][0]["content"] = args.strip()
        self._sender.send_text(target, f"AI提示词已更新喵~\n新提示词: {args.strip()}")

    def _do_ai_chat(self, ctx: CommandContext, key: str) -> None:
        target = Target.from_data(ctx.raw_data)
        try:
            reply = self._call_ai(
                Config.AI_MODEL["chat"],
                self._ai_contexts[key],
                temperature=0.8,
            )
            reply = self._truncate(reply)
            self._ai_contexts[key].append({"role": "assistant", "content": reply})
            self._trim_context(key)
            self._sender.send_text(target, reply)
        except Exception as e:
            self._sender.send_text(target, f"AI出错了: {e}")

    def cmd_ai_setup(self, ctx: CommandContext) -> None:
        """设置群AI自动回复概率和性格词"""
        target = Target.from_data(ctx.raw_data)
        args = ctx.get_args()

        if not target.is_group:
            self._sender.send_text(target, "只能在群里设置喵")
            return
        if target.group_id not in self._ai_response:
            self._sender.send_text(target, "这个群不在AI自动回复列表里")
            return

        parts = args.split(" ", 1)
        if len(parts) < 2:
            cfg = self._ai_response[target.group_id]
            self._sender.send_text(
                target,
                f"当前配置: 概率万分之{cfg['f']} (上限{MAX_AUTO_REPLY_PROB}), 性格: {cfg['s']}\n"
                f"设置格式: ai设置 <概率(万分比)> <性格词>\n"
                f"示例: ai设置 50 你是个毒舌的群友"
            )
            return

        try:
            prob = int(parts[0])
            prob = max(0, min(prob, MAX_AUTO_REPLY_PROB))
        except ValueError:
            self._sender.send_text(target, "概率需要是数字喵")
            return

        persona = parts[1].strip()
        self._ai_response[target.group_id]["f"] = prob
        self._ai_response[target.group_id]["s"] = persona
        self._sender.send_text(
            target,
            f"AI自动回复概率设为万分之{prob}，性格词: {persona}"
        )

    def cmd_ai_set_voice(self, ctx: CommandContext) -> None:
        """设置语音合成的音色描述词（仅管理员）"""
        target = Target.from_data(ctx.raw_data)
        args = ctx.get_args()

        if target.user_id not in Config.ADMIN_USER_IDS:
            self._sender.send_text(target, "只有管理员能设置喵")
            return
        if not args:
            self._sender.send_text(
                target,
                f"当前音色: {self._voice_persona}\n设置新音色: aisetvoice <描述词>"
            )
            return

        self._voice_persona = args.strip()
        self._sender.send_text(target, f"AI音色设为: {self._voice_persona}")

    def cmd_ai_voice(self, ctx: CommandContext) -> None:
        """AI语音合成：用当前音色朗读预览文本"""
        target = Target.from_data(ctx.raw_data)
        args = ctx.get_args()

        if not args:
            self._sender.send_text(target, "请输入要朗读的文字喵~")
            return

        output_dir = self._assets.get("output", "")
        output_path = os.path.join(output_dir, "tts_preview.wav")

        def _do():
            try:
                self._sender.send_text(target, "生成语音中喵...")
                design_voice(
                    voice_description=self._voice_persona,
                    preview_text=args,
                    output_path=output_path,
                )
                self._sender.send_voice(target, output_path)
            except ImportError:
                self._sender.send_text(target, "缺少依赖，请安装: pip install openai numpy soundfile")
            except Exception as e:
                self._sender.send_text(target, f"语音生成失败: {e}")

        threading.Thread(target=_do, daemon=True).start()

    def cmd_todo(self, ctx: CommandContext) -> None:
        """暂不可用功能的统一提示"""
        target = Target.from_data(ctx.raw_data)
        self._sender.send_text(target, "这个功能暂时不可用喵~")

    # ==================== 被动触发方法（供 main.py 调用） ====================

    def auto_reply(self, ctx: CommandContext, chat_history: List[str]) -> None:
        """群自动回复：按概率触发，AI回一句"""
        target = Target.from_data(ctx.raw_data)
        group_id = target.group_id

        config = self._ai_response.get(group_id)
        if config is None:
            return

        # 上下文太少不触发
        if len(chat_history) < 3:
            return

        if random.randint(0, 10000) >= config["f"]:
            return

        chat_text = "\n".join(chat_history[-5:])

        # ✅ 优化：system 放身份，user 放对话内容
        messages = [
            {"role": "system", "content": config["s"]},
            {"role": "user", "content": (
                f"下面是群里的最近聊天记录：\n{chat_text}\n\n"
                f"请你作为上面的身份，对对话中最后一句进行简短回复。"
                f"要求：通常20字以内，最多不超过100字。直接输出回复内容即可，"
                f"不要包含思考过程或解释你为什么这么回复。"
            )}
        ]

        def _do():
            try:
                reply = self._call_ai(
                    Config.AI_MODEL["reply"],
                    messages,
                    temperature=0.9,
                )
                reply = self._truncate(reply)
                if "silverwind" in reply.lower() or "银风" in reply:
                    return
                self._sender.send_text(target, reply.strip())
            except Exception as e:
                print(f"[AI auto_reply] error: {e}")

        threading.Thread(target=_do, daemon=True).start()

    def choose_image(self, ctx: CommandContext, chat_history: List[str]) -> None:
        """选图回复：极低概率触发，AI从taleanswer文件夹选一张图"""
        target = Target.from_data(ctx.raw_data)
        group_id = target.group_id

        if group_id in (913954208, 1080341951, 688132922, 343761411):
            return

        if len(chat_history) < 3:
            return

        folder_path = self._assets.get("tale_answer", "")
        if not folder_path or not os.path.isdir(folder_path):
            return

        try:
            file_names = os.listdir(folder_path)
        except OSError:
            return

        if not file_names:
            return

        chat_text = "\n".join(chat_history[-5:])
        file_list = "\n".join(f"{i}:{fn}" for i, fn in enumerate(file_names))

        # ✅ 优化：system 放角色，user 放任务
        messages = [
            {"role": "system", "content": "你是一个群聊中选表情包的机器人。"},
            {"role": "user", "content": (
                f"群里最近聊天：\n{chat_text}\n\n"
                f"下面是可用的图片文件名（文件名即图片内容）：\n{file_list}\n\n"
                f"请选一张最适合回复最后一句的图片，只返回编号数字即可，不要其他内容。"
            )}
        ]

        def _do():
            try:
                reply = self._call_ai(
                    Config.AI_MODEL["reply"],
                    messages,
                    temperature=0.3,
                )
                match = re.search(r"\d+", reply)
                if not match:
                    return
                idx = int(match.group())
                if 0 <= idx < len(file_names):
                    self._sender.send_image(
                        target,
                        os.path.join(folder_path, file_names[idx])
                    )
            except Exception as e:
                print(f"[AI choose_image] error: {e}")

        threading.Thread(target=_do, daemon=True).start()

    # ==================== 底层 API 调用 ====================

    def _call_ai(
        self,
        model: str,
        messages: List[dict],
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> str:
        """调用硅基流动 API（OpenAI 兼容格式）"""
        api_key = Config.SILICONFLOW_API_KEY
        if not api_key or api_key.startswith("sk-") and len(api_key) <= 3:
            raise RuntimeError("API Key 未配置")

        url = f"{Config.SILICONFLOW_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }

        # ✅ 简单重试
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            except requests.RequestException as e:
                last_error = e

        raise last_error or RuntimeError("AI 调用失败，已重试多次")

    # ==================== 工具方法 ====================

    def _trim_context(self, key: str) -> None:
        """裁剪上下文到上限（保留 system 消息）"""
        ctx = self._ai_contexts[key]
        if len(ctx) <= self._max_context_len:
            return
        system_msg = ctx[0] if ctx and ctx[0]["role"] == "system" else None
        start = len(ctx) - self._max_context_len + (1 if system_msg else 0)
        self._ai_contexts[key] = [system_msg] + ctx[start:] if system_msg else ctx[start:]

    def _truncate(self, text: str) -> str:
        """截断过长回复"""
        if len(text) <= self._max_reply_len:
            return text
        return text[:self._max_reply_len - 3] + "..."

    # ==================== 暴露 getter ====================

    @property
    def ai_response_config(self) -> Dict[int, dict]:
        return self._ai_response
