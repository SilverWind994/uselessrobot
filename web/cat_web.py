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
import avatar_web


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
        portrait_cat = pool_cat or {"name": "", "job_path": []}
        rarity = pool_cat.get("rarity", "normal")
        power = (CatConfig.CAT_BASE_POWER_BY_RARITY.get(rarity, 0)
                 * CatConfig.CAT_STAR_POWER_MULT.get(star, 1))
        country = pool_cat.get("country", "")
        cats.append({
            "id": owned["id"],
            "name": pool_cat.get("name", owned["id"]),
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
    """按 QQ 聚合伤害排行（全部玩家）"""
    totals, names = {}, {}
    for entry in exp.get("damage_log", []):
        qq = entry.get("qq")
        totals[qq] = totals.get(qq, 0) + entry.get("damage", 0)
        names[qq] = entry.get("name", qq)
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [{"qq": qq, "name": names.get(qq, qq), "damage": dmg,
             "avatar": avatar_web.avatar_url(qq)} for qq, dmg in ranked]


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
        "insurance": _plugin.insurance_status(player),
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


def _drawn_payload(results) -> list:
    """把插件抽卡结果整理成网页绘图/展示用的列表"""
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
    return drawn


def _insurance_event_payload(event):
    """把插件返回的保险事件整理成 JSON（赔付结果转成 drawn 列表）"""
    if not event or event.get("status") in (None, "none"):
        return None
    data = dict(event)
    payout = data.get("payout")
    if payout:
        payout = dict(payout)
        if payout.get("results"):
            payout["drawn"] = _drawn_payload(payout.pop("results"))
        data["payout"] = payout
    return data


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

    results, cost, lucky, insurance, relic_events = _plugin._summon_batch_core(
        player, count, pool_key)
    _plugin._update_player(qq, player)

    return None, {
        "drawn": _drawn_payload(results),
        "cost": cost,
        "lucky": lucky,
        "fish": player.get("fish", 0),
        "eye_stones": player.get("eye_stones", 0),
        "summon_count": player.get("summon_count", 0),
        "insurance": _plugin.insurance_status(player),
        "insurance_event": _insurance_event_payload(insurance),
        "relic_events": relic_events,
    }


# ==================== 喵保险 ====================

def insurance_info(qq: int) -> dict:
    """保险档位说明与当前保单状态"""
    player = _player(qq)
    return {
        "tiers": _plugin.insurance_tiers(),
        "insurance": _plugin.insurance_status(player),
        "fish": player.get("fish", 0),
        "eye_stones": player.get("eye_stones", 0),
    }


def insurance_buy(qq: int, tier: str):
    """购买喵保险，返回 (错误信息, 最新状态)"""
    if tier not in CatConfig.CAT_INSURANCE_TIERS:
        return "没找到这个保险档位喵", None
    player = _plugin._get_player(qq)
    err = _plugin._insurance_buy(player, tier)
    if err:
        return err, None
    _plugin._update_player(qq, player)
    return None, {
        "tiers": _plugin.insurance_tiers(),
        "insurance": _plugin.insurance_status(player),
        "fish": player.get("fish", 0),
        "eye_stones": player.get("eye_stones", 0),
    }


# ==================== 遗物研究 ====================

def _relic_project_view(code: str, relics: list, state: dict, logs: list) -> list:
    """把某国研究项目整理成前端视图：状态、进度、记录量"""
    unlocked = state.get("unlocked", [])
    by_id = {r["id"]: r for r in relics}
    projects = []
    for tier in range(len(relics)):
        entries = [e for e in logs if e.get("code") == code and e.get("tier") == tier]
        people = {str(e.get("qq")) for e in entries if e.get("qq") is not None}
        item = {
            "tier": tier + 1,
            "records": len(entries),
            "people": len(people),
            "name": "",
            "effect": "",
        }
        if tier < len(unlocked):
            done = by_id.get(unlocked[tier]) or {}
            item.update({"status": "done", "name": done.get("name", "???"),
                         "effect": done.get("effect", "")})
        elif tier == len(unlocked):
            need = CatConfig.CAT_RELIC_REQUIREMENTS[tier]
            item.update({
                "status": "current",
                "need": need,
                "progress": int(state.get("progress", 0)),
                "kill_line": max(0, need - CatConfig.CAT_RELIC_FINAL_REMAIN),
            })
        else:
            item.update({"status": "locked"})
        projects.append(item)
    return projects


def relic_info(qq: int) -> dict:
    """遗物研究总览：各国项目状态、个人研究力、今日机会"""
    data = _plugin._load_relics()
    logs = _plugin._load_relic_logs()
    player = _player(qq)
    today = _today()
    countries = []
    for code, relics in CatConfig.CAT_RELICS.items():
        state = _plugin._relic_country_state(data, code)
        score, counts = _plugin._relic_cat_score(player, code)
        total_score = CatConfig.CAT_RELIC_BASE_SCORE + score
        countries.append({
            "code": code,
            "name": _plugin._countries.get(code, code),
            "unlocked": len(state.get("unlocked", [])),
            "total": len(relics),
            "progress": int(state.get("progress", 0)),
            "score": score,
            "total_score": total_score,
            "chance": total_score / CatConfig.CAT_RELIC_DIVISOR,
            "eureka": score / CatConfig.CAT_RELIC_EUREKA_DIVISOR,
            "rarity_counts": {k: v for k, v in counts.items() if v},
            "projects": _relic_project_view(code, relics, state, logs),
        })
    total_actual = sum(float(e.get("actual") or 0) for e in logs)
    total_expected = sum(float(e.get("expected") or 0) for e in logs)
    return {
        "countries": countries,
        "rarity_names": CatConfig.CAT_RARITY_NAMES,
        "base_score": CatConfig.CAT_RELIC_BASE_SCORE,
        "final_remain": CatConfig.CAT_RELIC_FINAL_REMAIN,
        "total": {
            "actual": round(total_actual, 1),
            "expected": round(total_expected, 1),
            "rate": (round((total_actual - total_expected) / total_expected * 100, 1)
                     if total_expected > 0 else None),
            "count": len(logs),
            "players": len({str(e.get("qq")) for e in logs if e.get("qq") is not None}),
        },
        "used_today": player.get("relic_research_date") == today,
        "fish": player.get("fish", 0),
        "eye_stones": player.get("eye_stones", 0),
    }


def relic_rank(code: str, tier: int) -> dict:
    """某个研究项目的完整双榜：实际进度、高于期望百分比（tier 从 0 开始）"""
    relics = CatConfig.CAT_RELICS.get(code) or []
    if not relics:
        return {"ok": False, "msg": "这个国家还没有遗物喵"}
    try:
        tier = int(tier)
    except (TypeError, ValueError):
        tier = 0
    tier = max(0, min(tier, len(relics) - 1))

    state = _plugin._relic_country_state(_plugin._load_relics(), code)
    unlocked = state.get("unlocked", [])
    if tier > len(unlocked):
        return {"ok": False, "msg": f"第{tier + 1}件还没开始研究喵"}

    by_id = {r["id"]: r for r in relics}
    if tier < len(unlocked):
        relic = by_id.get(unlocked[tier]) or {}
        title = f"第{tier + 1}件（{relic.get('name', '???')}）"
        status = "done"
        need = progress = kill_line = None
    else:
        title = f"第{tier + 1}件（研究中）"
        status = "current"
        need = CatConfig.CAT_RELIC_REQUIREMENTS[tier]
        progress = int(state.get("progress", 0))
        kill_line = max(0, need - CatConfig.CAT_RELIC_FINAL_REMAIN)

    entries = [e for e in _plugin._load_relic_logs()
               if e.get("code") == code and e.get("tier") == tier]
    players = _plugin._load_players()
    agg = {}
    for entry in entries:
        key = str(entry.get("qq"))
        stat = agg.get(key)
        if stat is None:
            stat = agg[key] = {"name": "", "actual": 0.0, "expected": 0.0, "count": 0}
        nick = (players.get(key) or {}).get("nick") or entry.get("nick") or ""
        if nick:
            stat["name"] = nick
        stat["actual"] += float(entry.get("actual") or 0)
        stat["expected"] += float(entry.get("expected") or 0)
        stat["count"] += 1

    rows = []
    total_actual = 0.0
    total_expected = 0.0
    for key, stat in agg.items():
        total_actual += stat["actual"]
        total_expected += stat["expected"]
        rate = ((stat["actual"] - stat["expected"]) / stat["expected"] * 100
                if stat["expected"] > 0 else None)
        rows.append({
            "qq": key,
            "name": stat["name"] or f"玩家{key}",
            "avatar": avatar_web.avatar_url(key),
            "count": stat["count"],
            "actual": round(stat["actual"], 1),
            "expected": round(stat["expected"], 1),
            "rate": round(rate, 1) if rate is not None else None,
        })
    rows.sort(key=lambda r: (-r["actual"], r["qq"]))
    percent = sorted([r for r in rows if r["rate"] is not None],
                     key=lambda r: (-r["rate"], r["qq"]))

    return {
        "ok": True,
        "code": code,
        "tier": tier,
        "country": _plugin._countries.get(code, code),
        "title": title,
        "status": status,
        "need": need,
        "progress": progress,
        "kill_line": kill_line,
        "records": len(entries),
        "players": len(agg),
        "total": {
            "actual": round(total_actual, 1),
            "expected": round(total_expected, 1),
            "rate": (round((total_actual - total_expected) / total_expected * 100, 1)
                     if total_expected > 0 else None),
            "count": len(entries),
            "players": len(agg),
        },
        "rows": rows,
        "percent": percent,
    }


def relic_research(qq: int, code: str):
    """执行一次遗物研究，返回 (错误信息, 结果)"""
    resolved = _plugin._resolve_relic_country(code or "")
    if not resolved:
        return "没找到这个国家喵", None
    player = _plugin._get_player(qq)
    before = player.get("relic_research_date")
    lines = _plugin._relic_research_core(qq, player, resolved)
    used = before != _today() and player.get("relic_research_date") == _today()
    return None, {
        "lines": lines,
        "used": used,
        "fish": player.get("fish", 0),
        "eye_stones": player.get("eye_stones", 0),
        "state": relic_info(qq),
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
