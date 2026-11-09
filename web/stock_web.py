"""串子小车 · 喵股市网页端数据层。

行情、买卖、兑换、锁仓、手续费等规则全部复用 plugins/cat_stock.py，
网页端只负责把结果整理成 JSON，并把插件发出的文案原样带回，
避免网页端与机器人端出现规则漂移。

注意：网页端不启动整点调度线程（start_scheduler=False），
既有的机器人进程负责每小时更新行情与推送快报。
"""

from config import Config
from plugins.cat_stock import CatStockPlugin, STOCK_DIR, CAT_STOCK_WORLD_ADMIN
from plugins.ai_functions import AIFunctionsPlugin
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
_ai = AIFunctionsPlugin(_sender, Config.ASSETS)
# 复用远征队网页端插件实例，鱼干读写与机器人端走同一份存档
_plugin = CatStockPlugin(_sender, cat_web._plugin, _ai, start_scheduler=False)


def _run(func, qq: int, rest: list, **kwargs) -> str:
    """执行插件里的一个操作，返回它原本要发给玩家的文案"""
    _sender.texts.clear()
    func(Target(user_id=qq), qq, rest, **kwargs)
    return "\n".join(_sender.texts).strip()


def overview(qq: int) -> dict:
    """行情 + 新闻 + 本人持仓 + 盈亏排行

    同一份行情快照同时算个人收益与排行榜，避免整点更新时两边价格不一致。
    """
    market = _plugin._load_market()
    data = _plugin.snapshot(qq, market=market)
    data["ranking"] = _plugin.rank_players(market=market)
    return data


def buy(qq: int, code, shares) -> str:
    return _run(_plugin._buy, qq, [str(code or "").strip(), str(shares).strip()])


def sell(qq: int, code, shares) -> str:
    return _run(_plugin._sell, qq, [str(code or "").strip(), str(shares).strip()])


def short(qq: int, code, shares) -> str:
    """开空：押注某家企业下跌，不设固定期限，第二天起可平空"""
    return _run(_plugin._short, qq, [str(code or "").strip(), str(shares).strip()])


def cover(qq: int, code=None, shares=None) -> str:
    """平空：不填代码则全部了结"""
    rest = []
    if code:
        rest.append(str(code).strip())
        if shares not in (None, ""):
            rest.append(str(shares).strip())
    return _run(_plugin._cover, qq, rest)


def change_sector(qq: int, code, sectors, replace=True) -> str:
    """最大股东调整公司的经营方向"""
    rest = [str(code or "").strip()] + [str(s).strip() for s in (sectors or []) if str(s).strip()]
    return _run(_plugin._change_sector, qq, rest, replace=bool(replace))


def bond_buy(qq: int, code, shares) -> str:
    return _run(_plugin._bond_buy, qq, [str(code or "").strip(), str(shares).strip()])


def bond_sell(qq: int, code, shares) -> str:
    return _run(_plugin._bond_sell, qq, [str(code or "").strip(), str(shares).strip()])


def bond_policy(qq: int, code, text) -> str:
    return _run(_plugin._set_country_policy, qq, [str(code or "").strip(), str(text or "").strip()])


def deposit(qq: int, stone_amount) -> str:
    """猫眼石 -> 猫薄荷"""
    return _run(_plugin._deposit, qq, [str(stone_amount).strip()])


def withdraw(qq: int, stone_amount) -> str:
    """猫薄荷 -> 猫眼石"""
    return _run(_plugin._withdraw, qq, [str(stone_amount).strip()])


# ==================== 掌管者设置 ====================

def is_world_admin(qq) -> bool:
    """QQ 端掌管者：与隐藏指令的授权是同一个 QQ"""
    try:
        return int(qq) == int(CAT_STOCK_WORLD_ADMIN)
    except (TypeError, ValueError):
        return False


def news_effect_range() -> dict:
    """新闻单条影响的上涨/下跌上限（仅掌管者可见）"""
    up, down = _plugin.news_effect_range()
    return {"up": up, "down": down}


def set_news_effect_range(up, down) -> str:
    """分别调整上涨/下跌上限，两个都传空或「默认」恢复默认"""
    return _plugin.set_news_effect_range(up, down)


# ==================== 股东大会 ====================

def meeting_state(qq: int, code) -> dict:
    return _plugin.meeting_state(qq, str(code or "").strip())


def meeting_start(qq: int, code) -> dict:
    return _plugin.start_meeting(qq, str(code or "").strip())


def meeting_say(qq: int, code, text) -> dict:
    return _plugin.meeting_say(qq, str(code or "").strip(), str(text or ""))


def meeting_set_policy(qq: int, code, text) -> dict:
    return _plugin.meeting_set_policy(qq, str(code or "").strip(), str(text or ""))


def meeting_vote(qq: int, code, choice) -> dict:
    return _plugin.meeting_vote(qq, str(code or "").strip(), choice)


def meeting_finish(qq: int, code) -> dict:
    return _plugin.meeting_finish(qq, str(code or "").strip())


# ==================== 商战 ====================

def war_start(qq: int, code, my_code=None) -> dict:
    return _plugin.start_trade_war(qq, str(code or "").strip(), str(my_code or "").strip())


def war_activity(qq: int, code, country, kind) -> dict:
    return _plugin.war_activity(qq, str(code or "").strip(),
                                str(country or "").strip(), str(kind or "").strip())
