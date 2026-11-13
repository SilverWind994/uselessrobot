# 喵股市收益口径审计 · 任务清单

- [x] T1 修改 `_show_holdings` 的 `day_asset` 重建条件（cat_stock.py 约 2800 行）
- [x] T2 修改 `_portfolio_view` 的 `day_asset` 重建条件（cat_stock.py 约 5573 行）
- [x] T3 `_economy_check` 跳过缺流水字段的旧快照账户，删除不可达兜底（约 6563 行）
- [x] T4 `py -3 -m py_compile newbot/plugins/cat_stock.py`
- [x] T5 临时脚本验证三种场景（充值不进入今日盈亏 / 旧快照重建 / 旧账户不参与冷热比对）
- [x] T6 汇总改动与 commit message，等待用户确认后再 commit + push
