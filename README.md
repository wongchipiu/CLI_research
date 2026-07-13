# quant-agent

个人量化研究系统：纯 Python 数据/回测层 + Codex 研究助手层。

## 当前状态

项目代码已经实现第一期主流程：

- 数据更新：A股用 akshare， 美股用 yfinance，失败时有 akshare 备援。
- 本地存储：`data/daily/<market>/<symbol>.parquet`。
- 数据质检：输出 `data/quality_summary.txt` 摘要。
- 回测：`sma_cross`、`momentum`、`boll_revert` 三个基线策略。
- 报告：每次回测写入 `results/<run>/metrics.json`、净值图和 CSV。
- Agent skills：`/research`、`/backtest`、`/review`。

注意：Agent 只读摘要，不直接读取 `data/` 原始数据或 `results/**/*.csv`。

## 环境准备

需要 Python 3.11+ 和 uv。

如果 `uv` 不在当前终端 PATH 中，先新开一个 PowerShell 终端再试：

```powershell
uv --version
```

如果仍然找不到 `uv`，安装或修复 uv：

```powershell
winget install --id astral-sh.uv
```

重建项目虚拟环境：

```powershell
cd C:\claude\quant-agent-codex
uv sync --dev
```

如果 `.venv` 指向了已经不存在的 Python，可先删除 `.venv` 后再执行 `uv sync --dev`。

## 常用命令

运行测试：

```powershell
uv run pytest
```

更新全部市场数据：

```powershell
uv run python scripts/update_data.py
```

只更新某个市场：

```powershell
uv run python scripts/update_data.py --market cn
uv run python scripts/update_data.py --market us
```

检查数据质量：

```powershell
uv run python scripts/check_data.py
```

跑回测：

```powershell
uv run python scripts/run_backtest.py --strategy sma_cross --market cn
uv run python scripts/run_backtest.py --strategy momentum --market us -p lookback=60 -p top_n=2
uv run python scripts/run_backtest.py --strategy boll_revert --market cn -p window=20 -p num_std=2
```

可选策略：

- `sma_cross`
- `momentum`
- `boll_revert`

回测 stdout 会打印 `metrics.json` 同款 JSON 摘要；完整结果在 `results/<run>/`。

## Codex 用法

日常研究建议按一个任务一个对话：

```text
/research 想研究的策略想法
/backtest momentum us lookback=60 top_n=2
/review
```

开发新功能时，先读 `docs/REQUIREMENTS.md`、`docs/PLAN.md`、`docs/STATUS.md`，一次只做 PLAN 里的一个 S 条目。
