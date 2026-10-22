"""一次性把旧 UCML（PostgreSQL）里的赛季数据导入网页版存档。

旧系统（archive/mybot/ucml.py）的数据存在本地 PostgreSQL 的 ucml 库里，
新赛季会直接删表，所以只能在旧库还保留着上个赛季数据时执行一次。

用法（在仓库根目录）：
    py -3 web/import_ucml_legacy.py --dry-run
    py -3 web/import_ucml_legacy.py

连接参数优先读环境变量：
    UCML_PG_HOST / UCML_PG_PORT / UCML_PG_DB / UCML_PG_USER / UCML_PG_PASSWORD
也可以用 --host/--port/--db/--user/--password 覆盖。

默认把导入的数据存为第 1 赛季，然后把当前赛季号推到第 2 赛季；
想改用 --season 指定。导入后旧赛季会出现在网页端顶部的赛季切换里。
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ucml_web  # noqa: E402


def _connect(args):
    try:
        import psycopg2
    except ImportError:
        raise SystemExit("缺少 psycopg2，请先执行：py -3 -m pip install psycopg2-binary")
    return psycopg2.connect(
        database=args.db,
        user=args.user,
        password=args.password,
        host=args.host,
        port=args.port,
        connect_timeout=5,
    )


def _fetch(cursor, sql):
    """单表查询失败时返回空列表（旧库可能缺某张表）"""
    try:
        cursor.execute(sql)
        return cursor.fetchall()
    except Exception as exc:  # noqa: BLE001
        cursor.connection.rollback()
        print(f"[跳过] 查询失败（{exc}）：{sql.strip()[:60]}")
        return []


def _read_legacy(args):
    conn = _connect(args)
    try:
        cur = conn.cursor()
        team_rows = _fetch(cur, "SELECT TEAMNAME,COLORR,COLORG,COLORB FROM TEAM ORDER BY TEAMNAME;")
        player_rows = _fetch(cur, "SELECT PLAYERNAME,TEAMNAME FROM PLAYER ORDER BY TEAMNAME,PLAYERNAME;")
        match_rows = _fetch(cur, """SELECT ID,TYPE,
            PLAYERNAMEFIRST,TEAMNAMEFIRST,SCOREFIRST,
            PLAYERNAMESECOND,TEAMNAMESECOND,SCORESECOND,
            PLAYERNAMETHIRD,TEAMNAMETHIRD,SCORETHIRD,
            PLAYERNAMEFORTH,TEAMNAMEFORTH,SCOREFORTH
            FROM MATCHRESULT ORDER BY ID ASC;""")
        stage_rows = _fetch(cur, "SELECT STAGE FROM MATCHMESSAGE;")
        return team_rows, player_rows, match_rows, stage_rows
    finally:
        conn.close()


def _build_season(args, team_rows, player_rows, match_rows, legacy_stage=4):
    teams = []
    for name, r, g, b in team_rows:
        teams.append({"name": str(name), "r": int(r), "g": int(g), "b": int(b)})

    players = [{"name": str(name), "team": str(team)} for name, team in player_rows]

    matches = []
    for row in match_rows:
        entries = []
        for i in range(4):
            base = 2 + i * 3
            entries.append({
                "rank": i + 1,
                "player": str(row[base] or ""),
                "team": str(row[base + 1] or ""),
                "raw": None,          # 旧库只存了换算后的 pt，没有原始点数
                "pt": round(float(row[base + 2] or 0), 1),
            })
        matches.append({
            "id": int(row[0]),
            "stage": int(row[1]),
            "time": 0.0,
            "entries": entries,
        })

    stage = int(legacy_stage)
    if stage not in (1, 2, 3, 4):
        stage = 4
    snapshot = {
        "season": int(args.season),
        "stage": stage,
        "teams": teams,
        "players": players,
        "matches": matches,
        "inherit": {},
    }

    # 旧库的阶段表在新赛季开始时清空，这里按比赛记录重新推导晋级继承分
    if stage >= 2:
        rows1 = ucml_web._team_standings(snapshot, 1)
        top6 = rows1[:6]
        snapshot["inherit"]["2"] = {
            "teams": {r["name"]: round(r["score"] / 2.0 + 0.01, 1) for r in top6},
            "players": [p["name"] for p in players if p["team"] in {r["name"] for r in top6}],
        }
    if stage >= 3:
        rows2 = ucml_web._team_standings(snapshot, 2)
        top4 = rows2[:4]
        snapshot["inherit"]["3"] = {
            "teams": {r["name"]: round(r["score"] / 2.0 + 0.01, 1) for r in top4},
            "players": [p["name"] for p in players if p["team"] in {r["name"] for r in top4}],
        }
    return snapshot


def _merge_into(data, snapshot, season, force):
    """把 snapshot 写进 data 的归档，并把当前赛季号推到下一季"""
    if data.get("matches") and not force:
        return "当前存档里已经有比赛记录；确认要覆盖请加 --force"

    season = int(season)
    snapshot["season"] = season
    seasons = list(data.get("seasons", []))
    if data.get("matches"):
        seasons.append({
            "season": int(data.get("season", 1)),
            "stage": 4,
            "teams": data["teams"],
            "players": data["players"],
            "matches": data["matches"],
            "inherit": data["inherit"],
        })
    seasons = [s for s in seasons if int(s.get("season", 0)) != int(season)]
    seasons.append(snapshot)
    seasons.sort(key=lambda s: int(s.get("season", 0)))

    current = int(data.get("season", 1))
    if current > int(season):
        # 当前赛季比导入赛季新，只写归档，不动正在进行的赛季
        data["seasons"] = seasons
        return None

    fresh = ucml_web._blank()
    fresh["season"] = max(current, int(season) + 1)
    fresh["seasons"] = seasons
    data.clear()
    data.update(fresh)
    return None


def main():
    parser = argparse.ArgumentParser(description="导入旧 UCML 赛季数据到网页版存档")
    parser.add_argument("--host", default=os.environ.get("UCML_PG_HOST", "127.0.0.1"))
    parser.add_argument("--port", default=os.environ.get("UCML_PG_PORT", "5432"))
    parser.add_argument("--db", default=os.environ.get("UCML_PG_DB", "ucml"))
    parser.add_argument("--user", default=os.environ.get("UCML_PG_USER", "postgres"))
    parser.add_argument("--password", default=os.environ.get("UCML_PG_PASSWORD", ""))
    parser.add_argument("--season", type=int, default=1, help="导入数据保存为第几赛季")
    parser.add_argument("--force", action="store_true", help="当前存档已有比赛记录时仍然导入")
    parser.add_argument("--dry-run", action="store_true", help="只打印导入结果，不写入存档")
    args = parser.parse_args()

    team_rows, player_rows, match_rows, stage_rows = _read_legacy(args)
    if not team_rows and not match_rows:
        raise SystemExit("旧库里没有读到队伍或比赛数据，请确认数据库和连接参数")

    snapshot = _build_season(args, team_rows, player_rows, match_rows,
                             stage_rows[0][0] if stage_rows else 4)
    print(f"旧库当前阶段：{stage_rows[0][0] if stage_rows else '未知'}")
    print(f"读取到 {len(snapshot['teams'])} 支队伍、{len(snapshot['players'])} 位选手、"
          f"{len(snapshot['matches'])} 场比赛")
    for stage in (1, 2, 3):
        rows = ucml_web._team_standings(snapshot, stage)
        if rows:
            print(f"  阶段 {stage}：" + "、".join(f"{r['name']} {r['score']:.1f}" for r in rows[:6]))

    data = ucml_web._load()
    err = _merge_into(data, snapshot, args.season, args.force)
    if err:
        raise SystemExit(err)

    if args.dry_run:
        print(f"[dry-run] 将第 {args.season} 赛季写入存档，当前赛季为第 {data['season']} 赛季，"
              f"历史赛季共 {len(data['seasons'])} 个，未写入文件")
        return

    ucml_web._save(data)
    print(f"导入完成：第 {args.season} 赛季已归档，当前赛季为第 {data['season']} 赛季")
    print(f"存档位置：{ucml_web.DATA_PATH}")


if __name__ == "__main__":
    main()
