# 喵股市收益口径审计与修正

## 背景

用户反馈「算收益时总把充值的提现的算进去」，并明确「不止冷热观测，很多地方都要检查」。上一轮已修复冷热观测的小时收益与当日变动（提交 `c38cc21`），本次对喵股市全部收益/盈亏/涨跌口径做一次完整审计，并修正仍存在的同类问题。

## 审计范围与结论

| # | 位置 | 现状 | 结论 |
|---|------|------|------|
| 1 | `_net_in_of`（cat_stock.py 5543） | 初始 1000 + 累计充值 - 累计提现 | 正确，不改 |
| 2 | `_day_pnl_of`（5549） | 总资产 - 当日基准 - 充值增量 + 提现增量 | 正确，不改 |
| 3 | `rank_players` 盈亏排行（2893） | `assets - net_in` | 正确，不改 |
| 4 | `snapshot` 累计收益（5700） | `assets - net_in` | 正确，不改 |
| 5 | 网页端 `web/stock_web.py`、`web/static/app.js` | 只展示后端 `profit` / `day_pnl`，无自算 | 正确，不改 |
| 6 | 红包/转账 `catnip_transfer_in/out`（5231/5249） | 转入记充值、转出记提现 | 正确，不改 |
| 7 | 充值/提现 `_deposit` / `_withdraw`（5171/5211） | 同步记流水 | 正确，不改 |
| 8 | 冷热观测 `_economy_check` 小时收益 / 当日变动（6541-6583） | 上一轮已按流水增量剔除 | 正确，不改 |
| 9 | 旧存档 `day_asset` 缺 `deposit` / `withdraw` 字段（2800、5573、6563） | 被当成「当天无资金进出」，当天充值会被算成盈利/涨跌 | **需修** |
| 10 | 迁移玩家 `_migrate_economy`（859-923）：`deposit = 余额`，同时 `_net_in_of` 再加 1000 | 迁移过的玩家累计盈亏恒定 -1000 | 不改代码，见「不做的事」 |
| 11 | 商战一次性重估 `econ_offset`（4827） | 冷热观测已剔除；个人今日盈亏保留 | 保持不变（对个人是真实盈亏） |

## 变更内容

### 变更 1：QQ 端持仓页重建旧形状当日基准

文件：`newbot/plugins/cat_stock.py`，函数 `_show_holdings`（约 2800 行）

`day_asset` 的重建条件由

```
if not isinstance(day_asset, dict) or day_asset.get("day") != today:
```

改为同时判断流水字段是否缺失：

```
if (not isinstance(day_asset, dict) or day_asset.get("day") != today
        or "deposit" not in day_asset or "withdraw" not in day_asset):
```

旧形状快照会按当前资产与当前流水重建，当日盈亏从 0 起算，避免当天充值被显示成盈利。

### 变更 2：网页端持仓视图同样重建

文件：`newbot/plugins/cat_stock.py`，函数 `_portfolio_view`（约 5573 行）

与变更 1 完全相同的条件判断，保证 `snapshot()["day_pnl"]` 口径一致。

### 变更 3：冷热观测跳过无流水快照的账户

文件：`newbot/plugins/cat_stock.py`，函数 `_economy_check` 的当日累计循环（约 6563 行）

在 `day.get("day") != today` 判断之后增加：

```
if "deposit" not in day or "withdraw" not in day:
    continue
```

即无法区分外部资金进出的旧账户不参与当日冷热比对（不计入 `day_base` / `day_now` / `shared_day`），避免把当天充值当成市场过热信号。随后删除两行 `dep_base = dep_now if dep_base is None else int(dep_base)` 兜底（已不可达）。

## 不做的事

- 不改 `_net_in_of` 公式，不改 `_day_pnl_of` 公式。
- 不修改历史 `players.json`：迁移问题需要重写真实玩家数据，且没有可靠的「迁移玩家」标记，代码侧不做一次性改写；仅在此文档记录，若需修正由用户决定是否人工处理。
- 不从个人今日盈亏中剔除 `econ_offset`（商战重估对个人是真实盈亏，市场层面已在冷热判定中剔除）。
- 不新增存档字段。

## 验证

1. `py -3 -m py_compile newbot/plugins/cat_stock.py`
2. 临时脚本（%TEMP%，不入库）模拟三种场景：
   - 当日开盘后充值：`_day_pnl_of` 不含充值金额；
   - 旧形状 `day_asset`（无 `deposit` / `withdraw`）+ 当天充值：持仓页重建后今日盈亏为 0，不显示 `+充值额`；
   - `_economy_check` 中旧形状账户不计入 `shared_day`。
3. 人工核对：QQ 端「我的持仓」今日盈亏、盈亏排行，网页端总收益/今日盈亏/排行与后端数值一致。

## 风险

- 旧形状快照的用户当天今日盈亏会暂时归零，次日开盘快照恢复正常数值。
- 冷热观测当日比对账户数会略减（仅旧形状账户），不影响正常账户。
