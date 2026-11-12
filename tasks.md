# 任务清单：大凤林联赛成绩（l2t / l1t / slt / l2p）

> 依赖规格：`spec.md`。逐项完成后立即更新状态。

## T1 新增 `newbot/plugins/leaguetwo.py`（数据层）

- [x] 常量：`API_BASE="https://cdn.r-mj.com/api/data.php"`、`COMPETITIONS={220:"超级",221:"主级",222:"次级"}`、`TIMEOUT=20`。
- [x] `_api(t, cid, **extra)`：`requests.get(..., timeout=TIMEOUT)`，`raise_for_status()`，返回 `r.json()`（含 3 次重试，规避 CDN 偶发 522）。
- [x] `_fetch_admin(cid)` → dict；`_fetch_teams(cid)` → dict；`_fetch_classes(cid)` → list。
- [x] `_fetch_multi_log(cid, max_round)`：`t=multi_log&r=1,2,...,N`；轮次上限由 `admin.c_round` 与 `class` 最大轮次取较大值。
- [x] `compute_standings(cid)`：
  - `n = 3 if int(admin["r_type"]) in (2,5) else 4`
  - `start = int(admin.get("c_s_po") or 100000)`
  - `cls = {rid: item}`；`team = _fetch_teams(cid)`
  - 遍历 `multi_log`：每个 rid 取 `rowi` 最大行；对 `i in 1..n` 计算 `pts/num`、`net=pts-start`、组内名次 `pos`，累计到 `tid`，按 `row["round"]` 记录 `(net,pos,pts)`。
  - 仅保留有数据的轮次；按总分降序做并列名次。
  - 返回 `(c_name, rounds, rows)`。
- [x] `find_team(keyword)`：按 `[222,221,220]` 顺序，在 `team` 中匹配 `tid == keyword` 或 `keyword in t_name`，返回 `(cid, tid, t_name)` 或 `None`。
- [x] `compute_players(cid, tid)`：
  - 玩家集合 = `t_player.splitlines() + t_sub.splitlines()`
  - 每行按 `pint1..4` 降序得位次；累计 `总分` 与 `N位次数`
  - 返回 `(team_name, rows)`，rows 按总分降序，列：队员/总分/1位次数/2位次数/3位次数/4位次数。

## T2 渲染层（同文件）

- [x] `_font(size)`：msyh.ttc → simhei.ttf → simsun.ttc → `load_default()`。
- [x] `render_table(title, headers, rows, path)`：
  - 用 `textbbox` 计算每列宽（文本宽 + 20，最小列宽按列名）。
  - 行高 44、表头 48、标题区 70；白底、表头 `#4CAF50` 白字、隔行 `#F5F5F5`。
  - 目录不存在则 `os.makedirs`；`image.save(path, "PNG")`；返回 path。
- [x] 队伍表：列 `排名/队伍名称/总分/第k轮PT/第k轮详情...`；PT 带符号，详情 `#pos pts`。
- [x] 选手表：标题 `<队名> 队员统计`，列按旧版 6 列。

## T3 插件与命令（同文件）

- [x] `class LeagueTwoPlugin`：
  - `__init__(self, sender: MessageSender)`
  - `register(router)` 注册主指令 `["立直联赛", "rmnl", ".rmnl", "/rmnl"]` → `cmd_entry`，并注册 4 个兼容旧别名：
    - `["slt", ".slt", "/slt"]` → `_team_standings(ctx, 220)`
    - `["l1t", ".l1t", "/l1t"]` → `_team_standings(ctx, 221)`
    - `["l2t", ".l2t", "/l2t"]` → `_team_standings(ctx, 222)`
    - `["l2p", ".l2p", "/l2p"]` → `_player_standings(ctx, ctx.get_args())`
  - `cmd_entry` 解析：
    - 空 / `帮助` / `help` → 回复帮助文本
    - `超级|slt|220` → 220；`主级|l1t|221` → 221；`次级|l2t|222` → 222
    - `队员|player|p` + 剩余参数 → 队员统计；`队员` 无参数 → 用法
    - 其它 → 回复帮助文本
  - 每个查询先 `self._sender.reply(ctx, "正在获取联赛成绩…")`，再启动 daemon 线程执行抓取/渲染/发图；线程内 `try/except` 回复错误。
- [x] 图片路径：`newbot/assets/leaguetwo/team_<cid>_<ms>.png`、`player_<tid>_<ms>.png`。
- [x] 无数据回复：`该赛事暂无成绩数据`；队员无参回复用法；找不到队伍回复 `没有找到队伍：<参数>`。

## T4 接入与清理

- [x] `newbot/main.py`：新增 import，`_register_plugins()` 中实例化并注册。
- [x] `newbot/plugins/simple_functions.py`：删除 4 个 l2t/l1t/slt/l2p 的 `cmd_deprecated` 注册块。
- [x] `newbot/plugins/simple_functions.py`：`help_map` 新增 `"立直联赛"` 与 `"rmnl"` 详细说明；`l2t/l1t/slt/l2p` 改为「同『立直联赛』」。
- [x] `newbot/core/image_cleanup.py`：`_RUNTIME_IMAGE_DIRS` 增加 `"leaguetwo"`。

## T5 验证

- [x] `py_compile` 4 个改动文件通过。
- [x] `compute_standings(221)`：队伍数 = 14，轮次 `[1,2]`，`总分 == ΣPT` 校验 0 处不一致。
- [x] 生成队伍表 / 选手表 PNG，人工确认中文与排版（无重叠、无截断）。
- [x] 路由冒烟：`立直联赛`/`rmnl`/`.rmnl`/`/rmnl`/`slt`/`l1t`/`l2t`/`l2p` 均可解析；`rmnl` 返回帮助、`rmnl 队员` 返回用法、`rmnl 主级` 触发查询；220/221/222 三个级别均能拉到数据。
- [x] `help` 中显示「立直联赛 / rmnl」新说明。

## T6 交付

- [x] 汇总改动清单与 commit message，等待用户确认后再 commit + push（用户未说「提交」前不提交）。
