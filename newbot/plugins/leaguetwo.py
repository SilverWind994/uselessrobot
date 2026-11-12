"""立直联赛（大凤林）成绩查询。

数据来源：000.mk 页面所用接口 https://cdn.r-mj.com/api/data.php
- t=admin   赛事配置（c_name / c_round / c_s_po / r_type）
- t=team    全部队伍（t_name / t_player / t_sub）
- t=class   对阵分组（rid -> tid1..4 / round）
- t=multi_log 对局日志（num1..4 为组内累计点数，pint1..4 为单局得失点）

命令：立直联赛 / rmnl 超级|主级|次级|队员 <队伍>
兼容旧命令：slt / l1t / l2t / l2p
"""

import os
import threading
import time

import requests
from PIL import Image, ImageDraw, ImageFont

from core.command_router import CommandContext, CommandRouter
from core.message_sender import MessageSender, Target

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # newbot/
LEAGUE_DIR = os.path.join(_BASE_DIR, "assets", "leaguetwo")

API_BASE = "https://cdn.r-mj.com/api/data.php"
COMPETITIONS = {220: "超级", 221: "主级", 222: "次级"}
TIMEOUT = 20
SCORE_UNIT = 10000                       # 10000 点 = 1 分（保留小数）
RANK_POINTS = {1: 7, 2: 4, 3: 2, 4: 1}   # 单场顺位点
INTERVAL_BONUS = 1                       # 每个区间净得分最高的队伍

HELP_TEXT = (
    "立直联赛成绩指令（rmnl）\n"
    "立直联赛 超级 / 主级 / 次级 —— 查看对应级别的队伍排行\n"
    "立直联赛 队员 [超级|主级|次级] <队伍ID或队名> —— 查看该队队员排行\n"
    "队伍名支持模糊匹配，匹配到多个时会列出候选供复制\n"
    "示例: 立直联赛 主级\n"
    "示例: rmnl 队员 主级 千里山\n"
    "旧指令 slt / l1t / l2t / l2p 仍可使用"
)

_MEASURE_DRAW = ImageDraw.Draw(Image.new("RGB", (1, 1)))


# ==================== 数据抓取 ====================

def _api(t: str, cid: int, **extra):
    params = {"t": t, "cid": cid}
    params.update(extra)
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(API_BASE, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise last_error


def _fetch_multi_log(cid: int, max_round: int) -> dict:
    if max_round <= 0:
        return {}
    rounds = ",".join(str(i) for i in range(1, max_round + 1))
    return _api("multi_log", cid, r=rounds) or {}


def _signed(value: int) -> str:
    return f"{value:+d}" if value else "0"


def _max_round(admin: dict, classes) -> int:
    """轮次上限：admin 的 c_round 可能小于实际轮次，取两者较大值。"""
    try:
        value = int(admin.get("c_round") or 0)
    except (TypeError, ValueError):
        value = 0
    for item in classes or []:
        if not isinstance(item, dict):
            continue
        try:
            value = max(value, int(item.get("round") or 0))
        except (TypeError, ValueError):
            continue
    return value


def compute_standings(cid: int):
    """返回 (赛事名, 有数据的轮次列表, 队伍成绩行列表)。"""
    admin = _api("admin", cid)
    if not isinstance(admin, dict) or not admin:
        raise ValueError("赛事不存在")
    name = admin.get("c_name") or f"cid={cid}"

    seat_count = 3 if str(admin.get("r_type")) in ("2", "5") else 4

    teams = _api("team", cid) or {}
    classes = _api("class", cid) or []
    max_round = _max_round(admin, classes)
    cls = {}
    for item in classes:
        if isinstance(item, dict) and "rid" in item:
            cls[str(item["rid"])] = item

    logs = _fetch_multi_log(cid, max_round)

    # 每个 rid 是一组接力对局：10 场连续进行（5 个区间 × 2 场），
    # 上一场结束时的点数就是下一场的起点，区间以 2 场为单位。
    roster = [x for x in (admin.get("t_type") or "").splitlines() if x.strip()]
    interval_count = max(1, len(roster) // 2) if roster else 5

    stats = {}
    for rid, rows in logs.items():
        if not rows:
            continue
        cls_item = cls.get(str(rid))
        if not cls_item:
            continue
        rows = sorted(rows, key=lambda row: int(row.get("rowi") or 0))
        interval_size = max(1, len(rows) // interval_count)
        round_no = int(rows[0].get("round") or cls_item.get("round") or 0)

        # 十场结束时每个座位的最终点数
        last = rows[-1]
        seats = []
        for i in range(1, seat_count + 1):
            tid = str(cls_item.get(f"tid{i}") or "")
            if not tid:
                continue
            try:
                final = int(last.get(f"num{i}"))
            except (TypeError, ValueError):
                continue
            seats.append({"seat": i, "tid": tid, "final": final})

        # 十场结束后按最终点数排名：顺位点 7/4/2/1，最终点数 ÷ 10000（负分记 0）
        ranked = sorted(seats, key=lambda item: -item["final"])
        for pos, seat in enumerate(ranked, 1):
            tid = seat["tid"]
            rec = stats.setdefault(
                tid,
                {"tid": tid,
                 "tname": (teams.get(tid) or {}).get("t_name") or f"队伍{tid}",
                 "total": 0.0, "rounds": {}},
            )
            rank_pt = RANK_POINTS.get(pos, 0)
            point_pt = seat["final"] / SCORE_UNIT if seat["final"] > 0 else 0.0
            round_rec = rec["rounds"].setdefault(
                round_no, {"final": seat["final"], "rank": 0, "point": 0.0,
                           "pt": 0.0, "bonus": 0})
            round_rec["rank"] += rank_pt
            round_rec["point"] += point_pt
            round_rec["pt"] += rank_pt + point_pt
            rec["total"] += rank_pt + point_pt

        # 区间赏：每个区间两场净得分最高的队伍 +1（并列都加）
        interval_net = {}
        for row in rows:
            try:
                interval = int(row.get("rowi") or 0) // interval_size
            except (TypeError, ValueError):
                continue
            for seat in seats:
                try:
                    net = int(row.get(f"pint{seat['seat']}"))
                except (TypeError, ValueError):
                    continue
                key = (interval, seat["tid"])
                interval_net[key] = interval_net.get(key, 0) + net
        best = {}
        for (interval, _), net in interval_net.items():
            if interval not in best or net > best[interval]:
                best[interval] = net
        for (interval, tid), net in interval_net.items():
            if net != best[interval]:
                continue
            rec = stats.get(tid)
            if not rec:
                continue
            round_rec = rec["rounds"].setdefault(
                round_no, {"final": 0, "rank": 0, "point": 0.0,
                           "pt": 0.0, "bonus": 0})
            round_rec["bonus"] += INTERVAL_BONUS
            round_rec["pt"] += INTERVAL_BONUS
            rec["total"] += INTERVAL_BONUS

    for rec in stats.values():
        rec["total"] = round(rec["total"], 2)

    rows = sorted(stats.values(), key=lambda rec: (-rec["total"], rec["tname"]))
    rank = 0
    last_total = None
    for index, rec in enumerate(rows, 1):
        if rec["total"] != last_total:
            rank = index
            last_total = rec["total"]
        rec["rank"] = rank

    rounds = sorted({rd for rec in rows for rd in rec["rounds"] if rd > 0})
    return name, rounds, rows


_LEVEL_WORDS = {
    "超级": 220, "slt": 220, "220": 220,
    "主级": 221, "l1t": 221, "221": 221,
    "次级": 222, "l2t": 222, "222": 222,
}


def split_team_query(args: str):
    """解析「[级别] 队伍关键字」，返回 (级别cid 或 None, 关键字)。"""
    parts = (args or "").strip().split(None, 1)
    if not parts:
        return None, ""
    cid = _LEVEL_WORDS.get(parts[0].lower())
    if cid is not None:
        return cid, parts[1].strip() if len(parts) > 1 else ""
    return None, (args or "").strip()


def find_teams(keyword: str, cid=None):
    """在所有级别中按队名关键字或 tid 查找，返回 [(cid, tid, tname), ...]。

    有精确匹配（完整队名或队伍ID）时只返回精确匹配，避免复制队名后仍被模糊命中。
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []
    order = (cid,) if cid else (220, 221, 222)
    found = []
    for level in order:
        teams = _api("team", level) or {}
        for tid, team in teams.items():
            if not isinstance(team, dict):
                continue
            tname = team.get("t_name") or str(tid)
            if str(tid) == keyword or keyword in tname:
                found.append((level, str(tid), tname))
    exact = [item for item in found if item[1] == keyword or item[2] == keyword]
    return exact or found


def compute_players(cid: int, tid: str):
    """返回 (队名, 队员统计行列表)。"""
    admin = _api("admin", cid) or {}
    teams = _api("team", cid) or {}
    classes = _api("class", cid) or []
    max_round = _max_round(admin, classes)
    team = teams.get(str(tid))
    if not team:
        raise ValueError("队伍不存在")

    players = []
    for field in ("t_player", "t_sub"):
        for name in (team.get(field) or "").splitlines():
            name = name.strip()
            if name and name not in players:
                players.append(name)

    stats = {
        name: {"name": name, "total": 0, "cnt1": 0, "cnt2": 0, "cnt3": 0, "cnt4": 0}
        for name in players
    }
    logs = _fetch_multi_log(cid, max_round)
    for rows in logs.values():
        for row in rows:
            entries = []
            for i in range(1, 5):
                player_name = row.get(f"name{i}")
                pint = row.get(f"pint{i}")
                if player_name is None or pint is None:
                    continue
                entries.append((player_name, int(pint)))
            entries.sort(key=lambda item: item[1], reverse=True)
            for pos, (player_name, pint) in enumerate(entries, 1):
                rec = stats.get(player_name)
                if rec is None:
                    continue
                rec["total"] += pint
                rec[f"cnt{min(pos, 4)}"] += 1

    rows = sorted(stats.values(), key=lambda rec: (-rec["total"], rec["name"]))
    return team.get("t_name") or str(tid), rows


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
        line = [rec["rank"], rec["tname"], f"{rec['total']:.2f}"]
        for round_no in rounds:
            item = rec["rounds"].get(round_no)
            if not item:
                line.append("")
                continue
            cell = str(item["final"])
            if item["bonus"]:
                cell += f" 区间+{item['bonus']}"
            line.append(cell)
        table_rows.append(line)

    return render_table(f"{name} 队伍排行", headers, table_rows, path)


def render_players(team_name: str, rows, path: str) -> str:
    headers = ["队员", "总分", "1位次数", "2位次数", "3位次数", "4位次数"]
    table_rows = [
        [rec["name"], _signed(rec["total"]), rec["cnt1"], rec["cnt2"],
         rec["cnt3"], rec["cnt4"]]
        for rec in rows
    ]
    return render_table(f"{team_name} 队员统计", headers, table_rows, path)


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

        if sub in ("超级", "220") or sub_lower == "slt":
            self._team_standings(ctx, 220)
        elif sub in ("主级", "221") or sub_lower == "l1t":
            self._team_standings(ctx, 221)
        elif sub in ("次级", "222") or sub_lower == "l2t":
            self._team_standings(ctx, 222)
        elif sub in ("队员", "队员排行") or sub_lower in ("player", "p"):
            if not rest:
                self._sender.reply(
                    ctx, "用法: 立直联赛 队员 [超级|主级|次级] <队伍ID或队名>")
                return
            self._player_standings(ctx, rest)
        else:
            self._sender.reply(ctx, HELP_TEXT)

    def cmd_super(self, ctx: CommandContext) -> None:
        self._team_standings(ctx, 220)

    def cmd_main(self, ctx: CommandContext) -> None:
        self._team_standings(ctx, 221)

    def cmd_sub(self, ctx: CommandContext) -> None:
        self._team_standings(ctx, 222)

    def cmd_player(self, ctx: CommandContext) -> None:
        keyword = ctx.get_args()
        if not keyword:
            self._sender.reply(
                ctx, "用法: l2p [超级|主级|次级] <队伍ID或队名>")
            return
        self._player_standings(ctx, keyword)

    def _team_standings(self, ctx: CommandContext, cid: int) -> None:
        target = Target.from_data(ctx.raw_data)
        self._sender.reply(ctx, "正在获取联赛成绩…")

        def work():
            try:
                name, rounds, rows = compute_standings(cid)
                if not rows or not rounds:
                    self._sender.send_text(target, "该赛事暂无成绩数据")
                    return
                path = os.path.join(
                    LEAGUE_DIR, f"team_{cid}_{int(time.time() * 1000)}.png")
                render_standings(name, rounds, rows, path)
                self._sender.send_image(target, path)
            except Exception as exc:
                self._sender.send_text(target, f"获取联赛成绩失败：{exc}")

        threading.Thread(target=work, daemon=True).start()

    def _player_standings(self, ctx: CommandContext, args: str) -> None:
        target = Target.from_data(ctx.raw_data)
        cid, keyword = split_team_query(args)
        if not keyword:
            self._sender.reply(ctx, "请提供队伍ID或队名")
            return
        self._sender.reply(ctx, "正在获取队员成绩…")

        def work():
            try:
                found = find_teams(keyword, cid)
                if not found:
                    self._sender.send_text(target, f"没有找到队伍：{keyword}")
                    return
                if len(found) > 1:
                    lines = ["找到多个队伍，请复制完整队名或队伍ID重新查询："]
                    for level, tid, tname in found:
                        lines.append(
                            f"{COMPETITIONS.get(level, level)} {tname} (ID: {tid})")
                    lines.append("示例: 立直联赛 队员 <队伍ID>")
                    self._sender.send_text(target, "\n".join(lines))
                    return
                cid_found, tid, _ = found[0]
                team_name, rows = compute_players(cid_found, tid)
                if not rows:
                    self._sender.send_text(target, "该队伍暂无队员成绩数据")
                    return
                path = os.path.join(
                    LEAGUE_DIR, f"player_{tid}_{int(time.time() * 1000)}.png")
                render_players(team_name, rows, path)
                self._sender.send_image(target, path)
            except Exception as exc:
                self._sender.send_text(target, f"获取队员成绩失败：{exc}")

        threading.Thread(target=work, daemon=True).start()
