# 大凤林联赛成绩查询（l2t / l1t / slt / l2p）移植规格

## 1. 背景与目标

旧版 `archive/mybot/leaguetwo.py` 通过 `score.hieuzest.xyz/api/ranking_cfg` 拉取联赛积分榜，用 pandas + matplotlib 画表后发 QQ 图片。现有 newbot 里 l2t/l1t/slt/l2p 四个命令均为 `cmd_deprecated`。

用户给出的新版主页为 `https://000.mk/?cid=221`（cid=220 超级、221 主级、222 次级）。本次目标：从该页面所用 API 重建「联赛队伍成绩」与「队伍选手统计」两个看图功能，并接入 newbot。

## 2. 数据源结论（已实测）

页面 `https://000.mk/js/main.js`、`page_rank.js`、`rank_team.js`、`rank_player.js` 显示数据全部来自：

- 主机：`https://cdn.r-mj.com`
- 统一入口：`GET /api/data.php`

| 参数 | 含义 | 返回结构 |
| --- | --- | --- |
| `t=admin&cid=<cid>` | 赛事配置 | `{cid, c_name, c_round, c_s_po(起始点,如100000), r_type(1=天凤4麻,2=天凤3麻,4=雀魂4麻,5=雀魂3麻), t_type}` |
| `t=team&cid=<cid>` | 全部队伍 | `{ "<tid>": {tid,t_name,t_player("\n"分隔),t_sub("\n"分隔),t_type,img,t_ps} }` |
| `t=class&cid=<cid>` | 全部对阵分组 | `[{rid,tid1,tid2,tid3,tid4,round,t_class,clsmark,code}]` |
| `t=multi_log&cid=<cid>&r=1,2,...,N` | 指定轮次全部对局日志 | `{ "<rid>": [ {rowi,name1..4,num1..4,pint1..4,round,url,i_time} ] }` |

关键字段语义（已用 cid=221 实测核对）：

- 一个 `rid` = 一个对阵组（4 支队伍）。
- 每行 = 一局半庄；`name{i}` 为第 i 队本局上场选手，`pint{i}` 为该局第 i 队得失点（净点）。
- `num{i}` 为第 i 队在该对阵组内的**累计点数**，起始值为 `admin.c_s_po`（100000）。对局最后一行的 `num{i}` 即该队本组最终点数。
- `round` 为轮次；`rowi` 为行序号。

结论：**新 cid 的 `ranking_cfg` 已不可用**（220 超时、221/222 返回 500，旧 cid=207 仍正常），因此累计榜改为直接从 `multi_log` 聚合计算。

## 3. 命令设计（统一为一组 `立直联赛` 指令）

主指令：`立直联赛`（英文简写 `rmnl`，别名 `rmnl` / `.rmnl` / `/rmnl`）。

| 子命令 | 赛事 | cid | 行为 |
| --- | --- | --- | --- |
| `立直联赛` / `立直联赛 帮助` | — | — | 回复指令说明与示例 |
| `立直联赛 超级` | 超级联赛 | 220 | 发送队伍排行成绩图片 |
| `立直联赛 主级` | 主级联赛 | 221 | 发送队伍排行成绩图片 |
| `立直联赛 次级` | 次级联赛 | 222 | 发送队伍排行成绩图片 |
| `立直联赛 队员 <队伍ID或队名>` | 自动在 222→221→220 中查找 | — | 发送该队队员排行图片 |

说明：

- 子命令支持简写与数字：`超级/slt/220`、`主级/l1t/221`、`次级/l2t/222`、`队员/player/p`。
- 中文主指令与英文简写等价：`立直联赛 主级` == `rmnl 主级`。
- 兼容旧指令：`slt`=超级、`l1t`=主级、`l2t`=次级、`l2p <队伍>`=队员，全部转发到同一套处理器。
- `立直联赛 队员` 无参数时回复用法；队伍 ID 形如 `13236`，也可用队名关键字（如 `千里山`）。
- 未知子命令或无参数（非帮助场景）回复帮助文本，不静默。
- 帮助文本示例：

```text
立直联赛成绩指令（rmnl）
立直联赛 超级 / 主级 / 次级 —— 查看对应级别的队伍排行
立直联赛 队员 <队伍ID或队名> —— 查看该队队员排行
示例: 立直联赛 主级
示例: rmnl 队员 千里山
旧指令 slt / l1t / l2t / l2p 仍可使用
```

- 三个榜单/队员命令各发一张图片；标题包含赛事名（`c_name`）。
- 查询为同步 HTTP，放入 daemon 线程执行，避免阻塞 FastAPI 事件循环；开始查询时先回复一句「正在获取联赛成绩…」。

## 4. 计算口径

### 4.1 队伍成绩表（`立直联赛 超级/主级/次级`）

1. 读 `admin` 得到 `c_name`、`c_round`、`r_type`、`t_type`；轮次上限取 `max(c_round, class 中最大 round)`。
2. 读 `team`、`class`，一次请求 `multi_log&r=1,2,...,max_round`。
3. `multi_log` 每个 `rid` 是一组对阵，10 行 = 5 个区间（先鋒/次鋒/中堅/副將/大將）× 每区间 2 场；`rowi` 每 2 行为一个区间。
4. 对每一行（每场半庄）：
   - `net = pint{i}`（单局得失点）；`num{i}` 是组内累计点数，不能用于单场
   - 组内按 `net` 降序确定名次 `pos`（从 1 开始）
   - 按 `class` 把该成绩归属到 `tid{i}`
5. 单场得分：`net < 0` 该场记 0；否则 `net / 10000 + 顺位点`，顺位点 1位 7、2位 4、3位 2、4位 1。
6. 区间奖励：每个区间内按队伍 2 场累计净得分比较，最高的队伍 +1（并列都加）。
7. 每队汇总：
   - `第N轮PT` = 该轮所有单场得分 + 区间奖励（保留两位小数）
   - `第N轮详情` = `净<轮净得点>`，有区间奖励时追加 ` 区间+N`
   - `总分` = 各轮 PT 之和（保留两位小数）
8. 只输出实际有数据的轮次列，避免空列。
9. 按 `总分` 降序排名，采用并列同名次（1,2,2,4）。
10. 表格列：`排名 | 队伍名称 | 总分 | 第1轮PT | 第1轮详情 | ... | 第N轮PT | 第N轮详情`。

### 4.2 队员统计表（`立直联赛 队员`）

1. 用参数在 220、221、222 的 `team` 数据中一起查找：`tid` 完全匹配，或 `t_name` 包含关键字；有精确匹配（完整队名或 ID）时只取精确结果，否则返回全部模糊匹配。可加级别前缀限定范围（如 `队员 主级 千里山`）。
2. 读该 cid 的 `admin` 与 `multi_log&r=1..c_round`。
3. 队伍选手集合 = `t_player` 按行拆分 + `t_sub` 按行拆分（与旧版一致）。
4. 对每一行对局：按 `pint1..4` 降序得出 1/2/3/4 位；对属于该队的选手：
   - `总分 += pint`
   - 对应 `N位次数 += 1`
5. 表格列沿用旧版：`队员 | 总分 | 1位次数 | 2位次数 | 3位次数 | 4位次数`，按总分降序；标题为 `<队名> 队员统计`。

## 5. 图片渲染

- 使用 Pillow（newbot 已有依赖），不引入 pandas/matplotlib。
- 字体：`C:\Windows\Fonts\msyh.ttc` → `simhei.ttf` → `simsun.ttc`，取到为止（与 `mahjong17.py` 的 `_font` 策略一致）。
- 白底、绿色表头（`#4CAF50`）、隔行浅灰（`#F5F5F5`）、单元格内边距 10px，行高约 44px，列宽按文本实际宽度计算。
- 输出目录：`newbot/assets/leaguetwo/`，文件名 `team_<cid>_<毫秒时间戳>.png` / `player_<tid>_<毫秒时间戳>.png`。
- 发送：`MessageSender.send_image(Target.from_data(ctx.raw_data), path)`。

## 6. 改动文件

1. **新增** `newbot/plugins/leaguetwo.py`
   - 常量：`API_BASE`、`COMPETITIONS={220:"超级",221:"主级",222:"次级"}`、`TIMEOUT=20`。
   - `_api(t, cid, **extra)`：统一 GET + `raise_for_status()` + JSON。
   - `_round_range(admin)`：生成 `"1,2,...,N"`。
   - `compute_standings(cid)`：返回 `(c_name, rounds, rows)`；`rows` 每项含 rank/tname/total/rounds{round:(net,pos,pts)}。
   - `find_team(keyword)`：按 222→221→220 查找。
   - `compute_players(cid, tid)`：返回 `(team_name, player_rows)`。
   - `render_table(title, headers, rows, path)`：通用 PIL 表格绘制。
   - `class LeagueTwoPlugin`：`register()` 注册主指令 `立直联赛/rmnl/.rmnl//rmnl` + 4 个兼容旧别名；`cmd_entry` 解析子命令并分发到 `_team_standings(ctx, cid)` / `_player_standings(ctx, keyword)`；处理函数用 `threading.Thread(daemon=True)` 执行抓取 + 渲染 + 发图，异常回文本。
2. **修改** `newbot/main.py`
   - `from plugins.leaguetwo import LeagueTwoPlugin`
   - `_register_plugins()` 中 `LeagueTwoPlugin(self._sender).register(self._router)`。
3. **修改** `newbot/plugins/simple_functions.py`
   - 删除「未迁移：联赛计分」4 个 `router.register(... cmd_deprecated ...)`。
   - `help_map`：新增 `"立直联赛"`（及 `"rmnl"` 指向同一说明）详细说明（子命令、示例、cid 对应赛事）；`l2t/l1t/slt/l2p` 四条改为「同『立直联赛』，见 帮助 立直联赛」。
4. **修改** `newbot/core/image_cleanup.py`
   - `_RUNTIME_IMAGE_DIRS` 增加 `"leaguetwo"`，让生成图 12 小时后自动清理。

不修改：`archive/`、日志模块、其它插件、既有无关改动。

## 7. 错误处理

- 网络失败 / 非 JSON / 关键字段缺失：向会话回复 `获取联赛成绩失败：<reason>`，不抛到主循环。
- 赛事暂无成绩（`multi_log` 为空或全为空轮）：回复 `该赛事暂无成绩数据`。
- `立直联赛 队员` 找不到队伍：回复 `没有找到队伍：<参数>`；无参数：回复用法。
- 生成的图片路径确保目录存在。

## 8. 验证步骤

1. 语法检查：用本机可用解释器（`py -3` 或 `python3`）执行 `py_compile` 检查 4 个改动文件。
2. 纯数据验证（不发 QQ）：临时以 `python -c` 调用 `compute_standings(221)`，确认能解析出 12 支队伍、1~2 轮数据、总分/PT 合计正确（可用 `num - 100000` 手算抽查）。
3. 渲染验证：调用渲染函数生成 PNG，检查中文正常、列不重叠、图片可打开。
4. 命令验证：启动 newbot 后分别发送 `立直联赛`（帮助）、`rmnl 超级`、`rmnl 主级`、`rmnl 次级`、`rmnl 队员 13236`，确认收到对应图片或明确提示；旧指令 `slt/l1t/l2t/l2p` 同样可用。
5. 回归：`help` 中显示「立直联赛 / rmnl」新说明；不再出现「暂不可用」。

## 9. 不做的事

- 不重建旧 hieuzest 的 RTOP 评分公式（服务对新 cid 已失效）；按用户提供的计分口径计算。
- 不改动 `archive/` 旧实现。
- 不新增数据库/持久化缓存（每次命令实时抓取）。
- 未获用户明确「提交」前不 commit / push。

## 10. 口径确认

（计分口径已于 2026-11-12 由用户确认：单场 10000 点 = 1 分并加顺位点 7/4/2/1，负分该场记 0，每区间净得分最高队伍 +1。）
