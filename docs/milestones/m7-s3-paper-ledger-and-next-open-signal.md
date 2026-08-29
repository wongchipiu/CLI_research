# M7-S3：可信模拟账本与次日开盘信号

日期：2026-08-29。状态：**已完成并验收**。

## 目标

把 M7-S2 的 `next_open_v1` 研究证据安全接入本地模拟账户，同时保证：时间不能倒退、同一信号不能重复成交、执行价格必须来自后续交易时段且足够新、证据变化会阻止新增风险、进程重启不丢失这些约束。

本条目不连接券商、不更新行情、不执行实盘订单，也不宣称模拟结果能证明未来盈利。

## 实现规则

- `mark_to_market()` 拒绝倒退日期和周末；同一日期重复估值不会增加 `trading_days`，日收益始终相对该交易日固定的起始权益计算。
- 订单时间必须带 UTC offset，处于账户市场的常规交易时段，且不能早于此前订单或账户估值日期。
- 新信号使用 `paper_target_signal` schema v2，包含确定性的 `signal_id`、`signal_date`、`generated_at`、`available_at`、`expires_at` 和 `next_open_v1`。
- 信号文件只保存生成信号时的参考收盘价；模拟执行必须在命令中提供执行时段的新价格和 `price_as_of`。价格不可来自未来，默认最多陈旧 15 分钟。
- 收盘信号只能在更晚的交易日期执行；过期信号、同日执行、非交易时段、周末和重复 `signal_id` 均被拒绝。
- 已处理信号 ID、日初权益、最后估值日期、最后订单时间随账户状态原子保存；重启后继续生效。
- 每次新增风险前重新计算研究证据文件哈希。证据被修改、删除或主动撤销后账户进入 `HALTED`；新增买单被拒绝，风险降低卖单仍可手工执行。

## 明确限制

当前依赖为零的离线日历能拒绝周末并校验美股/A股常规交易时段，但没有完整交易所节假日表。节假日不能仅凭“周一到周五”证明是实际交易日；M7-S4 引入统一契约时应接入可版本化的正式交易日历。信号默认在信号收盘后七个自然日过期，长假后应更新数据并重新生成，而不是放宽过期检查。

## 验收案例

离线案例：

```bash
cd /Users/brucehuang/Documents/gpt_quant
../CLI_research/.venv/bin/python -B scripts/demo_paper_workflow.py
```

案例必须观察到：首次生成 1 个订单；重启后仍记录 1 个已处理信号；重放返回 `signal has already been processed`；30 分钟旧价格返回 `execution prices are stale`。

正确结论是：账本的幂等、持久化和价格时效保护在该合成案例中有效。错误结论是：策略已经盈利、可以进入模拟盘或实盘。后者仍需真实合格证据、至少 63 个不同模拟交易日和人工复核。

## 最终验收

- `CLI_research`：`.venv/bin/python -B -m pytest -q -p no:cacheprovider` → **92 passed**。
- `gpt_quant`：`PYTHONPATH=src ../CLI_research/.venv/bin/python -B -m unittest discover -s tests -q` → **30 tests OK**。
- 两仓 `git diff --check` 和 `compileall` 通过。
- `scripts/demo_paper_workflow.py` 观察到首次 1 个订单、重启后 1 个已处理信号、重放和陈旧价格均被拒绝。
- 未更新真实行情、未读取行情明细、未连接券商、未创建真实模拟账户或执行真实策略信号。
