# 项目计划与 Token 预算策略

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
