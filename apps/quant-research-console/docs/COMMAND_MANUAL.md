# CLI_research 与 gpt_quant 命令手册

以下命令默认从 `CLI_research` 项目根目录执行：

```bash
cd /Users/brucehuang/Documents/CLI_research
```

页面“操作手册”包含完整的可搜索命令目录。本文重点说明推荐顺序和容易误用的边界。

## 公开申报研究（只使用现有数据）

```bash
cd /Users/brucehuang/Documents/ChatGPT/crawler
PYTHONPATH=src /Users/brucehuang/Documents/CLI_research/.venv/bin/python \
  -m disclosurelab --compact
```

该命令不会下载或更新 13F、Congress 或行情数据。它只读取现有 SQLite/Parquet，按申报公开后的下一交易日计算，并写出 `reports/disclosure_research.json` 与 `reports/disclosure_research.md`。

## 1. 帮助与环境

```bash
.venv/bin/quant --help
.venv/bin/quant workflow --help
.venv/bin/quant scan --help
.venv/bin/quant signals track --help

PYTHONPATH=../gpt_quant/src \
.venv/bin/python -m gpt_quant.cli --help
```

项目测试：

```bash
.venv/bin/python -m pytest -q
```

不要用普通 `uv run pytest` 覆盖当前非 editable 的 CLI 安装。

## 2. 第一次练习

```bash
.venv/bin/python scripts/demo_research.py
```

输出位于 `results/tutorial/`。结果标记为合成数据，只能用来熟悉文件和流程。

## 3. 数据更新与检查

```bash
# 联网更新美股 baseline 股票池
.venv/bin/python scripts/update_data.py \
  --market us --universe baseline

# 只打印质量摘要
.venv/bin/python scripts/check_data.py \
  --market us --quiet
```

`update_data.py` 会写入本地行情；研究前应先检查质量。`normalize_data.py` 会重写全部旧行情文件，而且没有 dry-run，不应作为日常命令使用。

## 4. 每日美股 Radar

```bash
.venv/bin/quant scan \
  --workspace config/workspace.yaml \
  --market us \
  --profile momentum_volume

.venv/bin/quant signals track \
  --workspace config/workspace.yaml \
  --market us \
  --profile momentum_volume
```

Radar 对固定自选池做描述性排名，不是全市场扫描、上涨概率或交易建议。信号跟踪分别记录 1/3/5/10/20 个交易日的描述性与可执行口径收益。

## 5. 探索性回测

```bash
.venv/bin/python scripts/run_backtest.py \
  --strategy momentum \
  --market us \
  --end 2022-12-30 \
  -p lookback=120 \
  -p top_n=2
```

可用策略：

- `boll_revert`
- `momentum`
- `momentum_vol`
- `relative_strength`
- `sma_cross`
- `trend_momentum`

探索回测只能用于事先限定的训练区间，不能直接获得模拟或实盘准入。

## 6. 正式参数扫描

先预览边界：

```bash
.venv/bin/python scripts/run_parameter_scan.py \
  --strategy momentum --market us \
  --start 2018-01-01 --end 2026-07-20 \
  --study-file momentum_001.json \
  -p lookback=60,120,250 \
  -p top_n=1,2 \
  -p rebalance=20 \
  --walk-forward --preview
```

确认后运行同一实验，将 `--preview` 改为 `--compact`。正式运行可能消耗最终测试；即使之后失败，也不能把已查看过的最终测试重新称为独立测试。

统一工作流：

```bash
.venv/bin/quant workflow \
  --workspace config/workspace.yaml \
  --strategy momentum --market us --universe baseline \
  --membership-file config/universe_history.csv \
  --start 2018-01-01 --end 2026-07-20 \
  --study-file momentum_001.json \
  -p lookback=60,120,250 \
  -p top_n=1,2 \
  -p rebalance=20 \
  --walk-forward
```

它依次执行质量摘要、正式扫描和 GPT Quant 验证，同样可能消耗最终测试。

## 7. 阅读和验证结果

```bash
PYTHONPATH=../gpt_quant/src \
.venv/bin/python -m gpt_quant.cli validate-cli-result \
  /absolute/path/to/results/<run>/metrics.json
```

阅读顺序：

1. `schema_version`、`artifact_type`、`execution_model`、`synthetic_data`。
2. `research_protocol` 的日期和冻结参数。
3. `validation.final_test_status/reason`。
4. 数据指纹、费用、陈旧估值。
5. 各段天数、完整交易和期末未平仓。
6. 最终测试收益与风险。
7. 基准、邻参稳健性和 walk-forward。

`BLOCKED` 是证据或流程结论，不等于命令运行失败。

## 8. 模拟账户

初始化：

```bash
PYTHONPATH=../gpt_quant/src \
.venv/bin/python -m gpt_quant.cli paper-init \
  /absolute/path/to/metrics.json \
  /absolute/path/to/paper-state.json \
  --cash 100000
```

生成目标信号：

```bash
.venv/bin/python scripts/generate_paper_signal.py \
  /absolute/path/to/metrics.json \
  --output /absolute/path/to/paper-signal.json
```

调仓：

```bash
PYTHONPATH=../gpt_quant/src \
.venv/bin/python -m gpt_quant.cli paper-rebalance \
  /absolute/path/to/paper-state.json \
  /absolute/path/to/paper-signal.json \
  --execution-at 2026-08-31T09:35:00-04:00 \
  --price-as-of 2026-08-31T09:35:00-04:00 \
  --price AAPL=230.5
```

查看报告：

```bash
PYTHONPATH=../gpt_quant/src \
.venv/bin/python -m gpt_quant.cli paper-report \
  /absolute/path/to/paper-state.json
```

模拟信号只能使用一次；陈旧价格、日期倒退、信号重放或证据变化会被拒绝。

## 9. 风险控制

先进行不连接账户的预检：

```bash
.venv/bin/python scripts/run_live_risk.py \
  --config config/live_risk.paper.yaml \
  --preflight
```

内置状态机演示：

```bash
.venv/bin/python scripts/simulate_live_risk.py
```

连接账户读取一次快照属于关键动作：

```bash
.venv/bin/python scripts/run_live_risk.py \
  --config config/live_risk.paper.yaml \
  --once
```

该命令可能根据配置进入 `FREEZE`、`REDUCE` 或 `LIQUIDATE` 并触发处置。只应在 paper 配置、预检通过和人工确认后执行。

## 10. 专项分析

```bash
# 股票事件研究
.venv/bin/python scripts/analyze_stock_event.py \
  --symbol AAPL --benchmark SPY --event-date 2026-07-30

# 品牌复利公司评分
.venv/bin/python scripts/score_brand_compounders.py \
  --input config/brand_compounders.json --compact

# 资产增长复盘
.venv/bin/python scripts/review_asset_growth.py \
  config/asset_ledger.csv --target 1000000

# Agent 工具循环演示，不需要 API Key
PYTHONPATH=../gpt_quant/src \
.venv/bin/python -m gpt_quant.cli agent-demo
```

这些输出属于各自的专项研究，不应自动当作策略验证或交易准入证据。
