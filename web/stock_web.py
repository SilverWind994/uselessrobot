"""串子小车 · 喵股市网页端数据层。

行情、买卖、兑换、锁仓、手续费等规则全部复用 plugins/cat_stock.py，
网页端只负责把结果整理成 JSON，并把插件发出的文案原样带回，
避免网页端与机器人端出现规则漂移。

注意：网页端不启动整点调度线程（start_scheduler=False），
既有的机器人进程负责每小时更新行情与推送快报。
"""

from plugins.cat_stock import CatStockPlugin
from core.message_sender import MessageSender, Target
import cat_web


class _CaptureSender(MessageSender):
    """网页端不真的发 QQ 消息：把插件要发出的文案收集起来，供接口返回"""

    def __init__(self):
        super().__init__()
        self.texts = []

    def send_text(self, target, text: str, at_user_id=None) -> None:
        if text:
            self.texts.append(text)

    def reply(self, ctx, text: str) -> None:
        if text:
            self.texts.append(text)

    def send_image(self, target, file_path: str) -> None:
        pass


_sender = _CaptureSender()
# 复用远征队网页端插件实例，鱼干读写与机器人端走同一份存档
_plugin = CatStockPlugin(_sender, cat_web._plugin, None, start_scheduler=False)


def _run(func, qq: int, rest: list) -> str:
    """执行插件里的一个操作，返回它原本要发给玩家的文案"""
    _sender.texts.clear()
    func(Target(user_id=qq), qq, rest)
    return "\n".join(_sender.texts).strip()


def overview(qq: int) -> dict:
    """行情 + 新闻 + 本人持仓 + 盈亏排行"""
    data = _plugin.snapshot(qq)
    data["ranking"] = _plugin.rank_players()
    return data


def buy(qq: int, code, shares) -> str:
    return _run(_plugin._buy, qq, [str(code or "").strip(), str(shares).strip()])


def sell(qq: int, code, shares) -> str:
    return _run(_plugin._sell, qq, [str(code or "").strip(), str(shares).strip()])


def deposit(qq: int, fish_amount) -> str:
    """鱼干 -> 猫薄荷"""
    return _run(_plugin._deposit, qq, [str(fish_amount).strip()])


def withdraw(qq: int, fish_amount) -> str:
    """猫薄荷 -> 鱼干"""
    return _run(_plugin._withdraw, qq, [str(fish_amount).strip()])
