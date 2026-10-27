import json
import os
import random
import re
import threading
import time

import requests
from typing import Dict, List

from config import Config
from core.message_sender import MessageSender, Target
from core.command_router import CommandRouter, CommandContext
from core.tts import design_voice

# 所有 AI 回复（ai 提问、@ 聊天、随机自动回复）共用的统一性格
AI_PERSONA = (
    "你是一个活泼有趣的QQ群聊机器人，名叫「更有甚者」。"
    "说话风格：轻松幽默，偶尔带点毒舌，喜欢用颜文字(=w=)、喵~ 等口语化表达。"
    "你可以回答问题、闲聊、吐槽，但不要假装自己是人类，自我介绍时说自己是群里的机器人就好。"
)
# 三种使用场景的补充说明（性格统一，只是任务不同）
AI_QA_HINT = "\n\n现在有人直接向你提问，请认真、简洁地回答；除非对方明确要求，不要长篇大论。"
AI_AT_HINT = "\n\n现在有人在群里 @ 你聊天，像真正的群友一样自然地回一句。"
AI_AUTO_HINT = "\n\n现在没人点你的名，顺手接一句群聊就好，别抢戏。"

# 自动回复概率上限（万分比），防止自己回复自己无限循环
MAX_AUTO_REPLY_PROB = 2000

# 机器人在群里的 QQ 昵称（写进提示词，让它知道自己叫什么）
AI_SELF_NAME = "更有甚者"

# 对面也是一个机器人：对它说的话保持高概率接话（万分之 5000，即 50%），
# 不受群白名单、最少上下文条数与各群自动回复概率限制
AI_BOT_FRIEND_QQ = 1064485266
AI_BOT_FRIEND_PROB = 5000

# 长期记忆：每累计这么多次自动回复，就在后台整理一次群体记忆（不阻塞回复）
MEMORY_EVOLVE_EVERY = 20
# 注入提示词时最多带上几位群友的档案，控制 prompt 长度以免拖慢首字延迟
MEMORY_INJECT_USERS = 8


def _extract_json(text: str):
    """从模型输出里抠出第一个 JSON 对象（模型常带解释或代码块）"""
    match = re.search(r"\{[\s\S]*\}", text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class AIFunctionsPlugin:
    """AI功能插件：AI对话、群自动回复、选图回复、语音合成"""

    def __init__(self, sender: MessageSender, assets_config: dict):
        self._sender = sender
        self._assets = assets_config

        # 上下文存储: key = "user_{id}" 或 "group_{id}", value = [{"role":..., "content":...}]
        self._ai_contexts: Dict[str, List[dict]] = {}
        self._max_context_len = 50

        # 所有 AI 回复共用的统一性格（ai设置 可以整体改掉）
        self._persona: str = AI_PERSONA

        # 自动回复配置: {group_id: {"f": 概率万分比}}
        self._ai_response: Dict[int, dict] = {
            gid: {"f": 100} for gid in Config.SPECIAL_GROUPS
        }

        # 语音合成音色描述词
        self._voice_persona: str = Config.AI_VOICE[0]

        # 长期记忆：{群号: {persona, users, notes}}，落盘到 assets/ai_memory.json
        self._memory_path = self._assets.get("ai_memory", "")
        self._memory_lock = threading.Lock()
        self._memory = self._load_memory()
        # 各群自动回复计数，用于决定何时触发后台记忆整理
        self._reply_counts: Dict[int, int] = {}

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
            self._ai_contexts[key] = [
                {"role": "system", "content": self._persona + AI_QA_HINT}
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
        """设置群AI自动回复概率；性格词是所有人共用的统一性格"""
        target = Target.from_data(ctx.raw_data)
        args = ctx.get_args()

        if not target.is_group:
            self._sender.send_text(target, "只能在群里设置喵")
            return
        if target.group_id not in self._ai_response:
            # 允许新群通过 ai设置 自行开启，默认不随机接话
            self._ai_response[target.group_id] = {"f": 0}

        parts = args.split(" ", 1)
        if len(parts) < 2:
            cfg = self._ai_response[target.group_id]
            self._sender.send_text(
                target,
                f"当前配置: 概率万分之{cfg['f']} (上限{MAX_AUTO_REPLY_PROB})\n"
                f"统一性格: {self._persona}\n"
                f"设置格式: ai设置 <概率(万分比)> <性格词>\n"
                f"示例: ai设置 50 你是个毒舌的群友\n"
                f"性格词对所有人、所有群和三种回复方式统一生效"
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
        self._persona = persona
        self._sender.send_text(
            target,
            f"AI自动回复概率设为万分之{prob}，统一性格更新为: {persona}"
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

    # ==================== 长期记忆 ====================

    def _load_memory(self) -> dict:
        """读取长期记忆存档；文件缺失或损坏时按空记忆处理"""
        path = self._memory_path
        if not path or not os.path.exists(path):
            return {"groups": {}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print(f"[AI memory] load error: {e}")
            return {"groups": {}}
        if not isinstance(data, dict) or not isinstance(data.get("groups"), dict):
            return {"groups": {}}
        return data

    def _save_memory(self) -> None:
        """原子写入长期记忆，避免写一半被读到"""
        path = self._memory_path
        if not path:
            return
        with self._memory_lock:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._memory, f, ensure_ascii=False, indent=1)
                os.replace(tmp, path)
            except OSError as e:
                print(f"[AI memory] save error: {e}")

    def _group_memory(self, group_id: int) -> dict:
        """取出（必要时初始化）某个群的记忆节点"""
        mem = self._memory.setdefault("groups", {}).setdefault(str(group_id), {})
        mem.setdefault("persona", "")
        mem.setdefault("users", {})
        mem.setdefault("notes", [])
        return mem

    def _memory_hint(self, group_id: int) -> str:
        """把长期记忆压缩成一小段提示词注入 system，长度受控"""
        mem = self._group_memory(group_id)
        parts = []
        if mem["persona"]:
            # 只当作补充的说话习惯，不能盖过统一性格
            parts.append(f"你在长期聊天中逐渐养成的说话习惯：{mem['persona']}")

        users = sorted(mem["users"].items(),
                       key=lambda kv: kv[1].get("last_seen", 0), reverse=True)
        lines = []
        for name, info in users[:MEMORY_INJECT_USERS]:
            facts = [f for f in info.get("facts", []) if f][-3:]
            if facts:
                lines.append(f"- {name}：{'；'.join(facts)}")
        if lines:
            parts.append("你记得的群友：\n" + "\n".join(lines))

        if mem["notes"]:
            parts.append("你自己说过、之后可能还会提起的话：\n"
                         + "\n".join(f"- {n}" for n in mem["notes"][-5:]))
        return "\n".join(parts)

    def _maybe_evolve_memory(self, group_id: int, chat_history: List[str],
                             my_reply: str) -> None:
        """累计到阈值后，在后台把近期对话整理进长期记忆（不占用回复耗时）"""
        with self._memory_lock:
            n = self._reply_counts.get(group_id, 0) + 1
            self._reply_counts[group_id] = n
        if n % MEMORY_EVOLVE_EVERY != 0:
            return
        threading.Thread(
            target=self._evolve_memory,
            args=(group_id, list(chat_history), my_reply),
            daemon=True,
        ).start()

    def _evolve_memory(self, group_id: int, chat_history: List[str], my_reply: str) -> None:
        """让模型把「已有记忆 + 近期对话 + 自己刚说的话」合并成新的记忆"""
        mem = self._group_memory(group_id)
        old = {
            "persona": mem["persona"],
            "users": {k: v.get("facts", []) for k, v in mem["users"].items()},
            "notes": mem["notes"][-8:],
        }
        prompt = (
            "你在维护一个群聊机器人的长期记忆。请根据已有记忆和最近对话，输出更新后的记忆，"
            "只输出 JSON，不要任何解释。\n"
            '格式：{"persona": "一句话描述机器人在群里逐渐养成的说话习惯（只描述语气与表达方式，'
            '不要改写它的身份与性格设定）", '
            '"users": {"群友昵称": ["关于他的稳定事实", "最多3条"]}, '
            '"notes": ["机器人自己说过的、以后还会提起的观点或梗", "最多5条"]}\n'
            "要求：persona 不超过 60 字；只保留稳定、可复用的信息，不要记录一次性闲聊；"
            "不要编造对话里没有的内容。\n\n"
            f"已有记忆：{json.dumps(old, ensure_ascii=False)}\n\n"
            f"最近对话：\n" + "\n".join(chat_history) + "\n\n"
            f"机器人刚才的回复：{my_reply}"
        )
        try:
            raw = self._call_ai(
                Config.AI_MODEL["summarise"],
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600,
            )
            data = _extract_json(raw)
            if data:
                self._merge_memory(group_id, data)
        except Exception as e:
            print(f"[AI memory] evolve error: {e}")

    def _merge_memory(self, group_id: int, data: dict) -> None:
        """把模型整理出的记忆合并进存档（去重、截断、保留最近若干条）"""
        mem = self._group_memory(group_id)

        persona = data.get("persona")
        if isinstance(persona, str) and persona.strip():
            mem["persona"] = persona.strip()[:120]

        users = data.get("users")
        if isinstance(users, dict):
            now = int(time.time())
            for name, facts in users.items():
                if not isinstance(name, str) or not isinstance(facts, list):
                    continue
                key = name.strip()[:32]
                if not key:
                    continue
                info = mem["users"].setdefault(key, {"name": key, "facts": []})
                merged = []
                for f in list(info["facts"]) + [str(x).strip() for x in facts]:
                    if f and f not in merged:
                        merged.append(f[:60])
                info["facts"] = merged[-3:]
                info["last_seen"] = now

        notes = data.get("notes")
        if isinstance(notes, list):
            merged = list(mem["notes"])
            for n in notes:
                n = str(n).strip()
                if n and n not in merged:
                    merged.append(n[:80])
            mem["notes"] = merged[-6:]

        self._save_memory()

    # ==================== 被动触发方法（供 main.py 调用） ====================

    def auto_reply(self, ctx: CommandContext, chat_history: List[str],
                   force: bool = False) -> None:
        """群自动回复：按概率触发，AI回一句；force=True（被 @ 时）几乎必回"""
        target = Target.from_data(ctx.raw_data)
        group_id = target.group_id
        # 对面那个也是机器人：它的每句话都按固定高概率接，避免两个机器人互相沉默
        bot_friend = str(getattr(ctx, "user_id", "") or "") == str(AI_BOT_FRIEND_QQ)

        config = self._ai_response.get(group_id)
        if config is None:
            # 不在特殊群列表里：@ 机器人时仍回复一句，但默认不参与随机接话
            if not force and not bot_friend:
                return
            config = self._ai_response.setdefault(group_id, {"f": 0})

        if not force:
            # 上下文太少不触发（对面机器人说的话不受这条限制）
            if not bot_friend and len(chat_history) < 3:
                return

            prob = AI_BOT_FRIEND_PROB if bot_friend else config["f"]
            if random.randint(0, 10000) >= prob:
                return

        chat_text = "\n".join(chat_history)
        speaker = getattr(ctx, "sender_nickname", "") or "群友"

        # system 放统一性格 + 身份 + 长期记忆（记忆只补充语气，不覆盖性格）
        system = (self._persona + f"\n\n你在群里的QQ昵称是「{AI_SELF_NAME}」。"
                  + (AI_AT_HINT if force else AI_AUTO_HINT))
        mem_hint = self._memory_hint(group_id)
        if mem_hint:
            system += ("\n\n下面是你长期积累的记忆，用来让回复更自然；"
                       "如果与上面的性格设定或身份冲突，一律以上面的设定为准。\n"
                       + mem_hint)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": (
                f"下面是群里的最近聊天记录：\n{chat_text}\n\n"
                f"现在说话的是「{speaker}」。"
                f"请按上面的性格自然地接一句：可以接梗、吐槽、顺着话题聊，"
                f"也可以在合适的时候提到你记得的群友或你之前的观点。"
                f"长短随心情，不要每句都套同一个模板，不要解释你为什么这么回复。"
                f"（最多不超过100字）"
            )},
        ]

        def _do():
            try:
                reply = self._call_ai(
                    Config.AI_MODEL["reply"],
                    messages,
                    temperature=0.9,
                    max_tokens=300,
                )
                reply = self._truncate(reply)
                if "silverwind" in reply.lower() or "银风" in reply:
                    return
                self._sender.send_text(target, reply.strip())
                self._maybe_evolve_memory(group_id, chat_history, reply.strip())
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
        max_tokens: int = 0,
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
        if max_tokens > 0:
            payload["max_tokens"] = max_tokens

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
