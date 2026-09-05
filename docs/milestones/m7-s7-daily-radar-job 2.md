# M7-S7：每日 Radar 批处理与报告

状态：**已完成（2026-08-30）。**

## 范围

本条目把已有的行情更新、质检、Radar、后续表现跟踪和报告串成一个手动触发、可重试的确定性任务。不安装 launchd/cron，不调用真实模型，不发送通知，不连接模拟或实盘券商。

## 入口与阶段

入口：`.venv/bin/quant daily --workspace config/workspace.yaml --market us --profile momentum_volume`。

固定阶段顺序：

1. `update`：复用 `scripts/update_data.py` 增量更新 profile 对应的美股池；脚本新增 `--workspace`，股票池在应用工作区后校验。
2. `quality`：运行目标市场质量摘要；存在 ERROR 时停止，WARN 记入任务警告。
3. `scan`：调用 M7-S5，按交易日原子覆盖 `scan.json`。
4. `track`：调用 M7-S6，发现 profile 的历史扫描并按 `signal_id` 合并。
5. `report`：生成版本化 JSON 和面向用户的 Markdown。

显式 `--skip-update` 用于离线验收或回放，状态记录为 `SKIPPED`。`--as-of` 可固定更新截止与扫描交易日；`--job-date` 控制幂等任务和报告标签，默认是当前纽约日期。

## 状态、重试与幂等

- `daily_radar_job` v1 保存稳定 `job_id`、attempt、请求边界、总状态及五个阶段的开始/结束时间、简要详情、产物、警告和错误。
- 相同市场、profile、job_date 使用同一 job ID。同日重跑增加 attempt，重新执行幂等阶段，以便从失败恢复。
- 行情存储按日期去重；扫描按交易日覆盖；跟踪按 signal ID 去重；日报按 job date 覆盖。同日重跑不会追加重复信号。
- 阶段异常立即原子保存 `FAILED` 和 `failed_stage`，后续阶段保持 `PENDING`。下一次运行不需要删除锁或手工修改状态。
- `COMPLETED_WITH_WARNINGS` 表示报告已生成，但质检、扫描降级或成熟结果缺失需要人工查看；CLI 返回退出码 2。

## 报告口径

`daily_radar_report` v1 保存当日候选、扫描/跟踪快照和各期限汇总。Markdown 同时展示：

- 成熟样本数；
- 描述性收益中位数、胜率、中位超额和最差收益；
- 次日开盘、扣费后的可执行净收益中位数、胜率、中位超额和最差净收益；
- 待成熟、缺失和显式退市数量及比例。

只有 `MATURED` 进入收益统计；PENDING、MISSING、DELISTED 不填 0、不进入胜率。评分仍不是上涨概率，报告不生成订单。

## 验收

- 合成 handlers 覆盖同日重跑 attempt、稳定 job ID、逐阶段顺序、显式跳过更新、阶段失败状态、下一次恢复和警告不中断报告。
- 报告测试覆盖成熟样本统计以及未成熟/缺失排除。
- CLI 临时工作区集成覆盖 scan→track→daily、同日第二次运行、信号不重复、JSON/Markdown 落盘。
- 完整回归测试数与本地离线验收见 `STATUS.md`。

## 后续边界

S7 完成了 S0–S7 的确定性研究闭环。可选 S8 的真实模型接入与 S9 的物理合仓/界面必须分别确认；每日任务不会自动启用它们。系统调度、通知渠道和任何券商执行也仍需独立授权与验收。
