# M8-S1 准入与模拟信号加固验收记录

日期：2026-09-01

## 交付范围

本条目只加固 `CLI_research` 研究证据到 `gpt_quant` 本地模拟账本之间的边界，不接真实模型、券商或实盘执行。

1. 删除 `validate-cli-result` 的 `--paper-days` 和 `--manual-review` 自报入口；模拟天数只允许从 `--paper-state` 指定的持久化账本读取。
2. 跨项目验证在独立签名批准包实现前最高只返回 `PAPER_TRADING`；CLI 侧决定契约也拒绝 `LIVE_READY`。
3. `paper_target_signal` 升级为 schema v3。`signal_id` 对会影响执行的字段做 canonical JSON SHA-256，生成方与消费方分别计算并由跨仓测试核对。
4. 信号和账户绑定证据哈希与策略包哈希；策略包覆盖策略、市场、参数、风险覆盖、成交模型、股票池、成员快照、源码和数据快照。
5. 权重、价格、账户资金和持仓数值必须为有限数；JSON 字符串数字、布尔值、NaN 和 Infinity 均 fail closed。
6. 调仓在估值和下单前检查所有目标标的与现有持仓的执行价格。缺价时不改变估值日期、交易日数、订单或 `processed_signal_ids`。

## 关键契约

v3 `signal_id` 身份字段：

```text
schema_version, artifact_type, signal_date,
generated_at, available_at, expires_at, execution_model,
strategy, market, universe,
evidence_sha256, strategy_package_sha256, signal_data_sha256,
target_weights
```

`created_at` 和参考收盘价是非执行元数据，不进入身份；执行时仍必须另行提供同一交易日、带时区且不超过 15 分钟的新价格。

旧 v2 信号与没有 `strategy_package_sha256` 的旧模拟账户不会被静默升级：消费 v3 信号时会 fail closed，应从原始 `metrics.json` 重新创建账户和信号。

## 对抗验收

- 修改已签名目标权重但保留原 `signal_id`：拒绝。
- 权重为 NaN、布尔或字符串数字：拒绝。
- 目标包含 AAPL/MSFT 但只提供 AAPL 价格：原子拒绝，账户四项状态均不变。
- 持久化账户资金为 NaN：保存和加载拒绝。
- 重启后重放相同 v3 信号：拒绝。
- CLI 传入 `--paper-days` 或 `--manual-review`：参数解析拒绝。
- 跨项目决定载荷伪造 `LIVE_READY`：CLI 契约拒绝。

## 验证结果

- `CLI_research`：`.venv/bin/python -B -m pytest -q -p no:cacheprovider` → **117 passed**。
- `gpt_quant`：`PYTHONPATH=src ../CLI_research/.venv/bin/python -B -m unittest discover -s tests -q` → **35 tests OK**。
- `gpt_quant/scripts/demo_paper_workflow.py`：首次模拟成交 1 笔，重启后重放和陈旧价格均被拒绝。
- 两仓 `compileall` 与 `git diff --check` 通过。

## 未完成边界

- 正式 NYSE/SSE/SZSE 节假日日历仍未接入；当前代码只识别工作日与常规日内时段，列入 M8-S2。
- 签名、撤销和到期的 `ApprovalBundle` 尚未实现，所以不存在实盘批准路径。
- 共享 `quant-contracts` 包尚未建立；当前两仓保留相同 canonical 规则，并用跨仓测试防止漂移，后续在 M8-S3 收敛。
- 未更新真实行情、未运行新策略最终测试、未连接模型或券商，也没有产生收益结论。
