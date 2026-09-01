# 实用指南：用系统研究问题，判断证据，形成结论

适用日期：2026-08-30，M7-S5。主目录：`/Users/brucehuang/Documents/CLI_research`；验证器目录：`/Users/brucehuang/Documents/gpt_quant`。

本指南教你做可复查的研究，不提供个股买卖建议。先记住：**程序运行成功、回测赚钱、证据通过验证、允许实盘交易，是四件不同的事。** 历史表现不能保证未来结果，展示方式也可能影响你对表现的判断。[SEC 投资者教育：Performance Claims](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-47)

## 1. 系统现在能帮你做什么

| 你想解决的问题 | 现在可用的能力 | 不能据此声称什么 |
|---|---|---|
| 本地价格能不能用于研究 | 数据更新、来源/量纲质检、缺失报价识别 | 质检通过不等于数据源完整、复权正确或覆盖全市场 |
| 某个明确策略过去怎样 | 次日开盘模拟成交、费用、仓位限制和探索回测 | 全样本表现不能证明预测能力 |
| 参数是不是挑出来的巧合 | 训练选参、验证段、独立最终测试、逐折滚动验证 | 多次试验后挑最好结果仍然可能过拟合 |
| 证据能否进入下一步研究 | GPT 项目的独立验证器，逐项给出失败原因 | 当前最高只返回 `PAPER_TRADING`，它不是买入信号或实盘授权 |
| 在固定美股自选池中发现当日异动 | 手动运行 `quant scan`，计算量比、动量和收盘突破并确定性排名 | 不是全美股覆盖、上涨概率、未来表现验证或自动交易 |
| 跟踪异动后的表现 | `quant signals track` 按交易日更新 1/3/5/10/20 日描述性、可执行和基准超额收益 | 少量历史观察不能证明信号未来有效 |
| 完成每日研究跑批 | `quant daily` 依次更新、质检、扫描、跟踪并生成报告，阶段状态可重试 | 还没有自动安装系统调度，也不会自动下单 |

本轮新结果会标记 `schema_version=2`、`execution_model=next_open_v1`。旧的同日收盘回测仍可显式运行，但不能直接拿来通过新验证器。旧模式仅保留成交时点的比较，不恢复历史版本中已经修复的资金错误。

## 2. 第一次使用：先做一个不联网的练习

在终端运行：

```bash
cd /Users/brucehuang/Documents/CLI_research
.venv/bin/python scripts/demo_research.py
```

这条命令不需要 API Key、不拉行情、不连接券商，只用合成的 DEMO_A/DEMO_B 序列演示整个研究流程。输出中的 `metrics_path` 是详细摘要的位置；每次运行生成一个新目录，不覆盖真实研究。

本次已运行的例子：[查看示例摘要](../results/tutorial/scan_momentum_us_20260829-003540-400617/metrics.json)。示例只有学习用途，验证器会明确拒绝把它当作真实研究证据。

### 练习：面对一个“漂亮结果”，你应该怎么想

本例最终测试为 120 个合成交易日，输出如下（百分比由小数换算）：

| 指标 | 示例输出 | 应该怎样理解 |
|---|---:|---|
| 总收益 | +34.59% | 只是这段合成数据的收益 |
| 年化收益 | +86.62% | 是将短区间数学年化，不是未来一年的收益预测 |
| Sharpe | 6.073 | 数字很高，但合成数据可人为制造这种结果 |
| 最大回撤 | -0.80% | 只描述样本内经历过的回撤，不是未来亏损上限 |
| 基准总收益 | +34.73% | 本策略还略低于基准，不能说创造了超额收益 |
| 完成持仓次数 | 0 | 只买入后持有，没有一次完整退出；不能说“大量交易验证过” |

**合适的结论：**“流程能在合成数据上完成训练、验证和最终测试；结果不支持任何真实交易结论。虽然收益和 Sharpe 很高，但没有真实市场证据，也没有完成持仓样本，且未超过示例基准。”

**不合适的结论：**“这个策略年化 86%，可以投入资金。”

这个练习的目的，是让你先检查数据、比较对象与证据量，再看收益数字。

## 3. 提出一个能验证的问题

不要从“帮我找黑马”开始。先写成可被反驳的问题，例如：

> 在预先确定的美股股票池中，按过去 60/120/250 个交易日动量选择标的、每 20 个交易日调整，扣除费用后，能否在未用于选参的时期保持正收益，并达到我预先写下的回撤限制？

运行前写下这六项，保存到 `docs/research/` 下的新笔记：

1. **研究目标：**追求绝对正收益、超过 SPY，还是降低回撤？不要看到结果后才更换目标。
2. **股票池：**哪些标的、为什么选它们、是否包含当时已经退市或后来被剔除的标的。
3. **数据边界：**开始日期、截止日期、训练/验证/最终测试的边界。
4. **策略与参数网格：**一次尝试哪些组合；不要无限添加参数直到结果好看。
5. **费用与限制：**成交时点、成本假设、持仓限制、缺报价时如何处理。
6. **通过与否的条件：**最低样本数、最大回撤、是否需要基准超额等；同时写下会否定假设的情况。

当前系统费用是研究假设，不是你券商的实际收费报价。手续费、点差与滑点会影响净收益，比较策略时必须使用一致口径。[SEC：费用如何影响投资组合](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/updated)

## 4. 准备数据：先看质量，再看收益

下面的更新命令会联网并改变本地行情文件；本次开发没有替你执行真实更新：

```bash
cd /Users/brucehuang/Documents/CLI_research
.venv/bin/python scripts/update_data.py --market us --universe baseline
.venv/bin/python scripts/check_data.py --quiet
```

先看终端中的成功数量和 `errors/warnings`，再根据输出路径查看质量摘要。质检工具的 `--quiet` 只减少终端输出，不代表忽略错误；它会检查本地各市场，并非只检查美股。

遇到以下情况先停止研究结论：关键标的无历史数据；时间区间不同；来源/复权含义不清楚；成交量单位未确认；数据仍是旧日期；起始基准报价缺失。

`config/universe.yaml` 中的当前自选池不等于真实历史股票池。`config/universe_history.example.csv` 只是格式示例，不能复制后当作消除幸存者偏差的证据。没有可核实的历史成分数据，就在结论中注明这一限制，并接受验证器的阻止。

### 手动运行美股日线 Radar

更新并质检数据后，可以只读取本地日线做一次固定自选池扫描：

```bash
.venv/bin/quant scan --workspace config/workspace.yaml \
  --market us --profile momentum_volume
```

默认配置在 `config/radar.yaml`，股票来自 `config/universe.yaml` 的 `extended` 快照并排除 SPY。扫描日默认取已加载自选池中的最新日期，也可用 `--as-of YYYY-MM-DD` 重现历史快照。JSON 保存到 `results/radar/us/<profile>/<日期>/scan.json`；同一配置和数据快照重复运行会得到相同排名、快照哈希和 `signal_id`。

首版规则是：当日量比至少 1.5，且 5 日收益至少 3% 或当日收盘价突破此前 20 个有效交易日最高收盘价；同时检查最低价格、前 20 日平均成交额、至少 61 条历史、成交量为股、复权字段一致和当日非零成交量。20/60 日突破都只比较此前收盘价，不使用当日之后的数据。评分只是透明排序分，不是上涨概率。

`status=DEGRADED` 或退出码 2 表示至少一个配置标的无法计算，具体看 `excluded[].reasons`。价格、流动性或信号阈值未通过是正常过滤；`no_data`、`missing_bar_on_signal_date`、`volume_unit_not_share`、`adjustment_missing_or_mixed` 和 `insufficient_history` 才是需要处理的数据缺口。零候选也可能是正常结果，不能为了得到名单而临时降低阈值。

### 更新 Radar 信号的后续表现

扫描结果保存在按日期分隔的 `scan.json` 后，运行：

```bash
.venv/bin/quant signals track --workspace config/workspace.yaml \
  --market us --profile momentum_volume
```

命令会发现该 profile 已保存的所有扫描文件，以 `signal_id` 去重登记候选，并原子更新 `results/radar/us/<profile>/tracking.json`。同一扫描重复执行不会增加重复信号。默认以 SPY 的本地日线日期作为美股交易日序列，不用自然日猜测“第 5 天”。

每个期限分别保存两套口径：

- `descriptive`：信号日收盘价到未来收盘价的描述性收益，以及同期 SPY 收盘收益和超额。
- `executable`：下一交易日开盘到目标日收盘，按配置扣买卖双边费用，并与相同成交时点、相同费用口径的 SPY 比较。

`PENDING` 表示真实交易日还没有走够；`MISSING` 表示期限已经到达但标的或基准缺少所需开盘/收盘，命令退出码为 2。只有 `config/radar.yaml` 的 `tracking.delistings` 明确记录最终交易日时，目标日在其后才标记为 `DELISTED`；系统不会把普通缺 K 线猜成退市。缺失或退市收益都不会填 0。追加新的行情只会使新期限成熟；已经成熟的短期限结果仍由原目标交易日决定。

### 一条命令完成每日 Radar 跑批

```bash
.venv/bin/quant daily --workspace config/workspace.yaml \
  --market us --profile momentum_volume
```

它按顺序执行：增量更新美股日线 → 数据质检 → 当日 Radar → 历史信号跟踪 → JSON/Markdown 报告。任务状态写入 `results/radar/us/<profile>/jobs/<纽约日期>.json`，报告写入同一 profile 的 `reports/`。每个阶段都有 `PENDING/RUNNING/SKIPPED/COMPLETED/FAILED` 状态和简短错误；某阶段失败后，同一日期重跑会增加 `attempt` 并安全重做全部幂等阶段。

同一日期和 profile 使用同一个 `job_id`。行情增量合并会按日期去重，扫描覆盖同一交易日文件，跟踪按 `signal_id` 去重，报告覆盖同名日期，因此重跑不会制造重复信号。若只想用现有本地数据验收，必须显式传 `--skip-update`；这会在状态中留下 `SKIPPED`，不会伪装成已经更新。

退出码 0 表示所有阶段完成且没有警告；退出码 2 表示任务失败或完成但含数据降级、质量警告或成熟结果缺失。查看 JSON 的 `status`、`failed_stage` 和 `stages`，不要只看是否生成了 Markdown。该命令没有安装 launchd/cron，也不连接券商。

## 5. 预览实验边界，然后冻结实验

以下日期只是命令示例，应根据质量摘要选择实际可用区间，并在查看成绩前决定。不要为了提高结果而反复调整开始/结束日期。

```bash
.venv/bin/python scripts/run_parameter_scan.py \
  --strategy momentum --market us --universe baseline \
  --start 2018-01-01 --end 2026-07-20 \
  --study-file results/studies/momentum_001.json \
  --train-ratio 0.6 --validation-ratio 0.2 \
  -p lookback=60,120,250 -p top_n=1,2 -p rebalance=20 \
  --walk-forward --wf-train-days 756 --wf-test-days 126 \
  --preview
```

`--preview` 只显示实际日期边界，不计算成绩、不创建实验记录、不消耗最终测试。记下它输出的训练截止日期。

| 区间 | 允许做什么 | 不允许做什么 |
|---|---|---|
| 训练，前 60% | 比较参数，选择一组，检查邻参 | 用后面区间的表现倒过来挑参数 |
| 验证，中间 20% | 检查选定参数是否保持稳定 | 将验证集改名为最终测试集 |
| 最终测试，后 20% | 对冻结后的方案做一次检验 | 为所有参数做最终测试排行榜，再挑冠军 |

时间序列不能随意打乱后把“过去”和“未来”混在一起。测试数据参与调参，会让独立评估失去意义。[scikit-learn 官方交叉验证说明](https://scikit-learn.org/stable/modules/cross_validation.html)

需要固定具体日期时，可用 `--train-end YYYY-MM-DD --final-start YYYY-MM-DD` 一起替代默认的比例边界。最终测试日期不会在同一实验中随追加数据自动移动：数据指纹变更会被拒绝。

### 可选：只在训练区间做探索回测

```bash
.venv/bin/python scripts/run_backtest.py \
  --strategy momentum --market us --universe baseline \
  --start 2018-01-01 --end 2022-12-30 \
  -p lookback=120 -p top_n=2 -p rebalance=20
```

这里的结束日期仍是示例：应改为预览输出的训练截止日期或更早日期。输出类型为 `exploratory_backtest`，不能用于正式准入。不要先浏览全区间收益后，再声称后半段从未使用。

## 6. 正式运行：一份实验记录对应一套冻结规则

确认预览、数据和预先写好的规则后，执行第 5 节同一条扫描命令，将最后的 `--preview` 改为 `--compact`。

也可以改用 M7-S4 的统一入口；它会先检查目标市场数据，再运行同一套正式扫描并交给 `gpt_quant` 验证：

```bash
.venv/bin/quant workflow --workspace config/workspace.yaml \
  --strategy momentum --market us --universe baseline \
  --membership-file config/universe_history.csv \
  --start 2018-01-01 --end 2026-07-20 \
  --study-file momentum_001.json \
  -p lookback=60,120,250 -p top_n=1,2 -p rebalance=20 \
  --walk-forward --wf-train-days 756 --wf-test-days 126
```

统一入口不是预览命令：它同样可能消耗最终测试。相对的 `--study-file` 固定写入 `var/studies/`，结果固定写入配置中的 `results/`，不会随终端 cwd 改变。退出码 2 表示数据、契约或研究闸门已阻止流程；不要把 `BLOCKED` 当作程序运行成功后的可交易结论。

系统会做以下工作：

1. 保存数据指纹、源码指纹、边界、费用、参数网格和配置。
2. 只用训练段选参；`ranking.csv` 中的排名是训练排名。
3. 验证选定参数；启用滚动验证时，每折重新用该折训练段选参。
4. 验证不合格则输出 `final_test_status=not_run`，不查看最终测试成绩。
5. 通过前置检查才消耗并运行最终测试，写出 `metrics.json`。

实验文件中的 `final_test_consumed` 在最终测试执行前写入；即使之后运行失败，也不能冒充未看过该测试。已经完成的实验应直接阅读保存的结果，不反复执行。

如果更换参数、日期、数据或代码，同一实验记录会拒绝继续使用。这是为了留下清楚的研究边界。**另起一个文件名不会让已经看过的历史重新变得独立**：当前防重用保护只覆盖同一实验文件，你仍需在研究笔记中记录所有尝试和已接触过的测试区间。

滚动验证输出的各折是独立账户评估，不是一条连续实盘净值；程序不再将它们简单拼接成“连续收益”。需要连续持仓路径时，应另行实现并验证衔接。

## 7. 怎样阅读一份结果

打开命令输出的 `run_dir` 下的 `metrics.json`，按下面顺序读，不要先找最高 Sharpe：

| 先看什么 | 对应字段 | 你要回答的问题 |
|---|---|---|
| 结果身份 | `schema_version`、`artifact_type`、`execution_model`、`synthetic_data` | 是新口径、真实研究，还是旧结果/示例/探索？ |
| 选择过程 | `research_protocol` | 哪些日期用于选参？参数是否在最终测试前冻结？ |
| 是否真正测试 | `validation.final_test_status/reason` | 完成了，还是因为前置验证失败而未运行？ |
| 数据和费用 | `data_snapshot_sha256`、`costs`、各段 `stale_valuation_days` | 数据能否复现？是否有陈旧估值？费用假设是什么？ |
| 样本量 | 各段 `n_days`、`completed_trades`、`end_open_positions` | 有多长历史、多少次完整退出？有没有只买不卖？ |
| 收益与风险 | 最终段 `total_return/cagr/sharpe/max_drawdown/calmar` | 是否符合事前目标，而非某一个数字好看？ |
| 比较与稳健性 | `benchmark_status/benchmark/excess_cagr`、`parameter_robustness`、`walk_forward` | 是否超过预设基准？邻参和不同时间段是否也有支持？ |

注意：`daily_win_rate` 是有收益变化的日子中正收益日的比例，不是逐笔交易胜率。`completed_trades` 当前统计标的从持有到清空的次数，不等于相互独立的交易样本。低波动或短样本可能让比率异常高；Calmar 为 null 时不要自行当作无穷大或“完美策略”。

`benchmark_status` 不可用时不能声称跑赢基准。收益为正也不必然意味着策略有效：上涨市场中，简单持有基准可能更好。

## 8. 用验证器检查“还差什么”

把下面路径替换为你自己的新研究摘要路径；也可以直接使用示例路径练习，预期结果为 `BLOCKED`：

```bash
PYTHONPATH=/Users/brucehuang/Documents/gpt_quant/src \
/Users/brucehuang/Documents/CLI_research/.venv/bin/python -m gpt_quant.cli validate-cli-result \
  /Users/brucehuang/Documents/CLI_research/results/tutorial/scan_momentum_us_20260829-003540-400617/metrics.json
```

查看 `decision` 和每项 `checks`，不要只看进程退出码；当前验证命令即使输出 `BLOCKED` 也可能正常退出。

| 结果/原因 | 可以得出的结论 | 下一步 |
|---|---|---|
| `BLOCKED`，协议或执行模型不符 | 结果口径不符合当前准入要求 | 使用新流程重新研究，不能改 JSON 标记绕过检查 |
| 缺历史股票池 | 存在幸存者偏差方面的证据缺口 | 寻找可核实成分来源，或保持研究观察状态 |
| 样本不足或最终测试未运行 | 证据不够，不等于策略必定无效 | 说明缺口，增加真正新的观察，不降低标准凑通过 |
| 最终测试亏损或风险超标 | 当前证据不支持事前假设/约束 | 记录失败原因，停止宣称有效；新想法要重新登记 |
| `PAPER_TRADING` | 研究证据通过当前检查，可以讨论模拟验证 | 先验收 S3 的模拟账本与执行衔接，再持续观察 |
| `PAPER_TRADING` 且模拟天数达标 | 只表示持久化模拟账本满足当前观察门槛 | 当前命令仍保持 `PAPER_TRADING`；独立签名批准包尚未实现，不产生实盘授权 |

当前代码默认要求完整历史至少 756 个交易日、最终段完成持仓至少 50 次、最终段正收益、Sharpe/Calmar 不低于 1、最大回撤不超过 20%，并检查时点股票池、验证稳定性、滚动验证与邻参。它们是项目内的筛选规则，不是经过证明的盈利保证。

S3 已实现本地模拟账本的日期、证据哈希、信号重放和执行价格时效保护；新口径信号不再携带可冒充成交价的收盘执行价格。它仍是本地确定性模拟，不连接券商，也不代表实盘授权。

## 9. 把结果写成可复查的结论

每次研究最后用这份模板，而不是只说“不错/不好”：

```text
研究问题：
事前通过/否定条件：
数据与股票池：来源、区间、时点成员证据、快照标识。
方法：参数选择区间、冻结参数、成交规则、费用。
支持证据：最终测试结果、样本数、基准比较、稳定性。
反对证据与缺口：未通过项目、缺失数据、偏差和未覆盖风险。
结论：支持继续研究 / 证据不足 / 不支持当前假设。
下一步：一个明确动作；不改变已经看过的测试区间的身份。
关联文件：metrics.json 路径、实验记录路径。
```

**假设例子，不来自你的真实研究：**最终测试收益 +15%，同期 SPY +24%，回撤 -18%，完成持仓 8 次。若事前目标是“跑赢 SPY”，结论应是“当前证据不支持”；如果只说“赚了 15%，策略有效”，就遗漏了目标、比较对象和样本不足。不能看到这个结果后临时把目标改为“只求正收益”。

你可以把摘要交给研究助手，并要求：

> 只读取这次实验的 metrics.json 和研究笔记，不读原始行情或交易明细。先核对数据划分和执行模型，再分别列出支持证据、反证、缺口，按事前目标给出结论。不要自动改参数、降低阈值、重跑最终测试或给出下单指令。

## 10. 平时怎样安排使用

每次研究先确认数据状态，一次只研究一个明确假设。结果出来就记录结论；失败结果也保留，否则以后只能看到幸存的“成功案例”。

需要复盘已有结果时：

```bash
cd /Users/brucehuang/Documents/CLI_research
.venv/bin/python scripts/summarize_results.py --month 2026-08
```

月份当前是报告标签，脚本会汇总结果目录下的记录，不是严格按月份过滤。展示顺序不按最终测试收益挑冠军；报告仍需独立验证器复核。该命令会重写对应月份报告，已有人工笔记请另存。

常见报错：`no local data/missing local history` 先查数据；`study inputs/snapshot changed` 检查是否改了冻结实验；`final test already consumed` 阅读已保存结果；`.lock` 文件存在先确认是否有进程在运行，不能盲目删除后并发重跑。

当前边界：未实现完整交易日历、所有A股板块交易规则、真实订单撮合或分钟级成交；免费来源的时效和复权一致性仍需逐次验证。自定义策略必须通过“改变未来数据不改变历史信号”的因果性测试；系统隔离了选参区间，但不会自动证明任意策略代码没有前视逻辑。

**最值得带走的习惯：先写问题和失败条件，再运行；先核对证据，再看收益；允许结论是“暂时不知道”。**

## 11. 从合格证据进入本地模拟观察

先运行完全离线案例，学习信号为什么只能执行一次，以及怎样区分“系统保护有效”和“策略有效”：

```bash
cd /Users/brucehuang/Documents/gpt_quant
../CLI_research/.venv/bin/python -B scripts/demo_paper_workflow.py
```

逐项推理见 [模拟信号案例](CASE_STUDY_PAPER_SIGNAL.md)。案例使用合成证据，只验证账本规则，不验证投资策略。

真实流程必须从通过验证器的 `metrics.json` 开始。以下路径和时间都是格式示例，必须替换成你自己的文件、真实下一交易日和带时区的价格时间：

```bash
# 1. 再次确认研究证据；decision 必须是 PAPER_TRADING
PYTHONPATH=/Users/brucehuang/Documents/gpt_quant/src \
/Users/brucehuang/Documents/CLI_research/.venv/bin/python -m gpt_quant.cli validate-cli-result \
  /absolute/path/to/metrics.json

# 2. 为该证据创建独立模拟账户
PYTHONPATH=/Users/brucehuang/Documents/gpt_quant/src \
/Users/brucehuang/Documents/CLI_research/.venv/bin/python -m gpt_quant.cli paper-init \
  /absolute/path/to/metrics.json /absolute/path/to/paper-state.json --cash 100000

# 3. 在更新并质检最新行情后，生成确定性的目标信号
cd /Users/brucehuang/Documents/CLI_research
.venv/bin/python scripts/generate_paper_signal.py \
  /absolute/path/to/metrics.json --output /absolute/path/to/paper-signal.json

# 4. 到真实后续交易时段，提供新的执行价格；参考收盘价不会被当作成交价
PYTHONPATH=/Users/brucehuang/Documents/gpt_quant/src \
.venv/bin/python -m gpt_quant.cli paper-rebalance \
  /absolute/path/to/paper-state.json /absolute/path/to/paper-signal.json \
  --execution-at '2026-08-31T09:31:00-04:00' \
  --price-as-of '2026-08-31T09:30:00-04:00' \
  --price AAPL=100.25 --price MSFT=520.10

# 5. 后续按不同交易日估值并查看报告
PYTHONPATH=/Users/brucehuang/Documents/gpt_quant/src \
.venv/bin/python -m gpt_quant.cli paper-mark \
  /absolute/path/to/paper-state.json --date 2026-08-31 \
  --price AAPL=101.00 --price MSFT=518.00
PYTHONPATH=/Users/brucehuang/Documents/gpt_quant/src \
.venv/bin/python -m gpt_quant.cli paper-report /absolute/path/to/paper-state.json

# 6. 复核模拟天数时必须读取账本；该命令仍不会输出实盘批准
PYTHONPATH=/Users/brucehuang/Documents/gpt_quant/src \
.venv/bin/python -m gpt_quant.cli validate-cli-result \
  /absolute/path/to/metrics.json --paper-state /absolute/path/to/paper-state.json
```

执行前按这个顺序判断：

1. `metrics.json` 是否仍是同一文件和同一哈希，且验证结果为 `PAPER_TRADING`；文件变化会让账户进入 `HALTED`。
2. `signal_date` 是否早于执行日期，`execution_model` 是否为 `next_open_v1`，信号是否仍在有效期内。
3. `execution_at` 和 `price_as_of` 是否带 UTC offset、位于市场常规时段，价格是否不超过 15 分钟陈旧。
4. `signal_id` 是否未处理；重复执行会被拒绝，不能通过改文件名绕过。
5. 输出中的订单是 `FILLED` 还是 `REJECTED`，拒绝原因是什么；不能只看账户是否有持仓。

模拟期结论不要只写收益。至少记录：不同交易日数、已处理信号数、成交/拒绝订单数、费用、最大回撤、证据状态、与研究目标的偏差，以及任何缺失价格或人工干预。至少 63 个不同模拟交易日和人工复核只是进入下一次评审的必要条件，不是实盘许可。

当前离线日历能拒绝周末和非正常交易时段，但不能完整识别交易所节假日。节假日不要手工伪造价格通过检查；应等待正式交易时段或在后续统一入口中接入版本化交易日历。
