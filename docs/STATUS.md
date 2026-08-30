# 项目进度

> 每个 session 结束时更新本文件；新 session 开工先读这里。

## 已完成

- **M0 骨架**（2026-06-11）：uv + Python 3.12 环境、src 布局、pyproject（清华 PyPI 镜像）、git 仓库。
- **M1 数据层**（2026-06-11）：
  - 增量更新脚本 `scripts/update_data.py`，A股 5 只 + 沪深300 + 美股 5 只全部跑通（2024-01-01 起日线）。
  - 质量检查 `scripts/check_data.py` → `data/quality_summary.txt`，当前全部 [OK]。
  - 单测 5 个全过（storage 合并/去重逻辑）。

## 本机环境注意事项（重要，新 session 必读）

1. **代理**：本机挂 Clash（127.0.0.1:7890）。国内数据源必须绕过代理，`fetchers.py` 已在 import 时自动设置 NO_PROXY，勿删。
2. **数据源现状**：东财接口（stock_zh_a_hist / index_zh_a_hist）当前网络下连不通，运行时自动降级到新浪源；yfinance（Yahoo）同样不可用，自动降级新浪美股源。**新浪源是当前唯一稳定源**。
3. **新浪源量纲**：volume 单位是股（东财是手）；做成交量因子时注意。
4. uv 装在 winget 路径，老 shell 可能不在 PATH；新开终端可直接用 `uv`。
5. Windows 控制台 GBK：脚本已内置 `sys.stdout.reconfigure(encoding="utf-8")`。

- **M2 回测引擎**（2026-06-12）：组合级日频引擎（决策 t 收盘执行赚 t+1 收益）、
  涨跌停/停牌约束、费用模型、绩效指标、metrics.json + nav.png 落盘。21 个单测全过。
- **M3 基线策略**（2026-06-12）：sma_cross / momentum / boll_revert，注册表接口。
  6 组回测（2018~2026）已跑通：美股 momentum 最佳（cagr 30.3%, sharpe 1.04，超额 16%/年）；
  A股 momentum 超额 9%/年；boll_revert 两市场均跑输基准。
- **M4 Agent 层**（2026-06-12）：/research、/backtest、/review 三个 skills + CLAUDE.md 约定。
- **M5 研究验证流水线**（2026-07-20）：
  - 回测摘要新增交易日数和已完成持仓次数。
  - 支持 70/30 或指定日期的样本内/样本外 holdout，测试段保留历史指标预热但独立从空仓计净值。
  - 新增确定性参数网格、相邻参数稳健性检查和样本外优先排行榜。
  - 新增 `results/summary.csv` 与 `docs/monthly_review/<YYYY-MM>.md` 月度汇总。
  - 11 个行情序列已更新至 2026-07-20，质量检查全部通过；六组基线 holdout 和两市动量网格已跑通。

## 下一步：M6 扩展与滚动验证

- 日常：/research 提想法 → 写新策略到 strategies/ → /backtest 验证 → /review 复盘。
- 候选改进：A股池扩到沪深300成分、波动率目标仓位、walk-forward 滚动验证和模拟盘记账。

## 待办/技术债

- 数据已补全 2018-01-02 起。混源情况：东财间歇可用，部分标的东财、部分新浪，
  **volume 量纲不一致（手 vs 股）**，做量价因子前需统一。
- cn-index 的东财失败 warn 每次都会打印一次，属预期噪音。
- 扫参数（grid search）应做成确定性脚本，勿让 agent 循环跑回测烧 token。

## 2026-08-28：M7-S0 本机整合盘点

- 已检查 `/Users/brucehuang/Documents/CLI_research` 与相邻 `gpt_quant`，详细结论见 [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md)。本节补充此前进度，旧环境/数据状态未重新验证。
- 既有测试：CLI 52 项通过；GPT 24 项通过。GPT 的脚本模型 agent-demo 完成；没有调用真实模型或连接券商。
- 已有跨项目能力包括 metrics 验证、walk-forward 检查、本地模拟账本和信号文件；这些代码比此前部分计划描述更完整，但不等于整体已验收。
- 补充合成案例复现两个缺口：冻结仓位后总权重可达 2.0；模拟估值日期倒退后会多计交易天数。仅记录，未修复。
- 抽样最新美股参数扫描摘要被现有验证器 BLOCKED，包含缺历史时点股票池证据；未放宽闸门。
- 本轮仅文档改动，未改业务代码、行情和既有回测产物；下一建议条目：M7-S1。

## 2026-08-28：M7-S1 资金约束与可交易性

- 已修复冻结仓位后的超仓：先执行可卖仓位并扣费，再按可用现金同比例限制买入；费后实际权重重新归一，冻结资产数量不变。
- 行情加载器保留 NaN；引擎仅对估值价格前填，缺失报价不得成交。增加非有限价格、决策和无效费率的拒绝。
- 工作区验证：CLI 73 项测试通过，GPT 原有 24 项通过。新增案例涵盖冻结换仓、跌停、部分冻结、买卖费用、恢复报价及独立现金对账。
- 旧回测结果未重算；费用和缺失行情处理修正会影响净值，旧结果不可直接作为新引擎的验收结果。
- 本轮按授权提交修复、必要加载依赖和 M7 文档；未提交无关成果，未推送远程。完整提交验证见 [M7-S1 验收记录](milestones/m7-s1-capital-and-tradability.md)。
- 下一条目 M7-S2；模拟账本日期问题保留到 M7-S3，券商交易仍不在本轮范围内。

## 2026-08-29：M7-S2 已完成

- 已实现 [M7-S2 验收记录](milestones/m7-s2-execution-and-independent-test.md)约定的 60/20/20 顺序划分、仅训练选参、逐折重新选参、最终测试一次性消费和 `next_open_v1` 次日开盘成交。
- 已修复首日费用/初始净值统计和基准未来价格后填；旧 `legacy_same_close` 结果保留明确标签，不能通过新版证据验证。
- 已更新 `gpt_quant` 证据适配器，严格检查三段日期、参数冻结、源码/数据指纹、滚动验证和时点股票池；合成教程证据按预期被阻止准入。
- 已交付 [实用指南](USER_GUIDE.md)，覆盖提出问题、冻结实验、运行命令、阅读证据和形成可复查结论。
- 验收：`CLI_research` **91 passed**，`gpt_quant` **25 tests OK**，两仓 `git diff --check` 通过；离线教程与跨项目验证链路通过。
- 未更新真实行情、未运行真实策略最终测试、未连接券商。下一项为 M7-S3（模拟账本日期、信号重放和次日开盘衔接）。

## 2026-08-29：M7-S3 已完成

- 模拟估值日期只能单调前进；同日重复估值不重复累计交易日，日收益使用固定日初权益。周末、倒退日期和非正常交易时段被拒绝。
- 新 `paper_target_signal` v2 使用确定性 `signal_id`；只保存参考收盘价，执行时必须提供后续常规交易时段的新价格和带 offset 的时间戳，默认价格最长 15 分钟有效。
- 已处理信号、最后订单时间和日初权益随账户持久化；重启后重复信号仍被拒绝。证据文件删除、修改或撤销后账户 `HALTED` 并拒绝新增买单。
- 新增 [模拟信号案例](CASE_STUDY_PAPER_SIGNAL.md) 和 [M7-S3 验收记录](milestones/m7-s3-paper-ledger-and-next-open-signal.md)，实用指南补充从证据进入模拟观察、读取输出和限定结论的方法。
- 验收：`CLI_research` **92 passed**，`gpt_quant` **30 tests OK**，两仓差异与编译检查通过；未联网、未连接券商。
- 下一项为 M7-S4：统一入口与版本化契约。正式交易所节假日日历仍是明确技术限制。

## 2026-08-29：M7-S4 已实现

- 新增 `quant_workspace_config` v1，数据、结果、实验、股票池和相邻验证器均解析为不依赖 cwd 的绝对路径。
- 新增 `quant workflow`，顺序执行目标市场质量摘要、正式参数扫描、`strategy_validation` v2 检查和 `gpt_quant` 独立验证，并保存 `research_workflow` v1。
- `gpt_quant` CLI 现在返回 `strategy_validation_decision` v1；旧版本、旧成交口径、坏 JSON、空数据、质检错误和越界结果目录均明确阻止。
- 两仓通过可选 integration 依赖连接，不复制源码、不合仓；旧脚本只新增可选 `--workspace`，原入口保留。
- 验收详情与最终测试数见 [M7-S4 验收记录](milestones/m7-s4-unified-cli-and-contracts.md)。下一项为 M7-S5 美股日线 Radar MVP。

## 2026-08-29：M6-S2 夜间自动止损接口代码完成

- 强化官方 TWS API close-only 接口：订单 ID 单调推进，只允许 `risk-` 股票平仓，拒绝超量反向开仓；连接回调和订单状态有隔离测试。
- 连接/P&L 循环失败时，无需账户快照也会原子写出 `live_risk_status` v1 的不健康状态；恢复后重新写健康状态。
- 新增只读 `--preflight` 和 launchd/caffeinate plist 生成器；生成器不会安装服务或修改 macOS 设置。
- 离线三级止损仿真通过；两仓回归为 CLI 100 passed、GPT 31 tests OK。
- 本机尚无用户 Paper 配置且未安装官方 `ibapi`，所以未连接 TWS、未发 Paper/实盘订单。下一步由用户在本地填写精确 `DU` 账号并接受官方 API 许可后完成 Paper 验收。

## 2026-08-30：M7-S5 美股日线 Radar MVP 已完成

- 新增版本化 `daily_radar_config` 与 `daily_radar_scan`，`quant scan --market us` 可对配置内的固定美股自选池计算 1/5/20 日收益、20 日量比和 20/60 日收盘突破。
- 最低历史、价格、平均成交额、成交量单位、复权一致性和零成交量均有明确过滤；部分数据不可计算时返回 `DEGRADED` 与逐标的原因，整个池无数据时明确失败。
- 数据快照、排序和 `signal_id` 均确定性生成；未来 K 线不会改变历史扫描日特征。同分以代码排序，不把评分解释为上涨概率。
- 合成数据与 CLI 落盘测试已加入，`CLI_research` 完整回归为 **107 passed**；非 editable 重装后的 `quant scan/workflow --help` 冒烟检查通过。
- 本地存量数据只读扫描覆盖 49 个 extended 美股标的，45 个完成特征计算，4 个因复权字段混合降级，默认阈值下零候选；未更新行情、未连接外部服务或券商。
- 详细规则与边界见 [M7-S5 验收记录](milestones/m7-s5-us-daily-radar.md)。下一项为 M7-S6 后续表现跟踪。

## 2026-08-30：M7-S6 Radar 后续表现跟踪已完成

- 新增 `daily_radar_tracking` v1 和 `quant signals track`，按 `signal_id` 幂等登记扫描候选，并原子保存逐信号结果。
- 期限严格依 SPY 本地会话成熟 1/3/5/10/20 个交易日；描述性收盘收益与次日开盘、扣双边费用的可执行收益分开保存，并各自比较 SPY。
- 未成熟结果保持 `PENDING`；到期但缺开盘/收盘为 `MISSING` 并列出原因；只有配置提供明确最终交易日才标 `DELISTED`。三者均不前填、不补零，追加未来数据不会改写已经成熟的短期限目标日。
- 合成数据覆盖幂等、未来数据隔离、费用、基准、缺失和显式退市路径；CLI 集成覆盖扫描后跟踪落盘。`CLI_research` 完整回归为 **112 passed**。
- 详细规则见 [M7-S6 验收记录](milestones/m7-s6-forward-outcome-tracking.md)。下一项为 M7-S7 可重试每日批处理与报告。

## 2026-08-30：M7-S7 每日 Radar 批处理与报告已完成

- 新增 `daily_radar_job` v1、`daily_radar_report` v1 和 `quant daily`，固定执行更新→质检→扫描→跟踪→JSON/Markdown 报告。
- 同一 profile/job_date 使用稳定 job ID；同日重跑增加 attempt。更新、扫描、信号合并和报告均幂等，阶段失败会原子保存错误与 `failed_stage`，下一次可安全重做。
- 报告只统计 MATURED，展示描述性/可执行收益的样本数、中位数、胜率、基准超额、最差收益，以及待成熟/缺失/退市数量和比例。
- 合成与临时工作区测试覆盖阶段顺序、跳过更新、失败恢复、警告、同日两次 CLI 运行和信号不重复；完整回归为 **116 passed**。
- 本地存量数据以 `--skip-update --as-of 2026-07-20` 离线运行两次：两次 job ID 一致，attempt 从 1 增至 2，五个阶段均完成且仍为 0 个信号；质量摘要 50 个 WARN、0 ERROR，Radar 45/49 个标的完成特征计算并因 4 个复权字段不一致标记降级。未联网更新行情。
- 详细边界见 [M7-S7 验收记录](milestones/m7-s7-daily-radar-job.md)。S0–S7 确定性研究闭环完成；S8/S9 为需单独确认的可选扩展。
