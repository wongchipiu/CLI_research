# quant-agent

个人量化研究系统：Python 数据与回测底座，结合相邻 `gpt_quant` 的研究证据验证器。

**先看 [文档导航](docs/README.md)**；第一次使用可直接读 [实用指南](docs/USER_GUIDE.md)：怎样提出问题、运行命令、读结果、区分支持证据和反证，并写出可复查的结论。

## 快速练习（本机，无需联网）

```bash
cd /Users/brucehuang/Documents/CLI_research
.venv/bin/python scripts/demo_research.py
```

使用合成数据完成一次研究演示，并打印 `metrics.json` 路径。示例不可用于交易准入。

模拟账本的信号重放与价格时效练习：

```bash
cd /Users/brucehuang/Documents/gpt_quant
../CLI_research/.venv/bin/python scripts/demo_paper_workflow.py
```

现有环境运行测试：

```bash
.venv/bin/python -m pytest -q
```

新环境需要 Python 3.11+ 和 uv。普通开发可执行 `uv sync --dev`；安装跨项目统一命令执行 `uv sync --no-editable --extra integration`。源码更新后若要刷新已安装的 `quant` 命令，执行 `uv sync --no-editable --extra integration --reinstall-package quant-agent`。本机 Python 无法加载 uv 的隐藏 editable 路径，因此测试使用 `.venv/bin/python -m pytest`，不要用普通 `uv run pytest` 把环境切回 editable 安装。

## 当前能力

- A股/美股数据适配、Parquet 存储和质量摘要；实际来源连通性需单独验收。
- 组合回测：默认收盘信号在下一交易日开盘模拟成交，计入费用与仓位限制。
- 研究协议：训练 60%、验证 20%、最终测试 20%；只在训练段选参。
- 滚动验证：每折在本折训练段重新选参，不将独立账户曲线拼成连续收益。
- 实验记录：固定数据/源码指纹、时间边界和网格，记录最终测试使用状态。
- 固定美股自选池日线 Radar：量比、1/5/20 日动量、20/60 日收盘突破、过滤与确定性排名。
- Radar 信号跟踪：按 SPY 本地交易日成熟 1/3/5/10/20 日结果，分别保存描述性收益与次日开盘、扣费后的可执行收益；每日批处理仍未实现。
- 本地模拟账本：次日开盘信号、执行价格时效、证据哈希、重放保护和重启恢复；不连接券商。

## 常用命令

```bash
# 会联网并更新本地行情；运行后检查质量
.venv/bin/python scripts/update_data.py --market us --universe baseline
.venv/bin/python scripts/check_data.py --quiet

# 对 extended 美股自选池做一次本地日线扫描；不联网、不下单
.venv/bin/quant scan --workspace config/workspace.yaml --market us \
  --profile momentum_volume

# 读取已保存的 scan.json，去重登记信号并更新多期限结果
.venv/bin/quant signals track --workspace config/workspace.yaml --market us \
  --profile momentum_volume

# 探索回测：仅用于研究，不能直接准入；请限定在预先确定的训练区间
.venv/bin/python scripts/run_backtest.py --strategy momentum --market us --end 2022-12-30 -p lookback=120 -p top_n=2

# 日期只是示例，先按实际数据覆盖确定并预览边界
.venv/bin/python scripts/run_parameter_scan.py --strategy momentum --market us --start 2018-01-01 --end 2026-07-20 --study-file results/studies/momentum_001.json -p lookback=60,120,250 -p top_n=1,2 -p rebalance=20 --walk-forward --preview

# 确认后执行同一条扫描命令，将 --preview 改为 --compact
# 汇总记录；该月份是报告标签，写入时会覆盖同名月报
.venv/bin/python scripts/summarize_results.py --month 2026-08
```

完成预览并冻结实验后，可用一个命令执行“目标市场质量摘要 → 正式参数扫描 → `gpt_quant` 验证”：

```bash
.venv/bin/quant workflow --workspace config/workspace.yaml \
  --strategy momentum --market us --universe baseline \
  --membership-file config/universe_history.csv \
  --start 2018-01-01 --end 2026-07-20 \
  --study-file momentum_001.json \
  -p lookback=60,120,250 -p top_n=1,2 -p rebalance=20 \
  --walk-forward
```

正式工作流会按原规则一次性消费最终测试；首次使用前先阅读 [M7-S4 说明](docs/milestones/m7-s4-unified-cli-and-contracts.md)。相对实验路径固定解析到 `var/studies/`，从其他 cwd 启动也仍写入本项目配置的 `results/`。

`run_backtest.py` 不再使用 `--train-ratio`/`--split-date` 做正式验证，请迁移到 `run_parameter_scan.py`。旧同日收盘行为需显式传 `--execution-model legacy_same_close`，其结果不能用于新版准入。

完整结果由脚本保存；Agent 只读摘要，不直接读原始行情、大日志或交易明细 CSV。`final_test_status=completed` 只表示测试已执行，不表示盈利、准入或实盘授权。

Radar 只对配置内的固定自选池做描述性排名，不是全市场扫描、上涨概率或交易建议。退出码 2 和 `status=DEGRADED` 表示至少一个标的因缺数据、日期、量纲、复权一致性或历史长度不足而无法计算；普通阈值未通过不是数据故障。扫描规则见 [M7-S5 说明](docs/milestones/m7-s5-us-daily-radar.md)，后续表现口径见 [M7-S6 说明](docs/milestones/m7-s6-forward-outcome-tracking.md)。

开发入口统一见 [文档导航](docs/README.md)。路线图看 [PLAN](docs/PLAN.md)，当前状态看 [STATUS](docs/STATUS.md)，每个开发对话只完成一个 S 条目。
