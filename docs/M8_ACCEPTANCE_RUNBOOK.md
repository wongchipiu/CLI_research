# M8 未验收项操作手册

更新：2026-09-06

本文是 CLI_research × gpt_quant 当前未完成验收项的统一操作入口。它描述如何验收，不代表任何外部账号、模型、券商连接或真实前向结果已经存在。

## 0. 总原则

- 所有命令先在 Paper/隔离环境运行；不设置实盘配置，不把 LIVE_READY 当作授权。
- 每次验收记录两仓 SHA、quant_contracts 版本、日历版本、lockfile hash、fixture hash、测试报告和输出目录。
- 失败、缺数据、缺价、过期、版本漂移和对账差异都必须 fail closed；不能用手工改 JSON 补齐证据。
- 原始行情、SEC 原文、模型响应、订单回报保留在受限目录；日常报告只读取摘要。

## 1. 当前未验收项

| 条目 | 需要的外部条件 | 主要入口 | 通过标准 |
|---|---|---|---|
| M8-S3a 共享 contracts wheel | 可构建的干净 Python 环境 | 构建/安装/跨 cwd 回归 | 两仓安装同一 contracts 版本，生产者/消费者接受与拒绝集合一致，无 PYTHONPATH 补丁 |
| M8-S4a 真实 provider | 一个明确 provider、API key、预算和固定模型版本 | provider adapter + 离线 fixture | 超时/限流/认证分类正确，预算不超，响应保存可重放，无凭据泄漏 |
| M8-S4b B0–B3 终测 | PIT 股票池、SEC 数据、冻结模型/prompt、人工标注集 | CLI evaluator / trial ledger | 终测只运行一次，所有 trial 登记，B3 相对 B2 的置信区间和成本压力测试达到预登记门槛，否则 INCONCLUSIVE |
| M8-S5b Paper 前向 | 已验收 S5a、Paper 账户、持续运行环境 | 本地 Paper / IBKR Paper adapter | 至少 63 个真实交易会话、独立事件量达标、每日对账无未解释差异、无重复/未授权订单 |
| M6-S3 IBKR 风控 | TWS/IB Gateway Paper、精确 DU 账号、官方 ibapi | live_risk.md | 只读预检、连接恢复、夜间状态、close-only 和 kill switch 在 Paper 验收通过 |

## 2. 通用基线与证据目录

~~~bash
cd /Users/brucehuang/Documents/CLI_research
source .venv/bin/activate
export ACCEPT_ROOT="$PWD/var/acceptance/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ACCEPT_ROOT"
git rev-parse HEAD > "$ACCEPT_ROOT/cli_sha.txt"
git -C ../gpt_quant rev-parse HEAD > "$ACCEPT_ROOT/gpt_sha.txt"
python -B -m pytest -q -p no:cacheprovider | tee "$ACCEPT_ROOT/cli_tests.txt"
PYTHONPATH=../gpt_quant/src python -B -m pytest -q -p no:cacheprovider ../gpt_quant/tests | tee "$ACCEPT_ROOT/gpt_tests.txt"
~~~

把最终 JSON、Markdown、模型响应、Paper 日志和校验输出复制到同一个 ACCEPT_ROOT；不要把 API key 写入日志或提交 Git。

## 3. M8-S3a：共享 contracts wheel

目标是证明两仓在干净环境中使用同一份 schema、canonical hash 和交易日历，而不是继续依赖源码路径。

操作顺序：

1. 固定 quant_contracts 版本、exchange-calendars==4.13.2 和 lockfile；记录版本及 SHA256。
2. 在当前受限环境可用 `cd ../gpt_quant/packages/quant_contracts && python build_wheel.py` 生成共享 wheel；在完整开发环境也可用标准 PEP 517 builder 构建。
3. 在临时目录创建全新虚拟环境，只安装两个 wheel，不设置 PYTHONPATH。
4. 用 golden fixtures 分别测试：合法 v4 信号、错误日历、旧 schema、篡改 hash、NaN/Inf/bool、缺价、未来可用时间和非法 JSON 类型。
5. 从仓库根目录、临时目录和任意 cwd 分别运行同一条消费命令，比较 canonical 输出和拒绝原因集合。
6. 删除临时环境后重复安装，确认结果不依赖源码目录。

通过证据至少包括：两个 wheel、安装清单、fixture hash、每个 fixture 的接受/拒绝结果、两仓 SHA 和测试报告。任何一项仍需 PYTHONPATH 才能运行时，S3a 不通过。

## 4. M8-S4a：真实模型 provider

离线 adapter 测试已经完成；真实验收前必须先写入 provider、实际模型标识、预算和截止时间。禁止使用动态模型别名作为冻结版本。

操作顺序：

1. 准备脱敏 SEC fixture 和人工标注结果；先运行无网络 fixture 回归。
2. 设置只读研究进程的 provider 凭据，凭据只来自环境变量或受保护 secret store，不进入 prompt、JSONL 或 Git。
3. 对同一文档运行成功、超时、限流、认证失败、非法 schema、引用不存在和提示注入案例。
4. 检查每次 ModelRun 的模型标识、prompt/tool schema hash、输入输出 hash、usage、请求 ID、重试和成本。
5. 检查迟到响应、超预算响应和引用无法定位的响应均不会发布为 LLMFeature；模型只能抽取/解释，不能调用订单或 shell 工具。

通过标准：引用定位完整；关键事实与原文一致率、分类 F1、coverage、abstention 和置信区间达到实验 manifest 的冻结门槛。没有标注集或预算记录时，只能标记 OFFLINE_DONE，不能标记 provider 验收通过。

## 5. M8-S4b：B0–B3 终测

四组必须使用相同 PIT 股票池、行情快照、费用、执行延迟、持有期和 evaluator：

- B0：现金/基准
- B1：价格与量能 Radar
- B2：B1 + 确定性 XBRL/关键词字段
- B3：B2 + 经引用验证的 LLM 特征
- N1/N2：发行人/日期置乱或删除文本的负对照

操作顺序：冻结 manifest → 登记所有 trial → 锁定 prompt/model/阈值/预算 → 只运行一次 final test → 生成完整 EvidenceBundle。不得在最终测试后调参、挑期限或另建 study 文件复用终测。

通过标准：主比较 B3 - B2 的净收益增量 95% 区间下界、成本压力情景、回撤/集中度、coverage、弃权率、容量和独立事件量均达到预登记门槛；否则结果为 INCONCLUSIVE，不是策略通过。

## 6. M8-S5b：本地 Paper 与券商 Paper 前向

先完成本地 Paper 的审批、outbox、重启、重放、撤销、缺价、部分成交和对账故障注入，再连接券商 Paper。券商 Paper 不是实盘，也不能证明真实成交质量。

每个真实会话必须记录：

- 交易日、账户快照、现金、仓位、未结订单、信号/特征/策略版本
- 计划与实际信号、订单业务键、审批和风控 hash、成交/拒单/撤单回报
- 费用、滑点、延迟、对账差异、断线恢复和 kill switch 状态

通过标准：至少 63 个不同真实交易会话；达到 manifest 预登记的独立事件量；重复执行 0 次、未授权订单 0 次、未解释对账差异 0 个。回填、空跑、同日重复估值和重复回报不能增加会话数。

## 7. M6-S3：IBKR Paper 风控

具体配置、预检、连接和 launchd 说明见 live_risk.md。最小顺序是：

1. 只读 preflight，确认 Paper 环境、精确 DU 账号、本机地址、绝对路径和官方 API。
2. 前台连接，确认净值、Daily P&L、持仓和活动订单快照。
3. 注入断线/恢复、陈旧数据、部分成交和订单回报乱序，确认 fail closed。
4. 只测试风险服务生成的 close-only Paper 订单；确认超卖、反向开仓和非 risk- order ref 被拒绝。
5. 连续运行并每日保存 status.json、audit 和对账结果，再考虑生成 launchd plist。

ready: true 只表示预检通过；进程存在也不等于保护仍健康，必须同时检查状态文件的 healthy 和更新时间。

## 8. 验收记录模板

每项验收保存：目标 ID、开始/结束时间、两仓 SHA、contracts/calendar/lockfile/fixture hash、外部账号/模型标识（不含 secret）、命令、结果目录、通过/失败的反例、已知限制、结论和回滚版本。只有完成对应外部条件并达到上述门槛，才能把计划状态从 OFFLINE_DONE/PLANNED 改为 DONE 或 FORWARD_VALIDATED。

相关设计和计划：

- LLM_TRADING_DESIGN.md
- PLAN.md
- gpt_quant development_plan.md
- IBKR Paper 风控手册：live_risk.md
