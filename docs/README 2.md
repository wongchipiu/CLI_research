# 文档导航

这里保存项目约定、使用说明、开发记录和研究产物。入口文档只回答一类问题，避免把计划、现状和历史验收混在一起。

## 从哪里开始

- **第一次使用系统：**读 [实用指南](USER_GUIDE.md)，再按根目录 [README](../README.md) 运行命令。
- **开始一个开发条目：**依次读 [需求](REQUIREMENTS.md)、[计划](PLAN.md) 和 [当前状态](STATUS.md)。
- **继续 CLI_research × gpt_quant 整合：**再读 [整合计划](INTEGRATION_PLAN.md) 和相应的 [里程碑记录](milestones/)。
- **配置 IBKR Paper 风控：**读 [日损熔断器运行手册](live_risk.md)；它与研究回测流程相互隔离。
- **查以前研究过什么：**到 [research/](research/)；查自动生成的月度策略汇总到 [monthly_review/](monthly_review/)。

## 每份文档做什么

| 文档 | 用途 | 什么时候更新 |
|---|---|---|
| [REQUIREMENTS.md](REQUIREMENTS.md) | 产品边界、目标市场、功能与安全约束，是需求基线 | 需求或范围真正改变时 |
| [PLAN.md](PLAN.md) | 里程碑、待做条目和建议执行顺序 | 排期、下一步或里程碑状态变化时 |
| [STATUS.md](STATUS.md) | 已完成能力、当前环境注意事项、测试结果和技术债 | 每个开发条目完成后 |
| [USER_GUIDE.md](USER_GUIDE.md) | 面向使用者的完整研究流程、命令和证据解释 | 可用命令或工作流变化时 |
| [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) | CLI_research 与 gpt_quant 的职责边界、契约和 M7 路线 | 两项目整合设计或 M7 范围变化时 |
| [live_risk.md](live_risk.md) | IBKR Paper 日损熔断器的配置、预检、验收和部署手册 | 风控规则或部署方式变化时 |
| [CASE_STUDY_PAPER_SIGNAL.md](CASE_STUDY_PAPER_SIGNAL.md) | 用合成案例解释模拟信号的重放保护与结论边界 | 模拟信号协议变化时 |

`PLAN.md` 回答“接下来做什么”，`STATUS.md` 回答“现在实际有什么”。若两者冲突，以代码和最新验收结果为事实依据，并修正 `STATUS.md`；不要在历史里程碑记录里改写当时结论。

## 目录说明

### `milestones/`：开发验收记录

这些文件记录某个已完成条目的范围、设计和测试证据，用于追溯，不是当前使用手册：

| 条目 | 记录内容 |
|---|---|
| [M6-S2](milestones/m6-s2-ibkr-paper-risk-guard.md) | IBKR Paper 夜间风控接口、健康状态和 macOS 守护 |
| [M7-S1](milestones/m7-s1-capital-and-tradability.md) | 回测资金约束、估值价格与可交易状态分离 |
| [M7-S2](milestones/m7-s2-execution-and-independent-test.md) | 次日开盘成交、训练/验证/最终测试隔离 |
| [M7-S3](milestones/m7-s3-paper-ledger-and-next-open-signal.md) | 模拟账本、信号防重放和执行价格时效 |
| [M7-S4](milestones/m7-s4-unified-cli-and-contracts.md) | 统一 CLI、工作目录和版本化契约 |
| [M7-S5](milestones/m7-s5-us-daily-radar.md) | 固定美股自选池的量比、动量、收盘突破、过滤和排名 |
| [M7-S6](milestones/m7-s6-forward-outcome-tracking.md) | Radar 信号去重、交易日成熟、多期限收益和 SPY 基准比较 |
| [M7-S7](milestones/m7-s7-daily-radar-job.md) | 可重试每日跑批、阶段状态、幂等重跑和 JSON/Markdown 报告 |

### `research/`：人工研究笔记

按 `YYYY-MM-DD-主题.md` 命名，包含研究假设、公开资料、可证伪条件和下一步验证。它们是特定日期的研究快照，不代表当前事实，也不是交易指令。

### `monthly_review/`：生成的月度复盘

由 `scripts/summarize_results.py` 根据本地回测摘要生成。目录内的 [README](monthly_review/README.md) 说明准入规则；月份文件可以由同名月份的再次汇总覆盖。

## 命名与维护约定

- 长期入口文档继续使用现有稳定名称，避免破坏脚本、Agent 约定和外部仓库链接。
- 新的里程碑记录放在 `milestones/`，命名为 `m<里程碑>-s<条目>-<主题>.md`。
- 新的研究笔记放在 `research/`，使用日期前缀；月报只放在 `monthly_review/`。
- 新文档必须从本页或所属子目录的 `README.md` 链接，避免出现无人知道用途的孤立文件。
- 运行输出、行情、日志和大体积结果不放进 `docs/`。
