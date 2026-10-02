import random
import os
import re
import json
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional

from core.message_sender import MessageSender, Target
from core.command_router import CommandRouter, CommandContext
from core.database import Database, JSONRepository

# 答案之书题库（来自旧 answer.py）
ANSWER_BOOK = [
    "别难过，你是最棒的", "时间会证明一切", "需要一个相当大的努力",
    "专注你眼下的生活", "遵循别人的引导", "遵循专家的建议",
    "从现在开始,一年也没有关系", "按照你的意愿", "开始改变你的日常习惯",
    "遇上方知有", "采用一个冒险的态度", "允许你先休息一下",
    "好运将会降临", "避免第一个解决方案", "寻求援助会让你成功",
    "需要耐心", "实际一点吧", "合作将会是关键",
    "考虑一下这个机会", "早点去做", "无需多问，尽力去做",
    "别让压力打乱你的节奏", "也许会有好转", "是时候做新的打算了",
    "不用怀疑了", "不要陷入你的感情", "不要犹豫",
    "别浪费时间了", "先完成其他事倩", "坚持终有回报",
    "做好调查研究，然后做好它!", "这不可能失败", "也许是一段奇妙的旅程",
    "这是你不会忘记的", "这肯定会让事情变得有趣", "这是不确定的",
    "木已成舟", "这可能很难，但你会发现它的价", "这将影响别人对你的看法",
    "这将是一种享受", "这会带来好运", "前路仍不可预测",
    "这是不明智的", "它会让你付出代价", "现在就是绝佳的时机",
    "不值得反抗", "是你走的时候", "保持开放的心态",
    "不要让别人知道", "笑一下", "请摆脱当前束缚",
    "有充分的理由保持乐观", "让它过去吧", "会有障碍要克服",
    "为什么不列出原因", "这是制定新计划的好时机", "也许",
    "想做出最佳决策，需要保持冷静", "一直走下去", "相信自己的直觉",
    "你不会一个人", "别忘记你的初心", "只做一次",
    "尝试一种不太可能的解决方案", "注重细节", "不宜在这个时候",
    "为突发事件做好准备", "无论如何你可以提升", "重新考虑你的方法",
    "你能以任何方式改变现状", "等一等", "得真正地努力一下",
    "等待一个更好的机会", "重新考虑优先级", "尊重规则",
    "一个正在到来的晴天", "寻找更多选择", "注意你的节奏",
    "很快就会解决它", "不管你做什么，结果将会影响你", "整个宇宙都会过来帮你",
    "可以", "结果可能会令人震惊", "不",
    "需冒险一试", "是的，但不要勉强", "花更多的时间来决定",
    "你会发现自己无法妥协", "那将是浪费钱", "你知道现在比以前好",
    "这会超出你的控制", "你可能会放弃其他东西", "解决办法可能不太明显",
    "你现在必须行动", "机会不会很快再来", "你会发现一切你所需要知道的",
    "情况将很快发生改变", "岁月静好，长乐未央", "结果会是好的",
    "你需要适应", "你不会失望的", "你会庆幸你做了",
    "学会妥协", "您需要了解更多信息", "你需要考虑其他办法",
    "你需要主动出击", "你会后悔的", "期涂一点更好",
    "感恩，运气会越来越好", "学会自我欣赏，你很棒", "复杂的事情简单做",
    "小题大做", "学会保护自己", "给自己一个肯定",
    "你的行动会使一切变得更好", "把握现在", "不必为你无法控制的事情而担心",
    "会取得更好的结果", "不要忘记微笑", "看看会发生什么",
    "一切从头开始", "下这一注稳赢", "你失去的某天会归还与你",
    "且行且思", "你的状态很不对", "你或许需要突破",
    "你唯一能做的只有把握现在", "学会珍惜", "调整心情，重新出发",
    "请坚持不懈的努力", "不合适", "换一个方向",
    "放轻松，这很简单", "也许会迟到", "你的行动会改变现状",
    "奇迹会降临", "放手", "做最重要的决定",
    "亏本买卖", "今朝有酒，今朝醉", "及时行乐",
    "以甜治甜，以丧治丧", "你不是真心的在意", "你不用最棒",
    "你会因为你做了而感到快乐", "你很棒，自信起来吧", "你心里已有答案",
    "停止emo", "我们需要去打开窗", "糖吃多了会傻，苦一点没关系",
    "自己选择的路，跪着也要走完", "你说了算", "有一个重要的东西用来过渡",
    "准备迎接意料之外的结果", "难分好坏", "高兴起来吧，你这么厉害",
    "随波逐流未必是好事", "随波逐流未必是坏事", "需要一腔孤勇",
    "出门会遇到贵人", "别指望所有人理解你", "别灰心，人生总是起起落落的",
    "别要求太多", "别辜负了自己就好", "问问自己，为什么要这么干",
    "千万不能失败", "见好就收", "试着去爱",
    "答案就在你身边", "珍惜身边人", "另择吉日",
    "学会自我自愈", "学会表达自己", "尽人事，听天命",
    "由于是必经的过程", "带着你顽皮的好奇心去探索它", "令人期待的事情马上就要发生",
    "很多事会随着时间好起来的", "每天做一点，将会大不相同", "主动一点，人生会大不相同",
    "以后再说", "会很棒的", "会很顺利",
    "会感到庆幸", "会是完美的", "会有一个风光明媚的未来",
    "会是甜的", "你肯定会获得支持", "你开心就好",
    "时间会告诉你一切", "相信你最初的想法", "眼光长远一点",
    "研究它，然后享受它", "跟随其他人的领导", "值不值得争取",
    "这是必然的，不要抗拒", "不要刻意隐藏", "停止伤悲",
    "不要刻意压抑", "背不动就放下", "不要怕",
    "回家吧，家是永远的避风港", "不要去忘记", "自信起来吧",
    "接受那些消失的", "到此为止", "时间有限",
    "慢下来", "挥手道别", "事情会朝目标发展",
    "未来可期", "平平安安", "挥别错的",
    "有一些重要的事必须去做", "用平淡的心态去追求", "一切皆有可能",
    "控制自己的情绪", "一切顺其自然", "一场铺满鲜花的道路",
    "暂且不要判断", "不要一成不变", "你祈求的一切顺利",
    "享受全心全意的付出", "站在了最重要的地方", "你会得到大多数的支持",
    "十分好的预感", "学会改变什么", "最划算的交易",
    "学会成长", "最好的事情正要发生", "没有什么是对的",
    "必须努力奔跑起来", "会有人陪着你", "站起来去战斗",
    "不要看轻别人", "多读一本书", "出发",
    "差不多得了", "不要给人添麻烦", "有人浪费了你的时间",
    "最后什么都没改变", "对，去吧", "找回自己",
    "你会得到重生", "慢些，我们就会更快", "需要直面残酷",
    "你大概会受点伤", "回头看看", "当然",
    "别傻了", "烦恼快要消失了", "结束倒计时",
    "并不会让你高兴", "没什么放不下", "等待",
    "伤口很快会愈合", "如你所息", "悄悄躲开",
    "完美的", "不要做出任何决定", "浪费光阴",
    "停止向前", "再也不要见", "不会让你痛苦的",
    "试着慷慨一点", "这是不能犹豫的事", "试着安静一会",
    "戒掉过分的急躁", "不要隐藏起来", "你好像舍不得",
    "有点儿心疼", "车到山前必有路", "你有必要傻一点",
    "你会忘记它", "只是一场梦", "你要勇敢的离开",
    "先主后次", "尽你最大的努力", "去忘记",
    "大家好像都不认同", "认真起来", "值得去做的事",
    "转个身忘记吧", "这绝对是个好主意", "马上停下来",
    "你很幸运", "机会就在眼前", "不如忘掉这个问题",
    "专注一点", "殊途同归", "背道而驰",
    "吃点东西，冷静一下", "这大概会让你哭泣", "高兴起来吧，你这么厉害",
    "既往不恋", "捍卫它", "不必耿耿于怀",
    "放在心里吧，这样比较好点", "不用伪装到面目全非", "别压抑自己的天性",
    "一个人安安静静呆一会儿", "不要去想走多远", "大哭一场会好受一点",
    "总会慢慢淡去的", "明天就会有新鲜事发生", "这种事情要靠缘分",
    "这是起跑线", "没事，有我在", "可能会很累",
    "会让周围的人感到温暖", "大概要多想一会", "值得肯定",
    "注意一下周围", "看见的都不是真的", "那将是一件乐事",
    "看向未来", "不要把所有表情都写在脸上", "未来会变得特别繁忙",
    "别人会对你苦笑", "好像会很累", "你需要的只是勇气",
    "不甘心的话，就努力争取吧", "无条件的付出", "试着更快一些",
    "不能永远一成不变", "会有一些困难", "等待下一个故事的发生",
    "试着面对自己的真实想法", "愿意并且相信", "将要奔赴一场未知的旅程",
    "隐忍", "不必要的退让", "这大概会让你有点寂寞",
    "不要轻易去相信", "这简直太有趣了", "胜券在握",
    "突如其来的幸福", "特别的见解", "值得喝一杯",
    "并不确定真伪", "不要迫于压力草率行事", "保持你的好奇心，去挖掘真相",
    "谁说得准呢，先观望着", "天上要掉馅饼了", "还有另一种情况",
    "别让它影响到你", "时机不对", "照你想的那样去做",
    "量力面行", "但行好事，莫问前程", "迷途慢慢，终有一归",
    "抛弃首选方案", "走容易走的路", "最佳方案不一定可行",
    "借助他人的经验", "再多考虑", "说出来吧",
    "机会稍纵即逝", "你就是答案", "培养一项新爱好",
    "观察形势", "休息，休息一会", "这是你最后的机会",
    "并不明智", "保持头脑清醒", "保存你的实力",
    "不确定的因素有点多", "结果不错", "等待更好的",
    "制定计划", "很麻烦", "克服困难",
    "想法太多，选择太少", "一年后就不那么重要了", "去行动",
    "发挥你的想象力", "寻找一个指路人", "能让你快乐的那个决定",
    "若眼未来", "不要等了", "不要被情绪左右",
    "不要做得太过分", "改变自己", "这是一个机会",
    "问自己什么事最重要的", "不要忧虑", "你必须弥补这个缺点",
    "忽略了一件显而易见的事", "别太赶了", "还有别的选择",
    "不好忽视自己的力量", "尽在掌握之中", "无论怎样天塌不下来",
    "这件事会给你带来极大的乐趣", "无需纠结", "老天也许在给你准备惊喜",
    "是好的", "这是最佳选择之一", "没有更好的选择",
    "铸造自己的辉煌", "不一定", "是个很好的想法",
    "无尽的可能性", "请谨慎考虑后果", "这是一个明智的投资",
    "可以从过去的经验中学习", "请利用自己的优势", "证明自己的潜力和价值",
    "这是一个有潜力的想法", "可以期待的未来", "转移你的注意力",
    "下一页才是你的人生答案(哦书里这个答案在最后一页)", "试试吧", "等待，并心怀希望",
    "answer", "为什么不问问神奇海螺呢", "我觉得你应该先开一把雀魂",
    "不懂，关注优衣先辈谢谢喵", "事已至此先睡觉吧", "嘎拉吗！",
    "为什么不问问神奇的HasFin呢", "关注斗鱼优衣先辈谢谢喵"
]


class SimpleFunctionsPlugin:
    def __init__(self, sender: MessageSender, db: Database, json_repo: JSONRepository,
                 assets_config: dict):
        self._sender = sender
        self._db = db
        self._json_repo = json_repo
        self._assets = assets_config
        self._router: Optional[CommandRouter] = None

    def register(self, router: CommandRouter) -> None:
        self._router = router
        router.register(
            ["帮助", "help", ".help", "/help"],
            self.cmd_help,
            description="查看帮助信息"
        )
        router.register(
            ["随机UE", "randomue", ".randomue", "/randomue"],
            self.cmd_random_ue,
            description="随机发送一张UE表情包"
        )
        router.register(
            ["随机hasfin", "randomhasfin", ".randomhasfin", "/randomhasfin"],
            self.cmd_random_hasfin,
            description="随机发送一张hasfin表情包"
        )
        router.register(
            ["随机半吨", "random#", ".random#", "/random#"],
            self.cmd_random_ht,
            description="随机发送一张半吨表情包"
        )
        router.register(
            ["骰子", "dice", ".dice", "/dice"],
            self.cmd_dice,
            description="掷骰子 (如: 1d100)"
        )
        router.register(
            ["抽签", "lots", ".lots", "/lots"],
            self.cmd_draw_lots,
            description="抽签,用逗号分隔选项"
        )
        router.register(
            ["抽群友", "lotsgm", ".lotsgm", "/lotsgm"],
            self.cmd_draw_lots_gm,
            description="随机抽取群友"
        )
        router.register(
            ["名人名言", "wks", ".wks#", "/wks#"],
            self.cmd_random_tale,
            description="随机名人名言"
        )
        router.register(
            ["答案之书", "answer", ".answer", "/answer"],
            self.cmd_answer_book,
            description="随机翻一个答案之书"
        )
        router.register(
            ["今日运势", "fortune", ".fortune", "/fortune"],
            self.cmd_fortune,
            description="今日运势"
        )
        router.register(
            ["今日麻将运势", "mjfortune", ".mjfortune", "/mjfortune"],
            self.cmd_mj_fortune,
            description="今日麻将运势"
        )
        router.register(
            ["记事", "note", ".note", "/note"],
            self.cmd_record_reminder,
            description="记事提醒"
        )
        router.register(
            ["结束", "stop", ".stop", "/stop"],
            self.cmd_stop,
            description="结束当前活动"
        )
        # --- 暂不可用 ---
        router.register(
            ["早安", "morning", ".morning", "/morning"],
            self.cmd_deprecated,
            description="[暂不可用] 早安打卡"
        )
        # --- 未迁移：图片相关 ---
        router.register(
            ["meme", "随机梗图", ".meme", "/meme"],
            self.cmd_deprecated,
            description="[暂不可用] 随机梗图"
        )
        router.register(
            ["gethat", "圣诞帽", ".gethat", "/gethat"],
            self.cmd_deprecated,
            description="[暂不可用] 给头像P圣诞帽"
        )
        # --- 未迁移：联赛计分 ---
        router.register(
            ["l2t", ".l2t"],
            self.cmd_deprecated,
            description="[暂不可用] 联赛等级2计分"
        )
        router.register(
            ["l1t", ".l1t"],
            self.cmd_deprecated,
            description="[暂不可用] 联赛等级1计分"
        )
        router.register(
            ["slt", ".slt"],
            self.cmd_deprecated,
            description="[暂不可用] 联赛统计"
        )
        router.register(
            ["l2p", ".l2p"],
            self.cmd_deprecated,
            description="[暂不可用] 联赛等级2对战"
        )
        # --- 未迁移：赛事计分(ueml) ---
        router.register(
            ["ueml", "赛事计分", ".ueml", "/ueml"],
            self.cmd_deprecated,
            description="[暂不可用] 联赛赛事计分"
        )
        # --- 未迁移：运势旧版 ---
        router.register(
            ["今日运势-", "fortune-", ".fortune-", "/fortune-"],
            self.cmd_deprecated,
            description="[暂不可用] 旧版运势"
        )
        router.register(
            ["今日运势+", "fortune+", ".fortune+", "/fortune+"],
            self.cmd_deprecated,
            description="[暂不可用] 新版运势(未区分)"
        )
        # --- 未迁移：祝福/占卜 ---
        router.register(
            ["秘密祝福", "secretbless", ".secretbless", "/secretbless"],
            self.cmd_deprecated,
            description="[暂不可用] 匿名秘密祝福"
        )
        router.register(
            ["赛博占卜", "赛博塔罗", "cybertarot", ".cybertarot", "ct"],
            self.cmd_deprecated,
            description="[暂不可用] 赛博塔罗牌占卜"
        )
        # --- 未迁移：麻将小游戏 ---
        router.register(
            ["清一色", "fullflush", ".fullflush", "/fullflush"],
            self.cmd_deprecated,
            description="[暂不可用] 清一色小游戏"
        )
        router.register(
            ["麻酱宝藏", "mahjonggold", "mg", ".mg"],
            self.cmd_deprecated,
            description="[暂不可用] 麻将宝藏"
        )
        router.register(
            ["17步麻将", "十七步麻将", "m17", ".m17"],
            self.cmd_deprecated,
            description="[暂不可用] 17步麻将"
        )
        router.register(
            ["麻将比大小", "mahjongwar", "mgw", ".mgw"],
            self.cmd_deprecated,
            description="[暂不可用] 麻将比大小"
        )
        router.register(
            ["麻将帝国", "mahjongempire", "mje", ".mje"],
            self.cmd_deprecated,
            description="[暂不可用] 麻将帝国"
        )
        # --- 未迁移：其他小游戏 ---
        router.register(
            ["猜单词", "hardle", ".hardle", "/hardle"],
            self.cmd_deprecated,
            description="[暂不可用] Wordle猜单词"
        )
        router.register(
            ["飞行棋", "flightchess", "fc", ".fc"],
            self.cmd_deprecated,
            description="[暂不可用] 飞行棋游戏"
        )
        router.register(
            ["快艇骰子", "yahtzee", "y", ".y"],
            self.cmd_deprecated,
            description="[暂不可用] Yahtzee快艇骰子"
        )

    def cmd_deprecated(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        self._sender.send_text(target, "这个功能暂时不可用喵~ 使用 help 查看当前可用功能")

    def cmd_help(self, ctx: CommandContext) -> None:
        args = ctx.get_args().lower()
        msg = self._generate_help(args)
        self._sender.send_text(
            Target.from_data(ctx.raw_data),
            msg
        )

    def _generate_help(self, message: str) -> str:
        if not message:
            lines = ["使用 help <指令> 查看详细说明和示例", "指令格式: 中文 | .英文 | /英文 | 英文", ""]
            if self._router:
                normal = []
                cat_cmds = []
                unavailable = []
                for cmd in self._router.get_all_commands():
                    names = "/".join(cmd.names[:3])
                    desc = cmd.description
                    if "[暂不可用]" in desc:
                        unavailable.append(f"  {names} - {desc.replace('[暂不可用] ', '')}")
                    elif desc.startswith("猫猫远征队"):
                        cat_cmds.append(f"  {names} - {desc.replace('猫猫远征队·', '')}")
                    elif names not in ("帮助", "help", ".help", "/help"):
                        normal.append(f"  {names} - {desc}")
                if normal:
                    lines.append("── 可用指令 ──")
                    lines.extend(normal)
                if cat_cmds:
                    lines.append("")
                    lines.append("── 猫猫远征队 ──")
                    lines.extend(cat_cmds)
                    lines.append("  (help 猫猫远征队 单独查看)")
                if unavailable:
                    lines.append("")
                    lines.append("── 暂不可用 ──")
                    lines.extend(unavailable)
            return "\n".join(lines)

        # 分组查看：help 猫猫远征队
        if message.strip() == "猫猫远征队":
            if self._router:
                cat_lines = ["── 猫猫远征队 ──"]
                for cmd in self._router.get_all_commands():
                    desc = cmd.description
                    if desc.startswith("猫猫远征队"):
                        names = "/".join(cmd.names[:3])
                        cat_lines.append(f"  {names} - {desc.replace('猫猫远征队·', '')}")
                return "\n".join(cat_lines)
            return "指令系统未初始化"

        help_map = {
            # --- 基础功能 ---
            "帮助": "查看帮助信息\n示例: 帮助 / help 骰子",
            "help": "查看帮助信息\n示例: 帮助 / help 骰子",
            "骰子": "ndm格式，n=数量 d=面数，默认1d100\n示例: 骰子 1d100 → 掷1个100面骰子\n示例: dice 3d6 → 掷3个6面骰子\n示例: .dice d20 → 掷1个20面骰子",
            "抽签": "逗号分隔选项，随机抽一个\n示例: 抽签 火锅,烧烤,点外卖 → 三选一\n示例: lots 睡觉,吃饭 → 二选一\n特殊: 选项含'睡觉'直接命中",
            "抽群友": "群聊中随机抽取群友，数字指定人数(默认1，最多10)\n示例: 抽群友 → 抽1个\n示例: lotsgm 3 → 抽3个\n注意: 仅群聊可用",
            "随机ue": "随机发送一张UE表情包图片\n示例: 随机UE / randomue",
            "随机hasfin": "随机发送一张hasfin表情包图片\n示例: 随机hasfin / randomhasfin",
            "随机半吨": "随机发送一张半吨表情包图片\n示例: 随机半吨 / random#",
            "名人名言": "随机发送一张名人名言图片\n示例: 名人名言 → 随机一张\n示例: wks s → 统计所有名言\n示例: wks 鲁迅 → 指定人物名言",
            "今日运势": "每人每天固定运势数值(1-100)\n示例: 今日运势 / fortune\n注意: 同一天同一人结果固定",
            "今日麻将运势": "预测麻将顺位概率(四个位置百分比)\n示例: 今日麻将运势 / mjfortune\n注意: 同一天同一人结果固定",
            "记事": "设置定时提醒\n格式: 记事 <时间> <内容> [@用户QQ号]\n时间简写: 8位(YYYYMMDD 默认早8点)\n         10位(YYYYMMDDHH 默认00分)\n         12位(YYYYMMDDHHMM 精确到分)\n示例: 记事 202609041830 开组会\n示例: 记事 20260904 交作业 → 当日8点\n示例: 记事 202609050900 123456789 交学费 → 群内@某人",
            "结束": "结束当前进行中的活动(游戏/报名等)\n示例: 结束 / stop",
            # --- AI功能 ---
            "ai": "AI对话(带上下文，按用户/群隔离)\n示例: ai 今天天气怎么样\n示例: .ai 推荐几本科幻小说\n注意: 支持联网搜索，可用 ai清空 重置对话",
            "ai清空": "清空AI对话上下文\n示例: ai清空 / .aiclear",
            "群聊总结": "暂不可用",
            "ai设置": "设置群AI自动回复概率和性格词(仅管理员)\n格式: ai设置 <概率(万分比)> <性格词>\n示例: ai设置 50 你是个毒舌的群友",
            "aisetvoice": "设置AI语音音色(仅管理员)\n示例: aisetvoice 你是个磁性大叔",
            "aivoice": "AI语音合成预览\n示例: aivoice 大家好啊",
            # --- 猫猫远征队 ---
            "喵签到": "猫猫远征队·每日签到\n每天领鱼干80-120，10%双倍，1%四倍\n连续签到每满10天额外奖励(天数×10，上限2000)\n示例: 喵签到 / catsign",
            "抽喵喵": "猫猫远征队·抽卡\n100鱼干/次，概率: 普通75% 稀有20% 史诗4% 传说1%\n重复获得升星(最高5★)，3★/5★自动转职\n满星后重复返还鱼干(普通20/稀有50/史诗100/传说500)\n每次抽卡+1猫眼石\n示例: 抽喵喵 / 抽喵喵 10",
            "兑换喵": "猫猫远征队·猫眼石兑换\n100猫眼石兑换指定喵喵，名字或id精确匹配\n示例: 兑换喵 aul1\n示例: 兑换喵 优衣喵",
            "远征队": "猫猫远征队·基础属性面板\n查看猫猫数、基础战力、鱼干、猫眼石、遗物、\n出阵/研究上限、签到与抽喵统计\n示例: 远征队 / catinfo",
            "远征": "猫猫远征队·每日远征Boss\n每天1次，对全服共享Boss造成伤害\n用法：远征（一键远征，自动使用全部猫猫）\n伤害=(全部猫基础战力+特性加成)×(0.8~1.2随机)\n每次远征天气随机（隐藏），匹配天气/地形的猫有特性加成\n血量>10%时显示详细伤害明细\n血量≤10%时只显示???\n第1/2/3名奖励不同，最后一击有额外奖励\n示例: 远征",
            "boss": "猫猫远征队·查看当前Boss信息\n显示当前关卡、Boss名、血量、地形、\n奖励预览、伤害排行榜(前10名)\n血量≤10%时隐藏血量和排行榜\n示例: boss / bossinfo",
            "科研": "猫猫远征队·科研\n远征队还在准备中，敬请期待喵～",
            "喵喵图鉴": "猫猫远征队·图鉴\n无参: 已解锁国家列表\n国家编号: 该国全部喵喵图鉴图\n喵喵id/名字: 喵喵详情卡片(需已拥有)\n示例: 喵喵图鉴 / 喵喵图鉴 ci / 喵喵图鉴 cin01 / 喵喵图鉴 斩",
            "喵地图": "猫猫远征队·世界地图\n查看世界地图\n示例: 喵地图 / catmap",
            "邮件": "猫猫远征队·全服邮件(仅管理员)\n给全服所有玩家发放鱼干或猫眼石\n示例: 邮件 鱼干 500 开服庆典！\n示例: 邮件 猫眼石 10",
            # --- 暂不可用 ---
            "dsc": "暂不可用 - Steam游戏品味评价",
            "dsc2": "暂不可用 - Steam游戏品味评价(过滤短时)",
            "aifig": "暂不可用 - AI文生图",
            "aifig2": "暂不可用 - AI图生图",
            "aifig3": "暂不可用 - AI图生图(即梦)",
            "aifig4": "暂不可用 - AI图片扩边",
            "早安": "暂不可用 - 早安打卡",
            "meme": "暂不可用 - 随机梗图",
            "gethat": "暂不可用 - 给QQ头像P圣诞帽",
            "l2t": "暂不可用 - 联赛等级2计分",
            "l1t": "暂不可用 - 联赛等级1计分",
            "slt": "暂不可用 - 联赛统计",
            "l2p": "暂不可用 - 联赛等级2对战",
            "ueml": "暂不可用 - 联赛赛事计分系统",
            "今日运势-": "暂不可用 - 旧版运势",
            "今日运势+": "暂不可用 - 新版运势(未区分)",
            "秘密祝福": "暂不可用 - 匿名秘密祝福",
            "赛博占卜": "暂不可用 - 赛博塔罗牌占卜",
            "清一色": "暂不可用 - 清一色麻将小游戏",
            "麻酱宝藏": "暂不可用 - 麻将宝藏",
            "17步麻将": "暂不可用 - 17步麻将",
            "麻将比大小": "暂不可用 - 麻将比大小",
            "麻将帝国": "暂不可用 - 麻将帝国",
            "猜单词": "暂不可用 - Wordle猜单词",
            "飞行棋": "暂不可用 - 飞行棋游戏",
            "快艇骰子": "暂不可用 - Yahtzee快艇骰子",
        }
        msg = message.strip().lower()
        return help_map.get(msg, "没有该指令的详细说明\n使用 help 查看全部指令")

    def cmd_random_ue(self, ctx: CommandContext) -> None:
        path = self._random_file(self._assets.get("uefig", ""))
        if path:
            self._sender.send_image(Target.from_data(ctx.raw_data), path)

    def cmd_random_hasfin(self, ctx: CommandContext) -> None:
        path = self._random_file(self._assets.get("hasfinfig", ""))
        if path:
            self._sender.send_image(Target.from_data(ctx.raw_data), path)

    def cmd_random_ht(self, ctx: CommandContext) -> None:
        path = self._random_file(self._assets.get("htfig", ""))
        if path:
            self._sender.send_image(Target.from_data(ctx.raw_data), path)

    def _random_file(self, folder_path: str) -> Optional[str]:
        if not folder_path or not os.path.isdir(folder_path):
            return None
        files = os.listdir(folder_path)
        if not files:
            return None
        return os.path.join(folder_path, random.choice(files))

    def cmd_dice(self, ctx: CommandContext) -> None:
        args = ctx.get_args()
        num, face = 1, 100

        if args:
            args_lower = args.lower()
            if args_lower.startswith("d"):
                face_str = args_lower[1:]
                if not face_str.isdecimal():
                    self._sender.send_text(Target.from_data(ctx.raw_data), "骰子炸了")
                    return
                face = int(face_str)
                if len(face_str) > 8:
                    self._sender.send_text(Target.from_data(ctx.raw_data), "面数太多看不清是啥")
                    return
            else:
                parts = re.split("d", args_lower)
                if len(parts) != 2 or not parts[0].isdecimal() or not parts[1].isdecimal():
                    self._sender.send_text(Target.from_data(ctx.raw_data), "骰子炸了")
                    return
                if len(parts[0]) > 3:
                    self._sender.send_text(Target.from_data(ctx.raw_data), "寄器人被骰子埋了")
                    return
                if len(parts[1]) > 8:
                    self._sender.send_text(Target.from_data(ctx.raw_data), "面数太多看不清是啥")
                    return
                num = int(parts[0])
                face = int(parts[1])

        results = [str(random.randint(1, face)) for _ in range(num)]
        self._sender.send_text(Target.from_data(ctx.raw_data), " ".join(results))

    def cmd_draw_lots(self, ctx: CommandContext) -> None:
        args = ctx.get_args()
        if not args:
            self._sender.send_text(Target.from_data(ctx.raw_data), "缺少抽签内容")
            return
        lots = re.split("[,，]", args)
        for item in lots:
            if item.strip() == "睡觉":
                self._sender.send_text(Target.from_data(ctx.raw_data), "抽到了 睡觉")
                return
        chosen = random.choice([l for l in lots if l.strip()])
        self._sender.send_text(Target.from_data(ctx.raw_data), f"抽到了 {chosen}")

    def cmd_draw_lots_gm(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        if not target.is_group:
            self._sender.send_text(target, "需要在群聊中进行")
            return

        args = ctx.get_args().strip()
        num = int(args) if args.isdigit() and args else 1
        num = max(1, min(num, 10))

        resp = self._sender.get_group_members(target.group_id)
        if resp is None:
            self._sender.send_text(target, "获取群成员失败")
            return

        try:
            members = resp.json().get("data", [])
        except (json.JSONDecodeError, KeyError):
            self._sender.send_text(target, "解析群成员失败")
            return

        selected = random.sample(members, min(num, len(members))) if members else []
        names = [m.get("nickname", str(m.get("user_id", "?"))) for m in selected]
        self._sender.send_text(target, f"抽中了: {', '.join(names)}")

    def cmd_random_tale(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        args = ctx.get_args().lower()
        folder = self._assets.get("tale", "")

        if args == "s":
            result = self._generate_tale_stats(folder)
            self._sender.send_text(target, result)
            return

        if args:
            files = [f for f in os.listdir(folder) if f.startswith(args)]
            if not files:
                self._sender.send_text(target, "没有找到匹配的名人名言")
                return
            path = os.path.join(folder, random.choice(files))
        else:
            path = self._random_file(folder)

        if path:
            self._sender.send_image(target, path)

    def cmd_answer_book(self, ctx: CommandContext) -> None:
        """答案之书：随机返回一个答案"""
        target = Target.from_data(ctx.raw_data)
        self._sender.send_text(target, random.choice(ANSWER_BOOK))

    def _generate_tale_stats(self, folder: str) -> str:
        files = os.listdir(folder)
        name_stats = defaultdict(int)
        pattern = re.compile(r"^([^\d]+)\d+")
        for filename in files:
            match = pattern.match(filename)
            if match:
                name = match.group(1).rstrip()
                name_stats[name] += 1

        result = f"名言统计：{len(files)}\n"
        newline = False
        for name, count in sorted(name_stats.items(), key=lambda x: x[1], reverse=True):
            result += f"{name}: {count}"
            result += "\n" if newline else "     "
            newline = not newline
        return result.strip()

    def cmd_fortune(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        today = str(datetime.now().strftime("%Y-%m-%d"))
        f1 = hash(today + str(target.user_id) + "123") % 100 + 1
        f2 = hash(today + str(target.user_id) + "456") % 100 + 1
        fortune = max(f1, f2)
        name = ctx.sender_nickname

        if target.user_id in [904994820]:
            self._sender.send_text(target, f"太坏的小熊猫老师 今日运势：{fortune}")
        elif fortune == 1:
            self._sender.send_text(target, f"{name} 今日运势不足2,不予显示")
        else:
            self._sender.send_text(target, f"{name} 今日运势：{fortune}")

    def cmd_mj_fortune(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        today = str(datetime.now().strftime("%Y-%m-%d"))
        stats = [0, 0, 0, 0]
        for i in range(100):
            f = hash(today + str(target.user_id) + str(i)) % 4
            stats[f] += 1
        name = ctx.sender_nickname
        self._sender.send_text(
            target,
            f"{name} 今日顺位概率{stats[0]}-{stats[1]}-{stats[2]}-{stats[3]}"
        )

    def cmd_record_reminder(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        args = ctx.get_args().split(" ", 1)

        if len(args) < 2:
            self._sender.send_text(target, "听不懂喵")
            return

        time_str = args[0]
        content = args[1]

        if not time_str.isdecimal():
            self._sender.send_text(target, "看不懂时间喵")
            return
        if len(time_str) > 12:
            self._sender.send_text(target, "时间太精确了做不到喵")
            return
        if len(time_str) < 8:
            self._sender.send_text(target, "时间太宽泛了不知道啥时候提醒嘞")
            return
        if len(time_str) in (9, 11):
            self._sender.send_text(target, "晕了喵")
            return

        if len(time_str) == 8:
            time_str = time_str + "0800"
        elif len(time_str) == 10:
            time_str = time_str + "00"

        formatted = f"{time_str[0:4]}-{time_str[4:6]}-{time_str[6:8]} {time_str[8:10]}:{time_str[10:]}:00"

        if not self._is_valid_datetime(formatted):
            self._sender.send_text(target, "这个时间是存在的吗,看不明白喵")
            return

        user_id = target.user_id
        is_group = target.is_group
        group_id = target.group_id

        parts = content.split(" ", 1) if content else []
        if len(parts) >= 2 and parts[0].isdecimal():
            user_id = int(parts[0])
            content = parts[1]
            if not target.is_group:
                self._sender.send_text(target, "只有群里能艾特别人哦")
                return

        try:
            self._db.insert_reminder(user_id, is_group, group_id, content, formatted)
            self._sender.send_text(target, "记住了(希望不会忘记提醒)")
        except Exception as e:
            self._sender.send_text(target, f"记录失败: {e}")

    def cmd_stop(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        try:
            data = self._json_repo.get(target.user_id, target.is_group, target.group_id)
            if target.is_group and data.get("group_bind"):
                player_count = data.get("data", {}).get("player_num", 0)
                for i in range(player_count):
                    self._json_repo.reset(
                        data["data"]["player_id"][i], False, target.group_id
                    )
            self._json_repo.reset(target.user_id, target.is_group, target.group_id)
            self._sender.send_text(target, "不管之前在没在干啥反正停下了,我去睡觉了喵")
        except Exception as e:
            self._sender.send_text(target, f"结束失败: {e}")

    @staticmethod
    def _is_valid_datetime(date_str: str) -> bool:
        try:
            time.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            return True
        except ValueError:
            return False
