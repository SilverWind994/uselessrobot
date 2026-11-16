"""立直联赛（Arena 赛事平台）成绩查询。

数据来源：https://arena.pesiu.org 的公开接口
- GET /api/contests                          赛事列表（按名称区分超级/主级/次级）
- GET /api/contests/{cid}                    赛事信息
- GET /api/contests/{cid}/phases             阶段
- GET /api/contests/{cid}/participants       参赛队伍与队员
- GET /api/contests/{cid}/score-adjustments  罚分/加分
- GET /api/phases/{pid}/stages               阶段下的小局配置（slots / startingPoints）
- GET /api/stages/{sid}/matches              每桌对局（games 内含每个半庄的分数与顺位）

队伍计分沿用赛事平台的计分脚本（scheme「ti」）：
- 一桌 4 队接力 10 个半庄，每 2 个半庄为一个位置
- 最终接力分 ÷ 10000 + 名次分[7,4,2,0] + 区间 TOP×1
- 负分：名次分照发，再额外 -2
- 区间 TOP：单个位置接力分增量最高者 +1；两队并列各 +0.5；三队及以上不记

命令：立直联赛 / rmnl 超级|主级|次级|队员 <队伍>
兼容旧命令：slt / l1t / l2t / l2p
"""

import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image, ImageDraw, ImageFont

from core.command_router import CommandContext, CommandRouter
from core.message_sender import MessageSender, Target

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
LEAGUE_DIR = os.path.join(_BASE_DIR, "assets", "leaguetwo")

API_BASE = "https://arena.pesiu.org/api"
TIMEOUT = 150
RANK_POINTS = [7, 4, 2, 0]   # 一桌四队按最终接力分排名的名次分
NEGATIVE_PENALTY = -2        # 最终接力分为负时额外扣分
LEVELS = ("超级", "主级", "次级")
CONTEST_KEYWORD = "全国立直麻将网络联赛"

HELP_TEXT = (
    "立直联赛成绩指令（rmnl）\n"
    "立直联赛 超级 / 主级 / 次级 —— 查看对应级别的队伍排行\n"
    "立直联赛 队员 [超级|主级|次级] <队伍名> —— 查看该队队员排行\n"
    "队员排行按每局平均得失点排序（出场局数不同也能横向比较）\n"
    "队伍名支持模糊匹配，匹配到多个时会列出候选供复制\n"
    "数据来源：arena.pesiu.org\n"
    "示例: 立直联赛 主级\n"
    "示例: rmnl 队员 主级 东三国\n"
    "旧指令 slt / l1t / l2t / l2p 仍可使用"
)

_MEASURE_DRAW = ImageDraw.Draw(Image.new("RGB", (1, 1)))

# 接口较慢，结果缓存在内存里，避免同一条指令重复等待
_CACHE = {}
_CACHE_LOCK = threading.Lock()


# ==================== 数据抓取 ====================

def _api(path: str, **params):
    """GET 请求，失败重试两次；超时后仍然抛错由调用方提示。"""
    url = API_BASE + path
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 + attempt * 2)
    raise last_error


def _cached(key, ttl, factory):
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = factory()
    with _CACHE_LOCK:
        _CACHE[key] = (now + ttl, value)
    return value


def resolve_contest_id(level: str) -> str:
    """按级别从赛事列表里找最新的全国立直麻将网络联赛。"""
    def load():
        data = _api("/contests", limit=1000)
        return data.get("items") or []

    items = _cached("contests", 600, load)
    matched = [
        c for c in items
        if isinstance(c, dict) and (c.get("name") or "").rstrip().endswith("-" + level)
    ]
    if not matched:
        matched = [
            c for c in items
            if isinstance(c, dict) and CONTEST_KEYWORD in (c.get("name") or "")
            and level in (c.get("name") or "")
        ]
    if not matched:
        raise ValueError(f"没有找到「{level}」赛事")
    matched.sort(key=lambda c: c.get("createdAt") or "", reverse=True)
    return str(matched[0]["id"])


def load_bundle(level: str) -> dict:
    """一次抓齐计分需要的数据：赛事、队伍、阶段小局、对局、罚分。"""
    cid = resolve_contest_id(level)

    def load():
        with ThreadPoolExecutor(max_workers=6) as pool:
            f_contest = pool.submit(_api, f"/contests/{cid}")
            f_phases = pool.submit(_api, f"/contests/{cid}/phases", limit=1000)
            f_parts = pool.submit(_api, f"/contests/{cid}/participants", limit=1000)
            f_adj = pool.submit(_api, f"/contests/{cid}/score-adjustments", limit=1000)
            f_views = pool.submit(_api, f"/contests/{cid}/score-views", limit=1000)
            contest = f_contest.result() or {}
            phases = (f_phases.result() or {}).get("items") or []
            participants = (f_parts.result() or {}).get("items") or []
            adjustments = (f_adj.result() or {}).get("items") or []
            views = (f_views.result() or {}).get("items") or []

        phase_ids = [p["id"] for p in phases if p.get("id")]
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pid: pool.submit(_api, f"/phases/{pid}/stages", limit=1000)
                       for pid in phase_ids}
            stages = []
            for pid, future in futures.items():
                try:
                    stages.extend((future.result() or {}).get("items") or [])
                except Exception:
                    # 小局配置拿不到时按默认每 2 个半庄一个区间计分
                    continue

        stage_ids = [s["id"] for s in stages if s.get("id")]
        if not stage_ids:
            # 小局列表拿不到时，退回到排行榜配置里登记的小局
            for view in views:
                scope = view.get("scope") or {}
                for sid in scope.get("stageIds") or []:
                    if sid not in stage_ids:
                        stage_ids.append(sid)
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {sid: pool.submit(_api, f"/stages/{sid}/matches", limit=1000)
                       for sid in stage_ids}
            matches = []
            for sid, future in futures.items():
                matches.extend((future.result() or {}).get("items") or [])

        return {
            "contest": contest,
            "participants": participants,
            "adjustments": adjustments,
            "stages": stages,
            "matches": matches,
        }

    return _cached(f"bundle:{cid}", 300, load)


def _signed(value: int) -> str:
    return f"{value:+d}" if value else "0"


def _entry_of(last_game: dict, pid: str):
    for player in last_game.get("players") or []:
        if player.get("participantId") == pid:
            return player
    return None


def _position_groups(games, slots, games_per_position: int = 2):
    """把一桌的 10 个半庄按位置名分组（slots 与 games 一一对应）。"""
    positions = []
    by_name = {}
    for index, game in enumerate(games):
        if slots:
            number = game.get("number") or index + 1
            slot_index = number - 1 if len(slots) >= len(games) else (number - 1) // games_per_position
            name = slots[slot_index] if slot_index < len(slots) else f"区间{len(positions) + 1}"
        else:
            name = f"区间{index // games_per_position + 1}"
        if name not in by_name:
            by_name[name] = []
            positions.append(by_name[name])
        by_name[name].append(game)
    return positions


def compute_standings(level: str):
    """返回 (赛事名, 有数据的轮次列表, 队伍成绩行列表)。"""
    bundle = load_bundle(level)
    contest = bundle["contest"]
    name = contest.get("name") or level
    participants = bundle["participants"]
    stages = bundle["stages"]
    matches = bundle["matches"]
    adjustments = bundle["adjustments"]

    stage_by_id = {s["id"]: s for s in (stages or []) if isinstance(s, dict)}
    scores = {}
    for part in participants:
        scores[part["id"]] = {
            "pid": part["id"], "name": part.get("name") or part["id"],
            "total": 0.0, "rounds": {}, "tops": 0.0, "games": 0,
            "placement": 0, "raw": 0, "best": 0,
        }

    for match in matches:
        games = sorted((match.get("games") or []), key=lambda g: g.get("number") or 0)
        if not games:
            continue
        pids = [p.get("participantId") for p in (games[0].get("players") or [])]
        stage = stage_by_id.get(match.get("stageId"), {})
        slots = stage.get("slots") or []
        start_points = stage.get("startingPoints") or 100000

        stats = {pid: {"tops": 0.0, "games": 0, "placement": 0, "best": -10 ** 9}
                 for pid in pids if pid}
        start_scores = {pid: start_points for pid in stats}

        for position in _position_groups(games, slots):
            position_start = dict(start_scores)
            position_end = dict(start_scores)
            played = set()
            for game in position:
                scored = [p for p in (game.get("players") or []) if p.get("score") is not None]
                for player in scored:
                    pid = player.get("participantId")
                    if pid not in stats:
                        continue
                    position_end[pid] = player["score"]
                    played.add(pid)
                    stat = stats[pid]
                    stat["games"] += 1
                    rank = player.get("rank")
                    if not rank:
                        rank = 1 + sum(1 for q in scored if q["score"] > player["score"])
                    stat["placement"] += rank
                    stat["best"] = max(stat["best"], player["score"])
            gains = {pid: position_end[pid] - position_start[pid] for pid in played}
            if gains:
                max_gain = max(gains.values())
                winners = [pid for pid, gain in gains.items() if gain == max_gain]
                if len(winners) == 1:
                    stats[winners[0]]["tops"] += 1
                elif len(winners) == 2:
                    for pid in winners:
                        stats[pid]["tops"] += 0.5
            start_scores = position_end

        last_game = games[-1]
        finals = []
        for pid in stats:
            player = _entry_of(last_game, pid)
            num = player["score"] if player else 0
            stat = stats[pid]
            average = stat["placement"] / stat["games"] if stat["games"] else 0
            finals.append((pid, num, stat["tops"], average, stat["best"]))
        finals.sort(key=lambda item: (-item[1], -item[2], item[3], -item[4], item[0]))

        round_no = match.get("roundNumber") or 0
        for index, (pid, num, tops, average, best) in enumerate(finals):
            record = scores.get(pid)
            if record is None:
                continue
            base_score = math.floor(num / 100) / 100
            rank_point = (RANK_POINTS[index] if index < len(RANK_POINTS) else 0)
            rank_point += NEGATIVE_PENALTY if num < 0 else 0
            point = base_score + rank_point + tops
            record["total"] += point
            record["tops"] += tops
            record["games"] += stats[pid]["games"]
            record["placement"] += stats[pid]["placement"]
            record["raw"] += num
            record["best"] = max(record["best"], best)
            round_rec = record["rounds"].setdefault(
                round_no, {"final": 0, "tops": 0.0, "point": 0.0})
            round_rec["final"] = num
            round_rec["tops"] = tops
            round_rec["point"] = point

    # 罚分/加分：按 participantId 或队名匹配
    name_to_pid = {rec["name"]: pid for pid, rec in scores.items()}
    for extra in adjustments or []:
        if not isinstance(extra, dict):
            continue
        pid = extra.get("participantId") or name_to_pid.get(extra.get("participantName") or "")
        score = extra.get("score")
        if pid in scores and isinstance(score, (int, float)):
            scores[pid]["total"] += score

    rows = [rec for rec in scores.values() if rec["rounds"]]
    rows.sort(key=lambda rec: (
        -rec["total"], -rec["tops"],
        (rec["placement"] / rec["games"]) if rec["games"] else 0,
        -rec["raw"], -rec["best"], rec["name"]))

    rank = 0
    last_total = None
    for index, rec in enumerate(rows, 1):
        if rec["total"] != last_total:
            rank = index
            last_total = rec["total"]
        rec["rank"] = rank
        rec["total"] = round(rec["total"], 2)

    rounds = sorted({rn for rec in rows for rn in rec["rounds"] if rn})
    return name, rounds, rows


def compute_players(level: str, pid: str):
    """返回 (队名, 队员统计行列表)。

    队员成绩按每个半庄的得失点统计；出场局数不同，因此按「每局平均得失点」排名。
    """
    bundle = load_bundle(level)
    participants = bundle["participants"]
    stages = bundle["stages"]
    matches = bundle["matches"]

    team = next((p for p in participants if p.get("id") == pid), None)
    if not team:
        raise ValueError("队伍不存在")

    stage_by_id = {s["id"]: s for s in (stages or []) if isinstance(s, dict)}
    stats = {}

    for match in matches:
        games = sorted((match.get("games") or []), key=lambda g: g.get("number") or 0)
        if not games:
            continue
        stage = stage_by_id.get(match.get("stageId"), {})
        start_points = stage.get("startingPoints") or 100000
        previous = {p.get("participantId"): start_points
                    for p in (games[0].get("players") or [])}
        for game in games:
            scored = [p for p in (game.get("players") or []) if p.get("score") is not None]
            # 本局得失点：用于个人统计的顺位（接力赛的累计分排名无法反映单局发挥）
            deltas = {}
            for player in scored:
                key = player.get("participantId")
                deltas[key] = player["score"] - previous.get(key, start_points)
            previous.update({p.get("participantId"): p["score"] for p in scored})
            if pid not in deltas:
                continue
            delta = deltas[pid]
            player = next(p for p in scored if p.get("participantId") == pid)
            nickname = (player.get("snapshot") or {}).get("nickname") or "未知"
            rec = stats.setdefault(
                nickname, {"name": nickname, "total": 0, "games": 0,
                           "cnt1": 0, "cnt2": 0, "cnt3": 0, "cnt4": 0})
            rec["total"] += delta
            rec["games"] += 1
            rank = 1 + sum(1 for value in deltas.values() if value > delta)
            rec[f"cnt{min(max(rank, 1), 4)}"] += 1

    rows = sorted(stats.values(), key=lambda rec: (
        -(rec["total"] / rec["games"] if rec["games"] else 0),
        -rec["total"], rec["name"]))
    return team.get("name") or pid, rows


_LEVEL_WORDS = {
    "超级": "超级", "slt": "超级", "220": "超级",
    "主级": "主级", "l1t": "主级", "221": "主级",
    "次级": "次级", "l2t": "次级", "222": "次级",
}


def split_team_query(args: str):
    """解析「[级别] 队伍关键字」，返回 (级别 或 None, 关键字)。"""
    parts = (args or "").strip().split(None, 1)
    if not parts:
        return None, ""
    level = _LEVEL_WORDS.get(parts[0].lower())
    if level is not None:
        return level, parts[1].strip() if len(parts) > 1 else ""
    return None, (args or "").strip()


def find_teams(keyword: str, level=None):
    """按队名关键字或队伍ID查找，返回 [(级别, 队伍ID, 队名), ...]。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    order = (level,) if level else LEVELS
    bundles = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {name: pool.submit(load_bundle, name) for name in order}
        for name, future in futures.items():
            try:
                bundles[name] = future.result()
            except Exception:
                continue
    found = []
    for name in order:
        bundle = bundles.get(name)
        if bundle is None:
            continue
        for part in bundle["participants"]:
            pid = str(part.get("id"))
            pname = part.get("name") or pid
            if pid == keyword or keyword in pname:
                found.append((name, pid, pname))
    exact = [item for item in found if item[1] == keyword or item[2] == keyword]
    return exact or found


# ==================== 图片渲染 ====================

def _font(size: int):
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                 r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text_size(text, font):
    box = _MEASURE_DRAW.textbbox((0, 0), str(text), font=font)
    return box[2] - box[0], box[3] - box[1]


def _draw_center(draw, box, text, font, fill):
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), str(text), font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = x0 + (x1 - x0 - tw) / 2 - bbox[0]
    y = y0 + (y1 - y0 - th) / 2 - bbox[1]
    draw.text((x, y), str(text), font=font, fill=fill)


def render_table(title: str, headers, rows, path: str) -> str:
    """把二维文本表格画成 PNG。"""
    pad = 12
    title_font = _font(28)
    header_font = _font(20)
    body_font = _font(19)
    title_h, header_h, row_h = 70, 48, 44

    widths = []
    for col, header in enumerate(headers):
        width = _text_size(header, header_font)[0]
        for row in rows:
            width = max(width, _text_size(row[col], body_font)[0])
        widths.append(max(width + pad * 2, 70))

    table_w = sum(widths)
    width = max(table_w + 2, _text_size(title, title_font)[0] + pad * 2)
    height = title_h + header_h + row_h * len(rows) + 2
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width - 1, height - 1), outline=(180, 180, 180))

    _draw_center(draw, (0, 0, width, title_h), title, title_font, (34, 34, 34))

    y = title_h
    x = 1
    for col, header in enumerate(headers):
        draw.rectangle((x, y, x + widths[col], y + header_h), fill=(76, 175, 80))
        _draw_center(draw, (x, y, x + widths[col], y + header_h), header,
                     header_font, "white")
        x += widths[col]
    y += header_h

    for index, row in enumerate(rows):
        fill = (245, 245, 245) if index % 2 else "white"
        x = 1
        for col, value in enumerate(row):
            draw.rectangle((x, y, x + widths[col], y + row_h), fill=fill,
                           outline=(210, 210, 210))
            _draw_center(draw, (x, y, x + widths[col], y + row_h), value,
                         body_font, (30, 30, 30))
            x += widths[col]
        y += row_h

    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    image.save(path, "PNG")
    return path


def render_standings(name: str, rounds, rows, path: str) -> str:
    headers = ["排名", "队伍名称", "总分"]
    for round_no in rounds:
        headers.append(f"第{round_no}轮得点")

    table_rows = []
    for rec in rows:
        line = [rec["rank"], rec["name"], f"{rec['total']:.2f}"]
        for round_no in rounds:
            item = rec["rounds"].get(round_no)
            if not item:
                line.append("")
                continue
            cell = str(item["final"])
            if item["tops"]:
                cell += f" 区间+{item['tops']:g}"
            line.append(cell)
        table_rows.append(line)

    return render_table(f"{name} 队伍排行", headers, table_rows, path)


def render_players(team_name: str, rows, path: str) -> str:
    headers = ["排名", "队员", "得分", "局数", "平均", "1位", "2位", "3位", "4位"]
    table_rows = []
    for index, rec in enumerate(rows, 1):
        games = rec.get("games") or 0
        average = rec["total"] / games if games else 0
        table_rows.append([
            index, rec["name"], _signed(rec["total"]), games,
            (f"{average:+.1f}" if average else "0"),
            rec["cnt1"], rec["cnt2"], rec["cnt3"], rec["cnt4"],
        ])
    return render_table(
        f"{team_name} 队员统计（按每局平均得分排名）", headers, table_rows, path)


# ==================== 插件 ====================

class LeagueTwoPlugin:
    def __init__(self, sender: MessageSender):
        self._sender = sender

    def register(self, router: CommandRouter) -> None:
        router.register(
            ["立直联赛", "rmnl", ".rmnl", "/rmnl"],
            self.cmd_entry,
            description="立直联赛成绩（子命令：超级/主级/次级/队员 <队伍>）"
        )
        router.register(["slt", ".slt", "/slt"], self.cmd_super,
                        description="立直联赛·超级队伍排行")
        router.register(["l1t", ".l1t", "/l1t"], self.cmd_main,
                        description="立直联赛·主级队伍排行")
        router.register(["l2t", ".l2t", "/l2t"], self.cmd_sub,
                        description="立直联赛·次级队伍排行")
        router.register(["l2p", ".l2p", "/l2p"], self.cmd_player,
                        description="立直联赛·队员排行 (l2p <队伍ID或队名>)")

    def cmd_entry(self, ctx: CommandContext) -> None:
        args = ctx.get_args()
        parts = args.split(None, 1)
        sub = parts[0] if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""
        sub_lower = sub.lower()

        if not sub or sub in ("帮助", "help", "?"):
            self._sender.reply(ctx, HELP_TEXT)
            return

        level = _LEVEL_WORDS.get(sub_lower) or _LEVEL_WORDS.get(sub)
        if level and not rest:
            self._team_standings(ctx, level)
        elif sub in ("队员", "队员排行") or sub_lower in ("player", "p"):
            if not rest:
                self._sender.reply(
                    ctx, "用法: 立直联赛 队员 [超级|主级|次级] <队伍ID或队名>")
                return
            self._player_standings(ctx, rest)
        else:
            self._sender.reply(ctx, HELP_TEXT)

    def cmd_super(self, ctx: CommandContext) -> None:
        self._team_standings(ctx, "超级")

    def cmd_main(self, ctx: CommandContext) -> None:
        self._team_standings(ctx, "主级")

    def cmd_sub(self, ctx: CommandContext) -> None:
        self._team_standings(ctx, "次级")

    def cmd_player(self, ctx: CommandContext) -> None:
        keyword = ctx.get_args()
        if not keyword:
            self._sender.reply(
                ctx, "用法: l2p [超级|主级|次级] <队伍ID或队名>")
            return
        self._player_standings(ctx, keyword)

    def _team_standings(self, ctx: CommandContext, level: str) -> None:
        target = Target.from_data(ctx.raw_data)
        self._sender.reply(ctx, "正在获取联赛成绩…")

        def work():
            try:
                name, rounds, rows = compute_standings(level)
                if not rows or not rounds:
                    self._sender.send_text(target, "该赛事暂无成绩数据")
                    return
                path = os.path.join(
                    LEAGUE_DIR, f"team_{level}_{int(time.time() * 1000)}.png")
                render_standings(name, rounds, rows, path)
                self._sender.send_image(target, path)
            except Exception as exc:
                self._sender.send_text(target, f"获取联赛成绩失败：{exc}")

        threading.Thread(target=work, daemon=True).start()

    def _player_standings(self, ctx: CommandContext, args: str) -> None:
        target = Target.from_data(ctx.raw_data)
        level, keyword = split_team_query(args)
        if not keyword:
            self._sender.reply(ctx, "请提供队伍ID或队名")
            return
        self._sender.reply(ctx, "正在获取队员成绩…")

        def work():
            try:
                found = find_teams(keyword, level)
                if not found:
                    self._sender.send_text(target, f"没有找到队伍：{keyword}")
                    return
                if len(found) > 1:
                    lines = ["找到多个队伍，请复制完整队名或队伍ID重新查询："]
                    for found_level, pid, pname in found:
                        lines.append(f"{found_level} {pname} (ID: {pid})")
                    lines.append("示例: 立直联赛 队员 <队伍ID>")
                    self._sender.send_text(target, "\n".join(lines))
                    return
                found_level, pid, name = found[0]
                team_name, rows = compute_players(found_level, pid)
                if not rows:
                    self._sender.send_text(target, "该队伍暂无队员成绩数据")
                    return
                path = os.path.join(
                    LEAGUE_DIR, f"player_{pid}_{int(time.time() * 1000)}.png")
                render_players(team_name, rows, path)
                self._sender.send_image(target, path)
            except Exception as exc:
                self._sender.send_text(target, f"获取队员成绩失败：{exc}")

        threading.Thread(target=work, daemon=True).start()
