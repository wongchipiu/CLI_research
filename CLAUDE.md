# 量化交易 Agent

个人量化研究系统：纯 Python 数据/回测层 + Claude Code 研究助手层。
需求见 docs/REQUIREMENTS.md，计划与当前进度见 docs/PLAN.md。

## 强制约定（token 经济性）

- **严禁 Read** `data/` 下任何文件、`results/**/*.csv`、大日志。要了解数据，运行脚本打印摘要。
- 回测结果只读 `results/<run>/metrics.json`，不读交易明细和图片。
- 一个对话只做 PLAN.md 里的一个 S 条目；完成后提示用户结束对话。
- 新的需求变更先写入 docs/，不在对话里展开。
- 报错调试只看关键 traceback。

## 技术栈

- Python 3.11+，uv 管理依赖；pandas/numpy；存储 Parquet。
- 数据源：akshare（A股）、yfinance（美股）。
- 测试：pytest，回测引擎的费用/T+1 逻辑必须有测试。

## 命令

- 更新数据：`uv run python scripts/update_data.py`（增量；质检 `scripts/check_data.py`）
- 跑回测：`uv run python scripts/run_backtest.py --strategy <名> --market <cn|us> [-p k=v ...]`
  策略：sma_cross / momentum / boll_revert（注册表见 src/quant/strategies/）
- 测试：`uv run pytest`

## Skills

- `/research <想法>` 策略调研 → docs/research/ 笔记
- `/backtest <策略> <市场> [k=v]` 跑回测并解读（只读 stdout JSON）
- `/review` 对比 results/*/metrics.json 复盘

## 回测引擎要点（src/quant/backtest/engine.py）

- decision[t] 在 t 收盘执行、赚 t+1 收益（无前视）；权重行和 ≤1，余者现金。
- A股：涨停(±9.8%)禁买/跌停禁卖、停牌冻结；T+1 由日频收盘调仓天然满足。
- 费用：cn 买 0.13%/卖 0.18%；us 双边 0.1%。
