import json
import os
import random
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from config import Config
from core.message_sender import MessageSender, Target
from core.command_router import CommandRouter, CommandContext

# 喵股市：猫猫远征队世界观的 if 线娱乐功能。完全不改动主线存档字段，
# 只在 assets/cat_stock/ 下维护自己的行情、新闻与猫薄荷账本。

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
STOCK_DIR = os.path.join(_BASE_DIR, "assets", "cat_stock")
MARKET_PATH = os.path.join(STOCK_DIR, "market.json")
STOCK_PLAYERS_PATH = os.path.join(STOCK_DIR, "players.json")

# ==================== 经济数值 ====================
CAT_STOCK_INITIAL_CATNIP = 10000     # 每位玩家初始猫薄荷
CAT_STOCK_FISH_TO_CATNIP = 95        # 1 鱼干 -> 95 猫薄荷
CAT_STOCK_CATNIP_TO_FISH = 105       # 105 猫薄荷 -> 1 鱼干
CAT_STOCK_BUY_FEE = 0.01             # 买入手续费 1%
CAT_STOCK_SELL_FEE = 0.01            # 卖出手续费 1%
CAT_STOCK_OPEN_HOUR = 8              # 每日 08:00 开市
CAT_STOCK_CLOSE_HOUR = 20            # 每日 20:00 收市
CAT_STOCK_LOCK_HOURS = 4             # 买入后需满 4 个开市小时才能卖出
CAT_STOCK_MAX_SHARES = 1_000_000     # 单笔最大股数
CAT_STOCK_MIN_SHARES = 10            # 单笔买入最少股数
CAT_STOCK_DELIST_RATE = 0.7          # 退市清算按最新价的 70% 赔付
CAT_STOCK_DELIST_CHANCE = 0.02       # 每个整点的退市概率（偶发，不要太频繁）
CAT_STOCK_LIST_CHANCE = 0.02         # 每个整点的新上市概率（偶发，不要太频繁）
CAT_STOCK_TICK_NOISE = 0.015         # 每个整点的基础随机波动标准差
CAT_STOCK_MARKET_NOISE = 0.008       # 每个整点全市场共同情绪波动
CAT_STOCK_COUNTRY_NOISE = 0.008      # 每个整点各国家的共同波动
CAT_STOCK_EFFECT_MAX = 0.22          # 单条新闻对单只股票的单小时影响上限
CAT_STOCK_MOMENTUM_CARRY = 0.45      # 上一小时走势延续到下一小时的比例
CAT_STOCK_LINK_COUNTRY = 0.35        # 同国企业联动系数
CAT_STOCK_LINK_SECTOR = 0.25         # 同行业企业联动系数
CAT_STOCK_DELIST_BAD_RATIO = 0.6     # 股价低于基准价该比例视为持续低迷
CAT_STOCK_DELIST_BAD_TICKS = 10      # 连续低迷多少个整点才进入退市候选
CAT_STOCK_CATCHUP_MAX = 6            # 单次最多补发多少个错过的整点
CAT_STOCK_NEWS_DAYS = 3              # 新闻只保留最近 days 天
CAT_STOCK_WORLD_TICKS = 2            # 人工世界走向影响接下来几个整点
CAT_STOCK_WORLD_ADMIN = 2544910201   # 世界走向指令仅限该管理员私聊使用
CAT_STOCK_BIG_HOLDING_VALUE = 20000  # 单只股票持仓市值达到该值才可能被针对
CAT_STOCK_BIG_HOLDING_CHANCE = 0.04  # 每个整点针对大额持仓的概率
CAT_STOCK_NEWS_MAX = 200             # 新闻最多保留条数（需覆盖统计天数）
CAT_STOCK_POLICY_MIN_SHARES = 1000   # 改公司方针所需的最低持股数
CAT_STOCK_POLICY_MAX_LEN = 24        # 方针文本最大长度
CAT_STOCK_COUNTRY_MIN_LISTED = 2     # 每个国家尽量维持的上市公司数
CAT_STOCK_COMPANY_MIN = 35           # 市场最少保持的上市公司数
CAT_STOCK_COMPANY_MAX = 70           # 市场最多容纳的上市公司数
CAT_STOCK_AI_ACTION_CHANCE = 0.25    # 无世界走向时，AI 推动上市/摘牌被采纳的概率

# ==================== 世界地理 ====================
# 依据世界地图整理：land 为陆上邻国，sea 为海上/天空可达国家
_COUNTRY_GEO = {
    "vo": {"land": ["du", "ta"], "sea": []},
    "du": {"land": ["vo", "no", "ta"], "sea": []},
    "ta": {"land": ["du", "vo", "sy"], "sea": ["ze", "au"]},
    "ze": {"land": [], "sea": ["ta", "as", "au"]},
    "as": {"land": [], "sea": ["ze", "au", "dr"]},
    "au": {"land": ["sy", "za", "dr"], "sea": ["ta", "ze", "as", "ig", "ma"]},
    "ig": {"land": [], "sea": ["au", "ma", "dr"]},
    "ma": {"land": [], "sea": ["au", "ig", "dr", "so", "ab"]},
    "dr": {"land": ["au"], "sea": ["ma", "ab", "as", "ig"]},
    "sy": {"land": ["ta", "au", "za", "mo", "no"], "sea": []},
    "za": {"land": ["sy", "au", "mo", "so"], "sea": []},
    "no": {"land": ["du", "ch", "sy"], "sea": []},
    "ch": {"land": ["no", "mo"], "sea": []},
    "mo": {"land": ["ch", "sy", "za", "so"], "sea": []},
    "so": {"land": ["mo", "za"], "sea": ["ma", "ab"]},
    "ab": {"land": [], "sea": ["ma", "dr", "so"]},
    "ci": {"land": [], "sea": [], "note": "无固定国土，仅在各国雇佣据点活动"},
}

# ==================== 初始上市公司 ====================
# code / name / country / sector / base
_INITIAL_COMPANIES = [
    {"code": "FRS", "name": "霜牙兵器工坊", "country": "vo", "sector": "军备", "base": 86},
    {"code": "AUR", "name": "极光晶石行", "country": "vo", "sector": "矿脉", "base": 120},
    {"code": "EMB", "name": "余烬铸造厂", "country": "ig", "sector": "重工", "base": 64},
    {"code": "LAV", "name": "熔流运输团", "country": "ig", "sector": "物流", "base": 48},
    {"code": "VND", "name": "翠庭药材商会", "country": "sy", "sector": "草药", "base": 55},
    {"code": "LFL", "name": "叶语木工坊", "country": "sy", "sector": "木工", "base": 32},
    {"code": "SND", "name": "流沙商队", "country": "za", "sector": "贸易", "base": 70},
    {"code": "DUN", "name": "沙渊绿洲水利", "country": "za", "sector": "水利", "base": 41},
    {"code": "LUX", "name": "圣辉圣器坊", "country": "au", "sector": "圣器", "base": 150},
    {"code": "PRY", "name": "晨祷钟表行", "country": "au", "sector": "精密", "base": 92},
    {"code": "TID", "name": "潮歌航海公会", "country": "ma", "sector": "航运", "base": 78},
    {"code": "PRL", "name": "珍珠贝艺坊", "country": "ma", "sector": "奢侈", "base": 110},
    {"code": "IRN", "name": "暮铁矿务", "country": "du", "sector": "矿业", "base": 60},
    {"code": "GTL", "name": "灰门铁路", "country": "du", "sector": "交通", "base": 45},
    {"code": "THN", "name": "雷鸣锻锤行", "country": "ta", "sector": "军备", "base": 105},
    {"code": "SKY", "name": "高岭风电场", "country": "ta", "sector": "能源", "base": 88},
    {"code": "STR", "name": "星穹观星台", "country": "as", "sector": "占星", "base": 180},
    {"code": "ZRO", "name": "零重力船坞", "country": "as", "sector": "航运", "base": 210},
    {"code": "WND", "name": "长风风筝行", "country": "ze", "sector": "轻工", "base": 38},
    {"code": "GRF", "name": "疾风信使团", "country": "ze", "sector": "物流", "base": 52},
    {"code": "NOC", "name": "永夜影卫", "country": "no", "sector": "安保", "base": 96},
    {"code": "BAT", "name": "夜蝠药房", "country": "no", "sector": "医药", "base": 66},
    {"code": "CHR", "name": "时砂钟楼", "country": "ch", "sector": "精密", "base": 165},
    {"code": "PRD", "name": "悖论学社", "country": "ch", "sector": "学术", "base": 140},
    {"code": "DRM", "name": "梦沼安眠药房", "country": "so", "sector": "医药", "base": 58},
    {"code": "MST", "name": "雾沼渔获", "country": "so", "sector": "渔猎", "base": 29},
    {"code": "ABY", "name": "深渊黑市", "country": "ab", "sector": "贸易", "base": 75},
    {"code": "VOI", "name": "虚空回声矿", "country": "ab", "sector": "矿业", "base": 130},
    {"code": "MRT", "name": "骸骨殡仪社", "country": "mo", "sector": "服务", "base": 44},
    {"code": "OSS", "name": "白骨骷髅兵团", "country": "mo", "sector": "安保", "base": 84},
    {"code": "DRG", "name": "龙脊鳞甲坊", "country": "dr", "sector": "重工", "base": 175},
    {"code": "SKL", "name": "龙骨飞空团", "country": "dr", "sector": "航运", "base": 240},
    {"code": "OAT", "name": "灰誓雇佣团", "country": "ci", "sector": "服务", "base": 72},
    {"code": "CGY", "name": "灰烬熔炉", "country": "ci", "sector": "能源", "base": 63},
]

# 退市后可以重新上市的候补企业（行情激烈时补充新面孔）
_LISTING_CATALOG = [
    {"code": "MRC", "name": "魔物赏金所", "country": "ci", "sector": "服务", "base": 60},
    {"code": "ELX", "name": "元素炼金行", "country": "au", "sector": "炼金", "base": 128},
    {"code": "WYR", "name": "巨龙保险行", "country": "dr", "sector": "金融", "base": 90},
    {"code": "POT", "name": "药水速递", "country": "sy", "sector": "物流", "base": 35},
    {"code": "HRL", "name": "英雄招募处", "country": "ze", "sector": "服务", "base": 70},
    {"code": "GEM", "name": "魔晶交易所", "country": "as", "sector": "矿业", "base": 155},
    {"code": "FAE", "name": "妖精纺织", "country": "sy", "sector": "轻工", "base": 45},
    {"code": "RUN", "name": "符文刻印社", "country": "ch", "sector": "制造", "base": 102},
    {"code": "TAV", "name": "酒馆联盟", "country": "du", "sector": "消费", "base": 30},
    {"code": "SWD", "name": "断剑回收行", "country": "ci", "sector": "回收", "base": 25},
    {"code": "MNA", "name": "魔力供给所", "country": "as", "sector": "能源", "base": 80},
    {"code": "COF", "name": "棺材连锁店", "country": "mo", "sector": "服务", "base": 55},
    {"code": "PEG", "name": "飞马航空", "country": "ze", "sector": "航运", "base": 140},
    {"code": "LIC", "name": "地精银行", "country": "du", "sector": "金融", "base": 200},
    {"code": "BEA", "name": "巨兽牧场", "country": "ta", "sector": "农牧", "base": 45},
    {"code": "ICH", "name": "炼金试剂公司", "country": "au", "sector": "炼金", "base": 65},
    {"code": "VAM", "name": "吸血鬼诊所", "country": "no", "sector": "医药", "base": 88},
    {"code": "SIR", "name": "海妖歌剧院", "country": "ma", "sector": "娱乐", "base": 50},
    {"code": "RAT", "name": "鼠人巡逻队", "country": "ci", "sector": "安保", "base": 40},
    {"code": "FRO", "name": "霜冻保险公司", "country": "vo", "sector": "金融", "base": 95},
    {"code": "SAL", "name": "盐晶矿场", "country": "za", "sector": "矿业", "base": 58},
    {"code": "WEB", "name": "蛛丝纺织", "country": "so", "sector": "轻工", "base": 36},
    {"code": "ORC", "name": "兽人角斗场", "country": "ab", "sector": "娱乐", "base": 72},
    {"code": "ARC", "name": "古遗迹考古所", "country": "ch", "sector": "学术", "base": 115},
    {"code": "THR", "name": "雷石电池", "country": "ta", "sector": "能源", "base": 160},
    {"code": "FEL", "name": "妖精租车行", "country": "sy", "sector": "交通", "base": 42},
    {"code": "DRF", "name": "龙焰燃料", "country": "dr", "sector": "能源", "base": 135},
    {"code": "GRA", "name": "灰烬纸业", "country": "ci", "sector": "轻工", "base": 28},
    {"code": "NEK", "name": "夜猫快递", "country": "no", "sector": "物流", "base": 47},
    {"code": "HAU", "name": "幽灵房产", "country": "mo", "sector": "地产", "base": 68},
]

# AI 不可用时的兜底事件（奇幻世界 if 线）
_FALLBACK_EVENTS = [
    ("灰誓团与烬海共和国边境爆发冲突，军工订单激增",
     [("FRS", 0.28), ("EMB", 0.22), ("OAT", -0.18)]),
    ("魔力风暴席卷星穹议会，观星设备大面积损毁",
     [("STR", -0.26), ("ZRO", -0.14)]),
    ("凛霜部族突降千年寒潮，极光晶石供不应求",
     [("AUR", 0.24), ("FRS", 0.08)]),
    ("翡翠森庭爆发腐叶瘟疫，药材商会紧急扩产",
     [("VND", 0.21), ("DRM", 0.12), ("LFL", -0.16)]),
    ("沙渊苏丹国商路被魔物截断，香料价格暴涨",
     [("SND", 0.18), ("LAV", -0.15)]),
    ("圣辉教国宣布封圣节，圣器与钟表销量大增",
     [("LUX", 0.19), ("PRY", 0.10)]),
    ("潮歌联邦港口遭深海巨兽袭击，航线全面停摆",
     [("TID", -0.27), ("PRL", -0.12), ("SKL", 0.15)]),
    ("暮铁公国铁路被矿脉塌陷阻断，铁矿石积压",
     [("IRN", -0.15), ("GTL", -0.19), ("DRG", 0.10)]),
    ("雷鸣高原雷暴持续，风电产能创历史新高",
     [("SKY", 0.23), ("THN", -0.07)]),
    ("永夜王朝夜蝠药房研制出安神新药，销量翻倍",
     [("BAT", 0.25), ("DRM", 0.09)]),
    ("时砂遗国钟楼出现时间回溯，悖论学社被查",
     [("PRD", -0.22), ("CHR", 0.17)]),
    ("深渊王座开放黑市拍卖，虚空矿脉估值飙升",
     [("ABY", 0.20), ("VOI", 0.26), ("MRT", -0.10)]),
    ("骸骨圣所亡灵潮涌动，殡仪与安保需求激增",
     [("MRT", 0.22), ("OSS", 0.24)]),
    ("龙脊盟约与圣辉教国开战，龙甲与圣器双双大涨",
     [("DRG", 0.31), ("SKL", -0.20), ("LUX", 0.27)]),
]


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _extract_json(text: str):
    """从模型输出里抠出第一个 JSON 对象"""
    match = re.search(r"\{[\s\S]*\}", text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _market_hours_between(start: datetime, end: datetime) -> float:
    """计算两段时间内落在开市时段（08:00~20:00）的小时数，休市时间不计入"""
    if end <= start:
        return 0.0
    total = 0.0
    day = start.date()
    last = end.date()
    while day <= last:
        open_at = datetime(day.year, day.month, day.day, CAT_STOCK_OPEN_HOUR)
        close_at = datetime(day.year, day.month, day.day, CAT_STOCK_CLOSE_HOUR)
        seg_start = max(start, open_at)
        seg_end = min(end, close_at)
        if seg_end > seg_start:
            total += (seg_end - seg_start).total_seconds() / 3600.0
        day += timedelta(days=1)
    return total


def _lot_sellable(lot: dict) -> bool:
    """买入后满 4 个开市小时才能卖出，休市时间不计入"""
    try:
        bought = datetime.fromtimestamp(float(lot.get("ts", 0)))
    except (OSError, ValueError, OverflowError):
        return True
    return _market_hours_between(bought, datetime.now()) >= CAT_STOCK_LOCK_HOURS


class CatStockPlugin:
    """喵股市：奇幻世界 if 线的股票小游戏"""

    def __init__(self, sender: MessageSender, cat_game, ai_plugin=None,
                 start_scheduler: bool = True):
        self._sender = sender
        self._cat = cat_game
        self._ai = ai_plugin
        self._lock = threading.Lock()
        os.makedirs(STOCK_DIR, exist_ok=True)
        self._ensure_market()
        # 网页端复用同一个插件时不需要再起一条调度线程，避免整点重复跑 tick
        if start_scheduler:
            self._start_scheduler()

    # ==================== 注册命令 ====================

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["喵股市", "stock", ".stock", "/stock"],
            self.cmd_stock,
            description="喵股市·奇幻世界 if 线股票小游戏（大盘/新闻/持仓/买卖/兑换）"
        )
        # 隐藏指令：仅管理员私聊可用，不进帮助列表
        router.register(
            ["世界走向", "world"],
            self.cmd_world,
            description="外部世界走向",
            permission_check=lambda ctx: ctx.is_private and ctx.user_id == CAT_STOCK_WORLD_ADMIN
        )

    # ==================== 行情存档 ====================

    def _ensure_market(self) -> None:
        """首次运行时用静态企业表生成行情文件"""
        if os.path.exists(MARKET_PATH):
            return
        companies = {}
        for c in _INITIAL_COMPANIES:
            companies[c["code"]] = {
                "code": c["code"],
                "name": c["name"],
                "country": c["country"],
                "sector": c["sector"],
                "base": c["base"],
                "price": float(c["base"]),
                "prev_close": float(c["base"]),
            }
        state = {
            "day": "",
            "companies": companies,
            "catalog": list(_LISTING_CATALOG),
            "news": [],
            "last_tick": "",
        }
        _save_json(MARKET_PATH, state)

    def _load_market(self) -> dict:
        state = _load_json(MARKET_PATH)
        if not state or "companies" not in state:
            self._ensure_market()
            state = _load_json(MARKET_PATH)
        state.setdefault("news", [])
        state.setdefault("catalog", list(_LISTING_CATALOG))
        state.setdefault("last_tick", "")
        state.setdefault("day", "")
        state.setdefault("world", {"arc": "", "relations": []})
        state.setdefault("world_directives", [])
        return state

    def _save_market(self, state: dict) -> None:
        _save_json(MARKET_PATH, state)

    def _load_stock_players(self) -> dict:
        return _load_json(STOCK_PLAYERS_PATH)

    def _save_stock_players(self, players: dict) -> None:
        _save_json(STOCK_PLAYERS_PATH, players)

    def _stock_player(self, qq: int, players: dict) -> dict:
        """取玩家股市账本，首次使用赠送初始猫薄荷"""
        key = str(qq)
        if key not in players:
            players[key] = {"catnip": CAT_STOCK_INITIAL_CATNIP, "holdings": {}}
        st = players[key]
        st.setdefault("catnip", CAT_STOCK_INITIAL_CATNIP)
        st.setdefault("holdings", {})
        return st

    # ==================== 小工具 ====================

    @staticmethod
    def _is_open(now: datetime) -> bool:
        return CAT_STOCK_OPEN_HOUR <= now.hour < CAT_STOCK_CLOSE_HOUR

    @staticmethod
    def _fmt_price(price: float) -> str:
        return f"{price:.1f}"

    @staticmethod
    def _fmt_pct(pct: float) -> str:
        return f"{pct:+.1f}%"

    def _country_name(self, code: str) -> str:
        countries = getattr(self._cat, "_countries", {}) or {}
        return countries.get(code, code)

    def _are_adjacent(self, a: str, b: str) -> bool:
        geo = _COUNTRY_GEO.get(a) or {}
        return b in geo.get("land", []) or b in geo.get("sea", [])

    def _geography_prompt(self) -> str:
        lines = ["\n世界地理（国家间互动必须符合地图距离与连通性）："]
        for code, geo in _COUNTRY_GEO.items():
            name = self._country_name(code)
            if geo.get("note"):
                lines.append(f"- {name}（{code}）：{geo['note']}")
                continue
            land = "、".join(self._country_name(c) for c in geo["land"]) or "无"
            sea = "、".join(self._country_name(c) for c in geo["sea"]) or "无"
            lines.append(f"- {name}（{code}）：陆上邻国 {land}；海上/天空可达 {sea}")
        lines.append("边境摩擦、领土争端、陆路商队与陆上军事行动只能发生在陆上邻国之间；"
                     "海上封锁、海战、跨海远征与空袭只能发生在海上/天空可达国家之间；"
                     "既不相邻也不海上可达的国家之间，只能通过使团、远洋贸易、"
                     "代理战争或第三方转口产生间接影响，不得写成直接边境摩擦或海上冲突。"
                     "断交、结盟等外交行为可以跨国发生，但需说明是经由使团或第三方牵线。\n")
        return "\n".join(lines)

    def _resolve_company(self, market: dict, text: str) -> Optional[dict]:
        """按代码或名称匹配企业"""
        text = (text or "").strip()
        companies = market["companies"]
        if not text:
            return None
        up = text.upper()
        if up in companies:
            return companies[up]
        for comp in companies.values():
            if comp["name"] == text:
                return comp
        for comp in companies.values():
            if text in comp["name"]:
                return comp
        return None

    def _shares_of(self, lots: List[dict]) -> int:
        return sum(int(lot.get("shares", 0)) for lot in lots)

    def _avg_cost(self, lots: List[dict]) -> float:
        shares = self._shares_of(lots)
        if shares <= 0:
            return 0.0
        return sum(float(lot.get("price", 0)) * int(lot.get("shares", 0)) for lot in lots) / shares

    # ==================== 命令入口 ====================

    def cmd_stock(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        args = ctx.get_args()
        if not args:
            self._show_market(target, full=False)
            return

        parts = args.split()
        sub = parts[0].lower()
        rest = parts[1:]

        if sub in ("帮助", "help", "说明"):
            self._sender.send_text(target, self._help_text())
        elif sub in ("大盘", "行情", "市场"):
            self._show_market(target, full=True)
        elif sub in ("新闻", "快报", "消息"):
            self._show_news(target)
        elif sub in ("持仓", "仓位", "我的"):
            self._show_holdings(target, ctx.user_id)
        elif sub in ("排行", "榜单", "排名", "盈亏榜", "rank"):
            self._show_rank(target)
        elif sub in ("买", "买入", "购", "buy"):
            self._buy(target, ctx.user_id, rest)
        elif sub in ("卖", "卖出", "抛", "抛售", "sell"):
            self._sell(target, ctx.user_id, rest)
        elif sub in ("充值", "兑", "兑换", "存入"):
            self._deposit(target, ctx.user_id, rest)
        elif sub in ("提现", "取", "取出"):
            self._withdraw(target, ctx.user_id, rest)
        elif sub in ("方针", "政策", "policy"):
            self._set_policy(target, ctx.user_id, rest)
        else:
            # 直接输入企业代码/名称时给出该股详情
            comp = self._resolve_company(self._load_market(), parts[0])
            if comp:
                self._show_company(target, comp)
            else:
                self._sender.send_text(
                    target,
                    "没有这个子命令喵～ 可用：大盘 / 新闻 / 持仓 / 买 / 卖 / 充值 / 提现 / 排行 / 方针\n"
                    "发送「喵股市 帮助」查看完整说明"
                )

    # ==================== 隐藏指令：世界走向 ====================

    def cmd_world(self, ctx: CommandContext) -> None:
        target = Target.from_data(ctx.raw_data)
        raw = ctx.get_args().strip()
        ticks = CAT_STOCK_WORLD_TICKS
        text = raw
        head, _, tail = raw.partition(" ")
        if head.isdigit():
            ticks = max(1, min(48, int(head)))
            text = tail.strip()
        with self._lock:
            market = self._load_market()
            directives = market.setdefault("world_directives", [])
            if text:
                directives.append({"text": text[:100],
                                   "ticks": ticks,
                                   "remaining": ticks,
                                   "at": datetime.now().strftime("%m-%d %H:%M")})
                market["world_directives"] = directives[-20:]
                message = (f"已记录世界走向：{text[:100]}\n"
                           f"将在接下来 {ticks} 个整点影响世界局势、新闻与股价。")
            else:
                active = [d for d in directives if int(d.get("remaining", 0)) > 0]
                if active:
                    message = "当前生效的世界走向：\n" + "\n".join(
                        f"- {d.get('text', '')}（剩 {int(d.get('remaining', 0))} 个整点）"
                        for d in active)
                else:
                    message = ("当前没有生效中的世界走向。\n"
                               "用法：世界走向 <窗口数> <内容>（窗口数可省略，默认 2）")
            self._save_market(market)
        self._sender.send_text(target, message)

    # ==================== 展示 ====================

    def _market_status_line(self) -> str:
        now = datetime.now()
        if self._is_open(now):
            return f"开市中（08:00~20:00）｜当前 {now.strftime('%H:%M')}"
        return f"休市中（08:00~20:00）｜当前 {now.strftime('%H:%M')}"

    def _show_market(self, target: Target, full: bool) -> None:
        market = self._load_market()
        companies = market["companies"]
        up = sum(1 for c in companies.values() if c["price"] >= c.get("prev_close", c["price"]))
        down = len(companies) - up

        lines = [f"【喵股市 · 大盘】{self._market_status_line()}"]
        lines.append(f"在市企业 {len(companies)} 家｜上涨 {up} 家 · 下跌 {down} 家")

        # 按国家分组
        grouped: Dict[str, List[dict]] = {}
        for comp in companies.values():
            grouped.setdefault(comp["country"], []).append(comp)
        for country in grouped:
            lines.append("")
            lines.append(f"── {self._country_name(country)} ──")
            for comp in grouped[country]:
                prev = comp.get("prev_close") or comp["price"] or 1
                pct = (comp["price"] - prev) / prev * 100
                arrow = "▲" if pct >= 0 else "▼"
                lines.append(
                    f"{comp['code']} {comp['name']} {self._fmt_price(comp['price'])} "
                    f"{arrow}{abs(pct):.1f}% ({comp['sector']})"
                )
        if not full:
            lines.append("")
            lines.append("买入: 喵股市 买 <代码> <股数>｜卖出: 喵股市 卖 <代码> <股数>")
        lines.append("")
        lines.append("发送「喵股市 帮助」查看规则与手续费")
        self._sender.send_text(target, "\n".join(lines))

    def _show_company(self, target: Target, comp: dict) -> None:
        prev = comp.get("prev_close") or comp["price"] or 1
        pct = (comp["price"] - prev) / prev * 100
        lines = [
            f"【{comp['code']} {comp['name']}】",
            f"国家：{self._country_name(comp['country'])}｜行业：{comp['sector']}",
            f"现价：{self._fmt_price(comp['price'])}｜今日 {self._fmt_pct(pct)}",
            f"基准价：{comp['base']}｜买入手续费 {CAT_STOCK_BUY_FEE:.0%}，卖出手续费 {CAT_STOCK_SELL_FEE:.0%}",
            f"公司方针：{comp.get('policy') or '暂无（最大股东可制定）'}",
            f"买入：喵股市 买 {comp['code']} <股数>",
        ]
        self._sender.send_text(target, "\n".join(lines))

    def _show_news(self, target: Target) -> None:
        market = self._load_market()
        news = market.get("news", [])[:12]
        if not news:
            self._sender.send_text(target, "还没有新闻喵～ 股市开市后每个整点会更新世界快报")
            return
        lines = [f"【喵股市 · 最近新闻】{self._market_status_line()}"]
        for item in news:
            lines.append("")
            lines.append(f"· {item.get('time', '')} {item.get('title', '')}")
            detail = item.get("detail") or ""
            if detail:
                lines.append(f"  {detail}")
        self._sender.send_text(target, "\n".join(lines))

    def _show_holdings(self, target: Target, qq: int) -> None:
        market = self._load_market()
        with self._lock:
            players = self._load_stock_players()
            st = self._stock_player(qq, players)
            catnip = int(st.get("catnip", 0))
            holdings = {k: list(v) for k, v in st.get("holdings", {}).items()}
            self._save_stock_players(players)

        lines = [f"【喵股市 · 我的持仓】{self._market_status_line()}"]
        lines.append(f"猫薄荷：{catnip}｜约合鱼干：{catnip // CAT_STOCK_CATNIP_TO_FISH}（提现 105:1）")
        if not holdings:
            lines.append("当前空仓")
            self._sender.send_text(target, "\n".join(lines))
            return

        total_value = 0.0
        total_cost = 0.0
        for code, lots in holdings.items():
            comp = market["companies"].get(code)
            shares = self._shares_of(lots)
            cost = sum(float(l.get("price", 0)) * int(l.get("shares", 0)) for l in lots)
            if not comp:
                lines.append(f"{code}：{shares} 股（已退市，待清算）")
                continue
            value = shares * comp["price"]
            total_value += value
            total_cost += cost
            sellable = sum(int(l.get("shares", 0)) for l in lots if _lot_sellable(l))
            locked = shares - sellable
            avg = cost / shares if shares else 0
            pnl = value - cost
            lock_text = f"｜可卖 {sellable}，锁定 {locked}" if locked else "｜全部可卖"
            lines.append(
                f"{code} {comp['name']}：{shares} 股\n"
                f"  成本 {avg:.1f}｜现价 {self._fmt_price(comp['price'])}｜"
                f"市值 {value:.0f}｜浮动 {pnl:+.0f}{lock_text}"
            )
        total_pnl = total_value - total_cost
        lines.append("")
        lines.append(f"总市值：{total_value:.0f}｜总浮动：{total_pnl:+.0f}｜猫薄荷：{catnip}")
        lines.append("（买入后满 4 个交易小时才能卖出，休市时间不计入）")
        self._sender.send_text(target, "\n".join(lines))

    # ==================== 盈亏排行 ====================

    def rank_players(self) -> List[dict]:
        """按累计盈亏排序（从高到低）

        盈亏 =（猫薄荷 + 持仓市值）-（初始 10000 + 累计充值 - 累计提现），
        这样充值/提现不会被误算成盈利或亏损。
        """
        market = self._load_market()
        companies = market["companies"]
        players = self._load_stock_players()
        cat_players = self._cat._load_players()
        rows: List[dict] = []
        for key, st in players.items():
            catnip = int(st.get("catnip", 0))
            value = 0.0
            for code, lots in st.get("holdings", {}).items():
                comp = companies.get(code)
                if comp:
                    value += self._shares_of(lots) * comp["price"]
            net_in = (CAT_STOCK_INITIAL_CATNIP
                      + int(st.get("deposit_catnip", 0))
                      - int(st.get("withdraw_catnip", 0)))
            assets = catnip + value
            profit = assets - net_in
            player = cat_players.get(str(key)) or {}
            rows.append({
                "nick": player.get("nick") or "无名喵",
                "assets": int(round(assets)),
                "profit": int(round(profit)),
                "pct": round(profit / net_in * 100, 1) if net_in > 0 else 0.0,
            })
        rows.sort(key=lambda r: r["profit"], reverse=True)
        return rows

    def _show_rank(self, target: Target, limit: int = 5) -> None:
        rows = self.rank_players()
        if not rows:
            self._sender.send_text(target, "喵股市还没有人入场喵～ 发送「喵股市 充值」开始炒股")
            return
        lines = [f"【喵股市 · 盈亏排行】共 {len(rows)} 位股东"]
        lines.append("")
        lines.append("🏆 收益榜")
        for i, r in enumerate(rows[:limit], 1):
            lines.append(f"{i}. {r['nick']} {r['profit']:+d} 猫薄荷（{r['pct']:+.1f}%）")
        losers = [r for r in rows if r["profit"] < 0][::-1][:limit]
        lines.append("")
        lines.append("💀 亏损榜（亏得最惨）")
        if losers:
            for i, r in enumerate(losers, 1):
                lines.append(f"{i}. {r['nick']} {r['profit']:d} 猫薄荷（{r['pct']:.1f}%）")
        else:
            lines.append("暂时全员盈利，没人亏钱喵")
        lines.append("")
        lines.append("盈亏 =（猫薄荷 + 持仓市值）-（初始 10000 + 累计充值 - 累计提现）")
        self._sender.send_text(target, "\n".join(lines))

    # ==================== 交易 ====================

    def _buy(self, target: Target, qq: int, rest: List[str]) -> None:
        now = datetime.now()
        if not self._is_open(now):
            self._sender.send_text(target, "现在是休市时间喵～ 股市每日 08:00~20:00 开市")
            return
        if len(rest) < 2:
            self._sender.send_text(target, "用法：喵股市 买 <股票代码/名称> <股数>")
            return

        market = self._load_market()
        comp = self._resolve_company(market, rest[0])
        if not comp:
            self._sender.send_text(target, f"找不到企业「{rest[0]}」，发送「喵股市 大盘」查看代码")
            return
        try:
            shares = int(rest[1])
        except ValueError:
            self._sender.send_text(target, "股数必须是正整数喵")
            return
        if shares <= 0:
            self._sender.send_text(target, "股数必须是正整数喵")
            return
        if shares > CAT_STOCK_MAX_SHARES:
            self._sender.send_text(
                target, f"单笔最多 {CAT_STOCK_MAX_SHARES} 股喵～")
            return
        if shares < CAT_STOCK_MIN_SHARES:
            self._sender.send_text(
                target, f"单笔最少买 {CAT_STOCK_MIN_SHARES} 股喵～")
            return

        price = float(comp["price"])
        cost = int(round(price * shares))
        fee = max(1, int(round(cost * CAT_STOCK_BUY_FEE)))
        total = cost + fee

        with self._lock:
            players = self._load_stock_players()
            st = self._stock_player(qq, players)
            catnip = int(st.get("catnip", 0))
            if catnip < total:
                self._save_stock_players(players)
                self._sender.send_text(
                    target,
                    f"猫薄荷不足喵：{shares} 股 × {self._fmt_price(price)} + 手续费 {fee} = {total}，"
                    f"你只有 {catnip}\n可用「喵股市 充值 <鱼干数>」按 1:95 兑换猫薄荷"
                )
                return
            st["catnip"] = catnip - total
            lots = st["holdings"].setdefault(comp["code"], [])
            lots.append({"shares": shares, "price": price, "ts": time.time()})
            self._save_stock_players(players)
            new_balance = st["catnip"]

        self._sender.send_text(
            target,
            f"买入成交：{comp['code']} {comp['name']} {shares} 股\n"
            f"成交价 {self._fmt_price(price)}｜成交额 {cost}｜手续费 {fee}\n"
            f"剩余猫薄荷 {new_balance}\n"
            f"（买入后满 4 个交易小时才能卖出，休市时间不计入）"
        )

    def _sell(self, target: Target, qq: int, rest: List[str]) -> None:
        now = datetime.now()
        if not self._is_open(now):
            self._sender.send_text(target, "现在是休市时间喵～ 股市每日 08:00~20:00 开市")
            return
        if len(rest) < 2:
            self._sender.send_text(target, "用法：喵股市 卖 <股票代码/名称> <股数>")
            return

        market = self._load_market()
        comp = self._resolve_company(market, rest[0])
        if not comp:
            self._sender.send_text(target, f"找不到企业「{rest[0]}」，发送「喵股市 大盘」查看代码")
            return
        try:
            shares = int(rest[1])
        except ValueError:
            self._sender.send_text(target, "股数必须是正整数喵")
            return
        if shares <= 0:
            self._sender.send_text(target, "股数必须是正整数喵")
            return

        price = float(comp["price"])

        with self._lock:
            players = self._load_stock_players()
            st = self._stock_player(qq, players)
            lots = st["holdings"].get(comp["code"], [])
            sellable = sum(int(l.get("shares", 0)) for l in lots if _lot_sellable(l))
            if sellable <= 0:
                self._save_stock_players(players)
                self._sender.send_text(
                    target,
                    f"{comp['code']} 当前没有可卖出的股份\n"
                    f"买入后满 4 个交易小时才能卖出（只计算开市时间）"
                )
                return
            if shares > sellable:
                self._save_stock_players(players)
                self._sender.send_text(
                    target,
                    f"可卖数量不足喵：{comp['code']} 现在只能卖 {sellable} 股"
                    f"（其余为未满 4 个交易小时的持仓）"
                )
                return

            remaining = shares
            kept_lots = []
            for lot in lots:
                if remaining <= 0:
                    kept_lots.append(lot)
                    continue
                lot_shares = int(lot.get("shares", 0))
                if not _lot_sellable(lot) or lot_shares <= 0:
                    kept_lots.append(lot)
                    continue
                take = min(remaining, lot_shares)
                remaining -= take
                if lot_shares > take:
                    kept = dict(lot)
                    kept["shares"] = lot_shares - take
                    kept_lots.append(kept)
            if remaining > 0:
                self._save_stock_players(players)
                self._sender.send_text(target, "卖出失败：可卖数量核对异常喵")
                return
            if kept_lots:
                st["holdings"][comp["code"]] = kept_lots
            else:
                st["holdings"].pop(comp["code"], None)

            proceeds = int(round(price * shares))
            fee = max(1, int(round(proceeds * CAT_STOCK_SELL_FEE)))
            net = proceeds - fee
            st["catnip"] = int(st.get("catnip", 0)) + net
            self._save_stock_players(players)
            new_balance = st["catnip"]

        self._sender.send_text(
            target,
            f"卖出成交：{comp['code']} {comp['name']} {shares} 股\n"
            f"成交价 {self._fmt_price(price)}｜成交额 {proceeds}｜手续费 {fee}｜到手 {net}\n"
            f"剩余猫薄荷 {new_balance}"
        )

    # ==================== 公司方针 ====================

    def _set_policy(self, target: Target, qq: int, rest: List[str]) -> None:
        """最大股东为公司制定方针；AI 每个整点写新闻时会参考方针"""
        if not rest:
            self._sender.send_text(
                target,
                "用法：喵股市 方针 <股票代码> <方针内容>\n"
                f"条件：持有该公司 ≥{CAT_STOCK_POLICY_MIN_SHARES} 股，且是该公司最大股东\n"
                "示例：喵股市 方针 FRS 稳健经营，优先交付长期军备订单"
            )
            return
        comp = self._resolve_company(self._load_market(), rest[0])
        if not comp:
            self._sender.send_text(target, f"找不到企业「{rest[0]}」，发送「喵股市 大盘」查看代码")
            return
        code = comp["code"]
        text = " ".join(rest[1:]).strip()

        if not text:
            self._sender.send_text(
                target, f"{comp['name']}（{code}）当前方针：{comp.get('policy') or '暂无'}")
            return

        with self._lock:
            players = self._load_stock_players()
            mine = self._shares_of(self._stock_player(qq, players).get("holdings", {}).get(code, []))
            max_shares = max(
                [mine] + [self._shares_of(st.get("holdings", {}).get(code, []))
                          for st in players.values()]
            )
            self._save_stock_players(players)
            if mine < CAT_STOCK_POLICY_MIN_SHARES:
                self._sender.send_text(
                    target,
                    f"你在 {code} 只有 {mine} 股，至少持有 {CAT_STOCK_POLICY_MIN_SHARES} 股才能制定方针喵")
                return
            if mine < max_shares:
                self._sender.send_text(
                    target,
                    f"你不是 {code} 的最大股东（最大持股 {max_shares} 股），方针要由最大股东拍板喵")
                return

            market = self._load_market()
            comp = market["companies"].get(code)
            if not comp:
                self._sender.send_text(target, f"{code} 已经退市了喵～")
                return
            comp["policy"] = text[:CAT_STOCK_POLICY_MAX_LEN]
            comp["policy_owner"] = qq
            comp["policy_set_at"] = datetime.now().strftime("%Y-%m-%d")
            self._save_market(market)

        self._sender.send_text(
            target,
            f"【{comp['name']}】方针已更新为：{comp['policy']}\n"
            "接下来的整点快报里，AI 会参考这条方针来写新闻与调整市场情绪喵～"
        )

    # ==================== 鱼干 / 猫薄荷兑换 ====================

    def _deposit(self, target: Target, qq: int, rest: List[str]) -> None:
        if not rest:
            self._sender.send_text(
                target,
                f"用法：喵股市 充值 <鱼干数>\n兑换比例 {CAT_STOCK_FISH_TO_CATNIP} 猫薄荷 / 鱼干"
            )
            return
        try:
            fish_amount = int(rest[0])
        except ValueError:
            self._sender.send_text(target, "鱼干数必须是正整数喵")
            return
        if fish_amount <= 0:
            self._sender.send_text(target, "鱼干数必须是正整数喵")
            return

        player = self._cat._get_player(qq)
        if int(player.get("fish", 0)) < fish_amount:
            self._sender.send_text(
                target,
                f"鱼干不足喵：你有 {player.get('fish', 0)}，需要 {fish_amount}"
            )
            return
        player["fish"] = int(player.get("fish", 0)) - fish_amount
        self._cat._update_player(qq, player)

        gain = fish_amount * CAT_STOCK_FISH_TO_CATNIP
        with self._lock:
            players = self._load_stock_players()
            st = self._stock_player(qq, players)
            st["catnip"] = int(st.get("catnip", 0)) + gain
            # 记录累计充值，用于盈亏排行计算（不算作盈利）
            st["deposit_catnip"] = int(st.get("deposit_catnip", 0)) + gain
            self._save_stock_players(players)
            catnip = st["catnip"]

        self._sender.send_text(
            target,
            f"充值成功：-{fish_amount} 鱼干，+{gain} 猫薄荷\n"
            f"当前猫薄荷 {catnip}｜剩余鱼干 {player['fish']}"
        )

    def _withdraw(self, target: Target, qq: int, rest: List[str]) -> None:
        if not rest:
            self._sender.send_text(
                target,
                f"用法：喵股市 提现 <鱼干数>\n需要 {CAT_STOCK_CATNIP_TO_FISH} 猫薄荷 / 鱼干"
            )
            return
        try:
            fish_amount = int(rest[0])
        except ValueError:
            self._sender.send_text(target, "鱼干数必须是正整数喵")
            return
        if fish_amount <= 0:
            self._sender.send_text(target, "鱼干数必须是正整数喵")
            return

        need = fish_amount * CAT_STOCK_CATNIP_TO_FISH
        with self._lock:
            players = self._load_stock_players()
            st = self._stock_player(qq, players)
            catnip = int(st.get("catnip", 0))
            if catnip < need:
                self._save_stock_players(players)
                self._sender.send_text(
                    target,
                    f"猫薄荷不足喵：提现 {fish_amount} 鱼干需要 {need} 猫薄荷，你只有 {catnip}"
                )
                return
            st["catnip"] = catnip - need
            # 记录累计提现，用于盈亏排行计算（不算作亏损）
            st["withdraw_catnip"] = int(st.get("withdraw_catnip", 0)) + need
            self._save_stock_players(players)
            left = st["catnip"]

        self._cat.add_fish(qq, fish_amount)
        self._sender.send_text(
            target,
            f"提现成功：-{need} 猫薄荷，+{fish_amount} 鱼干\n剩余猫薄荷 {left}"
        )

    # ==================== 猫薄荷转账（红包/赠送） ====================

    def catnip_balance(self, qq: int) -> int:
        """取玩家猫薄荷余额（首次使用会建账并发放初始猫薄荷）"""
        with self._lock:
            players = self._load_stock_players()
            return int(self._stock_player(qq, players).get("catnip", 0))

    def catnip_transfer_out(self, qq: int, amount: int) -> Tuple[bool, int]:
        """转出猫薄荷：余额不足返回 (False, 余额)。

        金额记入累计提现流水，保证股市盈亏排行不受红包影响。"""
        if amount <= 0:
            return False, 0
        with self._lock:
            players = self._load_stock_players()
            st = self._stock_player(qq, players)
            balance = int(st.get("catnip", 0))
            if balance < amount:
                self._save_stock_players(players)
                return False, balance
            st["catnip"] = balance - amount
            st["withdraw_catnip"] = int(st.get("withdraw_catnip", 0)) + amount
            self._save_stock_players(players)
            return True, st["catnip"]

    def catnip_transfer_in(self, qq: int, amount: int) -> int:
        """转入猫薄荷：金额记入累计充值流水，保证股市盈亏排行不受红包影响"""
        with self._lock:
            players = self._load_stock_players()
            st = self._stock_player(qq, players)
            st["catnip"] = int(st.get("catnip", 0)) + amount
            st["deposit_catnip"] = int(st.get("deposit_catnip", 0)) + amount
            self._save_stock_players(players)
            return st["catnip"]

    # ==================== 网页端数据接口 ====================

    def _recent_news(self, news: list) -> list:
        """只保留最近 CAT_STOCK_NEWS_DAYS 天的新闻"""
        now = datetime.now()
        cutoff = now.timestamp() - CAT_STOCK_NEWS_DAYS * 86400
        result = []
        for item in news:
            ts = item.get("ts")
            if not ts:
                try:
                    stamp = datetime.strptime(item.get("time", ""), "%m-%d %H:%M")
                except ValueError:
                    result.append(item)
                    continue
                stamp = stamp.replace(year=now.year)
                if stamp.timestamp() > now.timestamp() + 86400:
                    stamp = stamp.replace(year=stamp.year - 1)
                ts = stamp.timestamp()
            if ts >= cutoff:
                result.append(item)
        return result

    def snapshot(self, qq: Optional[int] = None) -> dict:
        """整理成网页端用的结构化行情 / 新闻 / 持仓（只读，不改动存档）"""
        market = self._load_market()
        now = datetime.now()
        companies = market["companies"]

        rows = []
        for comp in companies.values():
            prev = comp.get("prev_close") or comp["price"] or 1
            pct = (comp["price"] - prev) / prev * 100
            rows.append({
                "code": comp["code"],
                "name": comp["name"],
                "country": comp["country"],
                "country_name": self._country_name(comp["country"]),
                "sector": comp["sector"],
                "base": comp["base"],
                "price": round(float(comp["price"]), 2),
                "pct": round(pct, 2),
                "policy": comp.get("policy") or "",
            })
        rows.sort(key=lambda r: (r["country"], r["code"]))
        up = sum(1 for r in rows if r["pct"] >= 0)

        news = [{"time": item.get("time", ""),
                 "title": item.get("title", ""),
                 "detail": item.get("detail", "")}
                for item in self._recent_news(market.get("news", []))[:40]]
        world = market.get("world") or {}
        world_view = {
            "arc": str(world.get("arc") or ""),
            "relations": [{
                "a": rel.get("a", ""), "a_name": self._country_name(rel.get("a", "")),
                "b": rel.get("b", ""), "b_name": self._country_name(rel.get("b", "")),
                "state": rel.get("state", ""),
            } for rel in (world.get("relations") or [])[:10]],
        }

        data = {
            "open": self._is_open(now),
            "status_line": self._market_status_line(),
            "open_hour": CAT_STOCK_OPEN_HOUR,
            "close_hour": CAT_STOCK_CLOSE_HOUR,
            "companies": rows,
            "up": up,
            "down": len(rows) - up,
            "news": news,
            "world": world_view,
            "rules": {
                "initial_catnip": CAT_STOCK_INITIAL_CATNIP,
                "fish_to_catnip": CAT_STOCK_FISH_TO_CATNIP,
                "catnip_to_fish": CAT_STOCK_CATNIP_TO_FISH,
                "buy_fee": CAT_STOCK_BUY_FEE,
                "sell_fee": CAT_STOCK_SELL_FEE,
                "lock_note": "买入后满 4 个交易小时才能卖出（休市不计）",
                "max_shares": CAT_STOCK_MAX_SHARES,
                "delist_rate": CAT_STOCK_DELIST_RATE,
            },
        }
        if qq is not None:
            data["portfolio"] = self._portfolio_view(qq, companies)
        return data

    def _portfolio_view(self, qq: int, companies: dict) -> dict:
        """某个玩家的持仓明细（含可卖 / 锁定股数）"""
        with self._lock:
            players = self._load_stock_players()
            st = self._stock_player(qq, players)
            catnip = int(st.get("catnip", 0))
            raw = {code: list(lots) for code, lots in st.get("holdings", {}).items()}
            self._save_stock_players(players)

        rows = []
        total_value = 0.0
        total_cost = 0.0
        for code, lots in raw.items():
            comp = companies.get(code)
            shares = self._shares_of(lots)
            cost = sum(float(lot.get("price", 0)) * int(lot.get("shares", 0)) for lot in lots)
            if not comp:
                rows.append({"code": code, "name": code, "shares": shares, "sellable": 0,
                             "locked": shares, "avg_cost": 0, "price": 0, "value": 0,
                             "pnl": 0, "delisted": True})
                continue
            value = shares * comp["price"]
            total_value += value
            total_cost += cost
            sellable = sum(int(lot.get("shares", 0)) for lot in lots if _lot_sellable(lot))
            avg = cost / shares if shares else 0
            rows.append({
                "code": code,
                "name": comp["name"],
                "shares": shares,
                "sellable": sellable,
                "locked": shares - sellable,
                "avg_cost": round(avg, 2),
                "price": round(float(comp["price"]), 2),
                "value": round(value, 0),
                "pnl": round(value - cost, 0),
                "delisted": False,
            })
        rows.sort(key=lambda r: r["value"], reverse=True)

        player = self._cat._peek_player(qq) or {}
        return {
            "catnip": catnip,
            "fish": int(player.get("fish", 0)),
            "catnip_to_fish_est": catnip // CAT_STOCK_CATNIP_TO_FISH,
            "holdings": rows,
            "total_value": round(total_value, 0),
            "total_pnl": round(total_value - total_cost, 0),
        }

    # ==================== 帮助 ====================

    def _help_text(self) -> str:
        return (
            "【喵股市 · 奇幻世界 if 线】\n"
            "这是猫猫远征队世界观的一条平行时间线，涨跌与新闻不会影响主线存档。\n"
            f"开市时间：每天 {CAT_STOCK_OPEN_HOUR:02d}:00 ~ {CAT_STOCK_CLOSE_HOUR:02d}:00，"
            "每个整点 AI 发布世界新闻并重新定价；休市期间不能买卖。\n"
            f"初始猫薄荷：每人 {CAT_STOCK_INITIAL_CATNIP}（首次使用自动到账）\n"
            f"充值：喵股市 充值 <鱼干数>（1 鱼干 = {CAT_STOCK_FISH_TO_CATNIP} 猫薄荷）\n"
            f"提现：喵股市 提现 <鱼干数>（{CAT_STOCK_CATNIP_TO_FISH} 猫薄荷 = 1 鱼干）\n"
            f"手续费：买入 {CAT_STOCK_BUY_FEE:.0%}、卖出 {CAT_STOCK_SELL_FEE:.0%}（每笔最低 1 猫薄荷）\n"
            f"交易规则：买入后满 {CAT_STOCK_LOCK_HOURS} 个开市小时才能卖出（休市时间不计）；"
            "单笔最少 10 股、最多 100 万股\n"
            "涨跌：不设涨跌停，单小时大致 -20% ~ +25%；事件会延续发酵，"
            "同国与同行业的企业也会联动涨跌\n"
            f"退市：连续 {CAT_STOCK_DELIST_BAD_TICKS} 个整点股价低于基准价 "
            f"{CAT_STOCK_DELIST_BAD_RATIO:.0%} 的企业会被摘牌，"
            "持仓按最新价 70% 强制清算，退市企业也可能改日重新上市\n"
            "买入：喵股市 买 <股票代码> <股数>\n"
            "卖出：喵股市 卖 <股票代码> <股数>\n"
            "查看：喵股市 大盘 / 喵股市 新闻 / 喵股市 持仓\n"
            "排行：喵股市 排行（收益榜 + 亏得最惨榜）\n"
            f"方针：持股 ≥{CAT_STOCK_POLICY_MIN_SHARES} 股且为该公司最大股东时，"
            "可用「喵股市 方针 <股票代码> <方针内容>」给公司定方向，AI 写新闻时会参考\n"
            f"（提示：大额持仓可能被空头盯上，别把猫薄荷都押在一只股上）"
        )

    # ==================== 整点行情调度 ====================

    def _start_scheduler(self) -> None:
        threading.Thread(target=self._scheduler_loop, daemon=True).start()

    def _scheduler_loop(self) -> None:
        while True:
            try:
                self._catch_up(datetime.now())
            except Exception as e:
                print(f"[cat_stock] tick error: {e}")
            time.sleep(30)

    def _catch_up(self, now: datetime) -> None:
        """补齐因停机/休市错过、且仍在开市时段内的整点，每个整点各补一次"""
        if not self._is_open(now):
            return
        current = now.replace(minute=0, second=0, microsecond=0)
        last = self._load_market().get("last_tick") or ""
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%d %H")
        except ValueError:
            last_dt = current - timedelta(hours=1)
        slots = []
        cursor = last_dt + timedelta(hours=1)
        while cursor <= current:
            if CAT_STOCK_OPEN_HOUR <= cursor.hour < CAT_STOCK_CLOSE_HOUR:
                slots.append(cursor)
            cursor += timedelta(hours=1)
        for slot in slots[-CAT_STOCK_CATCHUP_MAX:]:
            self._tick(slot)
            time.sleep(0.5)

    def _tick(self, now: datetime) -> None:
        key = now.strftime("%Y-%m-%d %H")
        snapshot = self._load_market()
        if snapshot.get("last_tick") == key:
            return

        # 人工世界走向：接下来两个整点内持续生效
        world = [d.get("text", "") for d in snapshot.get("world_directives", [])
                 if int(d.get("remaining", 0)) > 0]
        # AI 生成新闻较慢，先不占用锁，避免玩家交易被阻塞
        ai_news, effects, world_update, ai_actions = self._make_news(snapshot, now, world)

        with self._lock:
            market = self._load_market()
            if market.get("last_tick") == key:
                return
            companies = market["companies"]
            players = self._load_stock_players()
            today = now.strftime("%Y-%m-%d")
            if market.get("day") != today:
                # 新的一天：记下昨收作为当日涨跌幅基准
                for comp in companies.values():
                    comp["prev_close"] = comp["price"]
                market["day"] = today
            price_before = {code: comp["price"] for code, comp in companies.items()}

            # 1) 基础波动：全市场共同情绪 + 国家共同情绪 + 个股随机扰动
            market_move = random.gauss(0, CAT_STOCK_MARKET_NOISE)
            country_moves = {}
            for comp in companies.values():
                country_moves.setdefault(comp["country"], random.gauss(0, CAT_STOCK_COUNTRY_NOISE))
            for comp in companies.values():
                # 上一小时的走势会按比例延续，新闻造成的趋势不会一小时就消失
                momentum = float(comp.get("momentum", 0.0))
                move = (market_move
                        + country_moves.get(comp["country"], 0.0)
                        + momentum * CAT_STOCK_MOMENTUM_CARRY
                        + random.gauss(0, CAT_STOCK_TICK_NOISE))
                comp["price"] = max(1.0, comp["price"] * (1 + move))

            # 2) 新闻事件影响（同国/同行业会跟着联动）
            for eff in effects:
                self._apply_effect(companies, eff)

            # 3) 大额持仓被针对（轻度）
            pressure_news = self._big_holding_pressure(companies, players)

            # 4) 退市 / 新上市
            event_news = []
            delisted = self._maybe_delist(market, players)
            if delisted:
                event_news.append(delisted)
            listed = self._maybe_list(market)
            if listed:
                event_news.append(listed)
            # 4.1) AI 依据世界走向提出的产业上市 / 下市
            event_news.extend(self._apply_ai_actions(market, players, ai_actions))

            # 5) 价格上下限，并记录本小时走势供下一小时延续
            for comp in companies.values():
                comp["price"] = round(min(max(comp["price"], 1.0), comp["base"] * 50), 2)
                start = price_before.get(comp["code"]) or comp["price"] or 1
                comp["momentum"] = round(max(-0.6, min(0.6, (comp["price"] - start) / start)), 3)
                comp.pop("carry", None)

            stamp = now.strftime("%m-%d %H:%M")
            stamp_ts = now.timestamp()
            news_entries = []
            for item in ai_news:
                news_entries.append({"time": stamp, "ts": stamp_ts,
                                     "title": item.get("title", ""),
                                     "detail": item.get("detail", "")})
            for item in pressure_news + event_news:
                news_entries.append({"time": stamp, "ts": stamp_ts,
                                     "title": item.get("title", ""),
                                     "detail": item.get("detail", "")})
            if not news_entries:
                news_entries.append({"time": stamp, "ts": stamp_ts, "title": "世界暂时平静，大盘随资金情绪小幅波动",
                                     "detail": ""})

            market["news"] = self._recent_news(
                news_entries + market["news"])[:CAT_STOCK_NEWS_MAX]
            market["last_tick"] = key
            # 世界走向在本次整点已生效，剩余窗口数减一
            directives = market.get("world_directives") or []
            for item in directives:
                if int(item.get("remaining", 0)) > 0:
                    item["remaining"] = int(item.get("remaining", 0)) - 1
            market["world_directives"] = [
                d for d in directives if int(d.get("remaining", 0)) > 0]
            if world_update:
                market["world"] = world_update
            self._save_market(market)
            self._save_stock_players(players)

            moved = []
            for code, comp in companies.items():
                before = price_before.get(code, comp["price"]) or 1
                moved.append((comp, (comp["price"] - before) / before * 100))

        self._broadcast(now, market, moved, news_entries)

    def _apply_effect(self, companies: dict, eff: dict) -> None:
        pct = eff.get("pct", 0)
        if not isinstance(pct, (int, float)):
            return
        pct = float(pct)
        if abs(pct) > 1:
            pct = pct / 100.0
        pct = max(-CAT_STOCK_EFFECT_MAX, min(CAT_STOCK_EFFECT_MAX, pct))
        code = str(eff.get("code") or "").strip().upper()
        if code and code not in companies:
            # AI 偶尔会直接写企业名
            for comp in companies.values():
                if comp["name"] == eff.get("code"):
                    code = comp["code"]
                    break
        country = str(eff.get("country") or "").strip()
        if country and not any(c["country"] == country for c in companies.values()):
            # country 可能是国家名，换成国家代码
            for comp in companies.values():
                if self._country_name(comp["country"]) == country:
                    country = comp["country"]
                    break
        if code and code in companies:
            affected = {code: 1.0}
            comp = companies[code]
            for peer in companies.values():
                if peer["code"] == code:
                    continue
                if peer["country"] == comp["country"]:
                    affected[peer["code"]] = max(
                        affected.get(peer["code"], 0.0), CAT_STOCK_LINK_COUNTRY)
                elif peer["sector"] == comp["sector"]:
                    affected[peer["code"]] = max(
                        affected.get(peer["code"], 0.0), CAT_STOCK_LINK_SECTOR)
            for peer_code, ratio in affected.items():
                peer = companies[peer_code]
                peer["price"] = max(1.0, peer["price"] * (1 + pct * ratio))
        elif country:
            sectors = set()
            for comp in companies.values():
                if comp["country"] == country:
                    comp["price"] = max(1.0, comp["price"] * (1 + pct))
                    sectors.add(comp["sector"])
            # 同一行业在别国的企业也会受到小幅波及
            for comp in companies.values():
                if comp["country"] != country and comp["sector"] in sectors:
                    comp["price"] = max(1.0, comp["price"] * (1 + pct * CAT_STOCK_LINK_SECTOR))

    def _big_holding_pressure(self, companies: dict, players: dict) -> List[dict]:
        """大额持仓可能被空头狙击：概率低、幅度有限，只影响一只股票"""
        candidates: List[Tuple[str, float]] = []
        for st in players.values():
            for code, lots in st.get("holdings", {}).items():
                comp = companies.get(code)
                if not comp:
                    continue
                value = self._shares_of(lots) * comp["price"]
                if value >= CAT_STOCK_BIG_HOLDING_VALUE:
                    candidates.append((code, value))
        if not candidates:
            return []
        if random.random() >= CAT_STOCK_BIG_HOLDING_CHANCE:
            return []
        code = random.choice(candidates)[0]
        comp = companies.get(code)
        pct = -random.uniform(0.015, 0.03)
        comp["price"] = max(1.0, comp["price"] * (1 + pct))
        return [{
            "title": f"空头狙击！{comp['name']}（{code}）传出大额持仓被集中做空",
            "detail": f"盘中一度下挫约 {abs(pct) * 100:.0f}%，监管机构表示正在调查",
        }]

    def _maybe_delist(self, market: dict, players: dict) -> Optional[dict]:
        companies = market["companies"]
        # 每个整点记录经营状态：股价长期低于基准价一定比例才累积低迷计数
        for comp in companies.values():
            base = float(comp.get("base", 0) or 0)
            if base > 0 and comp["price"] <= base * CAT_STOCK_DELIST_BAD_RATIO:
                comp["bad_ticks"] = int(comp.get("bad_ticks", 0)) + 1
            else:
                comp["bad_ticks"] = 0

        if len(companies) <= CAT_STOCK_COMPANY_MIN or random.random() >= CAT_STOCK_DELIST_CHANCE:
            return None
        eligible = [c for c in companies.values()
                    if int(c.get("bad_ticks", 0)) >= CAT_STOCK_DELIST_BAD_TICKS]
        if not eligible:
            return None
        comp = random.choice(eligible)
        code = comp["code"]
        final_price = comp["price"]
        payout = int(round(final_price * CAT_STOCK_DELIST_RATE))
        paid = False
        for st in players.values():
            lots = st.get("holdings", {}).pop(code, None)
            if not lots:
                continue
            shares = self._shares_of(lots)
            if shares > 0:
                st["catnip"] = int(st.get("catnip", 0)) + shares * payout
                paid = True
        companies.pop(code, None)
        market["catalog"].append({
            "code": comp["code"], "name": comp["name"], "country": comp["country"],
            "sector": comp["sector"], "base": comp["base"],
        })
        detail = (f"连续 {comp.get('bad_ticks', CAT_STOCK_DELIST_BAD_TICKS)} 个整点股价"
                  f"低于基准价 {CAT_STOCK_DELIST_BAD_RATIO:.0%}，经营持续恶化，"
                  f"持仓按最新价 {CAT_STOCK_DELIST_RATE:.0%} 强制清算")
        if paid:
            detail += "（本小时有玩家持仓被清算）"
        return {"title": f"退市公告：{comp['name']}（{code}）长期低迷，正式摘牌",
                "detail": detail}

    def _maybe_list(self, market: dict) -> Optional[dict]:
        companies = market["companies"]
        catalog = market.get("catalog", [])
        if not catalog or len(companies) >= CAT_STOCK_COMPANY_MAX:
            return None

        # 保证每个国家至少有 CAT_STOCK_COUNTRY_MIN_LISTED 家：
        # 有国家低于下限时不看概率，本小时直接补一家
        counts: Dict[str, int] = {}
        for comp in companies.values():
            counts[comp["country"]] = counts.get(comp["country"], 0) + 1
        catalog_countries = {item["country"] for item in catalog}
        shortage = [ctry for ctry in catalog_countries
                    if counts.get(ctry, 0) < CAT_STOCK_COUNTRY_MIN_LISTED]
        if shortage:
            candidates = [item for item in catalog if item["country"] in shortage]
        else:
            if random.random() >= CAT_STOCK_LIST_CHANCE:
                return None
            candidates = catalog
        item = random.choice(candidates)
        catalog.remove(item)
        price = float(max(10, int(item["base"] * random.uniform(0.7, 1.3))))
        companies[item["code"]] = {
            "code": item["code"],
            "name": item["name"],
            "country": item["country"],
            "sector": item.get("sector", "综合"),
            "base": item["base"],
            "price": price,
            "prev_close": price,
            "bad_ticks": 0,
        }
        reason = "该国暂时缺上市公司，紧急挂牌" if shortage else "扩展业务版图"
        return {"title": f"新上市：{item['name']}（{item['code']}）挂牌交易",
                "detail": f"来自 {self._country_name(item['country'])}，{reason}；"
                          f"首日参考价 {self._fmt_price(price)}，行业 {item.get('sector', '综合')}"}

    def _apply_ai_actions(self, market: dict, players: dict,
                          actions: Optional[dict]) -> List[dict]:
        """落实 AI 依据世界走向提出的新产业上市 / 产业下市"""
        if not actions:
            return []
        companies = market["companies"]
        catalog = market.setdefault("catalog", [])
        catalog_codes = {str(c.get("code", "")).upper() for c in catalog}
        catalog_names = {str(c.get("name", "")) for c in catalog}
        existing_names = {c["name"] for c in companies.values()}
        news = []

        for item in actions.get("listings") or []:
            if len(companies) >= CAT_STOCK_COMPANY_MAX:
                break
            code = str(item.get("code") or "").strip().upper()
            name = str(item.get("name") or "").strip()[:10]
            country = str(item.get("country") or "").strip()
            sector = str(item.get("sector") or "").strip()[:4]
            base = item.get("base")
            if (not re.fullmatch(r"[A-Z]{3}", code) or code in companies
                    or code in catalog_codes or not name
                    or name in existing_names or name in catalog_names
                    or country not in _COUNTRY_GEO or not sector
                    or not isinstance(base, (int, float)) or not 20 <= base <= 300):
                continue
            base = int(base)
            price = float(max(10, int(base * random.uniform(0.85, 1.15))))
            companies[code] = {
                "code": code, "name": name, "country": country, "sector": sector,
                "base": base, "price": price, "prev_close": price, "bad_ticks": 0,
            }
            existing_names.add(name)
            news.append({
                "title": f"新产业上市：{name}（{code}）挂牌交易",
                "detail": (f"世界局势催生新的{sector}企业，落户"
                           f"{self._country_name(country)}；首日参考价 {self._fmt_price(price)}"),
            })

        for item in actions.get("delistings") or []:
            if len(companies) <= CAT_STOCK_COMPANY_MIN:
                break
            code = str(item.get("code") or "").strip().upper()
            comp = companies.get(code)
            if not comp:
                continue
            news.append(self._force_delist(market, players, comp,
                                           str(item.get("reason") or "").strip()[:40]))
        return news

    def _force_delist(self, market: dict, players: dict, comp: dict, reason: str) -> dict:
        """按世界走向强制摘牌，持仓按退市比例清算"""
        code = comp["code"]
        payout = int(round(float(comp["price"]) * CAT_STOCK_DELIST_RATE))
        paid = False
        for st in players.values():
            lots = st.get("holdings", {}).pop(code, None)
            if not lots:
                continue
            shares = self._shares_of(lots)
            if shares > 0:
                st["catnip"] = int(st.get("catnip", 0)) + shares * payout
                paid = True
        market["companies"].pop(code, None)
        market.setdefault("catalog", []).append({
            "code": comp["code"], "name": comp["name"], "country": comp["country"],
            "sector": comp["sector"], "base": comp["base"],
        })
        detail = reason or "世界局势变动，该产业整体退出市场"
        detail += f"，持仓按最新价 {CAT_STOCK_DELIST_RATE:.0%} 强制清算"
        if paid:
            detail += "（本小时有玩家持仓被清算）"
        return {"title": f"产业下市：{comp['name']}（{code}）正式摘牌",
                "detail": detail}

    # ==================== AI 新闻生成 ====================

    def _notable_cats(self) -> List[dict]:
        """传说 / 史诗 / 稀有喵喵：用于新闻故事里当主角或目击者"""
        pool = getattr(self._cat, "_pool", None) or []
        return [c for c in pool if c.get("rarity") in ("legend", "epic", "rare")]

    def _cat_news_seed(self) -> str:
        """随机挑几张传说/史诗/稀有喵喵，写进 AI 新闻提示词"""
        pool = self._notable_cats()
        if not pool:
            return ""
        labels = {"legend": "传说", "epic": "史诗", "rare": "稀有"}
        parts = []
        for rarity in ("legend", "epic", "rare"):
            group = [c for c in pool if c.get("rarity") == rarity]
            for cat in random.sample(group, k=min(2, len(group))):
                country = self._country_name(cat.get("country", "")) or cat.get("country", "")
                jobs = cat.get("job_path") or []
                job = str(jobs[-1]) if jobs else ""
                meta = "｜".join(x for x in (country, f"职业:{job}" if job else "") if x)
                trait = cat.get("intro") or cat.get("trait_desc") or ""
                if len(trait) > 60:
                    trait = trait[:60] + "…"
                line = f"- {labels[rarity]}喵「{cat.get('name', '无名喵')}」（{meta}）"
                if trait:
                    line += f"：{trait}"
                parts.append(line)
        if not parts:
            return ""
        return ("这个世界各领域的知名喵喵（可选择性提及，不必强制出场）：\n"
                + "\n".join(parts) + "\n")

    def _make_news(self, market: dict, now: datetime,
                   world: Optional[List[str]] = None
                   ) -> Tuple[List[dict], List[dict], Optional[dict], Optional[dict]]:
        try:
            news, effects, world_update, actions = self._ai_news(market, now, world)
            if actions and not world:
                # 没有世界走向时，普通事件偶尔也能推动换血，但概率压低避免频繁
                if random.random() >= CAT_STOCK_AI_ACTION_CHANCE:
                    actions = None
                else:
                    actions = {"listings": (actions.get("listings") or [])[:1],
                               "delistings": (actions.get("delistings") or [])[:1]}
            if news or actions:
                return news, effects, world_update, actions
        except Exception as e:
            print(f"[cat_stock] AI news failed, use fallback: {e}")
        return self._fallback_news(market, world)

    def _ai_news(self, market: dict, now: datetime,
                 world: Optional[List[str]] = None
                 ) -> Tuple[List[dict], List[dict], Optional[dict], Optional[dict]]:
        if not self._ai:
            return [], [], None, None
        companies = market["companies"]
        lines = []
        has_policy = False
        for comp in companies.values():
            line = (f"{comp['code']}｜{comp['name']}｜{comp['country']}({self._country_name(comp['country'])})"
                    f"｜{comp['sector']}｜现价{self._fmt_price(comp['price'])}"
                    f"｜近1小时{self._fmt_pct(float(comp.get('momentum', 0.0)) * 100)}")
            policy = comp.get("policy")
            if policy:
                has_policy = True
                line += f"｜方针:{policy}"
            lines.append(line)
        cat_seed = self._cat_news_seed()
        recent_news = (market.get("news") or [])[:5]
        recent_block = ""
        if recent_news:
            recent_block = ("\n最近几小时的新闻（供你延续事件线索，新新闻可以和它们呼应或升级）：\n"
                            + "\n".join(f"- {n.get('title', '')}" for n in recent_news if n.get("title"))
                            + "\n")
        world_block = ""
        if world:
            world_block = ("\n本小时的世界主线（由世界观察者下达，优先级最高，"
                           "必须体现在新闻和股价影响里）：\n"
                           + "\n".join(f"- {w}" for w in world)
                           + "\n请让至少一条新闻直接承接这些世界走向，并给出相应的涨跌影响。\n")
        state = market.get("world") or {}
        state_block = ""
        arc = str(state.get("arc") or "").strip()
        relations = state.get("relations") or []
        if arc or relations:
            state_block = "\n当前世界格局（必须延续，不要与已有关系自相矛盾）：\n"
            if arc:
                state_block += f"- 长期主线：{arc}\n"
            for rel in relations[:10]:
                state_block += (f"- {self._country_name(rel.get('a', ''))}"
                                f" ↔ {self._country_name(rel.get('b', ''))}："
                                f"{rel.get('state', '')}\n")
            state_block += ("各国存在合纵连横：盟友可能因共同敌人靠拢，敌对国可能互相制裁、"
                            "断商路、边境摩擦；新闻要顺着这些关系发展，而不是每个小时另起炉灶。\n")
        prompt = (
            "你是一个奇幻世界的财经新闻主编，世界背景是《猫猫远征队》的 if 线："
            "各国之间存在战争、魔物袭击、魔法灾变、王室更替、龙潮、亡灵复苏等事件。\n"
            f"现在是 {now.strftime('%H:%M')}，股市开市。\n"
            "以下是当前上市企业（代码｜名称｜国家｜行业｜现价｜近1小时涨跌）：\n"
            + "\n".join(lines) + recent_block + world_block + state_block
            + self._geography_prompt() +
            "\n\n请生成 1~3 条本小时的世界新闻。"
            "每条新闻必须与股市直接相关，并且至少给出 1 条能由这条新闻解释的股价影响"
            "（例如战争利好军工、灾变利空产地企业、商路被切断利空物流）。"
            "新闻要参考企业最近的走势和前面的新闻，保持事件连续性："
            "战事可以升级、灾后可以重建、订单可以交付、政策可以落地，不要每小时都凭空冒出新事件。"
            "涨跌可以有戏剧性，单小时大致 -20% ~ +25%，但必须有因果依据，也不要所有股票同涨同跌。"
            + ("\n有企业带着「方针」，那是最大股东制定的经营方向；"
               "新闻与股价影响请尽量呼应方针（例如方针偏军工，就更容易接到军备订单），"
               "但方针只是倾向，不是涨跌保证。\n" if has_policy else "")
            + (cat_seed + "\n" if cat_seed else "") +
            "上面这些喵喵只是这个世界各领域的知名人物，和股票涨跌没有必然关系；"
            "新闻里可以在合适的时候顺手提到他们（比如某位大师接了大单、某位名人现身商会），"
            "但不必强行出场，也不必每条新闻都提到。\n"
            "只输出一个 JSON 对象，不要解释，格式：\n"
            '{"news":[{"title":"新闻标题","detail":"一句话详情",'
            '"effects":[{"code":"股票代码","pct":0.15},{"country":"国家代码","pct":-0.1}]}],'
            '"world":{"arc":"当前世界局势主线（一句话）",'
            '"relations":[{"a":"国家代码","b":"国家代码","state":"同盟/敌对/贸易往来/边境摩擦"}]}}\n'
            "pct 是小数涨跌幅，范围 -0.2 ~ 0.25，正数为涨；code 和 country 二选一；"
            "每条新闻给 1~3 条 effects。"
            "world 是可选的：如果本小时局势有推进，就给出更新后的完整长期主线"
            "（不超过一句话）和仍然成立的完整国家关系列表（最多 10 条，没有变化可省略）。"
            "\n如果世界走向明确要求某个产业兴起、或局势催生全新行业，可以额外返回 listings"
            "（最多 2 家，没有就省略）："
            '{"code":"三位大写字母代码","name":"企业名","country":"国家代码",'
            '"sector":"行业名（不超过4字）","base":基准价整数20~300}；'
            "如果世界走向明确要求某行业整体衰败退出，可以额外返回 delistings"
            "（最多 2 家，没有就省略）："
            '{"code":"现有股票代码","reason":"一句话原因"}。'
            "世界走向涉及产业兴衰时必须给出；即使没有世界走向，普通事件（灾变、重建、"
            "贸易繁荣、行业衰败等）也可以促成上市或摘牌，但不要频繁，大多数整点不要返回；"
            "这类上市与摘牌会由交易所自动播报，不需要写进 news。\n"
        )
        text = self._ai._call_ai(
            Config.AI_MODEL["chat"],
            [{"role": "system", "content": "你是奇幻世界《猫猫远征队》if 线的财经新闻主编。"},
             {"role": "user", "content": prompt}],
            temperature=0.9,
            max_retries=1,
            max_tokens=900,
        )
        data = _extract_json(text)
        if not data:
            return [], [], None, None

        codes = {c["code"] for c in companies.values()}
        names = {c["name"] for c in companies.values()}
        country_codes = {c["country"] for c in companies.values()}

        def _valid(eff) -> bool:
            if not isinstance(eff, dict):
                return False
            if not isinstance(eff.get("pct"), (int, float)):
                return False
            code = str(eff.get("code") or "").strip().upper()
            if code:
                return code in codes or str(eff.get("code")).strip() in names
            country = str(eff.get("country") or "").strip()
            if not country:
                return False
            if country in country_codes:
                return True
            return any(self._country_name(c) == country for c in country_codes)

        news = []
        effects = []
        for item in data.get("news") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            item_effects = [e for e in item.get("effects") or [] if _valid(e)]
            # 没有可解释的股价影响就不算股市新闻，直接丢弃
            if not item_effects:
                continue
            news.append({"title": title[:60], "detail": str(item.get("detail") or "").strip()[:120]})
            effects.extend(item_effects)
            if len(news) >= 3:
                break

        # 兼容模型把 effects 放在顶层的写法
        if not news:
            top_effects = [e for e in data.get("effects") or [] if _valid(e)]
            if top_effects:
                news.append({"title": "市场突传未署名消息，交易所正在核实",
                             "detail": "多家机构已暂停报价"})
                effects = top_effects
        return (news, effects,
                self._parse_world(data, company_countries=country_codes),
                self._parse_actions(data))

    def _parse_actions(self, data: dict) -> Optional[dict]:
        """收集 AI 提出的新产业上市 / 产业下市，具体校验在落地时进行"""
        listings = [x for x in (data.get("listings") or []) if isinstance(x, dict)][:2]
        delistings = [x for x in (data.get("delistings") or []) if isinstance(x, dict)][:2]
        if not listings and not delistings:
            return None
        return {"listings": listings, "delistings": delistings}

    def _parse_world(self, data: dict, company_countries: set) -> Optional[dict]:
        """校验 AI 返回的世界格局，避免脏数据写入行情文件"""
        raw = data.get("world")
        if not isinstance(raw, dict):
            return None
        arc = str(raw.get("arc") or "").strip()[:120]
        relations = []
        for item in raw.get("relations") or []:
            if not isinstance(item, dict):
                continue
            a = str(item.get("a") or "").strip()
            b = str(item.get("b") or "").strip()
            state = str(item.get("state") or "").strip()[:16]
            if (a in company_countries and b in company_countries
                    and a != b and state and self._are_adjacent(a, b)):
                relations.append({"a": a, "b": b, "state": state})
            if len(relations) >= 10:
                break
        if not arc and not relations:
            return None
        return {"arc": arc, "relations": relations,
                "updated": datetime.now().strftime("%m-%d %H:%M")}

    def _fallback_news(self, market: dict,
                       world: Optional[List[str]] = None
                       ) -> Tuple[List[dict], List[dict], None, None]:
        companies = market["companies"]
        picks = random.sample(_FALLBACK_EVENTS, k=random.randint(1, 2))
        news = []
        effects = []
        # AI 不可用时，人工世界走向仍要体现在新闻和盘面上
        if world:
            text = world[-1][:50]
            news.append({"title": f"世界走向：{text}",
                         "detail": "世界观察者的动向正在影响各国市场情绪"})
            if companies:
                comp = random.choice(list(companies.values()))
                effects.append({"country": comp["country"],
                                "pct": round(random.uniform(-0.18, 0.18), 3)})
        for title, targets in picks:
            news.append({"title": title, "detail": "本消息由喵股市编辑部整理"})
            for code, pct in targets:
                if code in companies:
                    effects.append({"code": code, "pct": pct})
        # 再加一点随机小事件，避免每次都是模板股
        if companies and random.random() < 0.6:
            code = random.choice(list(companies.keys()))
            pct = random.choice([-0.22, -0.15, -0.1, 0.1, 0.15, 0.23])
            effects.append({"code": code, "pct": pct})
            sign = "暴涨" if pct > 0 else "跳水"
            detail = "交易所称原因不明，坊间传闻与神秘买盘有关"
            cats = self._notable_cats()
            if cats and random.random() < 0.5:
                cat = random.choice(cats)
                detail += f"，有人目击{cat.get('name', '某位喵喵')}出入交易大厅"
            news.append({
                "title": f"{companies[code]['name']}（{code}）盘中突然{sign}",
                "detail": detail,
            })
        return news, effects, None, None

    # ==================== 整点播报 ====================

    def _broadcast(self, now: datetime, market: dict, moved: List[Tuple[dict, float]],
                   news: List[dict]) -> None:
        group_id = getattr(Config, "STOCK_NEWS_GROUP", 1011679851)
        target = Target(user_id=0, group_id=group_id, is_group=True)

        comps = market["companies"]
        up = sum(1 for c in comps.values() if c["price"] >= c.get("prev_close", c["price"]))
        down = len(comps) - up

        lines = [f"【喵股市 · {now.strftime('%H:%M')} 整点快报】"]
        for item in news[:4]:
            lines.append(f"📰 {item.get('title', '')}")
            if item.get("detail"):
                lines.append(f"  {item['detail']}")
        lines.append("")
        lines.append(f"盘面：在市 {len(comps)} 家｜上涨 {up}｜下跌 {down}")
        world = market.get("world") or {}
        arc = str(world.get("arc") or "").strip()
        if arc:
            lines.append(f"🌍 世界局势：{arc}")

        movers = sorted(moved, key=lambda x: x[1], reverse=True)
        hottest = [m for m in movers if m[1] > 3][:3]
        worst = [m for m in movers[::-1] if m[1] < -3][:3]
        if hottest:
            lines.append("领涨：" + "，".join(
                f"{c['code']} {c['name']} {self._fmt_pct(p)} → {self._fmt_price(c['price'])}"
                for c, p in hottest))
        if worst:
            lines.append("领跌：" + "，".join(
                f"{c['code']} {c['name']} {self._fmt_pct(p)} → {self._fmt_price(c['price'])}"
                for c, p in worst))
        lines.append("发送「喵股市 大盘」查看全部行情")
        self._sender.send_text(target, "\n".join(lines))
