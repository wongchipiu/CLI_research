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

- 更新数据：`uv run python scripts/update_data.py`
- 跑回测：`uv run python scripts/run_backtest.py --strategy <名> --market <cn|us>`
- 测试：`uv run pytest`
