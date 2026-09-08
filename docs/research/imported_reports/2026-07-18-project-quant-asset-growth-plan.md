# 三个项目分析与资产年增长 25% 使用计划

生成时间：2026-07-18 00:44 CST  
分析对象：

- `/Users/brucehuang/Documents/aicodingagent`
- `/Users/brucehuang/Documents/CLI_research`
- `/Users/brucehuang/Documents/gpt_quant`

说明：本文是项目功能和使用计划分析，不构成投资建议，也不承诺任何收益。年化 25% 是很高的目标，必须用数据、回测、样本外验证、模拟交易和风险闸门约束，不能依靠大模型主观判断或单次回测结论。

## 1. 总体结论

这三个项目可以组合成一套“AI 辅助量化研究工作流”，但它们分工不同：

| 项目 | 核心定位 | 当前成熟度 | 在资产增长目标中的角色 |
| --- | --- | --- | --- |
| `aicodingagent` | 个人 AI Agent 远程控制框架，含 iPhone App、中继服务、CLI Agent | 工程底座较完整，但不是量化系统本身 | 控制台和远程审批层：随时发起研究、查看结果、批准低风险操作 |
| `CLI_research` | 个人量化研究系统，已有数据更新、质量检查、多策略回测和报告 | 最接近可实际使用的研究工具 | 主研究引擎：拉数据、跑策略、保存回测报告、沉淀研究笔记 |
| `gpt_quant` | 研究优先的量化验证框架，强调 Agent、审计、风险闸门 | 原型阶段，制度设计清晰，数据能力较弱 | 风控与治理模板：定义哪些策略可以进入模拟盘/实盘候选 |

推荐关系：

```text
aicodingagent
  作为远程 AI 操作入口
        ↓
CLI_research
  负责真实数据、策略研究、批量回测、报告生成
        ↓
gpt_quant
  抽取其中的审计、权限、验证闸门思想，作为上线前的风险控制层
```

如果目标是“让资产每年增长 25%”，当前最现实的路线不是直接自动交易，而是先把这三个项目整理成一条严格流水线：

1. `CLI_research` 负责发现和验证策略。
2. `gpt_quant` 负责判断策略是否允许进入下一阶段。
3. `aicodingagent` 负责远程调用、复盘、审批和任务编排。

## 2. 项目一：aicodingagent

### 2.1 功能

`aicodingagent` 是一个私人定制 AI Agent 框架，目标是把桌面 CLI Agent、中继服务器和 iPhone App 连接起来。

主要组件：

- `relay/`：Node.js 中继服务器，通过 HTTP API 和 WebSocket 桥接 CLI 与 iPhone。
- `iphone-app/`：SwiftUI iPhone App，支持远程对话、权限审批、中断请求、自动重连。
- `restored-src/`：CLI Agent 相关代码，负责 LLM 调用、本地工具执行和远程中继接入。
- `shared-types/`：共享消息协议和类型定义。

核心能力：

- iPhone 远程控制桌面 Agent。
- 工具调用时可以通过手机审批。
- 支持 OpenAI、Ollama、DeepSeek 或任意 OpenAI 兼容 API。
- 中继服务只做消息路由，不保存对话内容。

### 2.2 使用方法

启动中继服务器：

```bash
cd /Users/brucehuang/Documents/aicodingagent/relay
npm install
PA_RELAY_KEY=my-strong-secret-2026 npm start
```

Docker 方式：

```bash
cd /Users/brucehuang/Documents/aicodingagent
docker build -t pa-relay -f relay/Dockerfile .
docker run -d --name pa-relay \
  -p 7780:7780 \
  -e PA_RELAY_KEY=my-strong-secret-2026 \
  --restart unless-stopped \
  pa-relay
```

健康检查：

```bash
curl http://127.0.0.1:7780/health
```

iPhone 端：

1. 用 Xcode 打开 `iphone-app/`。
2. 配置 Signing & Capabilities。
3. 安装到 iOS 17+ 设备。
4. 输入 Server URL 和 CLI 生成的 Pair Code 完成配对。

### 2.3 适合的使用场景

- 不在电脑前时，远程让 Agent 执行研究任务。
- 收到工具调用请求时，通过手机审批。
- 让 Agent 定期汇总 `CLI_research/results/` 的回测结果。
- 未来接入模拟盘后，用手机批准“生成订单意图”，但不直接批准无约束实盘自动下单。

### 2.4 局限

- 它不是量化系统本身，不负责数据、策略、回测和风控。
- CLI Agent 部分仍处于改造状态，不能假设已经是稳定生产级交易控制台。
- 不应让它直接持有券商交易权限；交易权限必须由独立风控层和人工审批控制。

## 3. 项目二：CLI_research

### 3.1 功能

`CLI_research` 是当前最有实用价值的量化研究项目。它已经实现：

- A 股数据：`akshare`，失败时有备用源。
- 美股数据：`yfinance`，失败时有备用源。
- 本地存储：`data/daily/<market>/<symbol>.parquet`。
- 数据质检：输出 `data/quality_summary.txt`。
- 回测策略：
  - `sma_cross`：双均线策略。
  - `momentum`：动量轮动策略。
  - `boll_revert`：布林带均值回归策略。
- 回测结果：写入 `results/<run>/metrics.json`、净值图、CSV。
- Agent 约定：`/research`、`/backtest`、`/review`。

当前股票池在 `config/universe.yaml`：

- A 股：贵州茅台、五粮液、中国平安、招商银行、平安银行。
- A 股基准：沪深 300。
- 美股：AAPL、MSFT、NVDA、GOOGL、SPY。

### 3.2 使用方法

安装依赖：

```bash
cd /Users/brucehuang/Documents/CLI_research
uv sync --dev
```

运行测试：

```bash
uv run pytest
```

更新全部市场数据：

```bash
uv run python scripts/update_data.py
```

只更新某个市场：

```bash
uv run python scripts/update_data.py --market cn
uv run python scripts/update_data.py --market us
```

检查数据质量：

```bash
uv run python scripts/check_data.py
```

跑回测：

```bash
uv run python scripts/run_backtest.py --strategy sma_cross --market cn
uv run python scripts/run_backtest.py --strategy momentum --market us -p lookback=60 -p top_n=2
uv run python scripts/run_backtest.py --strategy boll_revert --market cn -p window=20 -p num_std=2
```

建议的日常 Agent 用法：

```text
/research 研究一个策略想法
/backtest momentum us lookback=60 top_n=2
/review
```

### 3.3 关键实现特点

`CLI_research` 的回测引擎有几个重要优点：

- 日频回测避免前视：`decision.loc[t]` 在 t 日收盘成交，赚取 t+1 收益。
- A 股约束：处理 T+1、涨跌停、停牌。
- 成本模型：A 股买卖成本不同，卖出包含印花税估计；美股预留滑点和点差。
- 组合级权重：策略输出目标仓位矩阵，而不是单只股票买卖点。
- 输出报告：方便长期追踪不同策略、参数和市场。

### 3.4 适合的使用场景

- 作为主力回测系统。
- 做参数扫描和策略对比。
- 维护研究笔记，形成自己的策略知识库。
- 用免费数据源低成本验证中低频策略。
- 先从日线策略做起，避免过早进入分钟线、高频和复杂实盘。

### 3.5 当前局限

- 当前本地没有 `results/` 目录，说明这次拉取后尚未在本机生成回测结果。
- 股票池太小，容易产生样本偏差。
- `STATUS.md` 提到混合数据源可能导致 volume 量纲不一致，成交量因子要先统一。
- 还没有完整样本内/样本外切分、walk-forward、参数网格扫描和模拟交易模块。
- 还不能直接作为实盘系统。

## 4. 项目三：gpt_quant

### 4.1 功能

`gpt_quant` 是一个更强调“研究路径可审计”的量化验证框架。它当前不是主力数据系统，而是用于定义安全边界和验证流程。

已有模块：

- `domain`：市场、K 线、信号、交易方向。
- `calendars`：A 股与美股交易时段。
- `strategy`：策略接口与移动均线示例。
- `backtest`：单标的长仓回测。
- `risk`：策略验证闸门。
- `data.csv_loader`：CSV 行情加载。
- `agent.runtime`：Agent 多轮 tool call 循环。
- `tools`：强类型工具注册、风险等级、执行器。
- `audit`：审计事件。

### 4.2 使用方法

安装：

```bash
cd /Users/brucehuang/Documents/gpt_quant
python -m pip install -e .
```

运行测试：

```bash
python -m unittest discover -s tests
```

运行示例回测：

```bash
python -m gpt_quant.cli sample-backtest
```

运行 Agent demo：

```bash
python -m gpt_quant.cli agent-demo
```

从 CSV 回测：

```bash
python -m gpt_quant.cli backtest-csv path/to/bars.csv --short-window 5 --long-window 20
```

CSV 至少包含：

```csv
timestamp,open,high,low,close,volume,symbol,market
2026-01-02T09:30:00,10,10.5,9.9,10.2,100000,600000,CN_A
```

### 4.3 风控闸门

`gpt_quant/src/gpt_quant/risk.py` 默认验证策略：

- 数据覆盖：至少 252 天。
- 完成交易：至少 20 笔。
- 总收益：不低于 0。
- 夏普：不低于 0.5。
- 最大回撤：不超过 20%。
- 模拟交易：至少 20 天。
- 人工复核：必须通过。

输出决策：

- `BLOCKED`：证据不足或风险不达标。
- `PAPER_TRADING`：回测初步合格，但还需要模拟交易。
- `LIVE_READY`：回测、模拟交易和人工复核都通过，可进入实盘审批。

### 4.4 适合的使用场景

- 作为策略上线前的风控标准模板。
- 把 `CLI_research` 的回测结果映射为统一验证报告。
- 未来做模拟交易和实盘前审批。
- 记录 Agent 工具调用、模型成本、终止原因和审计事件。

### 4.5 当前局限

- 当前依赖为空，说明项目还处于轻量原型阶段。
- 数据接入不如 `CLI_research` 完整。
- 回测是单标的示例，不如 `CLI_research` 的组合级回测实用。
- 风控阈值偏 MVP，若目标是年化 25%，验证标准需要显著提高。

## 5. 三者区别

| 维度 | aicodingagent | CLI_research | gpt_quant |
| --- | --- | --- | --- |
| 类型 | AI Agent 控制与远程操作框架 | 量化研究与回测项目 | 量化 Agent 与风控验证框架 |
| 语言 | TypeScript、Node.js、Swift | Python | Python |
| 是否直接处理行情 | 否 | 是 | 仅 CSV/示例，待扩展 |
| 是否有回测 | 否 | 有，组合级 | 有，单标的示例 |
| 是否有风控闸门 | 工具权限审批 | 回测指标，但闸门较弱 | 有明确验证闸门 |
| 是否适合实盘 | 不直接适合 | 不直接适合 | 不直接适合，定义了实盘前门槛 |
| 最佳用途 | 远程入口、审批、编排 | 主研究系统 | 风控、审计、上线制度 |

## 6. 三者关系

建议不要合并成一个大项目，而是保持分层：

### 6.1 控制层：aicodingagent

负责：

- 远程发起研究任务。
- 查看回测摘要。
- 审批低风险文件写入、报告生成、参数扫描任务。
- 未来审批模拟盘任务。

禁止：

- 直接下实盘订单。
- 让 LLM 持有券商密钥。
- 用自然语言绕过风控规则。

### 6.2 研究层：CLI_research

负责：

- 更新行情数据。
- 做数据质量检查。
- 跑策略回测。
- 保存 `metrics.json`、图表和交易明细。
- 形成研究笔记。

增强方向：

- 增加更大的股票池。
- 增加参数扫描脚本。
- 增加样本内/样本外切分。
- 增加 walk-forward 验证。
- 增加组合风控约束。

### 6.3 风控层：gpt_quant

负责：

- 定义策略进入下一阶段的硬门槛。
- 记录审计事件。
- 区分 Research、Paper、Live-Confirm、Live-Limited 模式。
- 阻止没有足够证据的策略进入实盘。

增强方向：

- 读取 `CLI_research/results/*/metrics.json`。
- 输出统一验证报告。
- 增加模拟交易天数、实盘审批、最大仓位、单日亏损限制。

## 7. 面向年增长 25% 的现实拆解

### 7.1 目标含义

资产每年增长 25% 意味着：

```text
第 1 年：1.25 倍
第 2 年：1.56 倍
第 3 年：1.95 倍
第 4 年：2.44 倍
第 5 年：3.05 倍
```

约 3.1 年翻倍。这个目标显著高于常见长期分散股票投资预期。Investor.gov 对长期分散美股投资给出的常用估算是约 7% 到 10% 年化，且所有投资都有风险。因此，25% 年增长必须被视为高风险进攻目标，而不是常规理财目标。

### 7.2 两种完成路径

路径 A：资产增长 = 投资收益 + 新增本金

这是更现实的路径。比如市场收益只贡献 8%-12%，剩余部分通过持续现金流投入、提高收入、控制支出、税务优化和策略超额收益补齐。

路径 B：仅靠投资组合年化 25%

这是高难度高波动路径。必须接受：

- 可能出现较大回撤。
- 策略可能阶段性失效。
- 回测高收益可能来自过拟合、幸存者偏差或数据问题。
- 若使用杠杆，亏损可能放大，甚至超过本金。

建议采用路径 A，把 25% 作为“净资产增长率目标”，而不是要求每一笔投资都达到 25% 年化。

## 8. 使用场景设计

### 场景 1：每周策略研究

目标：每周产生 1 个可验证策略假设。

流程：

1. 用 `aicodingagent` 远程发起研究问题。
2. 在 `CLI_research/docs/research/` 写研究笔记。
3. 在 `CLI_research/src/quant/strategies/` 实现策略。
4. 用 `scripts/run_backtest.py` 回测。
5. 保存结果到 `results/<run>/`。
6. 用 `gpt_quant` 的标准判断是否 `BLOCKED`。

### 场景 2：每月策略筛选

目标：从多个策略中筛出候选组合。

候选策略必须满足：

- 至少覆盖 3 年以上数据，最好覆盖牛市、熊市和震荡期。
- 样本外结果不能明显劣化。
- 最大回撤低于预设阈值。
- 交易次数足够，不能靠 1-2 次偶然交易撑起收益。
- 对参数变化不敏感。
- 扣除交易成本、滑点、税费后仍然有效。

### 场景 3：季度组合复盘

目标：判断是否继续投入资金。

检查：

- 年初至今收益。
- 最大回撤。
- 策略相关性。
- 是否跑输基准。
- 是否偏离原始假设。
- 是否存在数据源异常或执行偏差。

### 场景 4：模拟盘准入

目标：只让通过研究验证的策略进入模拟交易。

最低门槛建议高于 `gpt_quant` 默认值：

| 指标 | 建议门槛 |
| --- | --- |
| 数据覆盖 | 至少 3-5 年 |
| 交易次数 | 至少 50 笔，低频策略可按年份评估 |
| 样本外表现 | 正收益，且不显著低于样本内 |
| 最大回撤 | 低于 20%-25%，或符合个人承受能力 |
| Sharpe | 最好大于 1.0 |
| Calmar | 最好大于 1.0 |
| 参数稳定性 | 相邻参数不能从优秀变成崩溃 |
| 模拟盘 | 至少 3 个月，最好 6 个月 |
| 人工复核 | 必须通过 |

### 场景 5：实盘前审批

实盘只允许小资金、分阶段、可停止。

建议：

- 第一阶段只用总资产的 5%-10% 做策略资金。
- 单策略不超过总资产 5%。
- 单日亏损达到 1%-2% 策略资金，停止新开仓。
- 策略资金最大回撤达到 10%，减半。
- 策略资金最大回撤达到 15%-20%，暂停并复盘。
- 不使用未经验证的杠杆。

## 9. 12 个月使用计划

### 第 0 阶段：准备期，1-2 周

目标：让系统可运行、可复现。

任务：

- 跑通 `CLI_research` 的 `uv sync --dev`、测试、数据更新、数据质检。
- 跑通 `gpt_quant` 的测试、`sample-backtest`、`agent-demo`。
- 决定是否部署 `aicodingagent` 中继和 iPhone App。
- 建立统一目录：
  - `CLI_research/results/`
  - `CLI_research/docs/research/`
  - `CLI_research/docs/monthly_review/`

通过标准：

- 能稳定更新数据。
- 能生成至少 3 组回测结果。
- 每个结果都有 `metrics.json`。

### 第 1 阶段：基线期，第 1 个月

目标：建立基准，不急着追 25%。

任务：

- 跑通三个基线策略：
  - `sma_cross`
  - `momentum`
  - `boll_revert`
- 分别在 A 股和美股运行。
- 对比基准：沪深 300、SPY。
- 记录每个策略的收益、回撤、夏普、换手率、交易次数。

通过标准：

- 明确哪些策略跑输基准。
- 明确哪类策略有继续研究价值。
- 不做实盘投入。

### 第 2 阶段：扩展股票池，第 2-3 个月

目标：降低样本偏差。

任务：

- A 股从 5 只扩展到沪深 300 或至少 50-100 只流动性较好股票。
- 美股从 4 只扩展到纳指 100、标普 100 或自选行业池。
- 统一成交量量纲，避免量价因子错误。
- 增加数据质量报告字段：缺失率、停牌、异常涨跌幅、复权检查。

通过标准：

- 每个市场至少有一个稳定股票池。
- 数据质量报告可供 Agent 摘要读取。

### 第 3 阶段：策略工厂，第 3-6 个月

目标：系统地产生和淘汰策略。

优先策略方向：

- 动量轮动：不同 lookback、rebalance、top_n。
- 波动率目标仓位：降低大回撤。
- 趋势 + 现金过滤：市场弱势时降低仓位。
- 多市场分散：A 股、美股、ETF 分开测试。
- 基准相对强弱：只在策略强于基准时持仓。

禁止方向：

- 只凭大模型判断买卖。
- 高频交易。
- 复杂期权策略。
- 未处理成本、滑点、复权、幸存者偏差的策略。

通过标准：

- 每个策略都有研究笔记、参数表和回测结果。
- 至少 80% 的策略被淘汰。
- 少数候选策略进入样本外验证。

### 第 4 阶段：样本外和模拟盘，第 6-9 个月

目标：证明策略不是只适配历史。

任务：

- 增加样本内/样本外切分。
- 增加 walk-forward 验证。
- 用 `gpt_quant` 风控闸门评估策略。
- 对候选策略做 3-6 个月模拟盘。
- 每周复盘模拟盘与回测偏差。

通过标准：

- 样本外仍为正收益。
- 模拟盘没有明显漂移。
- 回撤在可接受范围内。
- 人工复核通过。

### 第 5 阶段：小资金实盘，第 9-12 个月

目标：验证执行，不追求立刻满仓收益。

任务：

- 只使用风险资金。
- 从总资产 5%-10% 开始。
- 每个策略单独记账。
- 每周复盘执行偏差。
- 每月决定加仓、减仓、暂停或淘汰。

通过标准：

- 实盘表现与模拟盘差异可解释。
- 没有越权交易。
- 没有超过预设最大回撤。
- 没有因为追求 25% 目标而扩大不可承受风险。

## 10. 年增长 25% 的组合执行框架

建议把资产分为三层，而不是全部押在量化策略上：

| 层级 | 比例建议 | 目标 | 工具使用 |
| --- | --- | --- | --- |
| 核心资产 | 60%-80% | 长期分散、降低毁灭性风险 | 不依赖这三个项目，可用指数、现金、债券等个人适合的资产 |
| 策略资产 | 10%-30% | 争取超额收益 | 由 `CLI_research` 研究，`gpt_quant` 审核 |
| 现金/机会资金 | 10%-20% | 应急、等待机会、降低被迫卖出 | 不参与高风险策略 |

如果坚持以 25% 为年度净资产目标，建议把目标拆成：

```text
年度净资产增长 = 新增本金贡献 + 核心资产收益 + 策略资产超额收益
```

示例目标拆解：

- 新增本金贡献：8%-12%。
- 核心资产收益：5%-8%。
- 策略资产超额收益：5%-10%。
- 合计目标：18%-30%。

这样比“全部资金每年投资收益 25%”更现实，也更能控制破产风险。

## 11. 每周、每月、每季度操作清单

### 每周

- 更新数据。
- 跑数据质量检查。
- 跑候选策略回测。
- 写一篇研究笔记。
- 淘汰不合格策略。

命令：

```bash
cd /Users/brucehuang/Documents/CLI_research
uv run python scripts/update_data.py
uv run python scripts/check_data.py
uv run python scripts/run_backtest.py --strategy momentum --market us -p lookback=60 -p top_n=2
```

### 每月

- 汇总 `results/`。
- 对比策略与基准。
- 检查是否出现参数过拟合。
- 更新候选策略名单。
- 调整下一月研究方向。

### 每季度

- 做组合级复盘。
- 判断策略是否进入模拟盘。
- 检查资产增长是否来自真实收益、新增本金，还是一次性运气。
- 重设风险预算。

## 12. 必须坚持的风险规则

1. LLM 只能做研究助手，不能做最终交易决策。
2. 任何策略没有样本外验证，不进入模拟盘。
3. 任何策略没有模拟盘，不进入实盘。
4. 任何策略没有人工复核，不进入自动化。
5. 单策略不能决定全年收益目标。
6. 不为了追求 25% 年增长而临时扩大仓位。
7. 不用生活费、应急资金、借贷资金做高风险策略。
8. 如果最大回撤超过预设阈值，先暂停，不加仓摊平。
9. 所有回测必须扣除成本、滑点、税费。
10. 每次策略调整都要留下文档和结果记录。

## 13. 下一步工程建议

优先级从高到低：

1. 在 `CLI_research` 增加参数扫描脚本，避免手工一条条跑。
2. 增加样本内/样本外切分。
3. 增加 `results/` 汇总脚本，输出月度策略排行榜。
4. 把 `gpt_quant` 的 `ValidationPolicy` 改造成可读取 `CLI_research/results/*/metrics.json` 的验证器。
5. 用 `aicodingagent` 编排每周任务和手机审批。
6. 模拟盘模块成熟前，不开发实盘下单。

### 13.1 实施进度（2026-07-20）

已完成：

- `CLI_research` 参数扫描脚本、70/30 或指定日期 holdout、相邻参数稳健性检查。
- `CLI_research` 结果汇总与月度候选榜；只有具备样本外和参数稳健性证据的结果可入榜。
- `gpt_quant` 对 `CLI_research/results/*/metrics.json` 的严格验证适配器与 CLI 入口。
- 11 个行情序列更新与质量检查，六组基线 holdout、A 股和美股各 18 组动量参数扫描。

本轮结论：A 股动量网格无组合通过参数稳健性；美股动量网格表现较强但最佳组合样本外仅 15 次完整退出，仍被 50 次交易证据门槛阻止进入模拟盘。下一工程阶段是扩展股票池、walk-forward 和模拟盘记账，不开发实盘下单。

## 14. 参考资料

本地项目资料：

- `aicodingagent/README.md`
- `aicodingagent/docs/DEPLOYMENT_GUIDE.md`
- `aicodingagent/relay/README.md`
- `aicodingagent/iphone-app/README.md`
- `CLI_research/README.md`
- `CLI_research/docs/REQUIREMENTS.md`
- `CLI_research/docs/STATUS.md`
- `CLI_research/src/quant/backtest/engine.py`
- `CLI_research/src/quant/strategies/baselines.py`
- `gpt_quant/README.md`
- `gpt_quant/docs/product_requirements.md`
- `gpt_quant/docs/development_plan.md`
- `gpt_quant/src/gpt_quant/risk.py`
- `gpt_quant/src/gpt_quant/agent/runtime.py`

外部风险与投资基础资料：

- Investor.gov: Introduction to Investing  
  https://www.investor.gov/introduction-investing
- Investor.gov: Asset Allocation and Diversification  
  https://www.investor.gov/introduction-investing/getting-started/asset-allocation
- Investor.gov: What is Risk?  
  https://www.investor.gov/introduction-investing/investing-basics/what-risk
- FINRA: Day Trading  
  https://www.finra.org/investors/investing/investment-products/stocks/day-trading
- Investor.gov: Understanding Margin Accounts  
  https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-29
