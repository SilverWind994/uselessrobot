"""串子小车 · 喵喵远征队网页端数据层。

图鉴 / 远征队 / 远征 / 绘图的规则与数值全部复用 plugins/cat_expedition.py，
网页端只负责把结果整理成 JSON（以及按需调用插件里的 PIL 绘图函数出图），
避免网页端与机器人端出现规则漂移。

远征状态（expedition.json）是运行时文件，缺失时按第一幕第一关初始化。
"""

import os
from datetime import date

from plugins.cat_config import CatConfig
from plugins.cat_expedition import CatExpeditionPlugin, CAT_RARITY_ORDER
from core.message_sender import MessageSender
from core.command_router import CommandContext


class _QuietSender(MessageSender):
    """网页端不需要真的发消息：把回复与发图都做成空操作，
    这样就能直接复用插件里「人手一份」的远征/绘图逻辑。"""

    def reply(self, ctx, text: str) -> None:
        pass

    def send_image(self, target, file_path: str) -> None:
        pass


_plugin = CatExpeditionPlugin(_QuietSender())

# 头像素材目录（供网页直接引用 <img>）
CATS_DIR = CatConfig.CAT_IMG_CATS_DIR
JOBS_DIR = CatConfig.CAT_IMG_JOBS_DIR
ORIGINS_DIR = CatConfig.CAT_IMG_ORIGINS_DIR
EXPEDITION_IMG_DIR = CatConfig.CAT_EXPEDITION_IMG_DIR
DATA_DIR = os.path.join(CatConfig.CAT_EXPEDITION_DIR, "data")


def _today() -> str:
    return date.today().isoformat()


def _job_for_star(job_path, star: int) -> str:
    """星级决定当前职业：1-2星初心、3-4星二转、5星终转（与插件 _render_cat_card 一致）"""
    if star >= 5 and len(job_path) >= 3:
        return job_path[2]
    if star >= 3 and len(job_path) >= 2:
        return job_path[1]
    return job_path[0] if job_path else ""


def _portrait_name(cat: dict) -> str:
    """立绘文件名（不含扩展名）：cats/猫名.png，缺则 cats/最终职业.png；都没有返回空"""
    path = _plugin._cat_portrait_path(cat)
    return os.path.splitext(os.path.basename(path))[0] if path else ""


def _player(qq: int) -> dict:
    return _plugin._peek_player(qq) or {}


def _ensure_expedition() -> dict:
    """读取全局远征状态；文件缺失时按第一幕第一关初始化并落盘"""
    exp = _plugin._load_expedition()
    if not exp.get("act"):
        first = (_plugin._get_act_config(1).get("stages") or [{}])[0]
        exp = {"act": 1, "stage": 1,
               "boss_hp": first.get("boss_hp", 1), "damage_log": []}
        _plugin._save_expedition(exp)
    return exp


# ==================== 图鉴 ====================

def cat_index(qq: int) -> dict:
    """图鉴索引：国家表、卡池表、全部喵喵（含本人星级）"""
    player = _player(qq)
    owned = {c["id"]: c.get("star", 1) for c in player.get("collection", [])}

    # 各卡池包含哪些喵喵（卡池视图分组用）；default 是全量池，不参与「归属卡池」判定
    pools = []
    pool_of = {}
    for key, pool in _plugin._pools.items():
        ids = [cat["id"] for cat in pool.get("cats", [])]
        if key != "default":
            for cid in ids:
                pool_of.setdefault(cid, key)
        pools.append({"key": key, "name": pool.get("name", key),
                      "count": len(ids), "ids": ids})

    cats = []
    for cat in _plugin._pool:
        star = owned.get(cat["id"], 0)
        job_path = cat.get("job_path", [])
        cats.append({
            "id": cat["id"],
            "name": cat["name"],
            "rarity": cat["rarity"],
            "country": cat.get("country", ""),
            "pool": pool_of.get(cat["id"], "default"),
            "trait": cat.get("trait_desc") or "—",
            "star": star,
            # 未解锁不返回职业/立绘，避免提前剧透；已解锁按星级给出当前职业与立绘图名
            "job": _job_for_star(job_path, star) if star else "",
            "portrait": _portrait_name(cat) if star else "",
        })

    total = len(cats)
    got = sum(1 for c in cats if c["star"] > 0)
    return {
        "countries": _plugin._countries,
        "pools": pools,
        "cats": cats,
        "rarity_order": CAT_RARITY_ORDER,
        "owned_count": got,
        "total_count": total,
    }


def cat_detail(qq: int, cat_id: str):
    """单只喵喵的详情；找不到返回 None"""
    cat = _plugin._find_pool_cat(cat_id)
    if cat is None:
        return None
    owned = _plugin._find_collection_cat(_player(qq), cat_id)
    star = owned.get("star", 0) if owned else 0
    job_path = cat.get("job_path", [])
    country = cat.get("country", "")
    pool_key = "default"
    for key, pool in _plugin._pools.items():
        if key == "default":
            continue
        if any(c["id"] == cat_id for c in pool.get("cats", [])):
            pool_key = key
            break
    return {
        "id": cat["id"],
        "name": cat["name"],
        "rarity": cat["rarity"],
        "country": country,
        "country_name": _plugin._countries.get(country, country),
        "pool": pool_key,
        "job_path": job_path,
        "job": _job_for_star(job_path, star) if star else (job_path[0] if job_path else ""),
        "portrait": _portrait_name(cat),
        "trait": cat.get("trait_desc") or "—",
        "affinity": cat.get("trait_affinity") or {},
        "intro": cat.get("intro", ""),
        "star": star,
        "owned": star > 0,
    }


# ==================== 远征队 ====================

def cat_collection(qq: int) -> dict:
    """远征队：本人的基础属性 + 每只喵喵的情况"""
    player = _player(qq)
    collection = player.get("collection", [])
    cats = []
    max_star = 0
    for owned in collection:
        pool_cat = _plugin._find_pool_cat(owned["id"]) or {}
        star = owned.get("star", 1)
        max_star += 1 if star >= CatConfig.CAT_MAX_STAR else 0
        job_path = pool_cat.get("job_path", [])
        portrait_cat = pool_cat or {"name": owned.get("name", ""), "job_path": []}
        rarity = owned.get("rarity", "normal")
        power = (CatConfig.CAT_BASE_POWER_BY_RARITY.get(rarity, 0)
                 * CatConfig.CAT_STAR_POWER_MULT.get(star, 1))
        country = pool_cat.get("country", "")
        cats.append({
            "id": owned["id"],
            "name": owned.get("name", owned["id"]),
            "rarity": rarity,
            "star": star,
            "job": _job_for_star(job_path, star),
            "portrait": _portrait_name(portrait_cat),
            "country": country,
            "country_name": _plugin._countries.get(country, country),
            "power": power,
        })
    cats.sort(key=lambda c: (CAT_RARITY_ORDER.index(c["rarity"]) if c["rarity"] in CAT_RARITY_ORDER else 0,
                             c["id"]), reverse=True)
    return {
        "info": {
            "cats": len(collection),
            "max_star": max_star,
            "base_power": _plugin._team_base_power(player),
            "fish": player.get("fish", 0),
            "eye_stones": player.get("eye_stones", 0),
            "relics": player.get("relics", 0),
            "research_limit": player.get("research_limit", CatConfig.CAT_INITIAL_RESEARCH_LIMIT),
            "signin_total": player.get("signin_total", 0),
            "signin_streak": player.get("signin_streak", 0),
            "summon_count": player.get("summon_count", 0),
            "expedition_total": player.get("expedition_total", 0),
            "expedition_damage": player.get("expedition_damage", 0),
        },
        "cats": cats,
    }


# ==================== 远征 ====================

def _ranking(exp: dict) -> list:
    """按 QQ 聚合伤害排行（前 10）"""
    totals, names = {}, {}
    for entry in exp.get("damage_log", []):
        qq = entry.get("qq")
        totals[qq] = totals.get(qq, 0) + entry.get("damage", 0)
        names[qq] = entry.get("name", qq)
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [{"name": names.get(qq, qq), "damage": dmg} for qq, dmg in ranked[:10]]


def expedition_state(qq: int):
    """当前远征 Boss 情况：血量（≤25% 隐藏）、奖励、伤害排行、剧情"""
    exp = _ensure_expedition()
    act = exp.get("act", 1)
    act_cfg = _plugin._get_act_config(act)
    stage_cfg = next((s for s in act_cfg.get("stages", []) if s["stage"] == exp.get("stage")), None)
    if stage_cfg is None:
        return None

    boss_max = stage_cfg.get("boss_hp", 1)
    hp = exp.get("boss_hp", boss_max)
    percent = hp / boss_max * 100 if boss_max else 0
    hidden = percent <= 25

    rewards = {
        "clear": {"fish": stage_cfg.get("reward_fish", 0), "eye": stage_cfg.get("reward_eye", 0)},
        "top": [
            {"rank": i, "fish": stage_cfg.get(f"top{i}_fish", 0), "eye": stage_cfg.get(f"top{i}_eye", 0)}
            for i in (1, 2, 3)
        ],
        "last_hit": {"fish": stage_cfg.get("last_hit_fish", 0), "eye": stage_cfg.get("last_hit_eye", 0)},
    }

    player = _player(qq)
    return {
        "act": act,
        "act_name": act_cfg.get("name", "???"),
        "stage": exp.get("stage"),
        "boss_name": stage_cfg.get("boss_name", "???"),
        "terrain": stage_cfg.get("terrain", "平原"),
        "hidden": hidden,
        "boss_hp": None if hidden else hp,
        "boss_max": None if hidden else boss_max,
        "percent": None if hidden else round(percent, 1),
        "rewards": rewards,
        "ranking": [] if hidden else _ranking(exp),
        "story_text": act_cfg.get("story_text", "") if exp.get("stage") == 1 else "",
        "boss_text": act_cfg.get("boss_text", "") if exp.get("stage") == 10 and not hidden else "",
        "ran_today": player.get("last_expedition") == _today(),
        # 签到 / 抽卡面板要用到的余额与状态
        "fish": player.get("fish", 0),
        "eye_stones": player.get("eye_stones", 0),
        "signin_done": player.get("last_signin") == _today(),
        "summon_cost": CatConfig.CAT_SUMMON_COST,
    }


def expedition_run(qq: int, nick: str) -> list:
    """执行一次远征：复用插件 _expedition_core，返回结果文本行（已就地落盘）"""
    player = _plugin._get_player(qq)
    ctx = CommandContext({
        "message_type": "private",
        "user_id": qq,
        "sender": {"nickname": nick},
    })
    return _plugin._expedition_core(ctx, player)


# ==================== 签到 / 抽卡 ====================

def signin(qq: int) -> dict:
    """每日签到：复用插件 _signin_core，返回消息行与最新余额"""
    player = _plugin._get_player(qq)
    lines = _plugin._signin_core(player)
    _plugin._update_player(qq, player)
    return {
        "lines": lines,
        "fish": player.get("fish", 0),
        "eye_stones": player.get("eye_stones", 0),
        "signin_total": player.get("signin_total", 0),
        "signin_streak": player.get("signin_streak", 0),
        "signin_done": player.get("last_signin") == _today(),
    }


def summon(qq: int, count, pool: str):
    """抽卡：复用插件 _summon_batch_core，返回 (错误信息, 结果)；pool 为空或「全」表示全部卡池"""
    try:
        count = int(count)
    except (TypeError, ValueError):
        return "数量要是数字喵", None
    if count < 1:
        return "数量至少为 1 喵~", None

    pool = (pool or "").strip()
    if pool in ("", "全", "全部", "all"):
        pool_key = None
    else:
        pool_key = _plugin._resolve_pool(pool)
        if pool_key is None:
            return f"没找到卡池「{pool}」喵", None

    player = _plugin._get_player(qq)
    total_cost = count * CatConfig.CAT_SUMMON_COST
    if player.get("fish", 0) < total_cost:
        return f"鱼干不够啦！需要 {total_cost}，还差 {total_cost - player.get('fish', 0)} 鱼干 🐟", None

    results, cost, lucky = _plugin._summon_batch_core(player, count, pool_key)
    _plugin._update_player(qq, player)

    drawn = []
    for r in results:
        pool_cat = _plugin._find_pool_cat(r["id"]) or {"name": r["name"], "job_path": []}
        drawn.append({
            "id": r["id"],
            "name": r["name"],
            "rarity": r["rarity"],
            "star": r["star"],
            "job": r.get("job", ""),
            "portrait": _portrait_name(pool_cat),
            "is_new": not r["is_dup"],
            "refunded": r["refunded"],
            "refund_amt": r["refund_amt"],
            "star_up": r["star_up"],
            "job_up": r["job_up"],
        })
    return None, {
        "drawn": drawn,
        "cost": cost,
        "lucky": lucky,
        "fish": player.get("fish", 0),
        "eye_stones": player.get("eye_stones", 0),
        "summon_count": player.get("summon_count", 0),
    }


# ==================== 绘图（PIL 合成图） ====================

def render_book(qq: int, code: str):
    """生成某国家图鉴拼图，返回图片路径；国家不存在返回 None"""
    if code not in _plugin._countries:
        return None
    return _plugin._render_country_book(code, qq)


def render_card(qq: int, cat_id: str):
    """生成单只喵喵队员卡片，返回图片路径；未拥有/不存在返回 None"""
    cat = _plugin._find_pool_cat(cat_id)
    if cat is None:
        return None
    owned = _plugin._find_collection_cat(_player(qq), cat_id)
    if not owned:
        return None
    return _plugin._render_cat_card(cat, owned.get("star", 1))
