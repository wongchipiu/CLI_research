---
name: review
description: 复盘对比 results/ 下的历次回测，输出对比结论与改进建议。用法：/review [可选：限定策略或市场]
---

# 回测复盘

## 步骤

1. 用 Glob 列出 `results/*/metrics.json`，逐个读取（每个 <2KB，这是唯一允许读的结果文件）。
   若超过 20 个，优先读最近的 20 个。
2. 按市场分组输出对比表：策略 | 参数 | 区间 | cagr | sharpe | mdd | calmar | excess_cagr | ann_turnover。
3. 分析：
   - 哪个策略/参数组合在风险调整后最优（以 sharpe 与 calmar 为主，不只看收益）；
   - 同一策略跨市场表现差异及可能原因；
   - 高换手策略扣费后是否还有超额；
   - 明显失效的策略给出停止投入的建议。
4. 把结论写入 `docs/research/review-<YYYY-MM-DD>.md`（覆盖当日旧文件），对话里给摘要。

## 禁令

- 严禁读 nav.csv / weights.csv / data/ 原始数据。
- 表格之外的分析控制在 30 行以内，结论先行。
