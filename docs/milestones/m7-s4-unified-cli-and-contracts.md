# M7-S4：统一入口、工作目录与版本化契约

状态：**已完成（2026-08-29）。**

## 范围

本条目只整合本地研究链路，不更新行情、不新增 Scanner、不连接模型或券商。两个仓库继续独立存在；`CLI_research` 负责确定性编排，`gpt_quant` 只通过公开 CLI 返回验证决定。

## 统一入口

新入口按固定顺序执行：

1. 对目标市场生成本地日线质量摘要；存在 `ERROR` 或没有本地标的时停止。
2. 调用既有 `run_parameter_scan.py`，沿用训练选参、验证和一次性最终测试规则。
3. 在跨项目调用前检查 `strategy_validation` v2 包络。
4. 调用相邻 `gpt_quant validate-cli-result`，检查其版本化决定并保存 `workflow.json`。

示例（正式执行会消耗该实验的最终测试；应先用旧入口 `--preview` 确认边界）：

```bash
cd /Users/brucehuang/Documents/CLI_research
uv sync --no-editable --extra integration
.venv/bin/quant workflow \
  --workspace config/workspace.yaml \
  --strategy momentum --market us --universe baseline \
  --membership-file config/universe_history.csv \
  --start 2018-01-01 --end 2026-07-20 \
  --study-file momentum_001.json \
  -p lookback=60,120,250 -p top_n=1,2 -p rebalance=20 \
  --walk-forward --wf-train-days 756 --wf-test-days 126
```

`--study-file` 的相对路径固定落在工作区 `studies` 目录；数据、结果、股票池和验证器路径都来自 [workspace.yaml](../../config/workspace.yaml)，不再依赖启动命令时的 cwd。已安装命令默认从虚拟环境所属项目加载该文件，也可用 `--workspace /absolute/path/workspace.yaml` 或 `QUANT_WORKSPACE` 覆盖。入口完整透传正式扫描的起止日期、三段边界、滚动窗口和风险覆盖参数，必须与预览命令保持一致。当前本机 Python 会忽略隐藏的 editable `.pth` 文件，因此安装统一命令时明确使用 `--no-editable`。

返回码为 0 表示证据至少可进入模拟观察；`BLOCKED`、坏数据、坏 JSON、未知契约版本、结果逃逸配置目录或验证器失败均返回 2。`PAPER_TRADING` 仍不是实盘授权。

## 契约登记

| `artifact_type` | 版本 | 生产者 → 消费者 |
|---|---:|---|
| `quant_workspace_config` | 1 | 人工配置 → `quant` |
| `data_quality_summary` | 1 | CLI 质检 → 工作流 |
| `strategy_validation` | 2 | CLI 参数扫描 → CLI/gpt_quant 验证器 |
| `strategy_validation_decision` | 1 | gpt_quant → CLI 工作流 |
| `research_workflow` | 1 | CLI 工作流 → 人工/后续服务 |
| `paper_target_signal` | 2 | CLI 信号生成器 → gpt_quant 模拟账本 |

现有 `scripts/check_data.py`、`run_backtest.py`、`run_parameter_scan.py` 和 `generate_paper_signal.py` 只增加可选 `--workspace`；不传时仍使用原仓库内默认目录和参数。

## 验收目标

- 同一配置从不同 cwd 加载得到相同的绝对数据、结果和实验目录。
- 统一命令完成质量摘要 → 参数扫描 → 契约检查 → 独立验证。
- 数据错误、空市场、旧 schema、旧成交口径和越界结果目录明确失败。
- 两仓仍可单独安装和测试，旧脚本入口保持兼容。

## 本机验收结果

- `CLI_research`：95 项 pytest 通过；`gpt_quant`：31 项 unittest 通过。
- `compileall`、两仓 `git diff --check` 通过。
- integration 依赖可由 uv 解析和安装；安装后的 `quant`、`gpt-quant` 控制台命令可运行。
- 从 `/tmp` 加载同一 `workspace.yaml`，结果和实验根目录仍解析为本项目的绝对路径。
- 既有合成教程证据通过跨仓调用得到版本化 `BLOCKED` 决定，未被误认为可准入。
- 本轮未更新行情、未运行真实策略、未消耗新的正式最终测试、未连接券商。
