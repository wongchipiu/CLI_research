# 项目计划与 Token 预算策略

> **2026-09-06 更新：M8-S0R 与 M8-S3a 已完成离线交付。** 已恢复 GPT 消费端的 PAPER-only 准入、v4 内容身份、有限数/缺价原子拒绝和正式交易日历，并完成共享 contracts 的本地 wheel/安装验证；下一条为 M8-S4b（完整实验 evaluator）。统一设计、review 证据、旧意见合并映射和验收标准见 [LLM_TRADING_DESIGN.md](LLM_TRADING_DESIGN.md)。

## 当前执行顺序（优先于历史排期）

| 顺序 | 条目 | 当前状态与交付 |
|---|---|---|
| 1 | M8-S0R | DONE/P0：恢复禁止自报准入、v4 内容身份/严格数值、缺价原子拒绝、消费端正式日历；GPT 121 tests 通过，验收记录见 GPT 仓库 |
| 2 | M8-S3a | OFFLINE DONE：共享 quant-contracts 源码、canonical hash、依赖声明、wheel 构建和全新临时环境安装/导入已通过 |
| 3 | M8-S3b / S3c | OFFLINE DONE：SEC v2、审批/风控上下文绑定；真实 provider、签发权限和券商连接待外部验收 |
| 4 | M8-S4a | OFFLINE DONE：受限抽取、原文引用、弃权、预算、超时与注入防护，新增 HTTPS provider gateway；真实凭据/服务验收待外部环境 |
| 5 | M8-S4b | OFFLINE PARTIAL：已完成版本化 manifest、确定性 experiment ID、质量/成本压力/负对照 evaluator、报告和 final-test 单次消费；SEC 增强 Radar、真实 LLM 特征和终测数据仍待完成 |
| 6 | M8-S5a / S5b | S5a OFFLINE DONE：审批到本地 Paper outbox/幂等恢复；S5b 仍需至少 63 个真实交易会话与独立事件量验收 |

首个研究 MVP 为美股、日频、长仓、SEC 财报事件。CLI 继续承担唯一正式量化评价；GPT 新增组合/策略模块保留为兼容基准。M6-S3 的 IBKR 账户止损守护独立验收；M7-S9 物理合仓、API/UI、新引擎及更多策略延后。完整依赖和完成条件以统一设计第 10 节为准，本轮只改计划、不修业务代码。

> 配合 REQUIREMENTS.md 使用。每个 session 开工时：只说"做 M几-S几"，让 agent 读这两个文档即可，不要在对话里重述需求。

## 1. 里程碑拆分

每个 Session 控制在一个明确交付物，做完就 `/clear`。预估为 Pro 订阅下的"工作 session"数（一个 session ≈ 一次连续的 Claude Code 对话）。

### M0 项目骨架（1 个 session）
- 初始化 git 仓库、uv 环境、目录结构、CLAUDE.md、.gitignore（排除 data/ 与 results/ 大文件）。
- 交付：空跑通 `uv run python -c "import pandas"`。

### M1 数据层（2–3 个 session）
- S1：akshare A股日线拉取 + Parquet 存储 + 增量更新（R1/R2）。
- S2：yfinance 美股日线，同一存储接口（R1/R2）。
- S3：数据质量检查脚本，输出 summary 文本（R3）。
- 交付：`uv run python scripts/update_data.py` 一键更新两市场数据。

### M2 回测引擎（3–4 个 session）
- S1：引擎选型落地（先用 pandas 自研向量化核心，接口对齐 vectorbt 以便日后替换）+ 费用/滑点模型。
- S2：A股 T+1、涨跌停约束；美股路径。**本 session 必须带单元测试。**
- S3：绩效指标 + 基准对比 + metrics.json / 图表落盘（R5/R6）。
- S4（缓冲）：修 bug、补测试。
- 交付：`uv run python scripts/run_backtest.py --strategy sma_cross --market cn`。

### M3 基线策略库（1–2 个 session）
- 统一策略接口 + 双均线/动量轮动/均值回归三个基线（R7/R8）。
- 交付：三个策略在两个市场各跑出一份 results/ 报告。

### M4 Agent 层（1–2 个 session）
- 写三个 skills（/research、/backtest、/review）+ 完善 CLAUDE.md 禁令与约定（R9–R11）。
- 交付：用 /backtest 跑一次完整流程，确认 agent 只读摘要不读原始数据。

### M5 投入使用（持续，低消耗）
- 日常用 /research 和 /review 做策略研究；确定性层跑数据和回测，0 token。

### M6 IBKR 账户级风控（二期扩展）
- S1：实现 Paper-first TWS API 熔断守护程序、三级阈值、持久化锁定、仿真适配器、配置与测试（R12–R17）。
- S2（代码完成，等待 Paper 连通验收）：已完善 close-only TWS 交易接口、夜间健康状态、只读 preflight 和 macOS launchd/caffeinate 守护；实盘保持锁定，详见 [M6-S2 验收记录](milestones/m6-s2-ibkr-paper-risk-guard.md)。
- 后续 S3（需单独确认）：Paper 连续运行验收、通知渠道接入与实盘上线评审。
- 交付：仿真测试全通过；默认配置不能连接或交易实盘账户。

**总预估：8–12 个开发 session 完成 M0–M4。** 按每周 3–4 个 session 的节奏，约 3 周完成，剩余额度留给日常使用。

## 2. Session 节奏建议（Pro 订阅）

Pro 的额度按 5 小时滚动窗口 + 每周上限计算。建议：
- 每天最多安排 1–2 个开发 session，每个 session 只做一个 S 条目，做完立即结束对话。
- 把重 session（M2 回测引擎）安排在额度刚刷新时段开始。
- 周末留出额度做策略研究（这才是项目的最终用途），不要把整周额度烧在 coding 上。

## 3. 每个开发 session 的标准流程

1. 开新对话（干净上下文）。
2. 第一句话："读 docs/REQUIREMENTS.md 和 docs/PLAN.md，实现 M1-S2，完成后跑测试。"
3. agent 写码 → 跑通 → 你验收 → 结束对话。
4. 发现的新需求/改动**写进文档**，不在当前 session 里展开讨论。

## 4. Token 节约守则（写进 CLAUDE.md 强制执行）

1. **数据不进上下文**：agent 严禁 Read data/*.parquet、交易明细 CSV、大日志。需要了解数据时跑脚本打印摘要（head/describe/行数）。
2. **结果只读摘要**：回测产出 metrics.json（<2KB）专供 agent 读；图表给人看，agent 不需要。
3. **一个 session 一个任务**：上下文越长越贵，任务完成就 /clear；避免在一个对话里连做三四个功能。
4. **文档即记忆**：决策、约定、踩坑写进 docs/，新 session 读文档恢复上下文，代替长对话历史。
5. **避免反复 compact**：对话快满时主动收尾，把状态写进 docs/STATUS.md，开新对话续。
6. **先设计后编码**：复杂模块（回测引擎）先让 agent 写 200 行以内的设计概要你确认，再一次性实现，避免大返工——返工是最大的 token 黑洞。
7. **调试上下文最小化**：报错时只贴关键 traceback，不整段日志倾倒。
8. **LLM 零参与运行时**：数据更新、回测执行均为命令行脚本，日常跑批 0 token。

## 5. 风险与备选

- akshare 接口偶发变动 → 数据层抽象出 fetcher 接口，必要时切 tushare。
- 自研回测引擎工作量超预期 → 直接落地 vectorbt，砍掉自研。
- Pro 额度某周用尽 → 确定性层不受影响，照常更新数据/跑回测；agent 研究顺延。

## 6. M7 跨项目整合与美股异动研究（2026-08-28）

- **S0 已完成：** 检查本机 CLI_research / gpt_quant 源码、既有适配关系与测试，形成 [整合开发计划](INTEGRATION_PLAN.md)。本条只交付盘点和方案，不迁移源码。
- **S1 已完成：** 修复冻结持仓后的资金约束，并分离估值价格和可交易状态；设计及验证见 [M7-S1 验收记录](milestones/m7-s1-capital-and-tradability.md)。
- S7–S9 的范围与验收见整合计划第 6 节；每个对话仍只做一个 S 条目。
- **S2 已完成（2026-08-29）：** 已实现 60/20/20 顺序划分、仅训练选参、逐折训练选参、一次性最终测试、次日开盘成交、新旧证据隔离和实用指南；设计与验收见 [M7-S2 验收记录](milestones/m7-s2-execution-and-independent-test.md)。
- **S3 已完成（2026-08-29）：** 已实现模拟账本单调日期、固定日初权益、信号唯一键与重放保护、新鲜执行价格、证据变更熔断和重启恢复；指南与验收见 [M7-S3 验收记录](milestones/m7-s3-paper-ledger-and-next-open-signal.md)。
- **S4 已完成（2026-08-29）：** 已实现版本化工作区、`quant workflow` 统一入口、质量/研究/验证决定契约、跨 cwd 路径固定和坏证据拒绝；详见 [M7-S4 验收记录](milestones/m7-s4-unified-cli-and-contracts.md)。
- **S5 已完成（2026-08-30）：** 已实现固定美股自选池的量比/动量/收盘突破、数据过滤、确定性排名、版本化 JSON 和 `quant scan`；详见 [M7-S5 验收记录](milestones/m7-s5-us-daily-radar.md)。
- **S6 已完成（2026-08-30）：** 已实现信号去重持久化、按 SPY 交易日成熟 1/3/5/10/20 日结果、描述性/可执行双口径、费用与基准超额、未成熟及缺失状态；详见 [M7-S6 验收记录](milestones/m7-s6-forward-outcome-tracking.md)。
- **S7 已完成（2026-08-30）：** 已实现可重试的更新→质检→扫描→跟踪→报告批处理、同日幂等 job ID、逐阶段状态、失败恢复和 JSON/Markdown 汇总；详见 [M7-S7 验收记录](milestones/m7-s7-daily-radar-job.md)。
- M7-S8 的真实模型研究接入并入 M8-S4a，不再维护独立排期；M7-S9 物理合仓/界面延后。模型配置/预算在连接验收时落实；离线契约与测试可以先完成。
- 两个仓库的未提交改动必须保留；合仓、联网数据验收、模拟运行与实盘接入均未在 S0 执行。

## 7. M8 下一代大模型研究系统（2026-09-01）

- **S1 历史回退已恢复：** M8-S0R 已恢复禁止自报准入、信号内容身份、策略包绑定、有限数及缺价原子拒绝；原始 [M8-S1 验收记录](milestones/m8-s1-gate-hardening.md) 保留作历史对照。
- **S2 历史回退已恢复：** CLI 与 GPT 均冻结 `exchange_calendars==4.13.2` 和 v4 `calendar_id`，并校验假日、提前收市和 A 股午休；原始 [M8-S2 验收记录](milestones/m8-s2-pinned-exchange-calendars.md) 保留作历史对照。
- **S3 PARTIAL：** SEC Evidence v1 离线存储/消费校验已实现；共享包、observed/reconstructed 时间、修订/事实与正式接入未完成，拆为 S3a/S3b；签名批准与风控上下文为 S3c。
- **S4 PLANNED：** 拆为 S4a 真实模型抽取与 S4b 对照实验。已有 ResearchTask 只是字段契约，不等于完整研究工作流或证据验证。
- **S5 PLANNED：** 新增端到端模拟链与前向验证。完成模块或增加模拟计日不能替代真实运行证据。
