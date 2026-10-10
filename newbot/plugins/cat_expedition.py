import os
import json
import random
import re
from datetime import date
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from config import Config
from plugins.cat_config import CatConfig
from core.message_sender import MessageSender, Target
from core.command_router import CommandRouter, CommandContext

# 稀有度：排序、编号字母、文字颜色（图鉴用）
CAT_RARITY_ORDER = ["normal", "rare", "epic", "legend"]
CAT_RARITY_LETTER = {"normal": "N", "rare": "R", "epic": "E", "legend": "L"}
CAT_RARITY_RGB = {
    "normal": (90, 90, 90),
    "rare": (40, 110, 200),
    "epic": (150, 70, 200),
    "legend": (210, 140, 20),
}
CAT_TEXT_RGB = (60, 45, 35)
CAT_STAR_RGB = (225, 170, 30)

# 详情卡片表格线坐标（底图 1536x1536，已检测）
_X_LABEL_END, _X_PHOTO_L, _X_PHOTO_R, _X_RIGHT = 438, 769, 1099, 1428
_Y_TOP, _Y_R1, _Y_R2, _Y_JOB = 235, 401, 483, 566
_Y_STRIP, _Y_TRAIT, _Y_INTRO, _Y_BOTTOM = 816, 899, 1064, 1402
_PAD = 12
CAT_CELLS = {
    "name":   (_X_LABEL_END + _PAD, _Y_TOP + _PAD,  _X_PHOTO_L - _PAD, _Y_R1 - _PAD),
    "star":   (_X_LABEL_END + _PAD, _Y_R1 + _PAD,   _X_PHOTO_L - _PAD, _Y_R2 - _PAD),
    "rarity": (_X_LABEL_END + _PAD, _Y_R2 + _PAD,   _X_PHOTO_L - _PAD, _Y_JOB - _PAD),
    "photo":  (_X_PHOTO_R + _PAD,  _Y_TOP + _PAD,   _X_RIGHT - _PAD,  _Y_JOB - _PAD),
    "job":    (_X_LABEL_END + _PAD, _Y_JOB + _PAD,  _X_PHOTO_L - _PAD, _Y_STRIP - _PAD),
    "job_name": (_X_LABEL_END + _PAD, _Y_STRIP + _PAD, _X_PHOTO_L - _PAD, _Y_TRAIT - _PAD),
    "origin": (_X_PHOTO_R + _PAD,  _Y_JOB + _PAD,  _X_RIGHT - _PAD,  _Y_STRIP - _PAD),
    "origin_name": (_X_PHOTO_R + _PAD, _Y_STRIP + _PAD, _X_RIGHT - _PAD, _Y_TRAIT - _PAD),
    "trait":  (_X_LABEL_END + _PAD, _Y_TRAIT + _PAD, _X_RIGHT - _PAD,  _Y_INTRO - _PAD),
    "intro":  (_X_LABEL_END + _PAD, _Y_INTRO + _PAD, _X_RIGHT - _PAD,  _Y_BOTTOM - _PAD),
}
CAT_FONT_SIZES = {"name": 72, "star": 60, "rarity": 56, "trait": 48, "intro": 40,
                  "job_name": 48, "origin_name": 44, "missing": 30}


def _ensure_dirs():
    """确保数据目录存在"""
    os.makedirs(CatConfig.CAT_EXPEDITION_DIR, exist_ok=True)


def _pad_cat_id(cat_id: Optional[str]) -> Optional[str]:
    """把形如 aue1 的卡池 id 序号补零为 aue01（cin01 等已是两位数则原样返回）"""
    m = re.fullmatch(r"([a-z]+)(\d+)", cat_id or "")
    if not m:
        return cat_id
    return f"{m.group(1)}{int(m.group(2)):02d}"


def _load_json(path: str) -> dict:
    """读 JSON 文件，文件不存在返回空 dict"""
    _ensure_dirs()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: dict) -> None:
    """写 JSON 文件"""
    _ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class CatExpeditionPlugin:
    """猫猫远征队：抽卡养成 + 远征战斗小游戏"""

    def __init__(self, sender: MessageSender):
        self._sender = sender
        self._countries = {}
        self._pools = {}          # 全部卡池 key -> pool dict
        self._pool = []           # 默认全量卡池（用于图鉴/兑换查询）
        self._pool, self._pools = self._load_pool()
        self._migrate_players()

    # ==================== 数据加载 ====================

    def _load_pool(self):
        """加载卡池与国家表。返回 (默认全量卡池, 全部卡池dict)"""
        data = _load_json(CatConfig.CAT_POOL_PATH)
        self._countries = data.get("countries", {})
        pools = data.get("pools", {})
        default = pools.get("default", {})
        return default.get("cats", []), pools

    def _migrate_players(self) -> None:
        """启动时迁移玩家存档：把历史 id 补零为两位数，并按 id 对齐卡池中的 name/rarity。
        卡池改 id/改名/调稀有度后，玩家收藏里的旧字段会在下次启动时自动更新。"""
        pool_by_id = {c["id"]: c for c in self._pool}
        players = self._load_players()
        changed = False
        for pl in players.values():
            for owned in pl.get("collection", []):
                new_id = _pad_cat_id(owned.get("id"))
                if new_id != owned.get("id"):
                    owned["id"] = new_id
                    changed = True
                ref = pool_by_id.get(owned.get("id"))
                if ref is None:
                    continue
                if owned.get("name") != ref["name"]:
                    owned["name"] = ref["name"]
                    changed = True
                if owned.get("rarity") != ref["rarity"]:
                    owned["rarity"] = ref["rarity"]
                    changed = True
            team = pl.get("deploy_team")
            if isinstance(team, list):
                for i, cid in enumerate(team):
                    new_id = _pad_cat_id(cid)
                    if new_id != cid:
                        team[i] = new_id
                        changed = True
        if changed:
            self._save_players(players)

    def _load_players(self) -> dict:
        """加载所有玩家存档"""
        return _load_json(CatConfig.CAT_PLAYERS_PATH)

    def _save_players(self, players: dict) -> None:
        """保存所有玩家存档"""
        _save_json(CatConfig.CAT_PLAYERS_PATH, players)

    def _get_player(self, qq: int) -> dict:
        """获取玩家数据，不存在则新建（首登送1000鱼干）"""
        players = self._load_players()
        if str(qq) not in players:
            players[str(qq)] = {
                "nick": "",
                "fish": CatConfig.CAT_WELCOME_FISH,
                "eye_stones": 0,
                "relics": 0,
                "last_signin": None,
                "signin_streak": 0,
                "signin_total": 0,
                "summon_count": 0,
                "deploy_limit": CatConfig.CAT_INITIAL_DEPLOY_LIMIT,
                "deploy_team": [],
                "research_limit": CatConfig.CAT_INITIAL_RESEARCH_LIMIT,
                "collection": []
            }
            self._save_players(players)
        return players[str(qq)]

    def _update_player(self, qq: int, player: dict) -> None:
        """更新玩家存档"""
        players = self._load_players()
        players[str(qq)] = player
        self._save_players(players)

    # ==================== 注册命令 ====================

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["喵签到", "catsign", ".catsign"],
            self.cmd_signin,
            description="猫猫远征队·每日签到"
        )
        router.register(
            ["抽喵喵", "catsummon", ".catsummon"],
            self.cmd_summon,
            description="猫猫远征队·抽卡（需指定卡池，输入「全」抽全部）"
        )
        router.register(
            ["兑换喵", "catredeem", ".catredeem"],
            self.cmd_redeem,
            description="猫猫远征队·猫眼石兑换指定猫"
        )
        router.register(
            ["远征队", "catinfo", ".catinfo"],
            self.cmd_team_info,
            description="猫猫远征队·查看远征队基础属性"
        )
        router.register(
            ["远征", "喵远征", "expedition", ".expedition"],
            self.cmd_expedition,
            description="猫猫远征队·每日远征Boss"
        )

        router.register(
            ["boss", "bossinfo", ".bossinfo"],
            self.cmd_boss,
            description="猫猫远征队·查看当前Boss信息"
        )
        router.register(
            ["科研", "喵科研", "research", ".research"],
            self.cmd_research,
            description="猫猫远征队·科研"
        )
        router.register(
            ["喵图鉴", "catpedia", ".catpedia"],
            self.cmd_catpedia,
            description="猫猫远征队·国家/喵喵图鉴与详情"
        )
        router.register(
            ["喵卡池", "catpool", ".catpool"],
            self.cmd_pool,
            description="猫猫远征队·查看卡池与介绍"
        )
        router.register(
            ["喵地图", "catmap", ".catmap"],
            self.cmd_map,
            description="猫猫远征队·世界地图"
        )
        router.register(
            ["喵邮件", "catmail", ".catmail"],
            self.cmd_mail,
            description="猫猫远征队·管理员全服邮件（仅管理员可用）",
            permission_check=lambda ctx: ctx.user_id == Config.CAT_ADMIN_QQ
        )

    # ==================== 签到 ====================

    def cmd_signin(self, ctx: CommandContext) -> None:
        player = self._get_player(ctx.user_id)
        today = date.today().isoformat()

        if player["last_signin"] == today:
            self._sender.reply(ctx, "今天已经签过啦~明天再来喵 (=^･ω･^=)")
            return

        player["last_signin"] = today
        player["signin_streak"] += 1
        player["signin_total"] = player.get("signin_total", 0) + 1

        # 随机鱼干 80-120，概率暴击
        base = random.randint(CatConfig.CAT_SIGNIN_MIN, CatConfig.CAT_SIGNIN_MAX)
        crit_chance = CatConfig.CAT_SIGNIN_CRIT_CHANCE
        super_chance = CatConfig.CAT_SIGNIN_SUPER_CHANCE
        # 非全服战力第一且鱼干不足时，暴击率按战力差提升，超级暴击率取暴击率的 10%
        if player["fish"] < CatConfig.CAT_SIGNIN_LOW_FISH:
            max_power = self._max_team_base_power()
            own_power = self._team_base_power(player)
            if own_power < max_power:
                crit_chance += (max_power - own_power) / max_power
                super_chance = crit_chance * 0.10
        crit_type = "normal"
        r = random.random()
        if r < super_chance:
            base *= 4
            crit_type = "super"
        elif r < super_chance + crit_chance:
            base *= 2
            crit_type = "crit"
        player["fish"] += base

        # 累计签到奖励：每10天一次，天数*10，上限2000
        bonus = 0
        interval = CatConfig.CAT_SIGNIN_BONUS_INTERVAL
        if player["signin_streak"] % interval == 0:
            raw_bonus = player["signin_streak"] * 10
            bonus = min(raw_bonus, CatConfig.CAT_SIGNIN_BONUS_CAP)
            player["fish"] += bonus

        self._update_player(ctx.user_id, player)

        # 拼消息
        crit_icon = ""
        if crit_type == "super":
            crit_icon = "🌟 超级暴击！"
        elif crit_type == "crit":
            crit_icon = "⚡ 暴击！"

        msg = f"签到成功！{crit_icon}+{base} 鱼干 🐟\n"
        if bonus > 0:
            msg += f"🎉 累计签到 {player['signin_streak']} 天！额外奖励 +{bonus} 鱼干\n"
        msg += f"当前余额：{player['fish']} 鱼干 | 连续签到：{player['signin_streak']}天"

        self._sender.reply(ctx, msg)

    # ==================== 抽喵 ====================

    @staticmethod
    def _summon_usage() -> str:
        return ("请指定卡池！\n"
                "用法：抽喵 [数量] <卡池名>   例：抽喵 3 方桌骑士\n"
                "输入「全」可从全部卡池抽取：例 抽喵 10 全\n"
                "发送「喵卡池」查看所有卡池与介绍")

    def cmd_summon(self, ctx: CommandContext) -> None:
        args = ctx.get_args().strip()
        tokens = args.split() if args else []
        if not tokens:
            self._sender.reply(ctx, self._summon_usage())
            return

        count = 1
        pool_name = tokens[0]
        if tokens[0].isdigit():
            count = int(tokens[0])
            if count < 1:
                self._sender.reply(ctx, "数量至少为 1 喵~")
                return
            if len(tokens) < 2:
                self._sender.reply(ctx, self._summon_usage())
                return
            pool_name = tokens[1]

        if pool_name in ("全", "全部", "all"):
            pool_key = None  # 全部卡池：从全量卡池抽取
        else:
            pool_key = self._resolve_pool(pool_name)
            if pool_key is None:
                self._sender.reply(ctx, f"没找到卡池「{pool_name}」。\n{self._summon_usage()}")
                return

        player = self._get_player(ctx.user_id)
        total_cost = count * CatConfig.CAT_SUMMON_COST

        if player["fish"] < total_cost:
            need = total_cost - player["fish"]
            self._sender.reply(
                ctx, f"鱼干不够啦！需要 {total_cost}，还差 {need} 鱼干 🐟"
            )
            return

        # 幸运：单抽有概率直接变成十连，仍只按 1 抽扣费
        lucky = (count == 1
                 and random.random() < CatConfig.CAT_SUMMON_LUCKY_CHANCE)
        draw_count = CatConfig.CAT_SUMMON_LUCKY_COUNT if lucky else count

        results = self._do_summon(player, draw_count, pool_key)
        player["fish"] -= total_cost
        # 每次抽卡获得猫眼石（幸运十连只按实际付费抽数计）
        player["eye_stones"] = player.get("eye_stones", 0) + count * CatConfig.CAT_EYE_STONE_PER_SUMMON
        player["summon_count"] = player.get("summon_count", 0) + count
        self._update_player(ctx.user_id, player)

        # 拼消息
        header = f"【抽喵结果】共 {len(results)} 只，消耗 {total_cost} 鱼干"
        if lucky:
            header = f"✨ 欧气爆发！一抽变十连！\n{header}"
        lines = [header]
        for r in results:
            rname = CatConfig.CAT_RARITY_NAMES[r["rarity"]]
            line = f"  [{rname}] {r['name']}"
            if r["job"]:
                line += f"（{r['job']}）"
            if r["is_dup"]:
                if r["refunded"]:
                    line += f"（已满星，返还 {r['refund_amt']} 鱼干）"
                else:
                    line += f"（已拥有，当前 ★{r['star']}）"
            if r["star_up"]:
                line += f" ★★ 升到 ★{r['star']}！"
            if r["job_up"]:
                line += f" ✨ 转职为 {r['job']}！"
            lines.append(line)

        lines.append(f"\n当前余额：{player['fish']} 鱼干 | 猫眼石：{player['eye_stones']}")
        self._sender.reply(ctx, "\n".join(lines))

    # ==================== 卡池查询 ====================

    def cmd_pool(self, ctx: CommandContext) -> None:
        """查看所有卡池或指定卡池详情"""
        args = ctx.get_args().strip()
        if not args:
            lines = ["【喵喵卡池】"]
            for key, pool in self._pools.items():
                if key == "default":
                    continue
                cats = pool.get("cats", [])
                legend = [c["name"] for c in cats if c["rarity"] == "legend"]
                desc = pool.get("desc", "")
                line = f"  · {pool.get('name', key)}（{len(cats)}张）"
                if legend:
                    line += f"  传说：{'、'.join(legend)}"
                lines.append(line)
                if desc:
                    lines.append(f"      {desc}")
            lines.append("")
            lines.append("用法：喵卡池 <卡池名>  查看该卡池全部喵喵")
            lines.append("抽卡必须指定卡池：抽喵 3 方桌骑士；抽喵 10 全 为全部卡池")
            self._sender.reply(ctx, "\n".join(lines))
            return

        pool_key = self._resolve_pool(args)
        if pool_key is None:
            self._sender.reply(ctx, f"没找到卡池「{args}」，可用「喵卡池」查看全部卡池")
            return

        pool = self._pools[pool_key]
        cats = pool.get("cats", [])
        lines = [f"【{pool.get('name', pool_key)}】"]
        desc = pool.get("desc")
        if desc:
            lines.append(desc)
        lines.append(f"共 {len(cats)} 张喵喵：")
        order = ["legend", "epic", "rare", "normal"]
        for r in order:
            rc = [c for c in cats if c["rarity"] == r]
            if not rc:
                continue
            rname = CatConfig.CAT_RARITY_NAMES.get(r, r)
            lines.append(f"—— {rname}（{len(rc)}）——")
            for c in rc:
                lines.append(f"  · {c['name']}")
        self._sender.reply(ctx, "\n".join(lines))

    def _do_summon(self, player: dict, count: int, pool_key: Optional[str] = None) -> List[dict]:
        """核心抽卡逻辑，返回每只的抽卡结果。
        pool_key=None 表示全部卡池（全量池抽取，即「全」）；
        指定 pool_key 时，稀有度 rare 及以上的卡只从该卡池中抽取，
        普通卡始终从全量卡池抽取，卡池缺少某稀有度时回退全量池。"""
        results = []
        default_by_rarity = self._group_by_rarity()

        pool_by_rarity = None
        if pool_key and pool_key in self._pools:
            pool_by_rarity = {}
            for cat in self._pools[pool_key].get("cats", []):
                pool_by_rarity.setdefault(cat["rarity"], []).append(cat)

        for _ in range(count):
            rarity = self._roll_rarity()
            if rarity == "normal":
                candidates = default_by_rarity.get("normal", [])
            elif pool_by_rarity and pool_by_rarity.get(rarity):
                candidates = pool_by_rarity[rarity]
            else:
                candidates = default_by_rarity.get(rarity, [])
            if not candidates:
                candidates = default_by_rarity.get("normal", [])
            cat = random.choice(candidates)
            results.append(self._grant_cat(player, cat))

        return results

    def _grant_cat(self, player: dict, cat_pool: dict) -> dict:
        """把一只喵喵给玩家，处理重复、升星、返还、自动转职"""
        job_path = cat_pool.get("job_path", [])

        def _job_for_star(star: int) -> str:
            """根据星级返回当前职业名"""
            if star >= 5 and len(job_path) >= 3:
                return job_path[2]
            if star >= 3 and len(job_path) >= 2:
                return job_path[1]
            if len(job_path) >= 1:
                return job_path[0]
            return ""

        # 查玩家 collection 里有没有这只
        owned = self._find_collection_cat(player, cat_pool["id"])

        if owned is None:
            # 新猫
            owned = {
                "id": cat_pool["id"],
                "name": cat_pool["name"],
                "rarity": cat_pool["rarity"],
                "star": 1,
                "job": _job_for_star(1)
            }
            player["collection"].append(owned)
            return {**owned, "is_dup": False, "refunded": False, "refund_amt": 0,
                    "star_up": False, "job_up": False}

        # 重复猫：星级+1（star即抽取次数）
        old_star = owned["star"]
        old_job = owned.get("job", "")

        # 已满星：返还鱼干
        if old_star >= CatConfig.CAT_MAX_STAR:
            refund = CatConfig.CAT_DUP_REFUND_BY_RARITY.get(owned["rarity"], 50)
            player["fish"] += refund
            return {**owned, "is_dup": True, "refunded": True, "refund_amt": refund,
                    "star_up": False, "job_up": False}

        # 未满星：升星
        owned["star"] += 1
        new_job = _job_for_star(owned["star"])
        job_up = new_job and new_job != old_job
        if job_up:
            owned["job"] = new_job

        return {**owned, "is_dup": True, "refunded": False, "refund_amt": 0,
                "star_up": True, "job_up": job_up}

    # ==================== 猫眼石兑换 ====================

    def cmd_redeem(self, ctx: CommandContext) -> None:
        args = ctx.get_args().strip()
        if not args:
            self._sender.reply(
                ctx, f"用法：兑换喵 <名字>\n需要 {CatConfig.CAT_EYE_STONE_COST} 个猫眼石兑换指定喵喵"
            )
            return

        player = self._get_player(ctx.user_id)
        stones = player.get("eye_stones", 0)

        if stones < CatConfig.CAT_EYE_STONE_COST:
            need = CatConfig.CAT_EYE_STONE_COST - stones
            self._sender.reply(
                ctx, f"猫眼石不够啦！需要 {CatConfig.CAT_EYE_STONE_COST}，还差 {need} 个"
            )
            return

        # 模糊匹配卡池里的猫
        target = self._find_pool_cat_by_name(args)
        if target is None:
            pool_names = "\n".join(f"  · {c['name']}" for c in self._pool)
            self._sender.reply(ctx, f"没找到叫「{args}」的喵喵。卡池里有：\n{pool_names}")
            return

        # 扣猫眼石，直接grant给玩家（不走概率，固定这只）
        player["eye_stones"] -= CatConfig.CAT_EYE_STONE_COST
        result = self._grant_cat(player, target)
        self._update_player(ctx.user_id, player)

        rname = CatConfig.CAT_RARITY_NAMES[target["rarity"]]
        msg = f"🎉 兑换成功！\n"
        msg += f"  [{rname}] {result['name']}（{result.get('job', '')}）"
        if result["star_up"]:
            msg += f" ★★ 升到 ★{result['star']}！"
        if result["job_up"]:
            msg += f" ✨ 转职为 {result['job']}！"
        if result["is_dup"]:
            msg += "\n（已拥有，累计数量+1）"
        msg += f"\n剩余猫眼石：{player['eye_stones']}"
        self._sender.reply(ctx, msg)

    def _find_pool_cat_by_name(self, name: str) -> Optional[dict]:
        """精确匹配卡池里的猫：名字（精确）或 id（大小写不敏感）"""
        for cat in self._pool:
            if cat["name"] == name or cat["id"].lower() == name.lower():
                return cat
        return None

    # ==================== 远征队基础属性 ====================

    def cmd_team_info(self, ctx: CommandContext) -> None:
        player = self._get_player(ctx.user_id)
        collection = player.get("collection", [])
        max_star_num = sum(
            1 for cat in collection if cat.get("star", 0) >= CatConfig.CAT_MAX_STAR
        )

        lines = [
            "【猫猫远征队 · 基础属性】",
            f"🐱 猫猫：{len(collection)} 只（满星 {max_star_num} 只）",
            f"👊 基础战力：{self._team_base_power(player)}",
            f"🐟 鱼干：{player.get('fish', 0)}",
            f"💎 猫眼石：{player.get('eye_stones', 0)}",
            f"🏺 遗物：{player.get('relics', 0)}",
            f"⚔️ 出阵猫猫上限：{player.get('deploy_limit', CatConfig.CAT_INITIAL_DEPLOY_LIMIT)}",
            f"🔬 研究猫猫上限：{player.get('research_limit', CatConfig.CAT_INITIAL_RESEARCH_LIMIT)}",
            f"📅 累计签到：{player.get('signin_total', 0)} 天"
            f"（连续 {player.get('signin_streak', 0)} 天）",
            f"🎴 累计抽喵：{player.get('summon_count', 0)} 次",
        ]
        self._sender.reply(ctx, "\n".join(lines))

    # ==================== 喵喵图鉴 ====================

    def cmd_catpedia(self, ctx: CommandContext) -> None:
        """无参：已解锁国家列表；国家码：该国喵喵图鉴图；喵喵id/名字：详情卡片图"""
        arg = ctx.get_args().strip()

        if not arg:
            self._reply_country_list(ctx)
            return

        key = arg.lower()
        if key in self._countries:
            try:
                path = self._render_country_book(key, ctx.user_id)
            except Exception as e:
                self._sender.reply(ctx, f"图鉴图生成失败：{e}")
                return
            self._sender.send_image(Target.from_data(ctx.raw_data), path)
            return

        cat = self._find_pool_cat_by_name(arg)
        if cat is not None:
            player = self._peek_player(ctx.user_id)
            owned = self._find_collection_cat(player or {}, cat["id"])
            if not owned:
                self._sender.reply(ctx, f"暂无「{cat['name']}」的档案，先去抽喵解锁吧～")
                return
            star = owned.get("star", 1)
            try:
                path = self._render_cat_card(cat, star)
            except Exception as e:
                self._sender.reply(ctx, f"详情图生成失败：{e}")
                return
            self._sender.send_image(Target.from_data(ctx.raw_data), path)
            return

        codes = "、".join(sorted(self._countries))
        self._sender.reply(
            ctx,
            f"没找到「{arg}」。\n可用国家编号：{codes}\n"
            "用法：喵喵图鉴 / 喵喵图鉴 国家编号 / 喵喵图鉴 喵喵id"
        )

    def cmd_map(self, ctx: CommandContext) -> None:
        """发送世界地图"""
        path = CatConfig.CAT_MAP_PATH
        if not os.path.exists(path):
            self._sender.reply(ctx, "地图还没画好喵～")
            return
        self._sender.send_image(Target.from_data(ctx.raw_data), path)

    def cmd_expedition(self, ctx: CommandContext) -> None:
        """每日远征Boss。一键远征，自动检索所有喵喵"""
        player = self._get_player(ctx.user_id)
        today = date.today().isoformat()

        if player.get("last_expedition") == today:
            self._sender.reply(ctx, "今天已经远征过了，明天再来喵～")
            return

        # 读取全局远征状态
        exp = self._load_expedition()
        act_cfg = self._get_act_config(exp["act"])
        stages = act_cfg.get("stages", [])
        if not stages:
            self._sender.reply(ctx, "远征关卡配置异常喵～")
            return

        stage_cfg = None
        for s in stages:
            if s["stage"] == exp["stage"]:
                stage_cfg = s
                break
        if stage_cfg is None:
            self._sender.reply(ctx, "远征关卡数据异常喵～")
            return

        # 天气每次远征都随机，不告诉玩家
        weather = random.choice(CatConfig.CAT_WEATHER_TYPES)
        terrain = stage_cfg.get("terrain", "平原")

        # 计算总伤害：基础战力(全部猫) × (1 + 匹配天气/地形的猫的特性加成比例)
        base_total = 0
        detail_lines = []
        total_bonus_ratio = 0.0

        for owned in player.get("collection", []):
            base = CatConfig.CAT_BASE_POWER_BY_RARITY.get(owned["rarity"], 0)
            star_mult = CatConfig.CAT_STAR_POWER_MULT.get(owned.get("star", 1), 1)
            base_power = base * star_mult
            base_total += base_power

            pool_cat = self._find_pool_cat_by_name(owned["id"])
            affinity = (pool_cat or {}).get("trait_affinity") or {}
            matched_weather = affinity.get("weather") == weather
            matched_terrain = affinity.get("terrain") == terrain

            matches = 0
            if matched_weather:
                matches += 1
            if matched_terrain:
                matches += 1

            if matches > 0:
                per_match = CatConfig.CAT_TRAIT_BONUS_BY_RARITY.get(owned["rarity"], 0.02)
                trait_mult = CatConfig.CAT_TRAIT_MULT_BY_STAR.get(owned.get("star", 1), 1)
                bonus_ratio = per_match * trait_mult * matches
                total_bonus_ratio += bonus_ratio
                name = owned.get("name", owned["id"])
                reason = ""
                if matched_weather and matched_terrain:
                    reason = f"（天气+地形匹配，+{bonus_ratio*100:.0f}%）"
                elif matched_weather:
                    reason = f"（天气匹配，+{bonus_ratio*100:.0f}%）"
                else:
                    reason = f"（地形匹配，+{bonus_ratio*100:.0f}%）"
                detail_lines.append(f"  {name}：{base_power}{reason}")

        total_power = int(base_total * (1 + total_bonus_ratio))

        if total_power <= 0:
            self._sender.reply(ctx, "你还没有喵喵喵～")
            return

        # 随机系数
        ratio = random.uniform(CatConfig.CAT_EXPEDITION_RANDOM_MIN,
                               CatConfig.CAT_EXPEDITION_RANDOM_MAX)
        damage = int(total_power * ratio)

        # 暴击：概率造成 1.5 倍伤害
        is_crit = random.random() < CatConfig.CAT_EXPEDITION_CRIT_CHANCE
        if is_crit:
            damage = int(damage * CatConfig.CAT_EXPEDITION_CRIT_MULT)

        # 扣减Boss血量
        exp["boss_hp"] = max(0, exp["boss_hp"] - damage)
        exp["damage_log"].append({
            "qq": str(ctx.user_id),
            "name": ctx.sender_nickname or f"玩家{ctx.user_id}",
            "damage": damage
        })

        # 更新玩家记录
        player["last_expedition"] = today
        player["expedition_total"] = player.get("expedition_total", 0) + 1
        player["expedition_damage"] = player.get("expedition_damage", 0) + damage

        self._update_player(ctx.user_id, player)
        self._save_expedition(exp)

        # 判断是否通关
        if exp["boss_hp"] <= 0:
            self._handle_stage_clear(ctx, exp, stage_cfg, act_cfg)
        else:
            hp_percent = exp["boss_hp"] / stage_cfg["boss_hp"] * 100
            if hp_percent > 10:
                # 血量>10%：显示详细伤害明细
                lines = [
                    f"【远征】{act_cfg.get('name', '???')} 第{exp['stage']}关",
                    f"天气：{weather} | 地形：{terrain}",
                    f"基础战力：{base_total}",
                    "特性加成明细：",
                ]
                if detail_lines:
                    lines.extend(detail_lines)
                else:
                    lines.append("  无匹配天气/地形的猫猫")
                lines.append(f"总战力：{base_total}×{1+total_bonus_ratio:.2f}={total_power}，随机倍率：{ratio:.2f}")
                crit_text = f"（⚡暴击 ×{CatConfig.CAT_EXPEDITION_CRIT_MULT}）" if is_crit else ""
                lines.append(f"本次伤害：{damage}{crit_text}")
                lines.append(f"Boss剩余血量：{exp['boss_hp']}/{stage_cfg['boss_hp']}（{hp_percent:.1f}%）")
                self._sender.reply(ctx, "\n".join(lines))
            else:
                # 血量≤10%：只显示"???"，不说伤害
                lines = [
                    f"【远征】{act_cfg.get('name', '???')} 第{exp['stage']}关",
                    f"天气：{weather} | 地形：{terrain}",
                    "Boss剩余血量：???",
                ]
                self._sender.reply(ctx, "\n".join(lines))

    def cmd_boss(self, ctx: CommandContext) -> None:
        """查看当前Boss信息"""
        exp = self._load_expedition()
        act_cfg = self._get_act_config(exp["act"])
        stages = act_cfg.get("stages", [])
        stage_cfg = None
        for s in stages:
            if s["stage"] == exp["stage"]:
                stage_cfg = s
                break
        if stage_cfg is None:
            self._sender.reply(ctx, "远征关卡数据异常喵～")
            return

        terrain = stage_cfg.get("terrain", "平原")
        boss_name = stage_cfg.get("boss_name", "???")
        boss_max = stage_cfg.get("boss_hp", 1)
        hp_percent = exp["boss_hp"] / boss_max * 100

        lines = [
            f"【{act_cfg.get('name', '???')}】第{exp['stage']}关",
            f"Boss：{boss_name}",
        ]

        # 第1关显示剧情
        if exp["stage"] == 1:
            story = act_cfg.get("story_text", "")
            if story:
                lines.insert(0, "")
                lines.insert(0, story)
                lines.insert(0, "———")
            story_img = act_cfg.get("story_image", "")
            if story_img:
                img_path = os.path.join(CatConfig.CAT_EXPEDITION_IMG_DIR, story_img)
                if os.path.exists(img_path):
                    self._sender.send_image(Target.from_data(ctx.raw_data), img_path)

        # 第10关显示Boss登场
        if exp["stage"] == 10 and hp_percent > 0:
            boss_text = act_cfg.get("boss_text", "")
            if boss_text:
                lines.insert(0, "")
                lines.insert(0, boss_text)
                lines.insert(0, "———")
            boss_img = act_cfg.get("boss_image", "")
            if boss_img:
                img_path = os.path.join(CatConfig.CAT_EXPEDITION_IMG_DIR, boss_img)
                if os.path.exists(img_path):
                    self._sender.send_image(Target.from_data(ctx.raw_data), img_path)

        if hp_percent > 10:
            lines.append(f"血量：{exp['boss_hp']}/{boss_max}（{hp_percent:.1f}%）")
        else:
            lines.append("血量：???")

        lines.append(f"地形：{terrain}")
        lines.append(f"通关奖励：🐟{stage_cfg['reward_fish']} 💎{stage_cfg['reward_eye']}")
        lines.append(f"第1名：🐟{stage_cfg['top1_fish']} 💎{stage_cfg['top1_eye']}")
        lines.append(f"第2名：🐟{stage_cfg['top2_fish']} 💎{stage_cfg['top2_eye']}")
        lines.append(f"第3名：🐟{stage_cfg['top3_fish']} 💎{stage_cfg['top3_eye']}")
        lines.append(f"最后一击：🐟{stage_cfg['last_hit_fish']} 💎{stage_cfg['last_hit_eye']}")

        # 排行榜（血量>10%才显示）
        if hp_percent > 10:
            damage_log = exp.get("damage_log", [])
            if damage_log:
                # 按QQ聚合伤害
                totals = {}
                names = {}
                for entry in damage_log:
                    qq = entry["qq"]
                    totals[qq] = totals.get(qq, 0) + entry["damage"]
                    names[qq] = entry["name"]
                sorted_players = sorted(totals.items(), key=lambda x: x[1], reverse=True)
                lines.append("")
                lines.append("【伤害排行】")
                for i, (qq, dmg) in enumerate(sorted_players[:10], 1):
                    name = names.get(qq, qq)
                    lines.append(f"  {i}. {name}：{dmg}")
        else:
            lines.append("")
            lines.append("【伤害排行】???")

        self._sender.reply(ctx, "\n".join(lines))

    def _handle_stage_clear(self, ctx: CommandContext, exp: dict,
                            stage_cfg: dict, act_cfg: dict) -> None:
        """通关处理：发放奖励、进入下一关"""
        lines = [
            f"🎉 恭喜通关！【{act_cfg.get('name', '???')}】第{exp['stage']}关！",
            f"Boss「{stage_cfg['boss_name']}」被击败了！",
        ]

        # 发放通关奖励（所有参与本关讨伐的玩家）
        participants = []
        seen_qq = set()
        for entry in exp.get("damage_log", []):
            if entry["qq"] not in seen_qq:
                seen_qq.add(entry["qq"])
                participants.append(entry["qq"])
        for qq in participants:
            p = self._peek_player(int(qq))
            if p is None:
                continue
            p["fish"] += stage_cfg["reward_fish"]
            p["eye_stones"] = p.get("eye_stones", 0) + stage_cfg["reward_eye"]
            self._update_player(int(qq), p)
        lines.append(f"通关奖励（全员 {len(participants)} 人）：🐟{stage_cfg['reward_fish']} 💎{stage_cfg['reward_eye']}")

        # 发放 top3 奖励
        damage_log = exp.get("damage_log", [])
        if damage_log:
            totals = {}
            names = {}
            for entry in damage_log:
                qq = entry["qq"]
                totals[qq] = totals.get(qq, 0) + entry["damage"]
                names[qq] = entry["name"]
            sorted_players = sorted(totals.items(), key=lambda x: x[1], reverse=True)

            for i, (qq, dmg) in enumerate(sorted_players[:3], 1):
                p = self._peek_player(int(qq))
                if p:
                    p["fish"] += stage_cfg[f"top{i}_fish"]
                    p["eye_stones"] = p.get("eye_stones", 0) + stage_cfg[f"top{i}_eye"]
                    self._update_player(int(qq), p)
                name = names.get(qq, qq)
                lines.append(f"  第{i}名 {name}：🐟{stage_cfg[f'top{i}_fish']} 💎{stage_cfg[f'top{i}_eye']}")

        # 发放最后一击奖励
        last_hit = exp.get("damage_log", [])
        if last_hit:
            last_qq = last_hit[-1]["qq"]
            p = self._peek_player(int(last_qq))
            if p:
                p["fish"] += stage_cfg["last_hit_fish"]
                p["eye_stones"] = p.get("eye_stones", 0) + stage_cfg["last_hit_eye"]
                self._update_player(int(last_qq), p)
            lines.append(f"  最后一击 {last_hit[-1]['name']}：🐟{stage_cfg['last_hit_fish']} 💎{stage_cfg['last_hit_eye']}")

        # 进入下一关
        stages = act_cfg.get("stages", [])
        current_idx = None
        for i, s in enumerate(stages):
            if s["stage"] == exp["stage"]:
                current_idx = i
                break

        if current_idx is not None and current_idx + 1 < len(stages):
            # 下一关
            next_stage = stages[current_idx + 1]
            exp["stage"] = next_stage["stage"]
            exp["boss_hp"] = next_stage["boss_hp"]
            exp["damage_log"] = []
            lines.append("")
            lines.append(f"进入第{next_stage['stage']}关！Boss：{next_stage['boss_name']}")
        else:
            # 本幕最后一关：显示通关剧情 + 通关图
            clear_text = act_cfg.get("clear_text", "")
            if clear_text:
                lines.append("")
                lines.append("———")
                lines.append(clear_text)
            clear_img = act_cfg.get("clear_image", "")
            if clear_img:
                img_path = os.path.join(CatConfig.CAT_EXPEDITION_IMG_DIR, clear_img)
                if os.path.exists(img_path):
                    self._sender.send_image(Target.from_data(ctx.raw_data), img_path)

            # 进入下一幕
            next_act = exp["act"] + 1
            next_act_cfg = self._get_act_config(next_act)
            if next_act_cfg:
                exp["act"] = next_act
                exp["stage"] = 1
                first_stage = next_act_cfg["stages"][0]
                exp["boss_hp"] = first_stage["boss_hp"]
                exp["damage_log"] = []
                lines.append("")
                lines.append(f"🎊 进入新幕【{next_act_cfg.get('name', '???')}】！")

                # 发送剧情图
                story_img = next_act_cfg.get("story_image", "")
                if story_img:
                    img_path = os.path.join(CatConfig.CAT_EXPEDITION_IMG_DIR, story_img)
                    if os.path.exists(img_path):
                        self._sender.send_image(Target.from_data(ctx.raw_data), img_path)
            else:
                lines.append("")
                lines.append("———\n远征队正在等待新的任务...")

        self._save_expedition(exp)
        self._sender.reply(ctx, "\n".join(lines))

    def _load_expedition(self) -> dict:
        """加载全局远征状态"""
        return _load_json(CatConfig.CAT_EXPEDITION_DATA)

    def _save_expedition(self, exp: dict) -> None:
        """保存全局远征状态"""
        _save_json(CatConfig.CAT_EXPEDITION_DATA, exp)

    def _get_act_config(self, act: int) -> dict:
        """从JSON文件读取指定幕的关卡配置"""
        data = _load_json(CatConfig.CAT_EXPEDITION_ACTS_PATH)
        return data.get(str(act), {})

    def cmd_research(self, ctx: CommandContext) -> None:
        """科研（占位）"""
        self._sender.reply(ctx, "远征队还在准备中，敬请期待喵～ (=^･ω･^=)")

    def cmd_mail(self, ctx: CommandContext) -> None:
        """管理员全服邮件：给所有玩家发放鱼干或猫眼石"""
        # 用法：邮件 鱼干 500 / 邮件 猫眼石 10 [附言]
        args = ctx.get_args().strip()
        parts = args.split(None, 2)
        if len(parts) < 2:
            self._sender.reply(ctx, "用法：邮件 <鱼干|猫眼石> <数量> [附言]")
            return

        kind_text, amount_text = parts[0], parts[1]
        note = parts[2].strip() if len(parts) > 2 else ""

        if kind_text in ("鱼干", "fish"):
            field, icon = "fish", "🐟"
        elif kind_text in ("猫眼石", "eye", "eyestone"):
            field, icon = "eye_stones", "💎"
        else:
            self._sender.reply(ctx, "发放类型只能是「鱼干」或「猫眼石」喵")
            return

        try:
            amount = int(amount_text)
        except ValueError:
            self._sender.reply(ctx, f"数量得是整数喵，收到了「{amount_text}」")
            return
        if amount == 0:
            self._sender.reply(ctx, "发放数量不能是 0 喵")
            return
        if amount < 0:
            # 负数为回收，不允许扣成负数，单列判断
            self._sender.reply(ctx, "暂时不支持回收喵，数量要为正数")
            return

        players = self._load_players()
        if not players:
            self._sender.reply(ctx, "还没有玩家注册过喵，无人可发")
            return

        count = 0
        for qq, player in players.items():
            player[field] = player.get(field, 0) + amount
            count += 1
        self._save_players(players)

        lines = [f"【全服邮件】已向 {count} 位玩家发放 {icon} {amount} {kind_text}"]
        if note:
            lines.append(f"附言：{note}")
        self._sender.reply(ctx, "\n".join(lines))

    def _reply_country_list(self, ctx: CommandContext) -> None:
        """文本回复：当前卡池里有喵喵的国家"""
        counts = {}
        for cat in self._pool:
            code = cat.get("country")
            if code:
                counts[code] = counts.get(code, 0) + 1

        lines = ["【喵喵图鉴】当前已解锁的国家："]
        for code in sorted(counts):
            name = self._countries.get(code, "未知国家")
            lines.append(f"{code} {name}（{counts[code]}只）")
        lines += [
            "",
            "发送「喵喵图鉴 国家编号」查看该国喵喵",
            "发送「喵喵图鉴 喵喵id」查看详细档案",
        ]
        self._sender.reply(ctx, "\n".join(lines))

    # ---------- 图鉴拼图 ----------

    def _render_country_book(self, code: str, qq: int) -> str:
        """生成某国家全部喵喵（按稀有度分组）的图鉴拼图，未拥有显示问号"""
        all_cats = [c for c in self._pool if c.get("country") == code]
        player = self._peek_player(qq)
        owned_ids = {c["id"] for c in (player or {}).get("collection", [])}
        owned_stars = {c["id"]: c.get("star", 1)
                       for c in (player or {}).get("collection", [])}

        # 按稀有度分组（只保留有猫的组，顺序 normal→rare→epic→legend）
        groups = []
        for r in CAT_RARITY_ORDER:
            rc = sorted((c for c in all_cats if c["rarity"] == r),
                        key=lambda c: c["id"])
            if rc:
                groups.append((r, rc))

        margin = 48
        header_h = 150
        group_h = 56
        gap = 16
        cell_w = 380
        portrait = 300
        caption_h = 110
        cell_h = portrait + caption_h
        cols = min(4, max((len(rc) for _, rc in groups), default=1))

        # 计算总高度
        body_h = 0
        for _, rc in groups:
            rows = (len(rc) + cols - 1) // cols
            body_h += group_h + rows * cell_h
        body_h += gap * (len(groups) - 1) if len(groups) > 1 else 0

        width = margin * 2 + cols * cell_w
        height = header_h + body_h + margin

        book = Image.new("RGBA", (width, height), (253, 249, 242, 255))
        draw = ImageDraw.Draw(book)
        draw.rectangle((6, 6, width - 7, height - 7), outline=(190, 165, 130), width=4)

        name = self._countries.get(code, "未知国家")
        self._center_text(
            draw, (0, 24, width, 96), name, self._font(60), CAT_TEXT_RGB
        )
        got = sum(1 for c in all_cats if c["id"] in owned_ids)
        self._center_text(
            draw, (0, 92, width, 138),
            f"{code} · 收集进度 {got}/{len(all_cats)}",
            self._font(32), (130, 110, 85)
        )

        q_img = self._find_img(CatConfig.CAT_IMG_CATS_DIR, "?")

        y = header_h
        for rarity, rc in groups:
            # 稀有度分组小标题
            self._center_text(
                draw, (margin, y, width - margin, y + group_h),
                f"—— {CatConfig.CAT_RARITY_NAMES[rarity]} ——",
                self._font(36), CAT_RARITY_RGB[rarity]
            )
            y += group_h

            for i, cat in enumerate(rc):
                r, col = divmod(i, cols)
                x0 = margin + col * cell_w
                y0 = y + r * cell_h
                img_box = (x0 + (cell_w - portrait) // 2, y0 + 10,
                           x0 + (cell_w + portrait) // 2, y0 + 10 + portrait)
                is_owned = cat["id"] in owned_ids

                if is_owned:
                    pic = self._cat_portrait_path(cat)
                    if pic:
                        self._paste_fit(book, pic, img_box)
                    else:
                        self._draw_question_block(draw, img_box, cat["name"], missing_asset=True)
                elif q_img:
                    self._paste_fit(book, q_img, img_box)
                else:
                    self._draw_question_block(draw, img_box, "?", missing_asset=False)

                cap_y0 = img_box[3] + 6
                self._center_text(draw, (x0, cap_y0, x0 + cell_w, cap_y0 + 34),
                                  cat["id"], self._font(28), (140, 140, 140))
                if is_owned:
                    label = f"{cat['name']} ★{owned_stars[cat['id']]}"
                    self._center_text_fit(
                        draw, (x0, cap_y0 + 34, x0 + cell_w, cap_y0 + 80),
                        label, 38, CAT_RARITY_RGB[cat["rarity"]], min_size=22
                    )
                else:
                    self._center_text(
                        draw, (x0, cap_y0 + 34, x0 + cell_w, cap_y0 + 80),
                        "？？？", self._font(38), (170, 170, 170)
                    )

            rows = (len(rc) + cols - 1) // cols
            y += rows * cell_h + gap

        os.makedirs(CatConfig.CAT_CARD_CACHE_DIR, exist_ok=True)
        path = os.path.join(CatConfig.CAT_CARD_CACHE_DIR, f"book_{code}_{qq}.png")
        book.convert("RGB").save(path)
        return path

    @staticmethod
    def _draw_question_block(draw: ImageDraw.ImageDraw, box, label: str,
                             missing_asset: bool) -> None:
        """缺立绘/未拥有时的灰色问号占位块"""
        draw.rounded_rectangle(box, radius=24, fill=(232, 228, 220))
        if missing_asset:
            CatExpeditionPlugin._center_text(
                draw, box, label, CatExpeditionPlugin._font(34), (160, 150, 135)
            )
        else:
            CatExpeditionPlugin._center_text(
                draw, box, "?", CatExpeditionPlugin._font(190), (170, 170, 170)
            )

    # ---------- 详情卡片（队员表格） ----------

    def _render_cat_card(self, cat: dict, star: int) -> str:
        """按队员表格模板合成单只喵喵详情卡片"""
        job_path = cat.get("job_path", [])
        # 当前职业：1-2星初心、3-4星二转、5星终转
        if star >= 5 and len(job_path) >= 3:
            cur_job = job_path[2]
        elif star >= 3 and len(job_path) >= 2:
            cur_job = job_path[1]
        elif job_path:
            cur_job = job_path[0]
        else:
            cur_job = ""
        country_name = self._countries.get(cat.get("country"), cat.get("country", ""))

        # 照片：cats/猫名.png 专属立绘 → cats/最终职业.png 兜底
        photo = None
        if job_path:
            photo = (self._find_img(CatConfig.CAT_IMG_CATS_DIR, cat["name"])
                     or self._find_img(CatConfig.CAT_IMG_CATS_DIR, job_path[-1]))
        job_img = self._find_img(CatConfig.CAT_IMG_JOBS_DIR, cur_job) if cur_job else None
        origin_img = self._find_img(CatConfig.CAT_IMG_ORIGINS_DIR, country_name)

        card = Image.open(CatConfig.CAT_CARD_TEMPLATE).convert("RGBA")
        draw = ImageDraw.Draw(card)

        for key, path, want in (
            ("photo", photo, cat["name"]),
            ("job", job_img, cur_job),
            ("origin", origin_img, country_name),
        ):
            if path:
                self._paste_fit(card, path, CAT_CELLS[key])
            else:
                self._center_text(
                    draw, CAT_CELLS[key], f"（缺图片）{want}",
                    self._font(CAT_FONT_SIZES["missing"]), (180, 90, 90)
                )

        self._center_text_fit(
            draw, CAT_CELLS["name"], cat["name"],
            CAT_FONT_SIZES["name"], CAT_TEXT_RGB
        )
        self._center_text(draw, CAT_CELLS["star"], "★" * star,
                          self._font(CAT_FONT_SIZES["star"]), CAT_STAR_RGB)
        self._center_text(
            draw, CAT_CELLS["rarity"], CatConfig.CAT_RARITY_NAMES[cat["rarity"]],
            self._font(CAT_FONT_SIZES["rarity"]), CAT_RARITY_RGB[cat["rarity"]]
        )
        self._center_text_fit(
            draw, CAT_CELLS["job_name"], cur_job,
            CAT_FONT_SIZES["job_name"], CAT_TEXT_RGB
        )
        self._center_text_fit(
            draw, CAT_CELLS["origin_name"], country_name,
            CAT_FONT_SIZES["origin_name"], CAT_TEXT_RGB
        )
        self._center_text(
            draw, CAT_CELLS["trait"], cat.get("trait_desc") or "—",
            self._font(CAT_FONT_SIZES["trait"]), CAT_TEXT_RGB
        )
        self._draw_intro(
            draw, CAT_CELLS["intro"], cat.get("intro", ""),
            self._font(CAT_FONT_SIZES["intro"]), CAT_TEXT_RGB
        )

        os.makedirs(CatConfig.CAT_CARD_CACHE_DIR, exist_ok=True)
        path = os.path.join(CatConfig.CAT_CARD_CACHE_DIR, f"card_{cat['id']}_{star}星.png")
        card.convert("RGB").save(path)
        return path

    def _peek_player(self, qq: int) -> Optional[dict]:
        """只读获取玩家存档，不存在返回 None（不触发新玩家建档）"""
        return self._load_players().get(str(qq))

    def _cat_portrait_path(self, cat: dict) -> Optional[str]:
        """专属立绘 cats/猫名.png，缺则用 cats/最终职业.png"""
        path = self._find_img(CatConfig.CAT_IMG_CATS_DIR, cat["name"])
        if path is None and cat.get("job_path"):
            path = self._find_img(CatConfig.CAT_IMG_CATS_DIR, cat["job_path"][-1])
        return path

    @staticmethod
    def _find_img(folder: str, name: str) -> Optional[str]:
        """精确匹配文件名，容忍多余空格；找不到返回 None"""
        if not name or not os.path.isdir(folder):
            return None
        exact = os.path.join(folder, f"{name}.png")
        if os.path.exists(exact):
            return exact
        compact = name.replace(" ", "")
        for fn in os.listdir(folder):
            if fn.lower().endswith(".png") and \
                    os.path.splitext(fn)[0].replace(" ", "") == compact:
                return os.path.join(folder, fn)
        return None

    @staticmethod
    def _font(size: int) -> ImageFont.FreeTypeFont:
        for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                   r"C:\Windows\Fonts\simsun.ttc"):
            if os.path.exists(fp):
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()

    @staticmethod
    def _paste_fit(canvas: Image.Image, path: str, box) -> None:
        """图片等比缩放放进格子并居中"""
        x0, y0, x1, y1 = box
        im = Image.open(path).convert("RGBA")
        im.thumbnail((x1 - x0, y1 - y0), Image.LANCZOS)
        pos = (x0 + (x1 - x0 - im.width) // 2,
               y0 + (y1 - y0 - im.height) // 2)
        canvas.alpha_composite(im, pos)

    @staticmethod
    def _center_text(draw: ImageDraw.ImageDraw, box, text: str,
                     fnt, fill) -> None:
        x0, y0, x1, y1 = box
        l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
        x = x0 + (x1 - x0 - (r - l)) / 2 - l
        y = y0 + (y1 - y0 - (b - t)) / 2 - t
        draw.text((x, y), text, font=fnt, fill=fill)

    def _center_text_fit(self, draw, box, text: str, max_size: int,
                         fill, min_size: int = 24) -> None:
        """居中文字；宽度超格时自动逐级缩字号"""
        x0, _, x1, _ = box
        size = max_size
        while size > min_size and \
                draw.textlength(text, font=self._font(size)) > x1 - x0:
            size -= 2
        self._center_text(draw, box, text, self._font(size), fill)

    @staticmethod
    def _wrap_cn(draw, text, fnt, max_w: int) -> List[str]:
        lines, cur = [], ""
        for ch in text:
            if draw.textlength(cur + ch, font=fnt) <= max_w:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines

    def _draw_intro(self, draw, box, text: str, fnt, fill) -> None:
        """简介按宽度自动换行，整块垂直居中"""
        x0, y0, x1, y1 = box
        lines = self._wrap_cn(draw, text, fnt, x1 - x0)
        line_h = fnt.size + 10
        y = y0 + (y1 - y0 - len(lines) * line_h) / 2
        for line in lines:
            l, t, r, b = draw.textbbox((0, 0), line, font=fnt)
            draw.text((x0 + (x1 - x0 - (r - l)) / 2 - l, y - t),
                      line, font=fnt, fill=fill)
            y += line_h

    # ==================== 战力计算（战斗系统预留） ====================

    def _team_base_power(self, player: dict) -> int:
        """远征队基础战力：目前只由猫猫决定（各猫 基础战力×星级倍率 之和），
        以后会叠加遗物加成。"""
        total = 0
        for owned in player.get("collection", []):
            base = CatConfig.CAT_BASE_POWER_BY_RARITY.get(owned.get("rarity", "normal"), 0)
            total += base * CatConfig.CAT_STAR_POWER_MULT.get(owned.get("star", 1), 1)
        return total

    def _max_team_base_power(self) -> int:
        """全服玩家中最高的基础战力（签到暴击提升判定用）"""
        players = self._load_players()
        return max((self._team_base_power(p) for p in players.values()), default=0)

    def _cat_power(self, owned_cat: dict, pool_cat: Optional[dict],
                   battle_type: Optional[str] = None,
                   weather: Optional[str] = None,
                   terrain: Optional[str] = None) -> int:
        """出阵猫战力：基础战力×星级倍率，再叠加适性特性加成。
        仅对出征队员调用，非出阵猫不享受特性加成。"""
        star = owned_cat.get("star", 1)
        base = CatConfig.CAT_BASE_POWER_BY_RARITY[owned_cat["rarity"]]
        power = base * CatConfig.CAT_STAR_POWER_MULT.get(star, 1)
        bonus = self._trait_bonus_ratio(pool_cat, owned_cat["rarity"], star,
                                        battle_type, weather, terrain)
        return int(power * (1 + bonus))

    @staticmethod
    def _trait_bonus_ratio(pool_cat: Optional[dict], rarity: str, star: int,
                           battle_type: Optional[str],
                           weather: Optional[str],
                           terrain: Optional[str]) -> float:
        """适性特性加成比例：战斗类型/天气/地形每匹配一项，
        按稀有度加 2%/3%/4%/5%，3星×2、5星×3。
        猫的适性（trait_affinity）以后在 cat_pool.json 分配，留空时无加成。"""
        affinity = (pool_cat or {}).get("trait_affinity") or {}
        conditions = (
            ("battle", battle_type),
            ("weather", weather),
            ("terrain", terrain),
        )
        matched = sum(
            1 for key, value in conditions
            if value is not None and affinity.get(key) == value
        )
        if matched == 0:
            return 0.0
        per_match = CatConfig.CAT_TRAIT_BONUS_BY_RARITY.get(rarity, 0.02)
        multiplier = CatConfig.CAT_TRAIT_MULT_BY_STAR.get(star, 1)
        return matched * per_match * multiplier

    # ==================== 辅助方法 ====================

    def _roll_rarity(self) -> str:
        """按概率 roll 稀有度"""
        rates = CatConfig.CAT_RARITY_RATES
        r = random.random()
        cum = 0.0
        for rarity, rate in rates.items():
            cum += rate
            if r <= cum:
                return rarity
        return "normal"  # 兜底

    def _group_by_rarity(self) -> dict:
        """把卡池按稀有度分组"""
        groups = {}
        for cat in self._pool:
            r = cat["rarity"]
            if r not in groups:
                groups[r] = []
            groups[r].append(cat)
        return groups

    def _find_pool_cat(self, cat_id: str) -> Optional[dict]:
        """在卡池里按 ID 找喵喵"""
        for cat in self._pool:
            if cat["id"] == cat_id:
                return cat
        return None

    def _resolve_pool(self, name: str) -> Optional[str]:
        """按卡池显示名或 key 解析卡池 key，找不到返回 None"""
        if not name:
            return None
        for key, pool in self._pools.items():
            if key == name or pool.get("name") == name:
                return key
        return None

    @staticmethod
    def _find_collection_cat(player: dict, cat_id: str) -> Optional[dict]:
        """在玩家收藏里按 ID 找喵喵"""
        for cat in player.get("collection", []):
            if cat["id"] == cat_id:
                return cat
        return None
