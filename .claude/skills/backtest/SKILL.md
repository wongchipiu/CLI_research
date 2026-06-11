---
name: backtest
description: 运行回测并解读结果。用法：/backtest <策略名> <cn|us> [k=v 参数...]，如 /backtest momentum cn lookback=60
---

# 运行回测

## 步骤

1. 组装命令并运行（参数用 `-p k=v` 传递）：
   ```
   uv run python scripts/run_backtest.py --strategy <策略> --market <市场> [-p k=v ...]
   ```
   可选策略见 src/quant/strategies/baselines.py（sma_cross / momentum / boll_revert 及后续新增）。
2. **只读 stdout 的 JSON 输出**（即 metrics.json 内容）进行解读：
   - 与 benchmark 对比：excess_cagr、sharpe、max_drawdown、calmar；
   - 指出换手率对应的费用拖累（ann_turnover × 双边费率）；
   - 给出 1~2 条参数或逻辑上值得尝试的改进方向。
3. 在 `docs/research/backtest-log.md` 追加一行记录（无则创建）：
   `| 日期 | run_dir | 策略 | 市场 | 参数 | cagr | sharpe | mdd | excess_cagr | 一句话结论 |`

## 禁令

- 严禁读 results/ 下的 nav.csv、weights.csv（大文件）；净值图 nav.png 是给人看的。
- 一次只跑用户要求的组合，不要自行批量扫参数（扫参用确定性脚本另行实现）。
